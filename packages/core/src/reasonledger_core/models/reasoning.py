"""Phase 4 reasoning-memory domain types: embeddings, conflicts, watchers."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DecisionEmbedding(BaseModel):
    """A decision's embedding vector under a pinned/pluggable model."""

    decision_id: str
    model_id: str
    vector: list[float]


class SemanticHit(BaseModel):
    decision_id: str
    score: float


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConflictStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    # Dismissed once, then re-surfaced because a decision's context/choice changed
    # underneath the dismissal. Distinct from OPEN so a reviewer can see that this
    # pair was already judged — on different content — rather than re-litigating it.
    REOPENED = "reopened"


class Relation(StrEnum):
    """What is known about a shortlisted pair of decisions.

    Similarity only says two decisions share a topic. Whether they contradict each
    other takes a judge, so a pair nobody has judged is reported as exactly that.
    """

    CONFLICT = "conflict"  # judged: both answer the same question, and the answers clash
    COMPATIBLE = "compatible"  # judged: related, but both choices can hold at once
    UNVERIFIED = "unverified"  # similar context, no verdict yet


class ConflictVerdict(BaseModel):
    """Classifier output for a candidate pair (stub or replayed real model)."""

    is_conflict: bool
    severity: Severity
    explanation: str
    score: float
    judged_by: str | None = None  # the tool and model that gave the verdict; None until judged
    judged_at: datetime | None = None


class Conflict(BaseModel):
    decision_a: str
    decision_b: str
    severity: Severity
    explanation: str
    score: float
    status: ConflictStatus = ConflictStatus.OPEN
    relation: Relation = Relation.CONFLICT
    judged_by: str | None = None  # the tool and model that gave the verdict; None until judged
    judged_at: datetime | None = None


class ConflictDetail(BaseModel):
    """Conflict with full decision details for UI rendering."""

    decision_id: str
    context: str | None
    choice: str | None
    source_ref: str | None
    justifies: list[str]


class ConflictWithDetails(BaseModel):
    """Conflict pair with full details for interactive UI (S30)."""

    severity: Severity
    explanation: str
    score: float
    status: ConflictStatus = ConflictStatus.OPEN
    relation: Relation = Relation.CONFLICT
    judged_by: str | None = None  # the tool and model that gave the verdict; None until judged
    judged_at: datetime | None = None
    detail_a: ConflictDetail
    detail_b: ConflictDetail


class WatcherStatus(StrEnum):
    HEALTHY = "healthy"
    DRIFTING = "drifting"
    STALE = "stale"


class WatcherCondition(BaseModel):
    raw: str
    metric: str
    op: str
    threshold: float


class Watcher(BaseModel):
    decision_id: str
    condition: str
    metric: str
    status: WatcherStatus
    last_value: float | None = None


class WatcherEvent(BaseModel):
    decision_id: str
    condition: str
    value: float
    transition: str = Field(description="e.g. healthy->stale")


class PullRequestDraft(BaseModel):
    """A recorded (sandbox) PR intent — no live GitHub call in CI."""

    decision_id: str
    title: str
    branch: str
    body: str
    status_from: str
    status_to: str
    file_path: str
    new_markdown: str


class PullRequestRef(BaseModel):
    number: int
    url: str
    draft: PullRequestDraft
