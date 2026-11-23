"""The compact shape of a decision in an MCP answer, shared by every tool that returns one.

An agent's context is the scarce resource: a hit is the handful of fields needed to decide
whether the record matters, and the full markdown is opt-in.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from reasonledger_core.decisions import render_decision_markdown
from reasonledger_core.models.decision import OUT_OF_FORCE, DecisionRecord

QUERY_LIMIT = 10


def in_force(record: DecisionRecord) -> bool:
    return record.frontmatter.status not in OUT_OF_FORCE


def in_force_first(records: Sequence[DecisionRecord]) -> list[DecisionRecord]:
    """Records in force ahead of retired and superseded ones, keeping each group's order."""
    return [r for r in records if in_force(r)] + [r for r in records if not in_force(r)]


def compact_hit(
    record: DecisionRecord, superseded_by: str | None, *, full: bool = False
) -> dict[str, Any]:
    fm = record.frontmatter
    hit: dict[str, Any] = {
        "id": fm.id,
        "context": fm.context,
        "choice": fm.choice,
        "justifies": fm.justifies,
        "status": fm.status.value,
        "oversight": fm.oversight.value,
        "proposed_by": fm.proposed_by.value if fm.proposed_by else None,
        "superseded_by": superseded_by,
    }
    if fm.retired_reason:
        hit["retired_reason"] = fm.retired_reason
    if fm.superseded_reason:
        hit["superseded_reason"] = fm.superseded_reason
    if full:
        hit["markdown"] = render_decision_markdown(record)
    return hit
