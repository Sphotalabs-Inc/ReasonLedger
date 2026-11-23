"""Module-detection data model: candidates from signals, modules in the manifest."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SignalKind(StrEnum):
    DECLARED = "declared"
    WORKSPACE = "workspace"
    SPECS = "specs"
    CONVENTION = "convention"
    CODEOWNERS = "codeowners"
    LAYOUT = "layout"
    COCHANGE = "cochange"
    TOOLING = "tooling"


# Which single signals are trusted alone; the rest need a second signal to agree.
SINGLE_SIGNAL_MEDIUM: frozenset[SignalKind] = frozenset(
    {
        SignalKind.DECLARED,
        SignalKind.WORKSPACE,
        SignalKind.SPECS,
        SignalKind.CONVENTION,
        SignalKind.CODEOWNERS,
    }
)
# Order for tie-breaks and for naming: stronger first.
SIGNAL_PRIORITY: tuple[SignalKind, ...] = (
    SignalKind.DECLARED,
    SignalKind.WORKSPACE,
    SignalKind.SPECS,
    SignalKind.CONVENTION,
    SignalKind.CODEOWNERS,
    SignalKind.COCHANGE,
    SignalKind.LAYOUT,
    SignalKind.TOOLING,
)


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ModuleKind(StrEnum):
    FEATURE = "feature"
    FOUNDATION = "foundation"
    BUCKET = "bucket"  # files no capability owns, grouped by the architecture


class Tier(StrEnum):
    BACKEND = "backend"
    FRONTEND = "frontend"


class ModuleStatus(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class Candidate:
    """One signal's claim that a set of files forms a module."""

    name: str
    signal: SignalKind
    files: frozenset[str]
    id_hint: str | None = None
    description: str = ""
    extras: tuple[str, ...] = field(default=())
    vendored: bool = False  # looks like someone else's project copied in


class Module(BaseModel):
    """A module as stored in ``.reasonledger/modules.yml``."""

    id: str
    name: str
    description: str = ""
    paths: list[str]
    kind: ModuleKind = ModuleKind.FEATURE
    tier: Tier | None = None  # set by code from the paths, in a repo with separate frontend/backend
    color: str | None = None
    status: ModuleStatus = ModuleStatus.PROPOSED
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence | None = None


class RejectedModule(BaseModel):
    """A proposal a person rejected; it stays down unless its paths drift."""

    fingerprint: str
    paths: list[str]
    reason: str = ""


class Suggestion(BaseModel):
    """New files a mapper would add to an existing module; a person accepts or rejects it."""

    module: str
    paths: list[str]
    reason: str = ""
    by: str = ""


class DecisionPlacement(BaseModel):
    """A person's placement of a decision that has no usable anchor."""

    modules: list[str]
    by: str
    at: datetime


class Manifest(BaseModel):
    version: str = "1"
    mapped_at_commit: str | None = None  # where the map was last brought up to date
    mapped_by: str | None = None  # the model or agent that proposed it (self-reported)
    hints: list[str] = Field(default_factory=list)  # modules the owner expects, for the mapper
    modules: list[Module] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)
    rejected: list[RejectedModule] = Field(default_factory=list)
    # A person's placement of files: path or glob -> module or bucket id. It outranks every
    # module glob and survives re-mapping.
    labels: dict[str, str] = Field(default_factory=dict)
    # Placements a person turned down: file -> module ids it is not to be suggested for again.
    declined: dict[str, list[str]] = Field(default_factory=dict)
    # Where a person put decisions that have no anchor, or only broken ones: decision id -> modules.
    # Applies only while the decision stays that way; an anchor that works places it instead.
    placements: dict[str, DecisionPlacement] = Field(default_factory=dict)

    @property
    def capabilities(self) -> list[Module]:
        """The modules proper; buckets hold what no capability owns."""
        return [m for m in self.modules if m.kind is not ModuleKind.BUCKET]


class ScanResult(BaseModel):
    """What a scan found. Never written to disk as is; the manifest is."""

    modules: list[Module]
    files_total: int
    files_per_module: dict[str, int]
    unplaced_files: int
    support_files: int = 0  # tests, docs, examples: outside any module by design
    commits_scanned: int
    limitations: list[str]
    seconds: float
