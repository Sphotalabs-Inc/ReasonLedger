"""Phase 2 policy engine golden tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_core.models.oversight import OversightClassification
from reasonledger_core.models.policy import ChangePolicyContext
from reasonledger_core.models.provenance import ProvenanceStatus
from reasonledger_core.policy import evaluate_policy, parse_policy_yaml

FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "policy"
POLICY_PATH = FIXTURE_ROOT / "sample_policy.yml"
CASES_PATH = FIXTURE_ROOT / "evaluation_cases.json"


@pytest.mark.phase_2
def test_policy_evaluation_golden_cases() -> None:
    policy = parse_policy_yaml(POLICY_PATH.read_text("utf-8"))
    cases = json.loads(CASES_PATH.read_text("utf-8"))["cases"]

    for case in cases:
        change = ChangePolicyContext.model_validate(case["change"])
        result = evaluate_policy(policy, change)
        assert result.overall.value == case["expected_overall"], case["id"]
        by_id = {rule.rule_id: rule.result.value for rule in result.rules}
        assert by_id == case["expected_rules"], case["id"]


@pytest.mark.phase_2
def test_policy_parse_rejects_invalid_root() -> None:
    from reasonledger_core.policy import PolicyParseError

    with pytest.raises(PolicyParseError):
        parse_policy_yaml("- just a list")


@pytest.mark.phase_2
def test_default_on_violation_is_warn() -> None:
    policy = parse_policy_yaml(
        """
rules:
  - id: soft-rule
    when: { provenance: ai_assisted }
    require: { oversight: reviewed }
"""
    )
    assert policy.rules[0].on_violation.value == "warn"
    change = ChangePolicyContext(
        provenance=ProvenanceStatus("ai_assisted"),
        oversight=OversightClassification("merged_unreviewed"),
        changed_paths=["x.py"],
        author_login="a",
    )
    result = evaluate_policy(policy, change)
    assert result.overall.value == "warn"


@pytest.mark.phase_2
def test_empty_policy_yaml_and_path_edge_cases() -> None:
    assert parse_policy_yaml("").rules == []
    assert parse_policy_yaml("null").rules == []

    # Paths required but change has no paths → no match on path filter via when.paths
    policy = parse_policy_yaml(
        """
rules:
  - id: needs-path
    when: { provenance: ai_assisted, paths: ["payments/**"] }
    require: { oversight: reviewed }
    on_violation: fail
"""
    )
    change = ChangePolicyContext(
        provenance=ProvenanceStatus("ai_assisted"),
        oversight=OversightClassification("reviewed"),
        changed_paths=[],
        author_login="a",
    )
    result = evaluate_policy(policy, change)
    assert result.rules[0].result.value == "skipped"


@pytest.mark.phase_2
def test_rule_with_no_requirements_passes() -> None:
    policy = parse_policy_yaml(
        """
rules:
  - id: match-only
    when: { provenance: human }
"""
    )
    change = ChangePolicyContext(
        provenance=ProvenanceStatus("human"),
        oversight=OversightClassification("n/a"),
        changed_paths=["a.py"],
        author_login="a",
    )
    result = evaluate_policy(policy, change)
    assert result.overall.value == "pass"
    assert result.rules[0].result.value == "pass"


@pytest.mark.phase_2
def test_parse_invalid_yaml_and_missing_file(tmp_path: Path) -> None:
    from reasonledger_core.policy import PolicyParseError, load_policy_file

    with pytest.raises(PolicyParseError):
        parse_policy_yaml("rules: [")
    with pytest.raises(PolicyParseError):
        parse_policy_yaml("rules:\n  - id: 1\n    when: { provenance: not_a_status }")
    with pytest.raises(PolicyParseError):
        load_policy_file(tmp_path / "missing.yml")


@pytest.mark.phase_2
def test_codeowner_required_but_none_configured() -> None:
    policy = parse_policy_yaml(
        """
rules:
  - id: needs-owner
    when: { provenance: ai_assisted }
    require: { approver: codeowner }
    on_violation: fail
"""
    )
    change = ChangePolicyContext(
        provenance=ProvenanceStatus("ai_assisted"),
        oversight=OversightClassification("reviewed"),
        changed_paths=["a.py"],
        author_login="alice",
        approver_logins=["bob"],
        codeowner_logins=[],
    )
    result = evaluate_policy(policy, change)
    assert result.overall.value == "fail"
    assert "no codeowners configured" in result.rules[0].explanation


@pytest.mark.phase_2
def test_paths_match_empty_patterns() -> None:
    from reasonledger_core.policy.evaluate import _paths_match

    assert _paths_match(["a.py"], []) is True
    assert _paths_match([], ["payments/**"]) is False
