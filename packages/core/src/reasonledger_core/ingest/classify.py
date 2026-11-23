"""Classify a merged PR fixture into a persistence-ready change record."""

from pydantic import BaseModel, Field
from reasonledger_core.ingest.contributors import contributor_kind
from reasonledger_core.ingest.github_types import GitHubPullRequestFixture
from reasonledger_core.ingest.normalize import (
    extract_changed_paths,
    normalize_oversight_input,
    normalize_provenance_input,
)
from reasonledger_core.models.oversight import OversightClassification
from reasonledger_core.models.provenance import ProvenanceFinding, ProvenanceStatus
from reasonledger_core.oversight.classify import classify_oversight
from reasonledger_core.paths.critical import matches_critical_path
from reasonledger_core.provenance.classify import classify_provenance


class ContributorRef(BaseModel):
    login: str
    kind: str


class ClassifiedChange(BaseModel):
    github_pr_number: int
    merged_at: str
    changed_paths: list[str] = Field(default_factory=list)
    provenance_status: ProvenanceStatus
    oversight_classification: OversightClassification
    is_critical_path: bool
    findings: list[ProvenanceFinding]
    contributors: list[ContributorRef]


def classify_merged_pr(
    pr: GitHubPullRequestFixture,
    *,
    critical_path_globs: list[str],
    human_commits_after_ai: bool = False,
) -> ClassifiedChange:
    provenance_input = normalize_provenance_input(pr)
    provenance_status, findings = classify_provenance(provenance_input)
    is_ai_assisted = provenance_status in {
        ProvenanceStatus.AI_ASSISTED,
        ProvenanceStatus.LIKELY_AI,
    }

    oversight_input = normalize_oversight_input(
        pr,
        is_ai_assisted=is_ai_assisted,
        human_commits_after_ai=human_commits_after_ai,
    )
    oversight = classify_oversight(oversight_input)
    changed_paths = extract_changed_paths(pr)

    logins = {pr.user.login}
    if pr.merged_by:
        logins.add(pr.merged_by.login)
    for review in pr.reviews:
        logins.add(review.user.login)
    for commit in pr.commits:
        if commit.author:
            logins.add(commit.author.login)

    return ClassifiedChange(
        github_pr_number=pr.number,
        merged_at=pr.merged_at,
        changed_paths=changed_paths,
        provenance_status=provenance_status,
        oversight_classification=oversight,
        is_critical_path=matches_critical_path(changed_paths, critical_path_globs),
        findings=findings,
        contributors=[
            ContributorRef(login=login, kind=contributor_kind(login)) for login in sorted(logins)
        ],
    )
