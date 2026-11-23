"""Phase 4 CLI coverage for the decision conflict gate."""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, main
from reasonledger_core.decisions import record_decision_to_path
from reasonledger_core.models.decision import (
    AiTool,
    DecisionOversight,
    DecisionStatus,
    RecordDecisionInput,
)
from reasonledger_core.models.reasoning import Severity
from verdict_helpers import commit_verdict


def _seed(
    root: Path, decision_id: str, choice: str, *, status: DecisionStatus = DecisionStatus.ACTIVE
) -> None:
    record, path = record_decision_to_path(
        RecordDecisionInput(
            context="Timestamp storage timezone policy",
            choice=choice,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            decision_id=decision_id,
        ),
        root=root,
    )
    if status is not DecisionStatus.ACTIVE:
        record.frontmatter.status = status
        from reasonledger_core.decisions.format import write_decision_file

        write_decision_file(path, record)


@pytest.mark.phase_4
def test_check_decisions_fails_on_high_conflict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path, "dec_sql001", "UTC")
    _seed(tmp_path, "dec_mongo01", "server-local")
    commit_verdict(tmp_path, "dec_sql001", "dec_mongo01")

    assert main(["check", "--decisions", "--root", str(tmp_path)]) == EXIT_FAIL
    output = capsys.readouterr().out
    assert "dec_sql001" in output
    assert "dec_mongo01" in output


@pytest.mark.phase_4
def test_check_decisions_ignores_superseded(tmp_path: Path) -> None:
    _seed(tmp_path, "dec_sql001", "UTC")
    _seed(tmp_path, "dec_mongo01", "server-local", status=DecisionStatus.SUPERSEDED)

    assert main(["check", "--decisions", "--root", str(tmp_path)]) == EXIT_PASS


@pytest.mark.phase_4
def test_check_decisions_respects_min_severity(tmp_path: Path) -> None:
    _seed(tmp_path, "dec_sql001", "UTC")
    _seed(tmp_path, "dec_mongo01", "server-local")
    commit_verdict(tmp_path, "dec_sql001", "dec_mongo01", severity=Severity.MEDIUM)

    assert main(["check", "--decisions", "--root", str(tmp_path)]) == EXIT_PASS
    assert (
        main(["check", "--decisions", "--root", str(tmp_path), "--min-severity", "medium"])
        == EXIT_FAIL
    )


@pytest.mark.phase_4
def test_check_decisions_unknown_base_treats_all_as_new(tmp_path: Path) -> None:
    _seed(tmp_path, "dec_sql001", "UTC")
    _seed(tmp_path, "dec_mongo01", "server-local")
    commit_verdict(tmp_path, "dec_sql001", "dec_mongo01")

    assert (
        main(["check", "--decisions", "--root", str(tmp_path), "--base", "missing-ref"])
        == EXIT_FAIL
    )


@pytest.mark.phase_4
def test_check_decisions_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed(tmp_path, "dec_sql001", "UTC")

    def _offline(*args: object, **kwargs: object) -> None:
        raise OSError

    monkeypatch.setattr(urllib.request, "urlopen", _offline)

    assert main(["check", "--decisions", "--root", str(tmp_path)]) == EXIT_PASS


@pytest.mark.phase_4
def test_check_mutually_exclusive_flags(tmp_path: Path) -> None:
    assert (
        main(["check", "--decisions", "--change", "change.json", "--root", str(tmp_path)])
        == EXIT_USAGE
    )


@pytest.mark.phase_4
def test_unjudged_pair_warns_but_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Similarity alone is not evidence enough to fail a build."""
    _seed(tmp_path, "dec_sql001", "UTC")
    _seed(tmp_path, "dec_mongo01", "server-local")

    assert main(["check", "--decisions", "--root", str(tmp_path)]) == EXIT_PASS
    err = capsys.readouterr().err
    assert "1 related pair(s) touching new decisions are not judged" in err
    assert "reasonledger judge" in err


@pytest.mark.phase_4
def test_judged_compatible_pair_passes_silently(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path, "dec_sql001", "UTC")
    _seed(tmp_path, "dec_mongo01", "server-local")
    commit_verdict(tmp_path, "dec_sql001", "dec_mongo01", conflict=False)

    assert main(["check", "--decisions", "--root", str(tmp_path)]) == EXIT_PASS
    assert "not judged" not in capsys.readouterr().err
