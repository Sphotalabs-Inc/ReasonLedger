"""GitHub fixture shapes for recorded ingest (subset of GitHub REST API)."""

from pydantic import BaseModel, Field


class GitHubUser(BaseModel):
    login: str


class GitHubLabel(BaseModel):
    name: str


class GitHubReview(BaseModel):
    user: GitHubUser
    state: str
    submitted_at: str | None = None


class GitHubCommit(BaseModel):
    sha: str
    commit: dict[str, object]
    author: GitHubUser | None = None
    committer: GitHubUser | None = None


class GitHubPullRequestFixture(BaseModel):
    """Recorded merged pull request fixture."""

    number: int
    state: str
    merged: bool = True
    merged_at: str
    title: str
    user: GitHubUser
    merged_by: GitHubUser | None = None
    head: dict[str, str] = Field(default_factory=dict)
    labels: list[GitHubLabel] = Field(default_factory=list)
    reviews: list[GitHubReview] = Field(default_factory=list)
    commits: list[GitHubCommit] = Field(default_factory=list)
    files: list[dict[str, str]] = Field(default_factory=list)


class FixtureRepository(BaseModel):
    name: str
    default_branch: str
    pulls: list[int]


class FixtureOrgManifest(BaseModel):
    org_slug: str
    org_name: str
    critical_path_globs: list[str] = Field(default_factory=list)
    repositories: list[FixtureRepository]
