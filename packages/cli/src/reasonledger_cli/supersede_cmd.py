"""``reasonledger supersede``: settle two decisions that clash by choosing the one that stands."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.decisions.lifecycle import RetireError, supersede_decision
from reasonledger_core.privacy.pii_linter import PiiLintError

from reasonledger_cli.approve_cmd import EXIT_PASS, EXIT_USAGE
from reasonledger_cli.identity import BY_HELP, acting_identity


def add_supersede_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    supersede = sub.add_parser(
        "supersede",
        help="Mark a decision superseded by another in the ledger: kept as history",
    )
    supersede.add_argument("decision_id", help="The decision that no longer stands")
    supersede.add_argument(
        "--successor", required=True, help="Id of the decision that stands in its place"
    )
    supersede.add_argument("--reason", required=True, help="Why the successor stands (recorded)")
    supersede.add_argument("--by", dest="decided_by", default=None, help=BY_HELP)
    supersede.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Application repo root (default: cwd)"
    )


def run_supersede_cmd(
    *, root: Path, decision_id: str, successor_id: str, reason: str, decided_by: str | None
) -> int:
    who = acting_identity(root, decided_by)
    if who is None:
        return EXIT_USAGE
    try:
        record = supersede_decision(
            decision_id,
            successor_id=successor_id,
            root=root,
            decided_by=who,
            superseded_at=datetime.now(UTC),
            reason=reason,
        )
    except (RetireError, PiiLintError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    fm = record.frontmatter
    print(
        f"{fm.id}: superseded by {fm.superseded_by}, "
        f"chosen by {fm.superseded_decided_by} ({fm.superseded_reason})"
    )
    return EXIT_PASS
