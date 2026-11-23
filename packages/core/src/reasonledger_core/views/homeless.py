"""Decisions that have no working anchor, for a person to place.

A decision belongs where its anchors put it. One with no anchor, or only anchors that point at
files that are gone, has nothing sound to go by, so the Organize tab lists it with a suggested
home and lets a person say. There are three states: no module at all (waiting), a module only
because a dead anchor's path still matches a module's folder (guessed), and placed by hand (kept
so the placement can be changed or taken back). Superseded decisions are left out.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from reasonledger_core.models.decision import OUT_OF_FORCE
from reasonledger_core.modules.decision_suggest import suggest_homes
from reasonledger_core.modules.hand_placement import AnchorState, anchor_state, stale_placements
from reasonledger_core.modules.manifest import load_manifest
from reasonledger_core.modules.placement import place_decisions
from reasonledger_core.modules.suggest import CoChangeIndex
from reasonledger_core.reasoning.anchors import locus_problem
from reasonledger_core.views.organize_files import load_records


class HomeIdea(BaseModel):
    module: str
    name: str
    confidence: str
    evidence: list[str]


class HomelessDecision(BaseModel):
    id: str
    context: str | None
    choice: str | None
    state: Literal["waiting", "guessed", "hand"]
    why: str  # why anchors cannot place it
    dead_anchors: list[str]
    modules: list[str]  # where it is now: by hand, or through a dead anchor's path
    placed_by: str | None = None
    placed_at: datetime | None = None
    ideas: list[HomeIdea]


class HomelessView(BaseModel):
    items: list[HomelessDecision]
    waiting: int  # decisions with no module at all
    stale: dict[str, str]  # hand placements that no longer apply, and why


def homeless_view(root: Path, files: list[str], history: CoChangeIndex | None) -> HomelessView:
    manifest = load_manifest(root)
    records = load_records(root)
    placed = place_decisions(records, manifest, root)
    names = {m.id: m.name for m in manifest.modules}
    items: list[HomelessDecision] = []
    for record in records:
        fm = record.frontmatter
        state = anchor_state(root, fm.justifies)
        here = placed[fm.id]
        if fm.status in OUT_OF_FORCE or state is AnchorState.ANCHORED:
            continue
        ideas = suggest_homes(record, manifest, files, root, history)
        hand = manifest.placements.get(fm.id) if here.by_hand else None
        items.append(
            HomelessDecision(
                id=fm.id,
                context=fm.context,
                choice=fm.choice,
                state="hand" if here.by_hand else "waiting" if here.unplaced else "guessed",
                why=(
                    "it has no anchor"
                    if state is AnchorState.NONE
                    else "every anchor points at a file or symbol that is gone"
                ),
                dead_anchors=[loc for loc in fm.justifies if locus_problem(root, loc)],
                modules=here.modules,
                placed_by=here.placed_by,
                placed_at=hand.at if hand else None,
                ideas=[
                    HomeIdea(
                        module=i.module,
                        name=names.get(i.module, i.module),
                        confidence=i.confidence,
                        evidence=i.evidence,
                    )
                    for i in ideas
                ],
            )
        )
    order = {"waiting": 0, "guessed": 1, "hand": 2}
    items.sort(key=lambda d: (order[d.state], d.id))
    stale = stale_placements(manifest, {r.frontmatter.id: r for r in records}, root)
    return HomelessView(
        items=items, waiting=sum(1 for d in items if d.state == "waiting"), stale=stale
    )
