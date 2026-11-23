"""Read-only projections of a repo's ``.reasonledger/`` state (S13).

``build_ledger_view`` is the single projection the status CLI, the local UI
(S14), and the org panel (S16) all consume. Views never mutate files: staleness
derived from ``watch_values`` is display-level only, and related decisions are
read from committed verdicts — the view never calls a model (see ``reasoning.judge``).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from reasonledger_core.decisions import load_decisions_from_dir, superseded_by_map
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.models.decision import (
    OUT_OF_FORCE,
    DecisionOversight,
    DecisionProposer,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.models.reasoning import Conflict, ConflictWithDetails, WatcherStatus
from reasonledger_core.reasoning.anchors import (
    ANCHOR_LOST,
    ANCHOR_MOVED,
    MISSING_FILE,
    MISSING_SYMBOL,
    drifted_loci,
    locus_problem,
)
from reasonledger_core.reasoning.cache import CachingEmbedder
from reasonledger_core.reasoning.conflict_config import (
    EmbedderStatus,
    resolve_conflict_embedder_with_status,
)
from reasonledger_core.reasoning.embeddings import Embedder
from reasonledger_core.reasoning.related import VerdictSource
from reasonledger_core.reasoning.verdicts import relate_in_repo
from reasonledger_core.reasoning.watchers import WatcherConditionError, rebuild_watchers
from reasonledger_core.sync.repo import first_commit_dates
from reasonledger_core.views.related_view import project_related, with_details

# Watcher display status when no source value is available for its metric.
WATCHER_STATUS_UNKNOWN = "unknown"


class ProposalSummary(BaseModel):
    id: str
    context: str | None
    choice: str | None
    source_ref: str | None
    extracted_by: str | None
    extracted_at: datetime | None
    supersedes: str | None = None
    has_conflict: bool = False  # in a pair a judge called a conflict


class DecisionSummary(BaseModel):
    id: str
    status: str
    context: str | None
    choice: str | None
    oversight: str
    proposed_by: str | None = None
    confirmed_by: str | None
    confirmed_at: datetime | None = None
    # Who and when, for every transition a reviewer may be asked to trust.
    ai_tool: str | None = None
    model: str | None = None
    recorded_at: datetime | None = None
    # True when recorded_at is the commit that added the file, not a date in the record.
    recorded_at_from_git: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    retired_by: str | None = None
    retired_at: datetime | None = None
    retired_reason: str | None = None
    superseded_by: str | None = None
    # Set only when a person chose between two decisions; a successor written to replace
    # this one carries its own recorder and date.
    superseded_decided_by: str | None = None
    superseded_at: datetime | None = None
    superseded_reason: str | None = None
    justifies: list[str]
    watchers: list[str]
    # What a reviewer vouches for beyond the choice: carried so a surface can show
    # them at the moment of approval instead of sending the reviewer to the file.
    assumptions: list[str] = []
    alternatives_rejected: list[str] = []


_MISSING_REASONS = frozenset({MISSING_FILE, MISSING_SYMBOL})


class OrphanView(BaseModel):
    """A `justifies` locus whose file or anchored symbol is no longer present."""

    decision_id: str
    locus: str
    reason: str  # missing_file | missing_symbol | anchor_moved | anchor_lost
    # Decisions still in force that explain code beside the lost locus (same file, or for a
    # missing file the same directory): where the replacement reasoning is most likely found.
    candidates: list[str] = []


class WatcherView(BaseModel):
    decision_id: str
    condition: str
    status: str  # healthy | drifting | stale | unknown
    last_value: float | None


class LedgerView(BaseModel):
    root: str
    generated_at: datetime
    proposals: list[ProposalSummary]
    decisions: list[DecisionSummary]
    stale: list[DecisionSummary]
    orphaned: list[OrphanView]
    watchers: list[WatcherView]
    # Pairs a judge called conflicts; `related` holds the rest of the shortlist
    # (judged compatible, or not judged yet). Each list also comes with both
    # decisions' details, so the UI can show what each side says.
    conflicts: list[Conflict]
    conflicts_with_details: list[ConflictWithDetails]
    related: list[Conflict] = []
    related_with_details: list[ConflictWithDetails] = []
    counts: dict[str, int]
    # Set only when this build resolved the embedder from repo config; a caller that
    # injects its own embedder already knows what it is running on.
    embedder: EmbedderStatus | None = None


def _proposal_summary(
    record: DecisionRecord, conflicted_ids: set[str] | None = None
) -> ProposalSummary:
    fm = record.frontmatter
    return ProposalSummary(
        id=fm.id,
        context=fm.context,
        choice=fm.choice,
        source_ref=fm.source_ref,
        extracted_by=fm.extracted_by,
        extracted_at=fm.extracted_at,
        supersedes=fm.supersedes,
        has_conflict=fm.id in (conflicted_ids or set()),
    )


def _decision_summary(
    record: DecisionRecord,
    git_dates: Mapping[str, datetime] | None = None,
    successors: Mapping[str, str] | None = None,
) -> DecisionSummary:
    fm = record.frontmatter
    git_date = None if fm.recorded_at else (git_dates or {}).get(decision_filename(fm.id))
    return DecisionSummary(
        ai_tool=fm.ai_tool,
        model=fm.model,
        recorded_at=fm.recorded_at or git_date,
        recorded_at_from_git=git_date is not None,
        approved_by=fm.approved_by,
        approved_at=fm.approved_at,
        retired_by=fm.retired_by,
        retired_at=fm.retired_at,
        retired_reason=fm.retired_reason,
        superseded_by=(successors or {}).get(fm.id),
        superseded_decided_by=fm.superseded_decided_by,
        superseded_at=fm.superseded_at,
        superseded_reason=fm.superseded_reason,
        id=fm.id,
        status=fm.status.value,
        context=fm.context,
        choice=fm.choice,
        oversight=fm.oversight.value,
        proposed_by=fm.proposed_by.value if fm.proposed_by else None,
        confirmed_by=fm.confirmed_by,
        confirmed_at=fm.confirmed_at,
        justifies=list(fm.justifies),
        watchers=list(fm.watchers),
        assumptions=list(fm.assumptions),
        alternatives_rejected=list(fm.alternatives_rejected),
    )


def _count_proposed_by(records: list[DecisionRecord], proposer: DecisionProposer) -> int:
    return sum(1 for r in records if r.frontmatter.proposed_by is proposer)


def _locus_file(locus: str) -> str:
    """The path part of a ``path::symbol`` or ``path:START-END`` locus."""
    file_part, separator, _ = locus.partition("::")
    return (file_part if separator else locus.rpartition(":")[0] or locus).strip()


def _candidates(
    record: DecisionRecord, locus: str, reason: str, in_force: list[DecisionRecord]
) -> list[str]:
    """Other decisions in force on the same file, or in its directory if the file is gone."""
    lost = _locus_file(locus)
    near = PurePosixPath(lost).parent if reason == MISSING_FILE else None
    found = []
    for other in in_force:
        if other.frontmatter.id == record.frontmatter.id:
            continue
        for other_locus in other.frontmatter.justifies:
            path = _locus_file(other_locus)
            if path == lost or (near is not None and PurePosixPath(path).parent == near):
                found.append(other.frontmatter.id)
                break
    return found


def _orphan_views(records: list[DecisionRecord], root: Path) -> list[OrphanView]:
    """Loci pointing at missing files or symbols, and line anchors that moved or were lost.

    Only decisions in force are listed: a retired or superseded one is history, and its
    code being gone is expected rather than something to act on.
    """
    in_force = [r for r in records if r.frontmatter.status not in OUT_OF_FORCE]
    orphans: list[OrphanView] = []
    lines_cache: dict[str, list[str] | None] = {}
    for record in in_force:
        found = list(drifted_loci(root, record, lines_cache))
        found.extend(
            (locus, problem)
            for locus in record.frontmatter.justifies
            if (problem := locus_problem(root, locus))
        )
        orphans.extend(
            OrphanView(
                decision_id=record.frontmatter.id,
                locus=locus,
                reason=reason,
                candidates=_candidates(record, locus, reason, in_force),
            )
            for locus, reason in found
        )
    orphans.sort(key=lambda orphan: (orphan.decision_id, orphan.locus))
    return orphans


def _load_sorted(directory: Path) -> list[DecisionRecord]:
    if not directory.is_dir():
        return []
    records = load_decisions_from_dir(directory)
    return sorted(records, key=lambda r: r.frontmatter.id)


def _watcher_views(
    records: list[DecisionRecord],
    values: Mapping[str, float],
) -> tuple[list[WatcherView], set[str]]:
    """Derive display watcher state; unknown metrics stay 'unknown', never stale."""
    views: list[WatcherView] = []
    display_stale_ids: set[str] = set()
    for record in records:
        if not record.frontmatter.watchers:
            continue
        try:
            watchers = rebuild_watchers(record, values)
        except WatcherConditionError:
            views.extend(
                WatcherView(
                    decision_id=record.frontmatter.id,
                    condition=raw,
                    status=WATCHER_STATUS_UNKNOWN,
                    last_value=None,
                )
                for raw in record.frontmatter.watchers
            )
            continue
        for watcher in watchers:
            no_value = watcher.last_value is None
            views.append(
                WatcherView(
                    decision_id=watcher.decision_id,
                    condition=watcher.condition,
                    status=WATCHER_STATUS_UNKNOWN if no_value else watcher.status.value,
                    last_value=watcher.last_value,
                )
            )
            if not no_value and watcher.status == WatcherStatus.STALE:
                display_stale_ids.add(watcher.decision_id)
    views.sort(key=lambda w: (w.decision_id, w.condition))
    return views, display_stale_ids


def build_ledger_view(
    root: Path,
    *,
    watch_values: Mapping[str, float] | None = None,
    embedder: Embedder | None = None,
    verdicts: VerdictSource | None = None,
) -> LedgerView:
    """Project the repo's decision lifecycle. Read-only — never writes a file."""
    proposal_records = _load_sorted(root / PROPOSED_DIR)
    ledger_records = _load_sorted(root / DECISIONS_DIR)

    watcher_views, display_stale_ids = _watcher_views(ledger_records, watch_values or {})
    orphan_views = _orphan_views(ledger_records, root)

    stale_records = [
        record
        for record in ledger_records
        if record.frontmatter.status == DecisionStatus.STALE
        or record.frontmatter.id in display_stale_ids
    ]

    all_records = proposal_records + ledger_records
    pairs: list[Conflict] = []
    embedder_status: EmbedderStatus | None = None
    if len(all_records) >= 2:
        if embedder is None:
            embedder, embedder_status = resolve_conflict_embedder_with_status(root)
        # Memory memo only here — per-vector disk writes dominate cold builds at
        # ledger scale; interactive callers already sit behind build_ledger_view_cached.
        pairs = relate_in_repo(
            root, all_records, embedder=CachingEmbedder(embedder), verdicts=verdicts
        )
    projection = project_related(pairs, all_records, root)
    conflicts = projection.conflicts

    # Older records carry no date of their own; git knows when each file was added.
    undated = any(record.frontmatter.recorded_at is None for record in ledger_records)
    git_dates = first_commit_dates(root, DECISIONS_DIR) if undated else {}
    successors = superseded_by_map(ledger_records)
    decisions = [_decision_summary(record, git_dates, successors) for record in ledger_records]

    # Build set of proposal IDs involved in conflicts for UI marking
    conflicted_ids: set[str] = set()
    for conflict in conflicts:
        conflicted_ids.add(conflict.decision_a)
        conflicted_ids.add(conflict.decision_b)

    counts = {
        "proposed": len(proposal_records),
        "confirmed": sum(
            1 for r in ledger_records if r.frontmatter.status == DecisionStatus.CONFIRMED
        ),
        "active": sum(1 for r in ledger_records if r.frontmatter.status == DecisionStatus.ACTIVE),
        "superseded": sum(
            1 for r in ledger_records if r.frontmatter.status == DecisionStatus.SUPERSEDED
        ),
        "retired": sum(1 for r in ledger_records if r.frontmatter.status == DecisionStatus.RETIRED),
        "pending_approval": sum(
            1
            for r in ledger_records
            if r.frontmatter.oversight is DecisionOversight.PENDING
            and r.frontmatter.status not in OUT_OF_FORCE
        ),
        "agreed": _count_proposed_by(ledger_records, DecisionProposer.HUMAN),
        "recommended": _count_proposed_by(ledger_records, DecisionProposer.AI),
        "stale": len(stale_records),
        "orphaned": sum(1 for o in orphan_views if o.reason in _MISSING_REASONS),
        "moved_anchors": sum(1 for o in orphan_views if o.reason == ANCHOR_MOVED),
        "lost_anchors": sum(1 for o in orphan_views if o.reason == ANCHOR_LOST),
        "conflicts": len(conflicts),
        "related": len(projection.related),
        "unverified": projection.unverified,
        "dismissed": projection.dismissed,
        "reopened": projection.reopened,
    }
    return LedgerView(
        root=str(root),
        generated_at=datetime.now(UTC),
        proposals=[_proposal_summary(record, conflicted_ids) for record in proposal_records],
        decisions=decisions,
        stale=[_decision_summary(record) for record in stale_records],
        orphaned=orphan_views,
        watchers=watcher_views,
        conflicts=conflicts,
        conflicts_with_details=with_details(conflicts, all_records),
        related=projection.related,
        related_with_details=with_details(projection.related, all_records),
        counts=counts,
        embedder=embedder_status,
    )
