"""Payload shapes of the module map: what the overview and a module page carry."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ModuleRef(BaseModel):
    id: str
    name: str
    kind: str  # feature | foundation | bucket
    tier: str | None = None  # backend | frontend, when the repo has both


class MapTile(ModuleRef):
    status: str  # proposed | confirmed
    description: str = ""
    files: int
    decisions: int  # unique live decisions listed on this module's page
    shared: int  # of those, anchored in two or more modules
    pending: int  # of those, no person has judged yet
    coverage: float  # share of the module's files anchored by a live decision, 0 to 1
    cross_cutting: int = 0  # cross-cutting decisions that touch a feature but are listed apart
    search: str = ""  # lower-case words of the module, its paths and the decisions listed on it


class MapDecision(BaseModel):
    id: str
    status: str
    oversight: str
    proposed_by: str | None = None
    context: str | None = None
    choice: str | None = None
    anchors: dict[str, list[str]]  # module id -> this decision's loci in it
    outside: list[str]  # loci whose file no module owns
    modules: list[ModuleRef]  # every module it anchors in, for chips and jump links
    shared: bool
    cross_cutting: bool
    superseded: bool
    placed_by: str | None = None  # who put it here by hand, when its anchors could not
    # Only set for a decision with no module: what a person can do about it from its card.
    claimable: list[str] = []  # label patterns that would bring its anchored files into a module
    placeable: bool = False  # no anchor works, so a person may say where it belongs


class MapView(BaseModel):
    root: str
    generated_at: datetime
    empty: bool  # no modules.yml yet
    mapped_by: str | None = None
    mapped_at_commit: str | None = None
    decisions: int = 0  # unique live decisions; tiles do not sum to this
    files: int = 0
    unplaced_files: int = 0
    pending_proposals: int = 0  # proposed modules nobody has confirmed
    dangling_labels: list[str] = []
    features: list[MapTile] = []
    foundations: list[MapTile] = []
    buckets: list[MapTile] = []
    cross_cutting: list[MapDecision] = []
    unplaced_decisions: list[MapDecision] = []


class Neighbour(ModuleRef):
    shared: int  # decisions this module has in common with it


class OrphanedAnchor(BaseModel):
    decision_id: str
    locus: str


class ModuleConflict(BaseModel):
    decision_a: str
    decision_b: str
    severity: str
    explanation: str


class ModulePage(BaseModel):
    tile: MapTile
    paths: list[str]
    files: list[str]  # paths only; no source is rendered
    anchored_files: list[str]
    decisions: list[MapDecision]
    orphaned: list[OrphanedAnchor]
    conflicts: list[ModuleConflict]
    neighbours: list[Neighbour]
