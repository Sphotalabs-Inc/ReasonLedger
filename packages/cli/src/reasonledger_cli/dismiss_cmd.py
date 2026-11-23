"""`reasonledger dismiss` — record that a surfaced conflict is not a real conflict.

This is the only action that means "the detector was wrong here". It is kept
separate from `reject` (which drops a proposed *decision*) because conflating the
two makes the pilot's conflict-quality signal unreadable.
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.metrics import MetricEvent, emit
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.reasoning.dismissals import (
    DismissalError,
    add_dismissal,
    dismissed_fingerprints,
    pair_fingerprint,
    pair_key,
)

EXIT_PASS = 0
EXIT_USAGE = 2

_DECISION_ID_RE = re.compile(r"^dec_[a-z0-9]+$")


def _known_records(root: Path) -> dict[str, DecisionRecord]:
    """Records present in the ledger or staged as proposals, by id."""
    records = load_decisions_from_dir(root / DECISIONS_DIR)
    records += load_decisions_from_dir(root / PROPOSED_DIR)
    return {record.frontmatter.id: record for record in records}


def run_dismiss_cmd(
    *,
    root: Path,
    decision_a: str,
    decision_b: str,
    reason: str,
    dismissed_by: str | None,
) -> int:
    """Record a reviewer's verdict that a conflict hint is wrong."""
    for decision_id in (decision_a, decision_b):
        if not _DECISION_ID_RE.match(decision_id):
            print(f"error: invalid decision id: {decision_id!r}", file=sys.stderr)
            return EXIT_USAGE
    if decision_a == decision_b:
        print("error: a decision cannot conflict with itself", file=sys.stderr)
        return EXIT_USAGE

    # Dismissing an id that does not exist is almost always a typo, and a silent
    # typo here permanently suppresses nothing while looking like it worked.
    known = _known_records(root)
    unknown = sorted({decision_a, decision_b} - set(known))
    if unknown:
        print(f"error: unknown decision id(s): {', '.join(unknown)}", file=sys.stderr)
        return EXIT_USAGE

    # Captured before the write so the outcome message can tell a first verdict apart
    # from one replacing a dismissal the decisions have since drifted away from.
    was_dismissed = pair_key(decision_a, decision_b) in dismissed_fingerprints(root)

    try:
        entry, created = add_dismissal(
            root,
            decision_a=decision_a,
            decision_b=decision_b,
            reason=reason,
            dismissed_by=dismissed_by,
            dismissed_at=datetime.now(UTC),
            fingerprint=pair_fingerprint(known[decision_a], known[decision_b]),
        )
    except DismissalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if not created:
        print(f"already dismissed: {entry.pair} ({entry.reason})")
        return EXIT_PASS
    if was_dismissed:
        print("  replaces an earlier verdict the decisions have since drifted away from.")

    emit(root, MetricEvent.CONFLICT_DISMISSED, pair=pair_key(decision_a, decision_b))
    print(f"dismissed {entry.pair}")
    print("  reason: " + entry.reason)
    print("  commit .reasonledger/dismissed.yml so your team stops seeing this hint.")
    return EXIT_PASS
