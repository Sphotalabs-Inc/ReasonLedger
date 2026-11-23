"""Policy evaluation command implementation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reasonledger_core.models.policy import ChangePolicyContext, CheckOutcome
from reasonledger_core.policy import (
    DEFAULT_POLICY_PATH,
    PolicyParseError,
    evaluate_policy,
    load_policy_file,
)

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def add_check_arguments(parser: argparse.ArgumentParser) -> None:
    """Configure the policy and decision-ledger check modes."""
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY_PATH,
        help="Path to policy.yml (default: .reasonledger/policy.yml)",
    )
    parser.add_argument("--change", type=Path, default=None, help="JSON change context for policy")
    parser.add_argument(
        "--decisions",
        action="store_true",
        help="Check the decision ledger for conflicts instead of policy.yml",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Decision ledger repo root (default: cwd)",
    )
    parser.add_argument("--base", default=None, metavar="REF", help="Git ref to diff against")
    parser.add_argument(
        "--min-severity",
        choices=["low", "medium", "high"],
        default="high",
        help="Minimum conflict severity that fails (default: high)",
    )
    parser.add_argument(
        "--strict-identity",
        action="store_true",
        help="With --decisions --base: fail (not just warn) when a verdict's recorded name "
        "differs from the author of the commit that added it",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")


def run_check(*, policy_path: Path, change_path: Path, as_json: bool) -> int:
    """Evaluate a policy change context and print its result."""
    if not policy_path.is_file():
        print(
            f"error: no policy file at {policy_path}; "
            "`reasonledger init --policy` writes a starter one",
            file=sys.stderr,
        )
        return EXIT_USAGE
    try:
        policy = load_policy_file(policy_path)
    except PolicyParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if not change_path.is_file():
        print(f"error: change file not found: {change_path}", file=sys.stderr)
        return EXIT_USAGE

    change = ChangePolicyContext.model_validate_json(change_path.read_text(encoding="utf-8"))
    result = evaluate_policy(policy, change)

    if as_json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"overall: {result.overall.value}")
        for rule in result.rules:
            print(f"  {rule.rule_id}: {rule.result.value} — {rule.explanation}")
    return EXIT_FAIL if result.overall == CheckOutcome.FAIL else EXIT_PASS
