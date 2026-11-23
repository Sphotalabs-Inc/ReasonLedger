"""S49 — a policy gate never silently ignores a condition."""

from __future__ import annotations

import pytest
from reasonledger_core.policy.parse import PolicyParseError, parse_policy_yaml

CASES = [
    ("top", 'version: "1"\nrules: []\nstrict: true\n', "unknown key 'strict' in the policy"),
    (
        "rule",
        "rules:\n  - id: r1\n    severity: high\n",
        "unknown key 'severity' in rule 'r1'; allowed: id, on_violation, require, when",
    ),
    (
        "when",
        "rules:\n  - id: r1\n    when:\n      ai_assisted: true\n",
        "unknown key 'ai_assisted' in 'when' of rule 'r1'; allowed: paths, provenance",
    ),
    (
        "require",
        "rules:\n  - id: r1\n    require:\n      reviewers: 2\n",
        "unknown key 'reviewers' in 'require' of rule 'r1'; "
        "allowed: approver, approver_not, oversight",
    ),
]


@pytest.mark.phase_2
@pytest.mark.parametrize(("name", "raw", "message"), CASES, ids=[c[0] for c in CASES])
def test_policy_unknown_key_rejected(name: str, raw: str, message: str) -> None:
    with pytest.raises(PolicyParseError) as caught:
        parse_policy_yaml(raw)
    assert message in str(caught.value)


@pytest.mark.phase_2
def test_policy_init_stub_loads() -> None:
    from reasonledger_cli.init_cmd import POLICY_STUB

    assert len(parse_policy_yaml(POLICY_STUB).rules) == 2
