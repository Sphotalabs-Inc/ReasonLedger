"""The coding agent backfills proposals from docs and commit messages, with no model call."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions.format import read_decision_file
from reasonledger_core.importer.agent_route import import_task, submit_candidates
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.models.decision import DecisionStatus

WHEN = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
DOC = "docs/adr.md"
PROSE = "We chose Postgres over SQLite because the app has more than one writer.\n"


def _candidate(source_ref: str = f"{DOC}#postgres") -> dict[str, object]:
    return {
        "context": "The app has more than one writer.",
        "choice": "Use Postgres.",
        "source_ref": source_ref,
        "alternatives_rejected": ["SQLite"],
    }


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.mark.phase_3
def test_the_task_names_docs_and_keeps_their_text_in_the_file(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / DOC).write_text(PROSE, encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("db = 'postgres'\n", encoding="utf-8")

    task = import_task(tmp_path)

    assert task["pending"] == 1
    assert task["sources"] == [{"path": DOC, "kind": "doc"}]
    assert PROSE not in str(task)
    assert "src/app.py" not in str(task)


@pytest.mark.phase_3
def test_a_submission_is_a_proposal_and_the_source_leaves_the_queue(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / DOC).write_text(PROSE, encoding="utf-8")

    result = submit_candidates(tmp_path, [_candidate()], "cursor/test", extracted_at=WHEN)

    assert result["ok"] is True and result["created"] == 1 and result["remaining"] == 0
    record = read_decision_file(tmp_path / PROPOSED_DIR / f"{result['proposed_ids'][0]}.md")
    assert record.frontmatter.status is DecisionStatus.PROPOSED
    assert record.frontmatter.extracted_by == "cursor/test"
    assert import_task(tmp_path)["sources"] == []


@pytest.mark.phase_3
def test_a_bad_source_ref_is_rejected_and_the_document_stays_pending(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / DOC).write_text(PROSE, encoding="utf-8")

    result = submit_candidates(tmp_path, [_candidate(DOC)], "cursor/test", [DOC], extracted_at=WHEN)

    assert result["created"] == 0
    assert result["rejected"]
    assert import_task(tmp_path)["pending"] == 1


@pytest.mark.phase_3
def test_an_empty_document_stays_out_of_the_queue_until_its_text_changes(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    path = tmp_path / DOC
    path.write_text("This page is a tutorial.\n", encoding="utf-8")

    result = submit_candidates(tmp_path, [], "cursor/test", [DOC], extracted_at=WHEN)

    assert result["created"] == 0 and result["remaining"] == 0
    path.write_text(PROSE, encoding="utf-8")
    assert import_task(tmp_path)["sources"] == [{"path": DOC, "kind": "doc"}]


@pytest.mark.phase_3
def test_a_long_commit_message_is_handed_over_because_it_is_not_a_file(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "readme.md").write_text("hello\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    message = (
        "store sessions in postgres\n\n"
        "Chose Postgres over an embedded database because two app processes write sessions "
        "and SQLite would lock. The rejected option was a single-file database.\n"
    )
    _git(tmp_path, "commit", "-qm", message)

    task = import_task(tmp_path)
    commits = [source for source in task["sources"] if source["kind"] == "commit"]

    assert len(commits) == 1
    assert commits[0]["path"].startswith("git:")
    assert "Chose Postgres" in commits[0]["text"]
    assert "readme.md" in {source["path"] for source in task["sources"]}


@pytest.mark.phase_3
def test_a_batch_with_no_decisions_says_so_and_how_much_is_left(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / DOC).write_text("This page is a tutorial.\n", encoding="utf-8")
    other = "docs/other.md"
    (tmp_path / other).write_text(PROSE, encoding="utf-8")

    task = import_task(tmp_path, limit=1)
    assert task["total"] == 2 and task["done"] == 0

    result = submit_candidates(tmp_path, [], "cursor/test", [DOC], extracted_at=WHEN)

    assert "no decisions found" in result["summary"]
    assert "1 source(s) still unread" in result["summary"]
    assert import_task(tmp_path)["done"] == 1


@pytest.mark.phase_3
def test_the_last_batch_points_the_user_at_the_review_screen(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / DOC).write_text(PROSE, encoding="utf-8")

    result = submit_candidates(tmp_path, [_candidate()], "cursor/test", extracted_at=WHEN)

    assert "1 proposal(s) staged" in result["summary"]
    assert "reasonledger ui" in result["summary"]
