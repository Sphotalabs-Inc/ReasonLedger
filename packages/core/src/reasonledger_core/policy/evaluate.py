"""Deterministic policy rule evaluation against a change context."""

from __future__ import annotations

import fnmatch

from reasonledger_core.models.policy import (
    ChangePolicyContext,
    CheckOutcome,
    PolicyDocument,
    PolicyEvaluationResult,
    PolicyRequire,
    PolicyRule,
    PolicyWhen,
    RuleEvaluation,
    RuleOutcome,
    ViolationAction,
)


def _paths_match(changed_paths: list[str], patterns: list[str]) -> bool:
    if not patterns:
        return True
    if not changed_paths:
        return False
    for path in changed_paths:
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
    return False


def rule_matches(when: PolicyWhen, change: ChangePolicyContext) -> bool:
    if when.provenance is not None and change.provenance != when.provenance:
        return False
    return not (when.paths and not _paths_match(change.changed_paths, when.paths))


def _check_oversight(require: PolicyRequire, change: ChangePolicyContext) -> str | None:
    if require.oversight is None:
        return None
    if change.oversight != require.oversight:
        return f"required oversight={require.oversight.value}, got={change.oversight.value}"
    return None


def _check_approver_codeowner(require: PolicyRequire, change: ChangePolicyContext) -> str | None:
    if require.approver != "codeowner":
        return None
    if not change.codeowner_logins:
        return "required codeowner approval, but no codeowners configured"
    approved = set(login.lower() for login in change.approver_logins)
    owners = set(login.lower() for login in change.codeowner_logins)
    if approved.isdisjoint(owners):
        return "required approval from a codeowner; none of the approvers are codeowners"
    return None


def _check_approver_not_author(require: PolicyRequire, change: ChangePolicyContext) -> str | None:
    if require.approver_not != "author":
        return None
    author = change.author_login.lower()
    if not change.approver_logins:
        return "required non-author approver, but no approvers present"
    if all(login.lower() == author for login in change.approver_logins):
        return "required approver_not=author; only the author approved"
    return None


def _requirement_failures(require: PolicyRequire, change: ChangePolicyContext) -> list[str]:
    failures: list[str] = []
    for checker in (_check_oversight, _check_approver_codeowner, _check_approver_not_author):
        message = checker(require, change)
        if message is not None:
            failures.append(message)
    return failures


def evaluate_rule(rule: PolicyRule, change: ChangePolicyContext) -> RuleEvaluation:
    if not rule_matches(rule.when, change):
        return RuleEvaluation(
            rule_id=rule.id,
            matched=False,
            result=RuleOutcome.SKIPPED,
            explanation="rule did not match change context",
        )
    failures = _requirement_failures(rule.require, change)
    if not failures:
        return RuleEvaluation(
            rule_id=rule.id,
            matched=True,
            result=RuleOutcome.PASS,
            explanation="all requirements satisfied",
        )
    outcome = RuleOutcome.FAIL if rule.on_violation == ViolationAction.FAIL else RuleOutcome.WARN
    return RuleEvaluation(
        rule_id=rule.id,
        matched=True,
        result=outcome,
        explanation="; ".join(failures),
    )


def _aggregate(results: list[RuleEvaluation]) -> CheckOutcome:
    outcomes = {r.result for r in results if r.result != RuleOutcome.SKIPPED}
    if RuleOutcome.FAIL in outcomes:
        return CheckOutcome.FAIL
    if RuleOutcome.WARN in outcomes:
        return CheckOutcome.WARN
    return CheckOutcome.PASS


def evaluate_policy(
    policy: PolicyDocument,
    change: ChangePolicyContext,
) -> PolicyEvaluationResult:
    rules = [evaluate_rule(rule, change) for rule in policy.rules]
    return PolicyEvaluationResult(overall=_aggregate(rules), rules=rules)
