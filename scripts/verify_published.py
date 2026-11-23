"""Prove a published version installs and runs for a stranger.

Run by the `verify` job of `.github/workflows/release.yml` on a fresh runner that has only `uv`.
It never touches a checkout's code: everything below goes through `uvx` against the index that
was just published to.

    python scripts/verify_published.py --index testpypi [--version 0.3.0a1]

Steps, each of which must pass:
  1. `uvx reasonledger==<version> --version`            (retried: an index lags an upload)
     with core and the MCP server pinned to the same version, so an older release of either
     cannot satisfy the install and let a broken new upload pass
  2. `init` in a brand-new git repository
  3. `status`
  4. start the MCP command that `init` wrote and complete `initialize` + `tools/list`

A red result means: do not hand this version to anyone. It is already on the index and a version
number can never be reused, so the fix ships as the next pre-release.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PYPROJECT = REPO_ROOT / "packages" / "cli" / "pyproject.toml"
CLI_DIST = "reasonledger"
CORE_DIST = "reasonledger-core"
MCP_DIST = "reasonledger-mcp"
MCP_CONFIG = ".mcp.json"
MCP_SERVER_KEY = "reasonledger"
REQUIRED_TOOLS = frozenset({"record_decision", "query_decisions", "decisions_for"})
MCP_PROTOCOL_VERSION = "2024-11-05"
TESTPYPI_ENV = {
    "UV_INDEX_URL": "https://test.pypi.org/simple/",
    # TestPyPI does not mirror third-party dependencies such as pydantic.
    "UV_EXTRA_INDEX_URL": "https://pypi.org/simple/",
    "UV_INDEX_STRATEGY": "unsafe-best-match",
}
# An index can take minutes to serve a file it has accepted.
PROPAGATION_ATTEMPTS = 12
PROPAGATION_DELAY_SECONDS = 20.0
# The first uvx run of a package downloads and builds its environment.
COMMAND_TIMEOUT_SECONDS = 600
MCP_REPLY_TIMEOUT_SECONDS = 300
# How long a server gets to leave on its own once its stdin closes, before it is killed.
MCP_EXIT_GRACE_SECONDS = 10
LIST_TOOLS_ID = 2


class VerifyError(Exception):
    """A check failed; the message is what the maintainer reads in the job log."""


def index_env(index: str) -> dict[str, str]:
    """Environment variables that point uv, and everything uv spawns, at the index."""
    if index == "pypi":
        return {}
    if index == "testpypi":
        return dict(TESTPYPI_ENV)
    raise ValueError(f"unknown index {index!r}: use pypi or testpypi")


def uvx_cli(version: str, *args: str, refresh: bool = False) -> list[str]:
    """The CLI at `version`, with both packages it depends on pinned to the same one.

    The CLI declares them as ranges (`>=0.3.0a1,<0.4.0`), so pinning only the CLI would let an
    older core or MCP release satisfy the install while the new upload goes untested.
    """
    return [
        "uvx",
        *(["--refresh"] if refresh else []),
        "--with",
        f"{CORE_DIST}=={version}",
        "--with",
        f"{MCP_DIST}=={version}",
        f"{CLI_DIST}=={version}",
        *args,
    ]


def mcp_command(repo: Path) -> list[str]:
    """The command `init` wrote for Claude Code, exactly as an agent would start it."""
    config = repo / MCP_CONFIG
    if not config.is_file():
        raise VerifyError(f"init did not write {MCP_CONFIG} in {repo}")
    entry = json.loads(config.read_text(encoding="utf-8"))["mcpServers"][MCP_SERVER_KEY]
    return [entry["command"], *entry.get("args", [])]


def _json_lines(lines: list[str]) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    for line in lines:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            messages.append(parsed)
    return messages


def non_protocol_lines(lines: list[str]) -> list[str]:
    """Stdout lines that are not JSON-RPC: a stdio server must print nothing else."""
    return [line for line in lines if line.strip() and not _json_lines([line])]


def tool_names(lines: list[str]) -> set[str]:
    for message in _json_lines(lines):
        result = message.get("result")
        if message.get("id") == LIST_TOOLS_ID and isinstance(result, dict) and "tools" in result:
            return {str(tool["name"]) for tool in result["tools"]}
    raise VerifyError("the server never answered tools/list with a tools result")


def require_tools(names: set[str]) -> None:
    missing = REQUIRED_TOOLS - names
    if missing:
        raise VerifyError(f"the server does not list: {', '.join(sorted(missing))}")


def retry[T](action: Callable[[], T], *, attempts: int, delay: float) -> T:
    """Run `action` until it succeeds; at most `attempts` times, so a real failure still fails."""
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except VerifyError:
            if attempt == attempts:
                raise
            time.sleep(delay)
    raise AssertionError("unreachable: attempts must be at least 1")


def _run(argv: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    print(f"$ {' '.join(argv)}", flush=True)
    done = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    print(done.stdout + done.stderr, end="", flush=True)
    if done.returncode != 0:
        raise VerifyError(f"`{' '.join(argv)}` exited {done.returncode}")
    return done.stdout


def _mcp_messages() -> list[str]:
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "verify-published", "version": "0"},
        },
    }
    initialized = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    list_tools = {"jsonrpc": "2.0", "id": LIST_TOOLS_ID, "method": "tools/list"}
    return [json.dumps(message) for message in (initialize, initialized, list_tools)]


def _stop(proc: subprocess.Popen[str]) -> None:
    """End the server and everything `uvx` started for it.

    Closing stdin lets a stdio server exit on its own. Failing that, `uvx` is only a launcher:
    killing it alone leaves the real server running, and on Windows a process keeps its working
    directory from being deleted, so the whole tree goes.
    """
    assert proc.stdin is not None
    try:
        proc.stdin.close()
        proc.wait(timeout=MCP_EXIT_GRACE_SECONDS)
        return
    except (OSError, subprocess.TimeoutExpired):
        pass
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False
        )
    proc.kill()
    proc.wait()


def mcp_exchange(command: list[str], *, cwd: Path, env: dict[str, str]) -> list[str]:
    """Start the server, send initialize + tools/list, return every stdout line read.

    The server's stderr goes to the job log afterwards, as every other command's does: a server
    that fails to start says why there, and nowhere else.
    """
    print(f"$ {' '.join(command)}   # MCP initialize + tools/list", flush=True)
    seen: list[str] = []
    with tempfile.TemporaryFile("w+", encoding="utf-8") as server_stderr:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=server_stderr,
            text=True,
        )
        assert proc.stdin is not None and proc.stdout is not None
        stdout = proc.stdout
        lines: queue.Queue[str] = queue.Queue()

        def pump() -> None:
            for line in stdout:
                lines.put(line)

        threading.Thread(target=pump, daemon=True).start()
        try:
            for message in _mcp_messages():
                proc.stdin.write(message + "\n")
                proc.stdin.flush()
            deadline = time.monotonic() + MCP_REPLY_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                try:
                    seen.append(lines.get(timeout=1).rstrip("\n"))
                except queue.Empty:
                    if proc.poll() is not None:
                        break
                    continue
                if any(m.get("id") == LIST_TOOLS_ID for m in _json_lines(seen)):
                    break
        finally:
            _stop(proc)
        server_stderr.seek(0)
        print(server_stderr.read(), end="", flush=True)
    return seen


def verify(version: str, index: str) -> None:
    env = {**os.environ, **index_env(index)}
    with tempfile.TemporaryDirectory() as work:
        repo = Path(work) / "app"
        repo.mkdir()
        _run(["git", "init", "-q"], cwd=repo, env=env)

        def installed() -> None:
            # --refresh: uv caches an index's 404, so without it every retry re-reads the miss.
            out = _run(uvx_cli(version, "--version", refresh=True), cwd=repo, env=env)
            if version not in out:
                raise VerifyError(f"--version printed {out.strip()!r}, wanted {version}")

        retry(installed, attempts=PROPAGATION_ATTEMPTS, delay=PROPAGATION_DELAY_SECONDS)
        _run(uvx_cli(version, "init"), cwd=repo, env=env)
        _run(uvx_cli(version, "status"), cwd=repo, env=env)

        seen = mcp_exchange(mcp_command(repo), cwd=Path(work), env=env)
        stray = non_protocol_lines(seen)
        if stray:
            raise VerifyError(f"the MCP server wrote non-protocol text to stdout: {stray[0]!r}")
        require_tools(tool_names(seen))
    print(f"verified {CLI_DIST}=={version} from {index}", flush=True)


def _default_version() -> str:
    project = tomllib.loads(CLI_PYPROJECT.read_text(encoding="utf-8"))["project"]
    return str(project["version"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--index", choices=["pypi", "testpypi"], required=True)
    parser.add_argument("--version", default=None, help="default: the version in packages/cli")
    args = parser.parse_args(argv)
    try:
        verify(args.version or _default_version(), args.index)
    except (VerifyError, subprocess.TimeoutExpired) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
