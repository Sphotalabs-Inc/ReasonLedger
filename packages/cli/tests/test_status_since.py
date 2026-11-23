"""Phase 3 coverage for git-native status filtering."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.decisions import record_decision_to_path
from reasonledger_core.models.decision import AiTool, DecisionOversight, RecordDecisionInput

GIT_AVAILABLE = shutil.which("git") is not None
pytestmark = pytest.mark.skipif(not GIT_AVAILABLE, reason="git executable is required")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _commit(root: Path, message: str) -> None:
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=Test User",
        "commit",
        "-m",
        message,
    )


def _record(root: Path, decision_id: str, choice: str) -> None:
    record_decision_to_path(
        RecordDecisionInput(
            context="Database choice",
            choice=choice,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            decision_id=decision_id,
        ),
        root=root,
    )


def _repo(root: Path) -> None:
    _git(root, "init")
    _record(root, "dec_base001", "PostgreSQL")
    _commit(root, "base decision")


@pytest.mark.phase_3
def test_status_since_lists_only_new_decisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)
    _record(tmp_path, "dec_new0001", "MongoDB")
    _commit(tmp_path, "new decision")

    assert main(["status", "--root", str(tmp_path), "--since", "HEAD~1"]) == EXIT_PASS
    output = capsys.readouterr().out
    assert "dec_new0001" in output
    assert "dec_base001" not in output


@pytest.mark.phase_3
def test_status_since_reports_supersedes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)
    path = tmp_path / ".reasonledger/decisions/dec_base001.md"
    raw = path.read_text("utf-8").replace("status: active", "status: superseded")
    path.write_text(raw, encoding="utf-8")
    _commit(tmp_path, "supersede decision")

    assert main(["status", "--root", str(tmp_path), "--since", "HEAD~1"]) == EXIT_PASS
    assert "superseded" in capsys.readouterr().out


@pytest.mark.phase_3
def test_status_since_unknown_ref_falls_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _repo(tmp_path)

    assert main(["status", "--root", str(tmp_path), "--since", "not-a-ref"]) == EXIT_PASS
    captured = capsys.readouterr()
    assert "dec_base001" in captured.out
    assert "cannot resolve not-a-ref" in captured.err


@pytest.mark.phase_3
def test_status_since_not_a_git_repo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _record(tmp_path, "dec_nogit01", "PostgreSQL")

    assert main(["status", "--root", str(tmp_path), "--since", "main"]) == EXIT_PASS
    captured = capsys.readouterr()
    assert "dec_nogit01" in captured.out
    assert "cannot resolve main" in captured.err


@pytest.mark.phase_3
def test_status_since_json_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _repo(tmp_path)
    _record(tmp_path, "dec_new0001", "MongoDB")
    _commit(tmp_path, "new decision")

    assert main(["status", "--root", str(tmp_path), "--since", "HEAD~1", "--json"]) == EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["since"]["ref"] == "HEAD~1"
    assert payload["since"]["count"] == 1
