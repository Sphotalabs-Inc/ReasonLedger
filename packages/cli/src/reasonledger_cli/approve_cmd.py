"""``reasonledger approve``: a person's verdict on a decision an agent left pending."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.decisions.service import ApproveError, approve_decision
from reasonledger_core.models.decision import DecisionOversight

from reasonledger_cli.identity import BY_HELP, acting_identity

EXIT_PASS = 0
EXIT_USAGE = 2
VERDICTS = tuple(v.value for v in DecisionOversight if v is not DecisionOversight.PENDING)


def add_approve_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    approve = sub.add_parser(
        "approve", help="Give a pending decision a human verdict (reviewed, modified or rejected)"
    )
    approve.add_argument("decision_id", help="Pending decision id, e.g. dec_1a2b3c")
    approve.add_argument("--as", dest="verdict", choices=VERDICTS, default="reviewed")
    approve.add_argument("--by", dest="approved_by", default=None, help=BY_HELP)
    approve.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Application repo root (default: cwd)"
    )


def run_approve_cmd(*, root: Path, decision_id: str, verdict: str, approved_by: str | None) -> int:
    who = acting_identity(root, approved_by)
    if who is None:
        return EXIT_USAGE
    try:
        record = approve_decision(
            decision_id,
            root=root,
            verdict=DecisionOversight(verdict),
            approved_by=who,
            approved_at=datetime.now(UTC),
        )
    except ApproveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    fm = record.frontmatter
    print(f"{fm.id}: {fm.oversight.value} by {fm.approved_by}")
    return EXIT_PASS
