"""Phase 1 ingest classifier tests."""

import json
from pathlib import Path

import pytest
from reasonledger_core.ingest.classify import classify_merged_pr
from reasonledger_core.ingest.github_types import GitHubPullRequestFixture
from reasonledger_core.models.oversight import OversightClassification
from reasonledger_core.models.provenance import ProvenanceStatus

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "github" / "orgs" / "acme"
GLOBS = ["payments/**", "auth/**"]


def _load_pr(repo: str, number: int) -> GitHubPullRequestFixture:
    path = FIXTURE_ROOT / "repos" / repo / "pulls" / f"{number}.json"
    return GitHubPullRequestFixture.model_validate(json.loads(path.read_text("utf-8")))


@pytest.mark.phase_1
def test_classify_ai_reviewed_pr() -> None:
    classified = classify_merged_pr(_load_pr("payments-service", 42), critical_path_globs=GLOBS)
    assert classified.provenance_status == ProvenanceStatus.AI_ASSISTED
    assert classified.oversight_classification == OversightClassification.REVIEWED
    assert classified.is_critical_path is True
    assert classified.findings


@pytest.mark.phase_1
def test_classify_ai_self_merged_critical_path() -> None:
    classified = classify_merged_pr(_load_pr("payments-service", 17), critical_path_globs=GLOBS)
    assert classified.provenance_status == ProvenanceStatus.AI_ASSISTED
    assert classified.oversight_classification == OversightClassification.MERGED_UNREVIEWED
    assert classified.is_critical_path is True


@pytest.mark.phase_1
def test_classify_human_only_pr() -> None:
    classified = classify_merged_pr(_load_pr("docs-site", 3), critical_path_globs=GLOBS)
    assert classified.provenance_status == ProvenanceStatus.HUMAN
    assert classified.oversight_classification == OversightClassification.NOT_APPLICABLE
    assert classified.is_critical_path is False
    assert classified.findings == []
