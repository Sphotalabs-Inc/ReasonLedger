"""``reasonledger retire``: take a decision that no longer applies out of force."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.decisions.lifecycle import RetireError, retire_decision
from reasonledger_core.privacy.pii_linter import PiiLintError

from reasonledger_cli.approve_cmd import EXIT_PASS, EXIT_USAGE
from reasonledger_cli.identity import BY_HELP, acting_identity


def add_retire_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    retire = sub.add_parser(
        "retire", help="Mark a decision retired: kept as history, no longer guidance"
    )
    retire.add_argument("decision_id", help="Ledger decision id, e.g. dec_1a2b3c")
    retire.add_argument("--reason", required=True, help="Why it no longer applies (recorded)")
    retire.add_argument("--by", dest="retired_by", default=None, help=BY_HELP)
    retire.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Application repo root (default: cwd)"
    )


def run_retire_cmd(*, root: Path, decision_id: str, reason: str, retired_by: str | None) -> int:
    who = acting_identity(root, retired_by)
    if who is None:
        return EXIT_USAGE
    try:
        record = retire_decision(
            decision_id, root=root, retired_by=who, retired_at=datetime.now(UTC), reason=reason
        )
    except (RetireError, PiiLintError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    fm = record.frontmatter
    print(f"{fm.id}: retired by {fm.retired_by} ({fm.retired_reason})")
    return EXIT_PASS
