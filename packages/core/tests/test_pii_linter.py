"""Phase 3 PII linter — 100% coverage on seeded rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.privacy.pii_linter import PiiLintError, lint_decision_text, lint_text

CASES = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "pii" / "seeded_cases.json"


@pytest.mark.phase_3
def test_pii_linter_seeded_cases() -> None:
    payload = json.loads(CASES.read_text("utf-8"))
    for case in payload["cases"]:
        findings = lint_text(
            case["text"],
            allow_emails=set(case.get("allow_emails", [])),
        )
        got = sorted({f.rule_id for f in findings})
        assert got == sorted(case["expect_rule_ids"]), case["id"]


@pytest.mark.phase_3
def test_decision_lint_blocks_email_in_body_allows_approver() -> None:
    clean = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id="dec_ok0001",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            approved_by="alice@acme.com",
            choice="Safe choice",
            context="Safe context",
        ),
        body="No personal data here.",
    )
    lint_decision_text(clean)

    dirty = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id="dec_bad001",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            approved_by="alice@acme.com",
            choice="Leaky",
            context="Context",
        ),
        body="Ping bob@evil.example for secrets",
    )
    with pytest.raises(PiiLintError) as exc:
        lint_decision_text(dirty)
    assert any(f.rule_id == "email" for f in exc.value.findings)


@pytest.mark.phase_3
def test_pii_error_message_redacts_snippet() -> None:
    from reasonledger_core.privacy.pii_linter import redact

    secret = "sk-ABCDEFGHIJKLMNOPQRSTUVWX"
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id="dec_pii001",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            choice="Use vault",
            context="Secrets handling",
        ),
        body=f"Do not commit {secret}",
    )
    with pytest.raises(PiiLintError) as exc:
        lint_decision_text(record)
    assert secret not in str(exc.value)
    assert secret in exc.value.findings[0].snippet
    assert redact(secret) in str(exc.value)


@pytest.mark.phase_3
def test_redact_keeps_prefix() -> None:
    from reasonledger_core.privacy.pii_linter import redact

    assert redact("sk-abcdef") == "sk-a*****"


@pytest.mark.phase_3
def test_decision_lint_without_approver() -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id="dec_noapr1",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.MODIFIED,
            choice="Safe",
            context="Safe",
        ),
        body="Clean technical rationale only.",
    )
    lint_decision_text(record)
