"""Oversight classification for AI-assisted changes."""

from reasonledger_core.models.oversight import ChangeOversightInput, OversightClassification


def classify_oversight(change: ChangeOversightInput) -> OversightClassification:
    if not change.is_ai_assisted:
        return OversightClassification.NOT_APPLICABLE

    if change.human_commits_after_ai:
        return OversightClassification.MODIFIED

    if _approving_reviewers(change):
        return OversightClassification.REVIEWED

    return OversightClassification.MERGED_UNREVIEWED


def _approving_reviewers(change: ChangeOversightInput) -> set[str]:
    authors = {login.lower() for login in change.author_logins}
    approved: set[str] = set()
    for review in change.reviews:
        if review.state.lower() != "approved":
            continue
        reviewer = review.reviewer_login.lower()
        if reviewer in authors:
            continue
        approved.add(reviewer)
    return approved
