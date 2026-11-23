"""Decision record domain types."""

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, model_validator

# A decision id becomes a file name under .reasonledger/decisions, so it is never free text: no
# separators or dots can name a path outside that folder. decision_filename enforces this; it is
# the one place an id becomes a path.
DECISION_ID_PATTERN = r"^dec_[a-z0-9_]{1,40}$"


class DecisionOversight(StrEnum):
    # Recorded by an agent, no human verdict yet. Every other value is a claim that a person
    # looked, so an agent that cannot honestly make that claim needs a value that does not.
    PENDING = "pending"
    REVIEWED = "reviewed"
    MODIFIED = "modified"
    REJECTED = "rejected"


class DecisionProposer(StrEnum):
    """Whose idea the choice was: a person directed or explicitly accepted it, or an agent made it.

    ``oversight`` says whether a person later reviewed the record; this says who originated the
    choice. A human-proposed decision a person has not yet looked at, and an AI-proposed one
    they signed off afterwards, both read ``reviewed`` there and are very different evidence.
    """

    HUMAN = "human"
    AI = "ai"


class AiTool(StrEnum):
    """Well-known tool names. ``ai_tool`` itself is free-form so new agents need no release."""

    CLAUDE_CODE = "claude-code"
    CURSOR = "cursor"
    COPILOT = "copilot"
    NONE = "none"
    OTHER = "other"


# Spellings agents actually send (our own CLAUDE.md says ``claude``) folded onto the canonical
# name, so one tool does not fragment into several values in the ledger.
_AI_TOOL_ALIASES = {"claude": AiTool.CLAUDE_CODE.value, "claudecode": AiTool.CLAUDE_CODE.value}
_SEPARATORS = re.compile(r"[\s_]+")


def normalize_ai_tool(value: object) -> str:
    """Lowercase, hyphenate and alias an ``ai_tool`` name; empty names are rejected."""
    name = _SEPARATORS.sub("-", str(value).strip().lower())
    if not name:
        raise ValueError("ai_tool must name the tool, e.g. 'claude-code', 'cursor' or 'grok'")
    return _AI_TOOL_ALIASES.get(name, name)


AiToolName = Annotated[str, BeforeValidator(normalize_ai_tool)]


class DecisionStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    SUPERSEDED = "superseded"
    # Taken out of force by a person with no replacement; the record and its verdict stay.
    RETIRED = "retired"
    # Import lifecycle (P0-4): extracted candidates await human confirmation
    # before they enter the ledger as active records.
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"


# No longer guidance: kept as history, left out of conflicts, coverage and live counts.
OUT_OF_FORCE = frozenset({DecisionStatus.SUPERSEDED, DecisionStatus.RETIRED})


class DecisionSource(StrEnum):
    """How a decision record originated."""

    RECORDED = "recorded"  # via record_decision (MCP / manual)
    HARVESTED = "harvested"  # from a merged PR (P0-1)
    DOC_IMPORT = "doc-import"  # extracted from existing docs (P0-4)
    COMMIT_IMPORT = "commit-import"  # extracted from a commit message during catch-up


