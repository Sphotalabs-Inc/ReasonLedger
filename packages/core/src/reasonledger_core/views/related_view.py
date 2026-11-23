"""Related-decision projection for the ledger view: dismissals, then the split by relation.

Kept apart from ``ledger.py`` so the lifecycle projection stays readable; this is the
part that decides what a reviewer sees as a conflict and what as a related pair.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reasonledger_core.metrics import MetricEvent, emit_once_many
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.models.reasoning import (
    Conflict,
    ConflictDetail,
    ConflictStatus,
    ConflictWithDetails,
    Relation,
)
from reasonledger_core.reasoning.dismissals import (
    dismissal_still_applies,
    dismissed_fingerprints,
    pair_fingerprint,
    pair_key,
)


@dataclass(frozen=True)
class RelatedProjection:
    conflicts: list[Conflict]
    related: list[Conflict]
    dismissed: int
    reopened: int

    @property
    def unverified(self) -> int:
        return sum(1 for pair in self.related if pair.relation is Relation.UNVERIFIED)


def project_related(
    pairs: list[Conflict], records: list[DecisionRecord], root: Path
) -> RelatedProjection:
    """Apply dismissals, record surfaced pairs once, and split conflicts from related.

    A pair the team already judged wrong must stop being reported, or it nags on every
    status call until the list gets ignored wholesale. But that verdict was passed on
    the decisions *as they read then*: if either one's context or choice has changed
    since, the dismissal no longer covers the pair and it re-opens.
    """
    record_map = {record.frontmatter.id: record for record in records}
    dismissed = dismissed_fingerprints(root)
    dismissed_here = 0
    reopened_here = 0
    surviving: list[Conflict] = []
    for pair in pairs:
        key = pair_key(pair.decision_a, pair.decision_b)
        if key not in dismissed:
            surviving.append(pair)
            continue
        left = record_map.get(pair.decision_a)
        right = record_map.get(pair.decision_b)
        current = pair_fingerprint(left, right) if left and right else None
        if dismissal_still_applies(dismissed[key], current):
            dismissed_here += 1
            continue
        reopened_here += 1
        surviving.append(pair.model_copy(update={"status": ConflictStatus.REOPENED}))
    # Once per pair, not once per view build, and only for pairs put in front of a
    # reviewer: a pair already judged compatible asks nothing of anyone.
    emit_once_many(
        root,
        MetricEvent.CONFLICT_SURFACED,
        [
            (pair_key(pair.decision_a, pair.decision_b), {"severity": pair.severity.value})
            for pair in surviving
            if pair.relation is not Relation.COMPATIBLE
        ],
    )
    return RelatedProjection(
        conflicts=[pair for pair in surviving if pair.relation is Relation.CONFLICT],
        related=[pair for pair in surviving if pair.relation is not Relation.CONFLICT],
        dismissed=dismissed_here,
        reopened=reopened_here,
    )


def _detail(record: DecisionRecord) -> ConflictDetail:
    fm = record.frontmatter
    return ConflictDetail(
        decision_id=fm.id,
        context=fm.context,
        choice=fm.choice,
        source_ref=fm.source_ref,
        justifies=list(fm.justifies),
    )


def with_details(pairs: list[Conflict], records: list[DecisionRecord]) -> list[ConflictWithDetails]:
    """Both sides' text for each pair, so the UI can show what each decision says."""
    record_map = {record.frontmatter.id: record for record in records}
    result: list[ConflictWithDetails] = []
    for pair in pairs:
        left = record_map.get(pair.decision_a)
        right = record_map.get(pair.decision_b)
        if left is None or right is None:
            continue
        result.append(
            ConflictWithDetails(
                severity=pair.severity,
                explanation=pair.explanation,
                score=pair.score,
                status=pair.status,
                relation=pair.relation,
                judged_by=pair.judged_by,
                judged_at=pair.judged_at,
                detail_a=_detail(left),
                detail_b=_detail(right),
            )
        )
    return result
