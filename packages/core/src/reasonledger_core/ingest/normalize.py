"""Normalize recorded GitHub PR fixtures into domain inputs."""

from reasonledger_core.ingest.github_types import GitHubPullRequestFixture
from reasonledger_core.models.oversight import ChangeOversightInput, ReviewRecord
from reasonledger_core.models.provenance import ChangeProvenanceInput


def normalize_provenance_input(pr: GitHubPullRequestFixture) -> ChangeProvenanceInput:
    merge_commit = pr.commits[-1] if pr.commits else None
    commit_message = None
    commit_author_login = None
    commit_committer_login = None
    commit_sha = None

    if merge_commit is not None:
        commit_sha = merge_commit.sha
        commit_message = str(merge_commit.commit.get("message", ""))
        commit_author_login = merge_commit.author.login if merge_commit.author else None
        commit_committer_login = merge_commit.committer.login if merge_commit.committer else None

    diff_hunks: list[str] = []
    for file_entry in pr.files:
        patch = file_entry.get("patch")
        if patch:
            diff_hunks.extend(patch.splitlines())

    return ChangeProvenanceInput(
        commit_sha=commit_sha,
        commit_message=commit_message,
        commit_author_login=commit_author_login,
        commit_committer_login=commit_committer_login,
        pr_author_login=pr.user.login,
        pr_labels=[label.name for label in pr.labels],
        branch_name=pr.head.get("ref"),
        diff_hunks=diff_hunks,
    )


def normalize_oversight_input(
    pr: GitHubPullRequestFixture,
    *,
    is_ai_assisted: bool,
    human_commits_after_ai: bool = False,
) -> ChangeOversightInput:
    author_logins = {pr.user.login}
    for commit in pr.commits:
        if commit.author:
            author_logins.add(commit.author.login)

    reviews = [
        ReviewRecord(
            reviewer_login=review.user.login,
            state=review.state,
            submitted_at=review.submitted_at,
        )
        for review in pr.reviews
    ]

    return ChangeOversightInput(
        author_logins=sorted(author_logins),
        merged_by_login=pr.merged_by.login if pr.merged_by else None,
        reviews=reviews,
        human_commits_after_ai=human_commits_after_ai,
        is_ai_assisted=is_ai_assisted,
    )


def extract_changed_paths(pr: GitHubPullRequestFixture) -> list[str]:
    return [entry["filename"] for entry in pr.files if "filename" in entry]