class DecisionFrontmatter(BaseModel):
    id: str = Field(description="Stable decision id, e.g. dec_8f3k2x")
    ai_tool: AiToolName
    model: str | None = None
    oversight: DecisionOversight
    status: DecisionStatus = Field(
        default=DecisionStatus.ACTIVE,
        description="Lifecycle status; watchers flip active->stale on assumption breach",
    )
    proposed_by: DecisionProposer | None = Field(
        default=None,
        description=(
            "human: a person stated or explicitly accepted the choice before it was made. "
            "ai: an agent chose it. Unset on records that predate the field or whose origin "
            "is not known, e.g. doc imports."
        ),
    )
    approved_by: str | None = Field(
        default=None,
        description="Approver identity the customer opts into (allowed PII exception)",
    )
    approved_at: datetime | None = Field(
        default=None,
        description="When the human verdict was given",
    )
    recorded_at: datetime | None = Field(
        default=None,
        description="Machine event: when the record was written (NOT when decided)",
    )
    justifies: list[str] = Field(
        default_factory=list,
        description="Code loci this decision justifies, e.g. payments/retry.py:40-72",
    )
    anchor_hashes: dict[str, str] | None = Field(
        default=None,
        description=(
            "Locus -> truncated hash of the lines it pointed at when recorded, so `why` can "
            "find the code again after it moves. Never source text. Unset on older records."
        ),
    )
    watchers: list[str] = Field(
        default_factory=list,
        description="Assumption conditions to monitor, e.g. 'postgres_version >= 15'",
    )
    confidence: str | None = None
    context: str | None = None
    choice: str | None = None
    alternatives_rejected: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    # --- Provenance (P0-4 doc import). All optional so recorded/harvested
    # records and pre-import golden files round-trip unchanged (exclude_none). ---
    source: DecisionSource | None = Field(
        default=None,
        description="How this record originated (recorded / harvested / doc- or commit-import)",
    )
    source_ref: str | None = Field(
        default=None,
        description="For imports: doc path (+ heading/anchor or line range) extracted from",
    )
    extracted_by: str | None = Field(
        default=None,
        description="For imports: provider/model id that extracted this record",
    )
    extracted_at: datetime | None = Field(
        default=None,
        description="Machine event: when the record was extracted (NOT when decided)",
    )
    confirmed_by: str | None = Field(
        default=None,
        description="Human who confirmed a proposed/imported record",
    )
    confirmed_at: datetime | None = Field(
        default=None,
        description="When a human confirmed the record",
    )
    decided_at: datetime | None = Field(
        default=None,
        description="Original decision date; best-effort. MUST NOT default to now.",
    )
    supersedes: str | None = Field(
        default=None,
        description=(
            "Id of the confirmed decision this record replaces. Both records are kept: "
            "the old one moves to status 'superseded' rather than being rewritten, so "
            "the evidence trail shows what was believed and when it changed."
        ),
    )
    retired_by: str | None = Field(
        default=None,
        description="Who took the decision out of force (same PII exception as approved_by)",
    )
    retired_at: datetime | None = None
    retired_reason: str | None = Field(
        default=None,
        description="Why it no longer applies; required to retire, so the trail explains itself",
    )
    # --- A person chose between two decisions already in the ledger. Written on the one that
    # lost, so the one that stands (and any approval it carries) is never rewritten. ---
    superseded_by: str | None = Field(
        default=None,
        description="Id of the ledger decision a person chose to stand in this one's place",
    )
    superseded_decided_by: str | None = Field(
        default=None,
        description="Who made that choice (same PII exception as approved_by)",
    )
    superseded_at: datetime | None = None
    superseded_reason: str | None = Field(
        default=None,
        description="Why the other decision stands; required, so the trail explains itself",
    )


class DecisionRecord(BaseModel):
    frontmatter: DecisionFrontmatter
    body: str = ""


class RecordDecisionInput(BaseModel):
    """Inputs for MCP record_decision (deterministic agent-supplied fields)."""

    context: str
    choice: str
    alternatives_rejected: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    confidence: str | None = None
    ai_tool: AiToolName
    model: str | None = Field(
        default=None,
        description="Exact model id, e.g. claude-sonnet-4-5; required unless ai_tool is none",
    )
    oversight: DecisionOversight | None = Field(
        default=None,
        description="Human verdict; omitted means reviewed if approved_by is set, else pending",
    )
    proposed_by: DecisionProposer | None = Field(
        default=None,
        description="human only if the user stated or explicitly accepted the choice in chat",
    )
    approved_by: str | None = None
    justifies: list[str] = Field(default_factory=list)
    watchers: list[str] = Field(default_factory=list)
    body: str | None = None
    decision_id: str | None = None
    supersedes: str | None = Field(
        default=None,
        description="Id of the ledger decision this one replaces, once a person approves this one",
    )

    @model_validator(mode="after")
    def _require_model_for_ai_tool(self) -> "RecordDecisionInput":
        """Which model produced a choice is audit evidence; only a human-made record may omit it."""
        self.model = (self.model or "").strip() or None
        self.approved_by = (self.approved_by or "").strip() or None
        if self.ai_tool != AiTool.NONE and self.model is None:
            raise ValueError(
                f"model is required when ai_tool is '{self.ai_tool}': pass the exact model id "
                "(e.g. 'claude-sonnet-4-5'), or ai_tool='none' for a human-made decision"
            )
        return self

    @property
    def resolved_oversight(self) -> DecisionOversight:
        """Explicit verdict, else reviewed only when someone put their name to it."""
        if self.oversight is not None:
            return self.oversight
        return DecisionOversight.REVIEWED if self.approved_by else DecisionOversight.PENDING


class QueryDecisionsInput(BaseModel):
    query: str
    paths: list[str] = Field(default_factory=list)
