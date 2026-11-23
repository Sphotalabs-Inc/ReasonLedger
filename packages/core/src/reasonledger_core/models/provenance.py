"""Provenance domain types."""

from enum import StrEnum

from pydantic import BaseModel, Field


class SignalConfidence(StrEnum):
    STRONG = "strong"
    WEAK = "weak"


class ProvenanceStatus(StrEnum):
    AI_ASSISTED = "ai_assisted"
    LIKELY_AI = "likely_ai"
    HUMAN = "human"
    UNKNOWN = "unknown"


class SignalType(StrEnum):
    COAUTHOR_TRAILER = "coauthor_trailer"
    BOT_AUTHOR = "bot_author"
    AGENT_PR_AUTHOR = "agent_pr_author"
    EXPLICIT_LABEL = "explicit_label"
    GENERATED_MARKER = "generated_marker"
    BRANCH_NAME = "branch_name"
    COMMIT_MESSAGE_PATTERN = "commit_message_pattern"


class ProvenanceFinding(BaseModel):
    signal_type: SignalType
    confidence: SignalConfidence
    evidence_pointer: str = Field(
        description="Commit SHA, trailer line, label name, or other reproducible pointer",
    )


class ChangeProvenanceInput(BaseModel):
    """Inputs available for deterministic provenance detection."""

    commit_sha: str | None = None
    commit_message: str | None = None
    commit_author_login: str | None = None
    commit_committer_login: str | None = None
    pr_author_login: str | None = None
    pr_labels: list[str] = Field(default_factory=list)
    branch_name: str | None = None
    diff_hunks: list[str] = Field(
        default_factory=list,
        description="Diff snippet lines only — used for generated-marker detection, never stored",
    )
