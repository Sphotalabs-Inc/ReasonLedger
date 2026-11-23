"""The module map: tiles, bands and a page per module.

Read-only and model-free. It joins what the repo already holds: ``modules.yml`` (the modules),
the source files they own, and the decisions whose code anchors fall in them.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.models.decision import OUT_OF_FORCE, DecisionOversight, DecisionRecord
from reasonledger_core.models.reasoning import Conflict
from reasonledger_core.modules.config import SEARCH_TEXT_CHARS
from reasonledger_core.modules.digest import source_files
from reasonledger_core.modules.files import modelled_files
from reasonledger_core.modules.hand_placement import can_place_by_hand
from reasonledger_core.modules.labels import folder_pattern
from reasonledger_core.modules.manifest import dangling_labels, load_manifest, membership
from reasonledger_core.modules.models import Manifest, Module, ModuleKind, ModuleStatus
from reasonledger_core.modules.placement import Placement, place_decisions
from reasonledger_core.reasoning.why import locus_file
from reasonledger_core.views.map_models import (
    MapDecision,
    MapTile,
    MapView,
    ModuleConflict,
    ModulePage,
    ModuleRef,
    Neighbour,
    OrphanedAnchor,
)


@dataclass(frozen=True)
class MapData:
    root: Path
    manifest: Manifest
    files: list[str]
    members: dict[str, list[str]]  # module id -> the source files it owns
    records: dict[str, DecisionRecord]
    placements: dict[str, Placement]
    conflicts: list[Conflict]
    unplaced_files: int  # source files no module, bucket or label owns


def load_map(root: Path, conflicts: Sequence[Conflict] = ()) -> MapData:
    manifest = load_manifest(root)
    files = source_files(root)
    owner = membership(manifest)
    members: dict[str, list[str]] = {m.id: [] for m in manifest.modules}
    unplaced = 0
    for path in files:
        found = owner.module_of(path)
        if found:
            members[found].append(path)
        else:
            unplaced += 1
    directory = root / DECISIONS_DIR
    loaded = load_decisions_from_dir(directory) if directory.is_dir() else []
    records = {r.frontmatter.id: r for r in sorted(loaded, key=lambda r: r.frontmatter.id)}
    return MapData(
        root=root,
        manifest=manifest,
        files=files,
        members=members,
        records=records,
        placements=place_decisions(list(records.values()), manifest, root),
        conflicts=list(conflicts),
        unplaced_files=unplaced,
    )


def _live(record: DecisionRecord) -> bool:
    return record.frontmatter.status not in OUT_OF_FORCE


def _ref(module: Module) -> ModuleRef:
    return ModuleRef(
        id=module.id,
        name=module.name,
        kind=module.kind.value,
        tier=module.tier.value if module.tier else None,
    )


def _listed(module: Module, placement: Placement) -> bool:
    """Whether a decision is listed on this module's page.

    A cross-cutting decision is listed once, apart, and under any foundation it anchors in; a
    feature page carries a pointer instead of repeating it.
    """
    if module.id not in placement.anchors:
        return False
    return module.kind is not ModuleKind.FEATURE or not placement.cross_cutting


def _anchored_files(data: MapData, module: Module) -> list[str]:
    """Files of the module that a live decision's locus names."""
    owned = set(data.members[module.id])
    named = {
        locus_file(locus)
        for record_id, record in data.records.items()
        if _live(record)
        for locus in data.placements[record_id].anchors.get(module.id, [])
    }
    return sorted(named & owned)


def _search_text(data: MapData, module: Module, listed: Sequence[Placement]) -> str:
    parts = [module.id, module.name, module.description, *module.paths]
    for placement in listed:
        fm = data.records[placement.decision_id].frontmatter
        context, choice = (fm.context or ""), (fm.choice or "")
        parts += [fm.id, context[:SEARCH_TEXT_CHARS], choice[:SEARCH_TEXT_CHARS]]
        parts += placement.anchors[module.id]
    return " ".join(parts).lower()


def _tile(data: MapData, module: Module) -> MapTile:
    listed = [
        data.placements[i]
        for i, record in data.records.items()
        if _live(record) and _listed(module, data.placements[i])
    ]
    pending = sum(
        1
        for p in listed
        if data.records[p.decision_id].frontmatter.oversight is DecisionOversight.PENDING
    )
    cross = sum(
        1
        for i, record in data.records.items()
        if _live(record)
        and module.kind is ModuleKind.FEATURE
        and module.id in data.placements[i].anchors
        and data.placements[i].cross_cutting
    )
    owned = len(data.members[module.id])
    return MapTile(
        **_ref(module).model_dump(),
        status=module.status.value,
        description=module.description,
        files=owned,
        decisions=len(listed),
        shared=sum(1 for p in listed if p.shared),
        pending=pending,
        coverage=round(len(_anchored_files(data, module)) / owned, 3) if owned else 0.0,
        cross_cutting=cross,
        search=_search_text(data, module, listed),
    )


