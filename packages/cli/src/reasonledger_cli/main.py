"""reasonledger CLI — Decision record onboarding, `why`, and policy checks."""

from __future__ import annotations

import sys

from reasonledger_cli.approve_cmd import run_approve_cmd
from reasonledger_cli.catchup_cmd import run_catchup_cmd
from reasonledger_cli.check_cmd import run_check
from reasonledger_cli.check_decisions_cmd import run_check_decisions
from reasonledger_cli.config_cmd import run_config
from reasonledger_cli.conflict_config_cmd import run_conflict_config
from reasonledger_cli.consent_cmd import run_consent_cmd
from reasonledger_cli.dismiss_cmd import run_dismiss_cmd
from reasonledger_cli.import_cmd import run_confirm_cmd, run_import_cmd
from reasonledger_cli.init_cmd import run_init
from reasonledger_cli.judge_cmd import run_judge_cmd
from reasonledger_cli.map_cmd import run_map_cmd
from reasonledger_cli.mcp_cmd import run_mcp_cmd
from reasonledger_cli.modules_cmd import run_modules_cmd
from reasonledger_cli.parser import build_parser
from reasonledger_cli.retire_cmd import run_retire_cmd
from reasonledger_cli.status_cmd import run_reject_cmd, run_status_cmd
from reasonledger_cli.supersede_cmd import run_supersede_cmd
from reasonledger_cli.ui_cmd import run_ui_cmd
from reasonledger_cli.why_cmd import run_why

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
OUTPUT_ENCODING = "utf-8"


def _use_utf8_output() -> None:
    """Records hold characters (em dashes, arrows) that a legacy Windows code page cannot encode.

    `replace` keeps a command from dying on one it still cannot show.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding=OUTPUT_ENCODING, errors="replace")


def main(argv: list[str] | None = None) -> int:
    _use_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        try:
            out = run_init(
                root=args.root,
                reasonledger_root=args.reasonledger_root,
                scan=not args.no_scan,
                agents=args.agents,
                rules=not args.no_rules,
                policy=args.policy,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE
        print(out)
        return EXIT_PASS
    if args.command == "check":
        if args.decisions == (args.change is not None):
            print("error: specify exactly one of --decisions or --change", file=sys.stderr)
            return EXIT_USAGE
        if args.decisions:
            return run_check_decisions(
                root=args.root,
                base=args.base,
                min_severity=args.min_severity,
                as_json=args.json,
                strict_identity=args.strict_identity,
            )
        assert args.change is not None
        return run_check(policy_path=args.policy, change_path=args.change, as_json=args.json)
    if args.command == "why":
        return run_why(target_raw=args.target, root=args.root, as_json=args.json, short=args.short)
    if args.command == "config":
        return run_config(
            root=args.root,
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            test=args.test,
        )
    if args.command == "import":
        return run_import_cmd(
            root=args.root,
            extracted_by=args.extracted_by,
            fixture=args.fixture,
        )
    if args.command == "confirm":
        return run_confirm_cmd(
            root=args.root,
            decision_id=args.decision_id,
            confirmed_by=args.confirmed_by,
            all_proposed=args.all_proposed,
        )
    if args.command == "status":
        return run_status_cmd(
            root=args.root,
            as_json=args.json,
            watch_values_path=args.watch_values,
            html_path=args.html,
            since=args.since,
            metrics=args.metrics,
            stats=args.stats,
        )
    if args.command == "catchup":
        return run_catchup_cmd(
            root=args.root,
            extracted_by=args.extracted_by,
            fixture=args.fixture,
            dry_run=args.dry_run,
            include_commits=args.include_commits,
        )
    if args.command == "dismiss":
        return run_dismiss_cmd(
            root=args.root,
            decision_a=args.decision_a,
            decision_b=args.decision_b,
            reason=args.reason,
            dismissed_by=args.dismissed_by,
        )
    if args.command == "conflict-config":
        return run_conflict_config(
            root=args.root,
            context_similarity_gate=args.context_similarity_gate,
            shortlist_k=args.shortlist_k,
            judge_model=args.judge_model,
            embedding_provider=args.embedding_provider,
            show=args.show,
        )
    if args.command == "map":
        return run_map_cmd(args)
    if args.command == "consent":
        return run_consent_cmd(args)
    if args.command == "modules":
        return run_modules_cmd(args)
    if args.command == "judge":
        return run_judge_cmd(
            root=args.root,
            limit=args.limit,
            dry_run=args.dry_run,
            pair=tuple(args.pair) if args.pair else None,
        )
    if args.command == "approve":
        return run_approve_cmd(
            root=args.root,
            decision_id=args.decision_id,
            verdict=args.verdict,
            approved_by=args.approved_by,
        )
    if args.command == "retire":
        return run_retire_cmd(
            root=args.root,
            decision_id=args.decision_id,
            reason=args.reason,
            retired_by=args.retired_by,
        )
    if args.command == "supersede":
        return run_supersede_cmd(
            root=args.root,
            decision_id=args.decision_id,
            successor_id=args.successor,
            reason=args.reason,
            decided_by=args.decided_by,
        )
    if args.command == "reject":
        return run_reject_cmd(root=args.root, decision_id=args.decision_id)
    if args.command == "mcp":
        return run_mcp_cmd(repo_root=args.repo_root)
    if args.command == "ui":
        return run_ui_cmd(root=args.root, port=args.port, no_open=args.no_open)
    parser.error(f"unknown command: {args.command}")
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
