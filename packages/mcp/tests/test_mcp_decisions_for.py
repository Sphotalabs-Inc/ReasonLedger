"""S51 — the agent can ask which decisions cover a file before it edits it."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions.lifecycle import retire_decision
from reasonledger_mcp.server import create_mcp_server
from reasonledger_mcp.tools import call_decisions_for, call_record_decision


def _record(root: Path, decision_id: str, justifies: list[str]) -> None:
    call_record_decision(
        root,
        context="Retry policy",
        choice="Jittered backoff",
        alternatives_rejected=["Fixed delay"],
        ai_tool="claude",
        model="m",
        justifies=justifies,
        decision_id=decision_id,
    )


@pytest.mark.phase_4
def test_decisions_for_returns_covering_decisions(tmp_path: Path) -> None:
    (tmp_path / "pay").mkdir()
    (tmp_path / "pay" / "retry.py").write_text("def retry():\n    return 1\n", encoding="utf-8")
    _record(tmp_path, "dec_sym001", ["pay/retry.py::retry"])
    _record(tmp_path, "dec_file01", ["pay/retry.py"])
    _record(tmp_path, "dec_other1", ["pay/other.py:1-5"])
    found = call_decisions_for(tmp_path, paths=["pay/retry.py"], line=2)
    assert found["ok"] is True
    assert [(d["id"], d["match"]) for d in found["decisions"]] == [
        ("dec_sym001", "symbol"),
        ("dec_file01", "file"),
    ]
    assert "markdown" not in found["decisions"][0]


@pytest.mark.phase_4
def test_decisions_for_excludes_out_of_force(tmp_path: Path) -> None:
    _record(tmp_path, "dec_live01", ["pay/retry.py:1-5"])
    _record(tmp_path, "dec_gone01", ["pay/retry.py:1-5"])
    retire_decision(
        "dec_gone01", root=tmp_path, retired_by="p", retired_at=datetime.now(UTC), reason="gone"
    )
    found = call_decisions_for(tmp_path, paths=["pay/retry.py"])
    assert [d["id"] for d in found["decisions"]] == ["dec_live01"]
    assert found["out_of_force"] == 1


@pytest.mark.phase_4
def test_decisions_for_refuses_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    for raw in ("../secret.txt", "/etc/passwd"):
        found = call_decisions_for(root, paths=["ok.py", raw])
        assert found["ok"] is False and "outside the repository" in found["error"]


@pytest.mark.phase_4
def test_contract_lists_decisions_for(tmp_path: Path) -> None:
    server = create_mcp_server(repo_root=tmp_path)
    assert server._tool_manager.get_tool("decisions_for") is not None