def _decision(data: MapData, decision_id: str) -> MapDecision:
    fm = data.records[decision_id].frontmatter
    placement = data.placements[decision_id]
    by_id = {m.id: m for m in data.manifest.modules}
    return MapDecision(
        id=decision_id,
        status=fm.status.value,
        oversight=fm.oversight.value,
        proposed_by=fm.proposed_by.value if fm.proposed_by else None,
        context=fm.context,
        choice=fm.choice,
        anchors=placement.anchors,
        outside=placement.outside,
        modules=[_ref(by_id[m]) for m in placement.modules],
        shared=placement.shared,
        cross_cutting=placement.cross_cutting,
        superseded=not _live(data.records[decision_id]),
        placed_by=placement.placed_by,
    )


def _without_module(data: MapData, live: Sequence[str]) -> list[MapDecision]:
    """Live decisions no module holds, each with what a person can do about it.

    Anchors in files nothing owns (a spec, a doc, a test) can be claimed by a label on their
    folder; a decision with no working anchor can be placed by hand instead.
    """
    unplaced = [i for i in live if data.placements[i].unplaced]
    if not unplaced:
        return []
    labelable = set(modelled_files(data.root)[0])
    found: list[MapDecision] = []
    for decision_id in unplaced:
        files = {locus_file(locus) for locus in data.placements[decision_id].outside}
        extra = {
            "claimable": sorted({folder_pattern(f) for f in files if f in labelable}),
            "placeable": can_place_by_hand(data.root, data.records[decision_id]),
        }
        found.append(_decision(data, decision_id).model_copy(update=extra))
    return found


def overview(data: MapData) -> MapView:
    manifest = data.manifest
    base = MapView(root=str(data.root), generated_at=datetime.now(UTC), empty=not manifest.modules)
    if base.empty:
        return base
    tiles = sorted((_tile(data, m) for m in manifest.modules), key=lambda t: (-t.files, t.id))
    live = [i for i, record in data.records.items() if _live(record)]
    return base.model_copy(
        update={
            "mapped_by": manifest.mapped_by,
            "mapped_at_commit": manifest.mapped_at_commit,
            "decisions": len(live),
            "files": len(data.files),
            "unplaced_files": data.unplaced_files,
            "pending_proposals": sum(
                1 for m in manifest.capabilities if m.status is ModuleStatus.PROPOSED
            ),
            "dangling_labels": dangling_labels(manifest),
            "features": [t for t in tiles if t.kind == ModuleKind.FEATURE.value],
            "foundations": [t for t in tiles if t.kind == ModuleKind.FOUNDATION.value],
            "buckets": [t for t in tiles if t.kind == ModuleKind.BUCKET.value],
            "cross_cutting": [_decision(data, i) for i in live if data.placements[i].cross_cutting],
            "unplaced_decisions": _without_module(data, live),
        }
    )


def module_page(data: MapData, module_id: str) -> ModulePage | None:
    module = next((m for m in data.manifest.modules if m.id == module_id), None)
    if module is None:
        return None
    listed = [i for i in data.records if _listed(module, data.placements[i])]
    live = [i for i in listed if _live(data.records[i])]
    neighbours = Counter(
        other for i in live for other in data.placements[i].anchors if other != module_id
    )
    by_id = {m.id: m for m in data.manifest.modules}
    listed_set = set(listed)
    return ModulePage(
        tile=_tile(data, module),
        paths=list(module.paths),
        files=sorted(data.members[module_id]),
        anchored_files=_anchored_files(data, module),
        decisions=[_decision(data, i) for i in listed],
        orphaned=[
            OrphanedAnchor(decision_id=i, locus=locus)
            for i in listed
            for locus in data.placements[i].anchors[module_id]
            if not (data.root / locus_file(locus)).exists()
        ],
        conflicts=[
            ModuleConflict(
                decision_a=c.decision_a,
                decision_b=c.decision_b,
                severity=c.severity.value,
                explanation=c.explanation,
            )
            for c in data.conflicts
            if c.decision_a in listed_set and c.decision_b in listed_set
        ],
        neighbours=[
            Neighbour(**_ref(by_id[other]).model_dump(), shared=count)
            for other, count in sorted(neighbours.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    )
