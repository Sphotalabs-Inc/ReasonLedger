"""P0-4 S6: import orchestrator — scan -> extract -> propose, conflict-first."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.extractor import DecisionCandidate, ReplayExtractor
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.importer.service import run_import
from reasonledger_core.reasoning import DeterministicEmbedder

EXTRACTED_AT = datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC)


def _repo_with_conflicting_date_docs(tmp_path: Path) -> ReplayExtractor:
    """A real-world case: claude.md says UTC, date-semantics.md says server-local."""
    (tmp_path / "claude.md").write_text("timestamps are UTC", encoding="utf-8")
    docs = tmp_path / "backend" / "docs"
    docs.mkdir(parents=True)
    (docs / "date-semantics.md").write_text("timestamps are server-local", encoding="utf-8")
    return ReplayExtractor(
        {
            "claude.md": [
                DecisionCandidate(
                    context="Timestamp storage timezone policy",
                    choice="UTC",
                    source_ref="claude.md#timestamps",
                    justifies=["backend/app/date_utils.py"],
                )
            ],
            "backend/docs/date-semantics.md": [
                DecisionCandidate(
                    context="Timestamp storage timezone policy",
                    choice="server-local",
                    source_ref="backend/docs/date-semantics.md#timestamps",
                    justifies=["backend/app/date_utils.py"],
                )
            ],
        }
    )


@pytest.mark.phase_4
def test_import_surfaces_conflict_and_stages_only(tmp_path: Path) -> None:
    extractor = _repo_with_conflicting_date_docs(tmp_path)
    report = run_import(
        tmp_path,
        extractor=extractor,
        extracted_by="anthropic/claude-sonnet-5",
        extracted_at=EXTRACTED_AT,
        embedder=DeterministicEmbedder(),
    )

    # Conflict-first: the UTC vs server-local contradiction is surfaced.
    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert {conflict.decision_a, conflict.decision_b} == set(report.result.proposed_ids)

    # Both proposed; nothing auto-written to the ledger.
    assert report.result.created == 2
    assert not (tmp_path / DECISIONS_DIR).exists()
    assert len(list((tmp_path / PROPOSED_DIR).glob("dec_*.md"))) == 2
