"""Shared builders for the `why` CLI and UI tests."""

from __future__ import annotations

from pathlib import Path

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

# The rehearsal's real miss: a decision at lines 15-19, asked about line 1.
HUNTER = "backend/src/routes/hunter.routes.ts"
HUNTER_LOCUS = f"{HUNTER}:15-19"


def write_source(root: Path, rel: str, lines: int = 30) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"// line {n}\n" for n in range(1, lines + 1)), encoding="utf-8")


def decide(
    root: Path,
    decision_id: str,
    justifies: list[str],
    *,
    choice: str = "Cache hunter lookups for sixty seconds",
    context: str = "Hunter lookups hit the API on every request.",
    rejected: list[str] | None = None,
    approved_by: str | None = "alice",
    status: DecisionStatus = DecisionStatus.ACTIVE,
) -> Path:
    _, path = record_decision_to_path(
        RecordDecisionInput(
            context=context,
            choice=choice,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED if approved_by else DecisionOversight.PENDING,
            approved_by=approved_by,
            justifies=justifies,
            alternatives_rejected=rejected or ["Redis: a new service for one cache"],
            decision_id=decision_id,
        ),
        root=root,
    )
    if status is not DecisionStatus.ACTIVE:
        record = read_decision_file(path)
        record.frontmatter.status = status
        if status is DecisionStatus.RETIRED:
            record.frontmatter.retired_reason = "no longer true"
        write_decision_file(path, record)
    return path
