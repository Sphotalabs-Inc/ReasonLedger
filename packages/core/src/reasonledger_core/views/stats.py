"""Ledger composition in numbers: one count for `status --stats` and the UI summary strip.

Every figure covers decisions in force only. A retired or superseded record still exists,
but counting it would inflate a backlog nobody can act on. Nothing here reads a file: the
figures are derived from the two views the caller already built.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from reasonledger_core.models.decision import OUT_OF_FORCE, DecisionOversight, DecisionProposer
from reasonledger_core.views.ledger import DecisionSummary
from reasonledger_core.views.map_models import MapView


class ModuleStat(BaseModel):
    id: str
    name: str
    kind: str  # feature | foundation
    decisions: int  # unique live decisions on the module's page
    pending: int  # of those, no person has judged yet
    files: int
    coverage: float  # share of the module's files anchored by a live decision, 0 to 1


class LedgerStats(BaseModel):
    in_force: int
    judged: int  # a person gave a verdict, whatever it was
    pending: int
    proposed_human: int
    proposed_ai: int
    proposed_unset: int  # older records that never said whose idea the choice was
    mapped: bool  # False when there is no module map, so `modules` is empty by absence
    # Most decisions first. A decision anchored in two modules counts in both, so this
    # column does not sum to `in_force`.
    modules: list[ModuleStat] = []
    modules_without_decisions: int = 0


def _module_stats(map_view: MapView) -> list[ModuleStat]:
    # Buckets hold files no capability owns; they are not modules and are left out.
    tiles = [*map_view.features, *map_view.foundations]
    rows = [
        ModuleStat(
            id=t.id,
            name=t.name,
            kind=t.kind,
            decisions=t.decisions,
            pending=t.pending,
            files=t.files,
            coverage=t.coverage,
        )
        for t in tiles
    ]
    return sorted(rows, key=lambda m: (-m.decisions, m.id))


def build_stats(decisions: Sequence[DecisionSummary], map_view: MapView | None) -> LedgerStats:
    """Count the ledger's decisions in force, and per module when a map exists."""
    out_of_force = {status.value for status in OUT_OF_FORCE}
    live = [d for d in decisions if d.status not in out_of_force]
    pending = sum(1 for d in live if d.oversight == DecisionOversight.PENDING.value)
    human = sum(1 for d in live if d.proposed_by == DecisionProposer.HUMAN.value)
    ai = sum(1 for d in live if d.proposed_by == DecisionProposer.AI.value)
    mapped = map_view is not None and not map_view.empty
    modules = _module_stats(map_view) if map_view is not None and mapped else []
    return LedgerStats(
        in_force=len(live),
        judged=len(live) - pending,
        pending=pending,
        proposed_human=human,
        proposed_ai=ai,
        proposed_unset=len(live) - human - ai,
        mapped=mapped,
        modules=modules,
        modules_without_decisions=sum(1 for m in modules if m.decisions == 0),
    )
