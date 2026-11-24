"""The `reasonledger` argument parser: every subcommand and its flags."""

from __future__ import annotations

import argparse
from importlib.metadata import version as package_version
from pathlib import Path
from typing import cast

from reasonledger_cli.approve_cmd import add_approve_parser
from reasonledger_cli.check_cmd import add_check_arguments
from reasonledger_cli.conflict_config_cmd import add_conflict_config_parser
from reasonledger_cli.consent_cmd import add_consent_parser
from reasonledger_cli.first_run import HintingParser
from reasonledger_cli.identity import BY_HELP
from reasonledger_cli.init_cmd import add_init_parser
from reasonledger_cli.judge_cmd import add_judge_parser
from reasonledger_cli.map_cmd import add_map_parser
from reasonledger_cli.modules_cmd import add_modules_parser
from reasonledger_cli.retire_cmd import add_retire_parser
from reasonledger_cli.supersede_cmd import add_supersede_parser

# A command with no group here still works and still shows in the list above.
COMMAND_GROUPS = """\
command groups:
  everyday   init, ui, why, status
  review     confirm, reject, approve, retire, supersede, dismiss
  setup      config, consent, conflict-config
  advanced   import, catchup, judge, map, modules, check, mcp

Run `reasonledger` with no command for a short getting-started guide."""


def build_parser() -> argparse.ArgumentParser:
    parser = HintingParser(
        prog="reasonledger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "ReasonLedger — decision memory for AI-assisted codebases. Your agents\n"
            "record what was decided and why; `reasonledger why <file:line>` tells\n"
            "you which decision justifies a line of code."
        ),
        epilog=COMMAND_GROUPS,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {package_version('reasonledger')}"
    )
    # Subparsers are built from `HintingParser` too; the helpers only need them as parsers.
    sub = cast(
        "argparse._SubParsersAction[argparse.ArgumentParser]",
        parser.add_subparsers(dest="command", metavar="<command>"),
    )

    add_init_parser(sub)

    check = sub.add_parser("check", help="Evaluate .reasonledger/policy.yml against a change")
    add_check_arguments(check)

    why = sub.add_parser("why", help="Show the decision(s) that justify a code locus")
    why.add_argument("target", help="Code locus as path or path:line, e.g. payments/retry.py:55")
    why.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repo root containing .reasonledger/decisions (default: cwd)",
    )
    why.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON result on stdout",
    )
    why.add_argument(
        "--short",
        action="store_true",
        help="Print only the id, the choice and the oversight state for each hit",
    )

    config = sub.add_parser("config", help="Configure BYOM decision extractor (no secrets on disk)")
    config.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Application repo root (default: cwd)",
    )
    config.add_argument(
        "--provider",
        choices=["anthropic", "openai_compatible", "local"],
        help="Extractor provider (non-interactive when set)",
    )
    config.add_argument("--model", help="Model id for the configured provider")
    config.add_argument("--base-url", help="Provider base URL (OpenAI-compatible / local)")
    config.add_argument(
        "--api-key-env",
        help="Env-var name holding the API key (never written to config as a value)",
    )
    config.add_argument(
        "--test",
        action="store_true",
        help="Run a connection probe after writing or against existing config",
    )

    imp = sub.add_parser("import", help="Import decisions from docs (propose-only, conflict-first)")
    imp.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Application repo root (default: cwd)",
    )
    imp.add_argument(
        "--extracted-by",
        required=True,
        help="Provider/model id recorded as extracted_by (e.g. anthropic/claude-sonnet-5)",
    )
    imp.add_argument(
        "--fixture",
        type=Path,
        help="Offline replay fixture JSON (CI/demo; skips live model)",
    )

    confirm = sub.add_parser(
        "confirm",
        help="Promote reviewed proposals into the ledger (human oversight gate)",
    )
    confirm.add_argument("decision_id", nargs="?", help="Proposed decision id; omit with --all")
    confirm.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Application repo root (default: cwd)",
    )
    confirm.add_argument("--confirmed-by", default=None, help=BY_HELP)
    confirm.add_argument(
        "--all",
        action="store_true",
        dest="all_proposed",
        help="Confirm all remaining staged proposals",
    )

    status = sub.add_parser("status", help="Show proposals, decisions, stale, and conflict hints")
    status.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Application repo root (default: cwd)",
    )
    status.add_argument(
        "--json",
        action="store_true",
        help="Emit the full LedgerView as machine-readable JSON",
    )
    status.add_argument(
        "--watch-values",
        type=Path,
        default=None,
        help="JSON file of {metric: number} to evaluate watcher conditions (display-only)",
    )
    status.add_argument(
        "--html",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write a self-contained read-only HTML export to PATH",
    )
    status.add_argument(
        "--since", default=None, metavar="REF", help="Show decisions changed since REF"
    )
    status.add_argument("--metrics", action="store_true", help="Summarise local pilot metrics")
    status.add_argument(
        "--stats",
        action="store_true",
        help="Count decisions in force: review backlog, who proposed, per module (--json too)",
    )

    catchup = sub.add_parser(
        "catchup",
        help="Report what changed since the last sync and import only that",
    )
    catchup.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Application repo root (default: cwd)",
    )
    catchup.add_argument(
        "--extracted-by",
        default=None,
        help="Provider/model id recorded as extracted_by (default: the configured model)",
    )
    catchup.add_argument(
        "--fixture",
        type=Path,
        help="Offline replay fixture JSON (CI/demo; skips live model)",
    )
    catchup.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the gap without scanning documents or spending a model call",
    )
    catchup.add_argument(
        "--no-commits",
        action="store_false",
        dest="include_commits",
        help="Skip commit messages from the gap and read changed documents only",
    )

    dismiss = sub.add_parser(
        "dismiss",
        help="Record that a surfaced conflict is not a real conflict (team-shared)",
    )
    dismiss.add_argument("decision_a", help="First decision id, e.g. dec_1a2b3c")
    dismiss.add_argument("decision_b", help="Second decision id, e.g. dec_8f3k2x")
    dismiss.add_argument(
        "--reason",
        required=True,
        help="Why this hint is wrong (committed and reviewable)",
    )
    dismiss.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Application repo root (default: cwd)",
    )
    dismiss.add_argument(
        "--dismissed-by",
        default=None,
        help="Who made the call (optional; recorded as oversight evidence)",
    )

    add_conflict_config_parser(sub)
    add_judge_parser(sub)
    add_consent_parser(sub)
    add_map_parser(sub)
    add_modules_parser(sub)
    add_approve_parser(sub)
    add_retire_parser(sub)
    add_supersede_parser(sub)

    reject = sub.add_parser("reject", help="Delete a staged proposal (does not touch the ledger)")
    reject.add_argument("decision_id", help="Proposed decision id, e.g. dec_1a2b3c")
    reject.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Application repo root (default: cwd)",
    )

    mcp = sub.add_parser(
        "mcp", help="Run the MCP server on stdio (what your agent's MCP config starts)"
    )
    mcp.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root where .reasonledger/decisions is written (default: cwd)",
    )

    ui = sub.add_parser("ui", help="Open a localhost UI to review proposals and decisions")
    ui.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Application repo root (default: cwd)",
    )
    ui.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port to bind (default: 0 = OS-assigned)",
    )
    ui.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open a browser tab",
    )
    return parser
