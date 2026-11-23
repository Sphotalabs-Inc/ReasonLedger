"""Equal membership: a decision belongs to every module its code anchors fall in.

There is no home module. Membership comes from anchors only, never from usage, so a decision
about dates stays in the dates foundation and does not turn up in every feature that calls it.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.modules.config import MAX_MODULES_PER_DECISION
from reasonledger_core.modules.hand_placement import can_place_by_hand
from reasonledger_core.modules.manifest import membership
from reasonledger_core.modules.models import Manifest
from reasonledger_core.reasoning.why import locus_file


class Placement(BaseModel):
    decision_id: str
    anchors: dict[str, list[str]]  # module id -> this decision's loci that fall in it
    outside: list[str]  # loci whose file no module, bucket or label owns
    placed_by: str | None = None  # who put it here by hand, when its anchors could not

    @property
    def modules(self) -> list[str]:
        return list(self.anchors)

    @property
    def shared(self) -> bool:
        return len(self.anchors) >= 2

    @property
    def cross_cutting(self) -> bool:
        return len(self.anchors) > MAX_MODULES_PER_DECISION

    @property
    def by_hand(self) -> bool:
        return self.placed_by is not None

    @property
    def unplaced(self) -> bool:
        """No anchor lands in a module: no anchors at all, or only ones outside every module."""
        return not self.anchors


def place_decisions(
    records: Sequence[DecisionRecord], manifest: Manifest, root: Path
) -> dict[str, Placement]:
    """Where each decision lives, by its anchors, keyed by decision id.

    A decision with no anchor, or only broken ones, that a person placed by hand lives where
    they put it; their placement replaces what its dead anchors would say. Anchors that still
    work always win.
    """
    owner = membership(manifest)
    known = {m.id for m in manifest.modules}
    placed: dict[str, Placement] = {}
    for record in records:
        decision_id = record.frontmatter.id
        hand = manifest.placements.get(decision_id)
        if hand is not None and can_place_by_hand(root, record):
            homes = sorted(m for m in hand.modules if m in known)
            if homes:
                placed[decision_id] = Placement(
                    decision_id=decision_id,
                    anchors={m: [] for m in homes},
                    outside=[],
                    placed_by=hand.by,
                )
                continue
        anchors: dict[str, list[str]] = defaultdict(list)
        outside: list[str] = []
        for locus in record.frontmatter.justifies:
            module = owner.module_of(locus_file(locus))
            if module is None:
                outside.append(locus)
            else:
                anchors[module].append(locus)
        placed[decision_id] = Placement(
            decision_id=decision_id, anchors=dict(sorted(anchors.items())), outside=outside
        )
    return placed
