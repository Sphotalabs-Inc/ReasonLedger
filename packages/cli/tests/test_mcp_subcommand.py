"""S57 — `reasonledger mcp` is the one name for the MCP server.

`uv tool install reasonledger` (or nothing at all, through `uvx`) must be the whole install, so
`init` writes a command built on `reasonledger` itself and never on an executable that exists
only inside a throwaway `uvx` environment.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from reasonledger_cli.init_cmd import run_init

# The `launch_as` fixture from conftest: the script that ran, and what PATH finds.
LaunchAs = Callable[[Path, Path | None], None]
REPO_ROOT = Path(__file__).resolve().parents[3]
# Relative, so each test places them under its own tmp_path.
EPHEMERAL_EXECUTABLE = ".cache/uv/environments-v2/9f3c/bin/reasonledger"
INSTALLED_EXECUTABLE = ".local/bin/reasonledger"


def _entry(root: Path) -> dict[str, object]:
    config = json.loads((root / ".mcp.json").read_text("utf-8"))
    entry: dict[str, object] = config["mcpServers"]["reasonledger"]
    return entry


@pytest.mark.phase_3
def test_mcp_subcommand_serves_stdio(tmp_path: Path) -> None:
    """An `initialize` and `tools/list` round trip through `reasonledger mcp`."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "reasonledger_cli", "mcp", "--repo-root", str(tmp_path)],
    )

    async def exchange() -> set[str]:
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            return {tool.name for tool in (await session.list_tools()).tools}

    names = asyncio.run(asyncio.wait_for(exchange(), timeout=60))
    assert {"record_decision", "query_decisions", "decisions_for"} <= names


@pytest.mark.phase_3
def test_init_entry_uses_the_mcp_subcommand(tmp_path: Path, launch_as: LaunchAs) -> None:
    """PATH resolves to the install that ran `init`, so the portable bare name is enough."""
    installed = tmp_path / INSTALLED_EXECUTABLE
    launch_as(installed, installed)
    run_init(root=tmp_path / "app", scan=False)
    assert _entry(tmp_path / "app") == {
        "command": "reasonledger",
        "args": ["mcp", "--repo-root", str((tmp_path / "app").resolve())],
    }


@pytest.mark.phase_3
def test_init_ignores_an_ephemeral_executable(tmp_path: Path, launch_as: LaunchAs) -> None:
    """Under `uvx`, this process lives in a cache directory that will not exist for the agent."""
    ephemeral = tmp_path / EPHEMERAL_EXECUTABLE
    launch_as(ephemeral, ephemeral)
    run_init(root=tmp_path / "app", scan=False)
    assert _entry(tmp_path / "app") == {
        "command": "uvx",
        "args": ["reasonledger", "mcp", "--repo-root", str((tmp_path / "app").resolve())],
    }


@pytest.mark.phase_3
def test_init_ignores_an_executable_inside_the_uv_cache_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, launch_as: LaunchAs
) -> None:
    cache = tmp_path / "custom-cache"
    monkeypatch.setenv("UV_CACHE_DIR", str(cache))
    script = cache / "tmp123" / "bin" / "reasonledger"
    launch_as(script, script)
    run_init(root=tmp_path / "app", scan=False)
    assert _entry(tmp_path / "app")["command"] == "uvx"


@pytest.mark.phase_3
def test_init_writes_the_absolute_launcher_when_path_finds_nothing(
    tmp_path: Path, launch_as: LaunchAs
) -> None:
    """A pip venv run by path without activating it: the agent's PATH will not find it either."""
    script = tmp_path / "venv" / "bin" / "reasonledger"
    launch_as(script, None)
    run_init(root=tmp_path / "app", scan=False)
    assert _entry(tmp_path / "app")["command"] == str(script)


@pytest.mark.phase_3
def test_init_writes_the_absolute_launcher_when_path_finds_another_install(
    tmp_path: Path, launch_as: LaunchAs
) -> None:
    """An older global `reasonledger` earlier on PATH must not serve this install's repo."""
    script = tmp_path / "venv" / "bin" / "reasonledger"
    launch_as(script, tmp_path / "old" / "bin" / "reasonledger")
    run_init(root=tmp_path / "app", scan=False)
    assert _entry(tmp_path / "app")["command"] == str(script)


@pytest.mark.phase_3
def test_the_rl_alias_writes_its_reasonledger_sibling(tmp_path: Path, launch_as: LaunchAs) -> None:
    installed = tmp_path / "bin" / "reasonledger"
    launch_as(tmp_path / "bin" / "rl", installed)
    run_init(root=tmp_path / "app", scan=False)
    assert _entry(tmp_path / "app")["command"] == "reasonledger"


@pytest.mark.phase_3
def test_python_dash_m_writes_the_interpreter(tmp_path: Path, launch_as: LaunchAs) -> None:
    launch_as(tmp_path / "reasonledger_cli" / "__main__.py", None)
    run_init(root=tmp_path / "app", scan=False)
    entry = _entry(tmp_path / "app")
    assert entry["command"] == sys.executable
    assert entry["args"] == [
        "-m",
        "reasonledger_cli",
        "mcp",
        "--repo-root",
        str((tmp_path / "app").resolve()),
    ]


@pytest.mark.phase_3
def test_reasonledger_root_keeps_uv_run_project_with_the_subcommand(tmp_path: Path) -> None:
    run_init(root=tmp_path, reasonledger_root=REPO_ROOT, scan=False)
    entry = _entry(tmp_path)
    assert entry["command"] == "uv"
    assert entry["args"] == [
        "run",
        "--project",
        str(REPO_ROOT.resolve()),
        "reasonledger",
        "mcp",
        "--repo-root",
        str(tmp_path.resolve()),
    ]


@pytest.mark.phase_3
def test_the_old_executable_and_an_existing_config_are_left_alone(tmp_path: Path) -> None:
    existing = tmp_path / ".mcp.json"
    old = '{"mcpServers": {"reasonledger": {"command": "reasonledger-mcp", "args": []}}}\n'
    existing.write_text(old, encoding="utf-8")
    run_init(root=tmp_path, scan=False)
    assert existing.read_text("utf-8") == old
