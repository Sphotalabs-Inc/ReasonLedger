"""Placing a decision by hand when its anchors cannot.

Membership comes from a decision's anchors (S34). A decision with no anchor, or only anchors that
point at files or symbols that are gone, has nothing to be placed by, so a person may say which
modules it belongs to. The answer is stored in ``modules.yml`` and applies only while that stays
true: a decision with an anchor that still works is placed by it, never by hand.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.modules.config import MAX_MODULES_PER_DECISION
from reasonledger_core.modules.models import DecisionPlacement, Manifest
from reasonledger_core.reasoning.anchors import locus_problem


class PlacementError(ValueError):
    """A hand placement the rules do not allow."""


class AnchorState(StrEnum):
    NONE = "none"  # no anchor at all
    BROKEN = "broken"  # every anchor points at a file or symbol that is gone
    ANCHORED = "anchored"  # at least one anchor still points at something


def anchor_state(root: Path, loci: Sequence[str]) -> AnchorState:
    if not loci:
        return AnchorState.NONE
    broken = all(locus_problem(root, locus) for locus in loci)
    return AnchorState.BROKEN if broken else AnchorState.ANCHORED


def can_place_by_hand(root: Path, record: DecisionRecord) -> bool:
    return anchor_state(root, record.frontmatter.justifies) is not AnchorState.ANCHORED


def place_by_hand(
    manifest: Manifest,
    record: DecisionRecord,
    root: Path,
    modules: Sequence[str],
    by: str,
    *,
    now: datetime | None = None,
) -> Manifest:
    """Store ``modules`` as the home of a decision that has no usable anchor."""
    decision_id = record.frontmatter.id
    who = by.strip()
    if not who:
        raise PlacementError("say who is placing it: a placement is a person's call")
    chosen = list(dict.fromkeys(modules))
    if not chosen:
        raise PlacementError("name at least one module or bucket")
    if len(chosen) > MAX_MODULES_PER_DECISION:
        raise PlacementError(
            f"more than {MAX_MODULES_PER_DECISION} modules makes a decision cross-cutting, and "
            "that is for anchors to say"
        )
    known = {m.id for m in manifest.modules}
    unknown = [m for m in chosen if m not in known]
    if unknown:
        raise PlacementError(f"no such module or bucket: {', '.join(unknown)}")
    if not can_place_by_hand(root, record):
        raise PlacementError(
            f"{decision_id} has an anchor that still points at code, so it is placed by that "
            "anchor; re-anchor it instead"
        )
    placement = DecisionPlacement(modules=chosen, by=who, at=now or datetime.now(UTC))
    return manifest.model_copy(
        update={"placements": {**manifest.placements, decision_id: placement}}
    )


def clear_hand_placement(manifest: Manifest, decision_id: str) -> Manifest:
    if decision_id not in manifest.placements:
        raise PlacementError(f"{decision_id} has no hand placement")
    kept = {i: p for i, p in manifest.placements.items() if i != decision_id}
    return manifest.model_copy(update={"placements": kept})


def stale_placements(
    manifest: Manifest, records: Mapping[str, DecisionRecord], root: Path
) -> dict[str, str]:
    """Hand placements that no longer apply, and why, keyed by decision id."""
    known = {m.id for m in manifest.modules}
    stale: dict[str, str] = {}
    for decision_id, placement in manifest.placements.items():
        record = records.get(decision_id)
        gone = [m for m in placement.modules if m not in known]
        if record is None:
            stale[decision_id] = "the decision is gone"
        elif not can_place_by_hand(root, record):
            stale[decision_id] = "it has an anchor that works now, which places it"
        elif gone:
            stale[decision_id] = f"module {', '.join(gone)} is gone"
    return stale
