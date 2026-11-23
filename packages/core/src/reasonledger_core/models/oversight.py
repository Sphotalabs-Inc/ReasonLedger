"""Oversight domain types."""

from enum import StrEnum

from pydantic import BaseModel, Field


class OversightClassification(StrEnum):
    REVIEWED = "reviewed"
    MODIFIED = "modified"
    MERGED_UNREVIEWED = "merged_unreviewed"
    NOT_APPLICABLE = "n/a"


class ReviewRecord(BaseModel):
    reviewer_login: str
    state: str
    submitted_at: str | None = None


class ChangeOversightInput(BaseModel):
    """Inputs for oversight classification of a merged change."""

    author_logins: list[str] = Field(default_factory=list)
    merged_by_login: str | None = None
    reviews: list[ReviewRecord] = Field(default_factory=list)
    required_codeowner_reviews: list[str] = Field(default_factory=list)
    human_commits_after_ai: bool = False
    is_ai_assisted: bool = False
