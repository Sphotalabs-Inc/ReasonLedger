"""Phase 4 — `reasonledger dismiss` and its effect on the CI conflict gate."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_cli.main import main
from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    decision_filename,
    write_decision_file,
)
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.reasoning.dismissals import DISMISSED_PATH, dismissed_keys
from verdict_helpers import commit_verdict

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def _write(root: Path, decision_id: str, *, context: str, choice: str) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            status=DecisionStatus.CONFIRMED,
            context=context,
            choice=choice,
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


def _conflicting_pair(root: Path) -> None:
    _write(root, "dec_pgsql", context="Primary datastore for orders", choice="PostgreSQL")
    _write(root, "dec_mongo", context="Primary datastore for orders", choice="MongoDB")


@pytest.mark.phase_4
def test_dismiss_writes_committable_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _conflicting_pair(tmp_path)
    code = main(
        [
            "dismiss",
            "dec_mongo",
            "dec_pgsql",
            "--reason",
            "different services, not the same datastore choice",
            "--root",
            str(tmp_path),
        ]
    )
    assert code == EXIT_PASS
    assert (tmp_path / DISMISSED_PATH).is_file()
    assert dismissed_keys(tmp_path) == {"dec_mongo::dec_pgsql"}
    assert "commit .reasonledger/dismissed.yml" in capsys.readouterr().out


@pytest.mark.phase_4
def test_dismiss_rejects_unknown_id(tmp_path: Path) -> None:
    """A typo must not silently record a dismissal that suppresses nothing."""
    _conflicting_pair(tmp_path)
    code = main(["dismiss", "dec_pgsql", "dec_nope", "--reason", "typo", "--root", str(tmp_path)])
    assert code == EXIT_USAGE
    assert not (tmp_path / DISMISSED_PATH).exists()


@pytest.mark.phase_4
def test_dismiss_rejects_self_pair(tmp_path: Path) -> None:
    _conflicting_pair(tmp_path)
    code = main(["dismiss", "dec_pgsql", "dec_pgsql", "--reason", "same", "--root", str(tmp_path)])
    assert code == EXIT_USAGE


@pytest.mark.phase_4
def test_ci_gate_passes_after_dismissal(tmp_path: Path) -> None:
    """The gate must stop failing a build once a human has judged the hint wrong."""
    _conflicting_pair(tmp_path)
    commit_verdict(tmp_path, "dec_pgsql", "dec_mongo")
    assert main(["check", "--decisions", "--root", str(tmp_path)]) == EXIT_FAIL

    assert (
        main(
            [
                "dismiss",
                "dec_pgsql",
                "dec_mongo",
                "--reason",
                "orders vs analytics; the shared context wording is coincidental",
                "--root",
                str(tmp_path),
            ]
        )
        == EXIT_PASS
    )
    assert main(["check", "--decisions", "--root", str(tmp_path)]) == EXIT_PASS
