"""PII linter for decision records: blocks common personal-data and key patterns at capture.

Pattern matching only (email, phone, SSN, card-like numbers, and the token shapes of the common
providers). It is a safety net for accidents, not a guarantee that free text holds no personal
data or secret: a secret with no recognisable shape, such as a bare AWS secret access key, passes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from reasonledger_core.models.decision import DecisionRecord

# Approver identity is the only allowed personal identifier (customer opt-in).
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# The user part of an SSH remote such as git@github.com:org/repo.git names a service, not a person.
SSH_REMOTE_USER = "git"
# A North American number written with separators or parentheses. Bare digit runs are left alone:
# in decision text they are far more often a timestamp or an id than a phone number. The area
# code and exchange cannot start with 0 or 1, which also rejects a grouped count like 512 000 0000.
PHONE_RE = re.compile(
    r"(?<![\w.])(?:\+?1[-.\s]?)?"
    r"(?:\([2-9]\d{2}\)\s?|[2-9]\d{2}[-.\s])"
    r"[2-9]\d{2}[-.\s]\d{4}(?!\w)"
)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
# One alternative per provider; each is anchored on a prefix the provider documents.
API_KEY_RE = re.compile(
    r"\b(?:"
    r"sk-[A-Za-z0-9_-]{20,}"  # OpenAI and Anthropic, including sk-ant-… and sk-proj-…
    r"|(?:AKIA|ASIA)[0-9A-Z]{16}"  # AWS access key id
    r"|gh[pousr]_[A-Za-z0-9]{36,}"  # GitHub classic tokens
    r"|github_pat_[A-Za-z0-9_]{22,}"  # GitHub fine-grained tokens
    r"|xox[abprs]-[A-Za-z0-9-]{10,}"  # Slack
    r"|[sr]k_live_[A-Za-z0-9]{16,}"  # Stripe live keys
    r"|AIza[A-Za-z0-9_-]{35}"  # Google API keys
    r"|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"  # JWT
    r")\b"
)
# A PEM private key block has no \b-friendly end, so it is matched on its header line.
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----")


@dataclass(frozen=True)
class PiiFinding:
    rule_id: str
    message: str
    snippet: str


class PiiLintError(ValueError):
    def __init__(self, message: str, findings: list[PiiFinding] | None = None) -> None:
        super().__init__(message)
        self.findings = findings or []


def _scan(text: str, pattern: re.Pattern[str], rule_id: str, label: str) -> list[PiiFinding]:
    findings: list[PiiFinding] = []
    for match in pattern.finditer(text):
        findings.append(
            PiiFinding(rule_id=rule_id, message=f"{label} detected", snippet=match.group(0))
        )
    return findings


def lint_text(text: str, *, allow_emails: set[str] | None = None) -> list[PiiFinding]:
    allowed = {email.lower() for email in (allow_emails or set())}
    findings: list[PiiFinding] = []
    for match in EMAIL_RE.finditer(text):
        email = match.group(0)
        if email.lower() in allowed or email.lower().startswith(f"{SSH_REMOTE_USER}@"):
            continue
        findings.append(
            PiiFinding(rule_id="email", message="email address detected", snippet=email)
        )
    findings.extend(_scan(text, PHONE_RE, "phone", "phone number"))
    findings.extend(_scan(text, SSN_RE, "ssn", "social security number"))
    # Credit-card heuristic: require separators or long digit runs with Luhn-ish length
    for match in CREDIT_CARD_RE.finditer(text):
        digits = re.sub(r"[^\d]", "", match.group(0))
        if 13 <= len(digits) <= 19 and (" " in match.group(0) or "-" in match.group(0)):
            findings.append(
                PiiFinding(
                    rule_id="credit_card",
                    message="credit card number detected",
                    snippet=match.group(0),
                )
            )
    findings.extend(_scan(text, API_KEY_RE, "api_key", "secret/API key"))
    findings.extend(_scan(text, PRIVATE_KEY_RE, "api_key", "private key"))
    return findings


def redact(snippet: str, *, keep: int = 4) -> str:
    """Message-safe form of a match: enough to locate, not enough to leak."""
    if len(snippet) <= keep:
        return "*" * len(snippet)
    return f"{snippet[:keep]}{'*' * (len(snippet) - keep)}"


def lint_decision_text(record: DecisionRecord) -> None:
    """Raise PiiLintError if the decision contains disallowed PII."""
    allowed: set[str] = set()
    named = (
        record.frontmatter.approved_by,
        record.frontmatter.retired_by,
        record.frontmatter.superseded_decided_by,
    )
    for name in named:
        if name:
            allowed.add(name)

    # Scan body and free-text frontmatter fields; approved_by itself is exempt.
    chunks = [
        record.body,
        record.frontmatter.context or "",
        record.frontmatter.choice or "",
        " ".join(record.frontmatter.alternatives_rejected),
        " ".join(record.frontmatter.assumptions),
        " ".join(record.frontmatter.justifies),
        record.frontmatter.model or "",
        record.frontmatter.confidence or "",
        record.frontmatter.retired_reason or "",
        record.frontmatter.superseded_reason or "",
    ]
    findings: list[PiiFinding] = []
    for chunk in chunks:
        findings.extend(lint_text(chunk, allow_emails=allowed))

    if findings:
        joined = "; ".join(f"{f.rule_id}:{redact(f.snippet)}" for f in findings)
        raise PiiLintError(f"PII lint failed: {joined}", findings=findings)
