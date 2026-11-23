"""`reasonledger import` + `confirm` — extract proposals, then promote reviewed ones."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.consent import DataClass, destination
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.adapters import ExtractorError, build_extractor
from reasonledger_core.importer.config import (
    ConfigError,
    ExtractorProvider,
    load_extractor_config,
)
from reasonledger_core.importer.extractor import Extractor, ReplayExtractor
from reasonledger_core.importer.propose import (
    PROPOSED_DIR,
    ImportConfirmError,
    confirm_proposed,
)
from reasonledger_core.importer.service import ImportReport, run_import

from reasonledger_cli.consent_cmd import ensure_consent, print_held
from reasonledger_cli.identity import acting_identity
from reasonledger_cli.related_output import print_related_summary

EXIT_PASS = 0
EXIT_USAGE = 2

_CONFIRM_REMINDER = (
    f"Proposals staged in {PROPOSED_DIR}/ — review and confirm before they land in the ledger."
)


def _print_report(report: ImportReport) -> None:
    print_related_summary(report.conflicts)

    result = report.result
    if result.superseded:
        # Louder than the counts below: a confirmed decision's own source has moved
        # under it, which is the one thing here a reviewer must not scroll past.
        print("supersedes (source changed since confirmation):")
        for item in result.superseded:
            print(f"  {item.proposal_id} replaces {item.supersedes} — {item.source_ref}")

    print("proposals:")
    print(f"  created: {result.created}")
    print(f"  updated: {result.updated}")
    print(f"  skipped_unchanged: {result.skipped_unchanged}")
    print(f"  skipped_confirmed: {result.skipped_confirmed}")
    print(f"  skipped_pii: {len(result.skipped_pii)}")
    print_held(report.held)
    print(_CONFIRM_REMINDER)


def run_import_cmd(
    *,
    root: Path,
    extracted_by: str,
    fixture: Path | None = None,
) -> int:
    """Run doc import and print a conflict-first report."""
    extractor: Extractor
    off_machine = False
    if fixture is not None:
        if not fixture.is_file():
            print(f"error: fixture not found: {fixture}", file=sys.stderr)
            return EXIT_USAGE
        extractor = ReplayExtractor.from_fixture(fixture)
    else:
        try:
            config = load_extractor_config(root)
        except ConfigError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE
        if config.provider is ExtractorProvider.DISABLED:
            print(
                "error: no model is configured. Run `reasonledger config`, or ask your coding "
                "agent to call the MCP tools get_import_task and submit_candidates.",
                file=sys.stderr,
            )
            return EXIT_USAGE
        denied = ensure_consent(root, config, [DataClass.REPO_TEXT], command="import")
        if denied is not None:
            return denied
        off_machine = destination(config) is not None
        try:
            extractor = build_extractor(config)
        except ExtractorError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE

    # Embedder resolves from settings (get_embedder): deterministic by default,
    # `local`/`remote` when configured via RL_EMBEDDING_PROVIDER — clean conflicts
    # on real prose instead of the stub's hash-collision noise.
    report = run_import(
        root,
        extractor=extractor,
        extracted_by=extracted_by,
        screen_outgoing=off_machine,
    )
    _print_report(report)
    return EXIT_PASS


def run_confirm_cmd(
    *,
    root: Path,
    decision_id: str | None,
    confirmed_by: str | None,
    all_proposed: bool = False,
) -> int:
    """Promote reviewed proposals from staging into the ledger (human oversight gate)."""
    who = acting_identity(root, confirmed_by, flag="--confirmed-by")
    if who is None:
        return EXIT_USAGE
    when = datetime.now(UTC)

    if all_proposed:
        proposed_dir = root / PROPOSED_DIR
        ids = (
            [path.stem for path in sorted(proposed_dir.glob("dec_*.md"))]
            if proposed_dir.is_dir()
            else []
        )
        if not ids:
            print("no proposed decisions to confirm")
            return EXIT_PASS
        for staged_id in ids:
            confirm_proposed(staged_id, root=root, confirmed_by=who, confirmed_at=when)
        print(f"confirmed {len(ids)} decision(s) into {DECISIONS_DIR}/")
        return EXIT_PASS

    if not decision_id:
        print("error: provide a decision id or use --all", file=sys.stderr)
        return EXIT_USAGE
    try:
        record = confirm_proposed(decision_id, root=root, confirmed_by=who, confirmed_at=when)
    except ImportConfirmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"confirmed {record.frontmatter.id} into {DECISIONS_DIR}/")
    return EXIT_PASS
