"""Phase 5 — a committed symlink cannot make the tool read or write outside the repository."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.decisions.fingerprint import read_lines
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.decisions.service import record_decision_to_path
from reasonledger_core.importer.scan import count_scannable_docs, scan_docs
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    RecordDecisionInput,
)
from reasonledger_core.reasoning.anchors import MISSING_FILE, locus_problem
from reasonledger_core.repo_files import RepoBoundaryError

OUTSIDE_TEXT = "PRIVATE TEXT THAT LIVES OUTSIDE THE REPO"


@pytest.fixture
def layout(tmp_path: Path) -> tuple[Path, Path]:
    repo, outside = tmp_path / "repo", tmp_path / "outside"
    repo.mkdir()
    outside.mkdir()
    (outside / "secret.md").write_text(OUTSIDE_TEXT, encoding="utf-8")
    (outside / "secret.py").write_text("def hidden():\n    return 1\n", encoding="utf-8")
    return repo, outside


def _record(decision_id: str) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.PENDING,
            context="Which queue backs the jobs?",
            choice="Postgres",
        ),
        body="",
    )


@pytest.mark.phase_5
def test_scan_skips_a_doc_that_links_outside_but_reads_one_that_links_inside(
    layout: tuple[Path, Path],
) -> None:
    repo, outside = layout
    docs = repo / "docs"
    docs.mkdir()
    (docs / "real.md").write_text("We chose Postgres.", encoding="utf-8")
    (docs / "private.md").symlink_to(outside / "secret.md")
    (docs / "alias.md").symlink_to(docs / "real.md")
    (repo / "linked").symlink_to(outside, target_is_directory=True)

    sources = scan_docs(repo)

    assert [source.path for source in sources] == ["docs/alias.md", "docs/real.md"]
    assert all(OUTSIDE_TEXT not in source.text for source in sources)
    assert count_scannable_docs(repo) == len(sources)


@pytest.mark.phase_5
def test_a_locus_that_resolves_outside_is_neither_read_nor_reported_present(
    layout: tuple[Path, Path],
) -> None:
    repo, outside = layout
    (repo / "src").mkdir()
    (repo / "src" / "escape.py").symlink_to(outside / "secret.py")

    assert read_lines(repo, "../outside/secret.py") is None
    assert read_lines(repo, "src/escape.py") is None
    assert locus_problem(repo, "src/escape.py::hidden") == MISSING_FILE
    assert locus_problem(repo, "../outside/secret.py::hidden") == MISSING_FILE


@pytest.mark.phase_5
def test_a_decision_is_never_written_through_a_symlinked_file(layout: tuple[Path, Path]) -> None:
    repo, outside = layout
    ledger = repo / DECISIONS_DIR
    ledger.mkdir(parents=True)
    linked = ledger / decision_filename("dec_linked")
    linked.symlink_to(outside / "secret.md")
    broken = ledger / decision_filename("dec_broken")
    broken.symlink_to(outside / "not-yet-there.md")

    for path in (linked, broken):
        with pytest.raises(RepoBoundaryError):
            write_decision_file(path, _record(path.stem))

    assert (outside / "secret.md").read_text(encoding="utf-8") == OUTSIDE_TEXT
    assert not (outside / "not-yet-there.md").exists()


@pytest.mark.phase_5
def test_a_ledger_directory_that_links_outside_takes_no_new_record(
    layout: tuple[Path, Path],
) -> None:
    repo, outside = layout
    (repo / ".reasonledger").mkdir()
    (repo / DECISIONS_DIR).symlink_to(outside, target_is_directory=True)
    inp = RecordDecisionInput(
        context="Which queue backs the jobs?",
        choice="Postgres",
        alternatives_rejected=["Redis"],
        ai_tool="none",
    )

    with pytest.raises(RepoBoundaryError, match="outside the repository"):
        record_decision_to_path(inp, root=repo)

    assert sorted(path.name for path in outside.iterdir()) == ["secret.md", "secret.py"]
