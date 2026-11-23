"""Phase 4 CLI — `rl why <file:line>` reasoning-blame."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.decisions import (
    read_decision_file,
    record_decision_to_path,
    write_decision_file,
)
from reasonledger_core.models.decision import (
    AiTool,
    DecisionOversight,
    DecisionStatus,
    RecordDecisionInput,
)


def _seed(root: Path) -> None:
    record_decision_to_path(
        RecordDecisionInput(
            context="Retry policy",
            choice="Exponential backoff",
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            approved_by="alice@acme.com",
            justifies=["payments/retry.py:40-72"],
            decision_id="dec_why001",
        ),
        root=root,
    )


@pytest.mark.phase_4
def test_why_returns_decision_for_line_in_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    code = main(["why", "payments/retry.py:55", "--root", str(tmp_path), "--json"])
    assert code == EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["decisions"][0]["id"] == "dec_why001"
    assert payload["decisions"][0]["status"] == "active"
    assert payload["decisions"][0]["match"] == "line"


@pytest.mark.phase_4
def test_why_no_record_is_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path)
    (tmp_path / "unrelated").mkdir()
    (tmp_path / "unrelated" / "file.py").write_text("x = 1\n", encoding="utf-8")
    code = main(["why", "unrelated/file.py:1", "--root", str(tmp_path)])
    assert code == EXIT_PASS
    assert "No decision names this file" in capsys.readouterr().out


@pytest.mark.phase_4
def test_why_nonexistent_path_is_an_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """S59.4 case 1: a typo'd path must not read as "nothing recorded yet"."""
    _seed(tmp_path)
    code = main(["why", "unrelated/file.py:1", "--root", str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert "no file at unrelated/file.py" in captured.err and captured.out == ""


@pytest.mark.phase_4
def test_why_json_for_a_nonexistent_path_is_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    code = main(["why", "unrelated/file.py:1", "--root", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == EXIT_PASS
    assert payload["path_exists"] is False and payload["count"] == 0 and payload["nearby"] == []


@pytest.mark.phase_4
def test_why_text_labels_file_level_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record_decision_to_path(
        RecordDecisionInput(
            context="Cache policy",
            choice="Use Redis",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            justifies=["catalog/cache.py"],
            decision_id="dec_file001",
        ),
        root=tmp_path,
    )

    code = main(["why", "catalog/cache.py", "--root", str(tmp_path)])

    assert code == EXIT_PASS
    assert "dec_file001 (file-level match)" in capsys.readouterr().out


@pytest.mark.phase_4
def test_why_flags_superseded_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A retired decision still answers `why`, but must be clearly marked as stale."""
    locus = "payments/retry.py:40-72"
    _, old_path = record_decision_to_path(
        RecordDecisionInput(
            context="Retry policy",
            choice="Exponential backoff",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            justifies=[locus],
            decision_id="dec_old001",
        ),
        root=tmp_path,
    )
    _, new_path = record_decision_to_path(
        RecordDecisionInput(
            context="Retry policy",
            choice="Fixed delay",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            justifies=[locus],
            decision_id="dec_new001",
        ),
        root=tmp_path,
    )
    old_record = read_decision_file(old_path)
    old_record.frontmatter.status = DecisionStatus.SUPERSEDED
    write_decision_file(old_path, old_record)
    new_record = read_decision_file(new_path)
    new_record.frontmatter.supersedes = "dec_old001"
    write_decision_file(new_path, new_record)

    json_code = main(["why", "payments/retry.py:55", "--root", str(tmp_path), "--json"])
    assert json_code == EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    by_id = {d["id"]: d for d in payload["decisions"]}
    assert by_id["dec_old001"]["status"] == "superseded"
    assert by_id["dec_old001"]["superseded_by"] == "dec_new001"
    assert by_id["dec_new001"]["superseded_by"] is None

    text_code = main(["why", "payments/retry.py:55", "--root", str(tmp_path)])
    assert text_code == EXIT_PASS
    out = capsys.readouterr().out
    assert "status: superseded (superseded by dec_new001) — see the successor" in out


@pytest.mark.phase_4
def test_why_still_answers_for_an_anchored_file_that_is_gone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A deleted or moved file keeps its decisions: only a miss on a missing path is an error."""
    _seed(tmp_path)
    assert main(["why", "payments/retry.py:55", "--root", str(tmp_path)]) == EXIT_PASS
    assert "dec_why001" in capsys.readouterr().out
