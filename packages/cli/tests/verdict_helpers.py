"""Test helper: commit a verdict the way `reasonledger judge` writes one."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.models.reasoning import Severity
from reasonledger_core.reasoning.dismissals import pair_fingerprint, pair_key
from reasonledger_core.reasoning.verdicts import StoredVerdict, load_verdicts, write_verdicts

JUDGED_AT = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)


def commit_verdict(
    root: Path,
    decision_a: str,
    decision_b: str,
    *,
    conflict: bool = True,
    severity: Severity = Severity.HIGH,
) -> None:
    records = load_decisions_from_dir(root / DECISIONS_DIR) + load_decisions_from_dir(
        root / PROPOSED_DIR
    )
    by_id = {record.frontmatter.id: record for record in records}
    verdicts = load_verdicts(root)
    verdicts[pair_key(decision_a, decision_b)] = StoredVerdict(
        same_question=True,
        compatible=not conflict,
        question="Which timezone are timestamps stored in?",
        reason="The two decisions pick different zones for the same storage.",
        severity=severity,
        decision_a=decision_a,
        decision_b=decision_b,
        fingerprint=pair_fingerprint(by_id[decision_a], by_id[decision_b]),
        model="test-judge",
        judged_at=JUDGED_AT,
    )
    write_verdicts(root, verdicts)
