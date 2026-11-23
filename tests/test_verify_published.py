"""S56.5 — the logic of scripts/verify_published.py, with no network and no uv.

The script itself runs only in the release workflow, against a real index. What can be checked
here is everything that decides whether it passes: how the index is selected, which command it
extracts from the config `init` wrote, and how it reads the MCP exchange.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify_published.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_published", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_published"] = module
    spec.loader.exec_module(module)
    return module


verify = _load()


@pytest.mark.phase_3
def test_pypi_needs_no_index_flags() -> None:
    assert verify.index_env("pypi") == {}


@pytest.mark.phase_3
def test_testpypi_uses_both_indexes_and_best_match() -> None:
    env = verify.index_env("testpypi")
    assert env["UV_INDEX_URL"] == "https://test.pypi.org/simple/"
    assert env["UV_EXTRA_INDEX_URL"] == "https://pypi.org/simple/"
    assert env["UV_INDEX_STRATEGY"] == "unsafe-best-match"


@pytest.mark.phase_3
def test_unknown_index_is_refused() -> None:
    with pytest.raises(ValueError, match="index"):
        verify.index_env("elsewhere")


@pytest.mark.phase_3
def test_mcp_command_is_read_from_the_config_init_wrote(tmp_path: Path) -> None:
    config = {
        "mcpServers": {
            "reasonledger": {"command": "uvx", "args": ["reasonledger", "mcp", "--repo-root", "/r"]}
        }
    }
    (tmp_path / ".mcp.json").write_text(json.dumps(config), encoding="utf-8")
    assert verify.mcp_command(tmp_path) == ["uvx", "reasonledger", "mcp", "--repo-root", "/r"]


@pytest.mark.phase_3
def test_missing_mcp_config_is_a_failure(tmp_path: Path) -> None:
    with pytest.raises(verify.VerifyError, match=r"\.mcp\.json"):
        verify.mcp_command(tmp_path)


@pytest.mark.phase_3
def test_tool_names_come_from_the_tools_list_reply() -> None:
    lines = [
        "not json at all",
        json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "rl"}}}),
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"tools": [{"name": "record_decision"}, {"name": "decisions_for"}]},
            }
        ),
    ]
    assert verify.tool_names(lines) == {"record_decision", "decisions_for"}


@pytest.mark.phase_3
def test_a_reply_without_tools_is_a_failure() -> None:
    with pytest.raises(verify.VerifyError, match="tools/list"):
        verify.tool_names([json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}})])


@pytest.mark.phase_3
def test_required_tools_are_checked() -> None:
    with pytest.raises(verify.VerifyError, match="record_decision"):
        verify.require_tools({"decisions_for"})
    verify.require_tools({"record_decision", "query_decisions", "decisions_for"})


@pytest.mark.phase_3
def test_retry_is_bounded_and_returns_the_first_success() -> None:
    calls: list[int] = []

    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise verify.VerifyError("not on the index yet")
        return "ok"

    assert verify.retry(flaky, attempts=5, delay=0) == "ok"
    assert len(calls) == 3


@pytest.mark.phase_3
def test_retry_gives_up_after_the_bound() -> None:
    calls: list[int] = []

    def never() -> None:
        calls.append(1)
        raise verify.VerifyError("still missing")

    with pytest.raises(verify.VerifyError, match="still missing"):
        verify.retry(never, attempts=3, delay=0)
    assert len(calls) == 3


@pytest.mark.phase_3
def test_the_version_is_pinned_in_the_uvx_invocation() -> None:
    command = verify.uvx_cli("0.3.0a1", "--version")
    assert command[-2:] == ["reasonledger==0.3.0a1", "--version"]
    assert command[0] == "uvx"


@pytest.mark.phase_3
def test_refresh_is_opt_in_and_precedes_the_package_pins() -> None:
    assert "--refresh" not in verify.uvx_cli("0.3.0a1", "--version")
    command = verify.uvx_cli("0.3.0a1", "--version", refresh=True)
    assert command[:2] == ["uvx", "--refresh"]


@pytest.mark.phase_3
def test_stop_lets_a_server_leave_when_its_stdin_closes() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.read()"],
        stdin=subprocess.PIPE,
        text=True,
    )
    verify._stop(proc)
    assert proc.returncode == 0


@pytest.mark.phase_3
def test_stop_kills_a_server_that_ignores_stdin_closing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verify, "MCP_EXIT_GRACE_SECONDS", 0.2)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdin=subprocess.PIPE,
        text=True,
    )
    verify._stop(proc)
    assert proc.returncode is not None


@pytest.mark.phase_3
def test_core_and_mcp_are_pinned_to_the_same_version_as_the_cli() -> None:
    """The CLI's own range would let an older core or MCP satisfy the install."""
    command = verify.uvx_cli("0.3.0a1", "--version")
    pinned = [command[i + 1] for i, part in enumerate(command) if part == "--with"]
    assert sorted(pinned) == ["reasonledger-core==0.3.0a1", "reasonledger-mcp==0.3.0a1"]
    assert command.index("reasonledger==0.3.0a1") > max(
        i for i, part in enumerate(command) if part == "--with"
    )


@pytest.mark.phase_3
def test_workflow_runs_verify_on_three_operating_systems_after_both_publishes() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    job = jobs["verify"]
    assert set(job["needs"]) == {"publish-app", "publish-mcp"}
    systems = set(job["strategy"]["matrix"]["os"])
    assert systems == {"ubuntu-latest", "macos-latest", "windows-latest"}
    steps = json.dumps(job["steps"])
    assert "scripts/verify_published.py" in steps
    assert "setup-uv" in steps


@pytest.mark.phase_3
def test_stray_stdout_is_reported_but_protocol_lines_are_not() -> None:
    assert verify.non_protocol_lines(['{"jsonrpc": "2.0", "id": 1}', "", "hello"]) == ["hello"]
