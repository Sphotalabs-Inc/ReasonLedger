"""LedgerView carries a decision's assumptions and rejected alternatives to its surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.views import build_ledger_view


def _write(
    root: Path,
    decision_id: str,
    *,
    alternatives_rejected: list[str] | None = None,
    assumptions: list[str] | None = None,
) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.PENDING,
            context="Which store?",
            choice="sqlite",
            alternatives_rejected=alternatives_rejected or [],
            assumptions=assumptions or [],
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


@pytest.mark.phase_3
def test_decision_summary_carries_assumptions_and_rejected_alternatives(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "dec_withwhy",
        assumptions=["single writer", "under 10k rows"],
        alternatives_rejected=["Postgres: needs a server"],
    )
    summary = build_ledger_view(tmp_path).decisions[0]
    assert summary.assumptions == ["single writer", "under 10k rows"]
    assert summary.alternatives_rejected == ["Postgres: needs a server"]


@pytest.mark.phase_3
def test_decision_summary_defaults_to_no_reasoning(tmp_path: Path) -> None:
    """A record without them is a normal record: the lists are empty, not missing."""
    _write(tmp_path, "dec_barebones")
    summary = build_ledger_view(tmp_path).decisions[0]
    assert summary.assumptions == []
    assert summary.alternatives_rejected == []
