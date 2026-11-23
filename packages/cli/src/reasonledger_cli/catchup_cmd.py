"""`reasonledger catchup` — bring the ledger back up to speed after a gap.

The question this answers is "what was decided while I wasn't using
ReasonLedger?". It reads the sync watermark, scans only what changed since,
and reports three buckets a reviewer can act on: **new** proposals, **superseded**
decisions whose source moved underneath them, and **orphaned** loci pointing at
files that no longer exist.

It is honest about its own scope. A decision that left no written trace in the
repo cannot be recovered by any scan, and the report says so rather than
implying the list is exhaustive.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.consent import DataClass, destination
from reasonledger_core.importer.adapters import ExtractorError, build_extractor
from reasonledger_core.importer.config import (
    ConfigError,
    extracted_by_label,
    load_extractor_config,
)
from reasonledger_core.importer.extractor import Extractor, ReplayExtractor
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.importer.scan import ImportSource, commit_sources, scannable_paths
from reasonledger_core.importer.service import run_import
from reasonledger_core.sync import (
    SyncState,
    SyncStateError,
    changed_paths_since,
    commit_messages_since,
    commits_since,
    head_commit,
    is_git_repo,
    load_sync_state,
    write_sync_state,
)
from reasonledger_core.views import build_ledger_view

from reasonledger_cli.consent_cmd import ensure_consent, print_held
from reasonledger_cli.related_output import print_related_summary

EXIT_PASS = 0
EXIT_USAGE = 2

_SCOPE_CAVEAT = (
    "Scope: decisions written down in this repo. A call made only in chat or a "
    "meeting left no trace here and cannot be recovered by a scan."
)

# A gap of thousands of commits is a first run, not a catch-up; scanning them all
# would be a surprise model bill. Past this, docs alone carry the delta.
MAX_COMMITS_SCANNED = 200


def _describe_gap(root: Path, state: SyncState) -> tuple[str, list[str] | None]:
    """Human summary of the gap, plus the changed-path delta (None = scan everything)."""
    if not is_git_repo(root):
        return ("not a git repo — scanning every document.", None)
    if state.last_synced_commit is None:
        return ("no previous catch-up recorded — scanning every document.", None)

    changed = changed_paths_since(root, state.last_synced_commit)
    if changed is None:
        return (
            f"commit {state.last_synced_commit[:12]} is no longer in history "
            "(rebased or squashed?) — scanning every document.",
            None,
        )
    # Report only what a scan would actually read: a raw git delta is mostly source
    # files and ReasonLedger's own bookkeeping, so its size would overstate the gap.
    scannable = scannable_paths(changed)
    count = commits_since(root, state.last_synced_commit)
    since = f"last synced at {state.last_synced_commit[:12]}"
    if state.last_synced_at is not None:
        days = (datetime.now(UTC) - state.last_synced_at).days
        since += f", {days} day{'s' if days != 1 else ''} ago"
    if count is not None:
        since += f", {count} commit{'s' if count != 1 else ''} behind"
    plural = "s" if len(scannable) != 1 else ""
    return (f"{since}; {len(scannable)} changed document{plural} to scan.", scannable)


def _gap_commit_sources(root: Path, state: SyncState, include: bool) -> list[ImportSource]:
    """Commit messages from the gap window, as extractable prose.

    Only ever within a *bounded* window: with no watermark there is no gap, just
    the whole history, and mining that is a different (explicit) operation.
    """
    if not include or state.last_synced_commit is None:
        return []
    commits = commit_messages_since(root, state.last_synced_commit, limit=MAX_COMMITS_SCANNED)
    if commits is None:
        return []
    return commit_sources(commits)


def _build_extractor(root: Path, fixture: Path | None) -> tuple[Extractor, bool] | None:
    """The extractor, and whether it sends off this machine; None after printing why not."""
    if fixture is not None:
        if not fixture.is_file():
            print(f"error: fixture not found: {fixture}", file=sys.stderr)
            return None
        return ReplayExtractor.from_fixture(fixture), False
    try:
        config = load_extractor_config(root)
        if ensure_consent(root, config, [DataClass.REPO_TEXT], command="catchup") is not None:
            return None
        return build_extractor(config), destination(config) is not None
    except (ConfigError, ExtractorError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return None


def _resolve_extracted_by(root: Path, explicit: str | None, fixture: Path | None) -> str:
    """`import` demands --extracted-by; catch-up derives it so the gap is one command."""
    if explicit:
        return explicit
    if fixture is not None:
        return "fixture"
    try:
        return extracted_by_label(load_extractor_config(root))
    except ConfigError:
        return "unknown"


def _print_orphans(root: Path) -> None:
    view = build_ledger_view(root)
    if not view.orphaned:
        return
    print("orphaned (justifies a file that no longer exists):")
    for orphan in view.orphaned:
        print(f"  {orphan.decision_id} -> {orphan.locus}")


def run_catchup_cmd(
    *,
    root: Path,
    extracted_by: str | None = None,
    fixture: Path | None = None,
    dry_run: bool = False,
    include_commits: bool = True,
) -> int:
    """Report the gap since the last catch-up, then close it."""
    if not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return EXIT_USAGE
    try:
        state = load_sync_state(root)
    except SyncStateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    summary, changed = _describe_gap(root, state)
    commit_srcs = _gap_commit_sources(root, state, include_commits)
    if commit_srcs:
        plural = "s" if len(commit_srcs) != 1 else ""
        summary += f" {len(commit_srcs)} commit message{plural} explain a change."
    print(summary)

    if dry_run:
        # Deliberately before any extractor is built: --dry-run must never spend
        # a model call, so it stays free to run on a repo with no model configured.
        _print_orphans(root)
        print("dry run — no documents scanned and the watermark is unchanged.")
        print(_SCOPE_CAVEAT)
        return EXIT_PASS

    built = _build_extractor(root, fixture)
    if built is None:
        return EXIT_USAGE
    extractor, off_machine = built

    report = run_import(
        root,
        extractor=extractor,
        extracted_by=_resolve_extracted_by(root, extracted_by, fixture),
        only_paths=changed,
        extra_sources=commit_srcs,
        screen_outgoing=off_machine,
    )
    result = report.result

    if result.superseded:
        print("superseded (source changed since confirmation):")
        for item in result.superseded:
            print(f"  {item.proposal_id} replaces {item.supersedes} — {item.source_ref}")
    print_related_summary(report.conflicts)
    _print_orphans(root)

    print(f"new proposals: {result.created}")
    print(f"already confirmed, unchanged: {result.skipped_confirmed}")

    print_held(report.held)
    # The watermark tracks what has been *scanned*, not what has been reviewed:
    # proposals stay staged in PROPOSED_DIR until confirmed, so advancing here
    # cannot lose them. A held source was never read, so advancing past it would
    # lose it for good; the watermark waits until every source in the gap was sent.
    if report.held:
        print("watermark unchanged: fix the held sources, then run catchup again.")
    else:
        commit = head_commit(root)
        write_sync_state(
            root,
            SyncState(last_synced_commit=commit, last_synced_at=datetime.now(UTC)),
        )
    if result.created or result.superseded:
        print(f"Review them in {PROPOSED_DIR}/ — `reasonledger ui` or `reasonledger confirm`.")
    print(_SCOPE_CAVEAT)
    return EXIT_PASS
