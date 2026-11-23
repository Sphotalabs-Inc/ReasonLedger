"""`reasonledger status` + `reject` — lifecycle views over `.reasonledger/`."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.metrics import (
    METRICS_CONFIG_PATH,
    METRICS_ENV_VAR,
    MetricEvent,
    load_metrics,
    metric_counts,
    metrics_enabled,
)
from reasonledger_core.models.decision import DecisionStatus
from reasonledger_core.models.reasoning import ConflictStatus
from reasonledger_core.sync import commit_author_for_path, decision_files_changed_since
from reasonledger_core.views import LedgerView, build_ledger_view

from reasonledger_cli.stats_cmd import run_stats
from reasonledger_cli.ui_html import write_status_html

EXIT_PASS = 0
EXIT_USAGE = 2

_DECISION_ID_RE = re.compile(r"^dec_[a-z0-9]+$")

_HINT = (
    "hint: `reasonledger ui` to review interactively; "
    "`reasonledger confirm <id> | --all` to promote proposals; "
    "`reasonledger reject <id>` to drop one."
)


def _load_watch_values(path: Path) -> dict[str, float] | None:
    """Parse a {metric: number} JSON file; None means invalid (caller errors)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    values: dict[str, float] = {}
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        values[str(key)] = float(value)
    return values


def run_status_cmd(
    *,
    root: Path,
    as_json: bool,
    watch_values_path: Path | None = None,
    html_path: Path | None = None,
    since: str | None = None,
    metrics: bool = False,
    stats: bool = False,
) -> int:
    """Print the repo's decision lifecycle (read-only), optionally export HTML."""
    values: dict[str, float] | None = None
    if watch_values_path is not None:
        values = _load_watch_values(watch_values_path)
        if values is None:
            print(
                f"error: watch values must be a JSON object of numbers: {watch_values_path}",
                file=sys.stderr,
            )
            return EXIT_USAGE

    # Strictly before any view build: building one emits CONFLICT_SURFACED, so
    # reporting the metrics here would mutate the numbers being reported — and
    # `--metrics` reads the log alone, so it would also pay the all-pairs conflict
    # scan for a view it then discards.
    if metrics:
        _print_metrics(root)
        return EXIT_PASS
    if stats:
        return run_stats(root=root, as_json=as_json)

    view = build_ledger_view(root, watch_values=values)

    if html_path is not None:
        try:
            write_status_html(html_path, view.model_dump(mode="json"))
        except OSError as exc:
            print(f"error: could not write HTML export: {exc}", file=sys.stderr)
            return EXIT_USAGE
        print(f"wrote {html_path}")

    changed = (
        decision_files_changed_since(root, since, DECISIONS_DIR)
        if (since is not None and html_path is None)
        else None
    )
    if since is not None and html_path is None and changed is None:
        print(f"note: cannot resolve {since}; showing full status", file=sys.stderr)

    if as_json:
        if since is not None and html_path is None and changed is not None:
            payload = view.model_dump(mode="json")
            payload["since"] = _since_payload(root, view, changed, since, DECISIONS_DIR)
            print(json.dumps(payload, indent=2))
            return EXIT_PASS
        print(view.model_dump_json(indent=2))
        return EXIT_PASS

    if html_path is not None:
        return EXIT_PASS
    if since is not None and changed is not None:
        _print_since(root, view, changed, since, DECISIONS_DIR)
        return EXIT_PASS

    c = view.counts
    # Suppressed hints are shown only when there are some: a conflict vanishing with
    # no explanation is confusing, but a permanent "dismissed: 0" is just noise.
    dismissed_note = f"  dismissed: {c['dismissed']}" if c.get("dismissed") else ""
    print(
        f"proposed: {c['proposed']}  confirmed: {c['confirmed']}  "
        f"active: {c['active']}  superseded: {c['superseded']}  retired: {c['retired']}  "
        f"stale: {c['stale']}  orphaned: {c['orphaned']}  "
        f"conflicts: {c['conflicts']}  related: {c['related']}{dismissed_note}"
    )
    if c.get("pending_approval"):
        print(
            f"note: {c['pending_approval']} decision(s) await a human verdict — "
            "run `reasonledger approve <id>`"
        )
    if c.get("unverified"):
        print(
            f"note: {c['unverified']} related pair(s) not judged yet — "
            "run `reasonledger judge`, or ask your coding agent to call get_judging_task, "
            "to check them for conflicts"
        )
    if view.embedder is not None and view.embedder.fallback_reason:
        print(
            f"warning: related-decision hints use basic word matching because "
            f"{view.embedder.fallback_reason}"
        )
    if view.proposals:
        print("proposals (awaiting review):")
        for p in view.proposals:
            replaces = f"  replaces {p.supersedes}" if p.supersedes else ""
            print(f"  {p.id}  {p.choice or ''}  [{p.source_ref or ''}]{replaces}")
    if view.orphaned:
        print("orphaned (missing files, symbols, or anchors that moved or were lost):")
        for orphan in view.orphaned:
            print(f"  {orphan.decision_id} -> {orphan.locus} ({orphan.reason})")
    if view.stale:
        print("stale (assumption breached):")
        for d in view.stale:
            print(f"  {d.id}  {d.choice or ''}")
    if view.conflicts:
        print("conflicts (judged: same question, answers clash):")
        for conflict in view.conflicts:
            # A re-opened pair was dismissed once, on text that has since changed.
            # Saying so stops it reading as the detector ignoring a settled verdict.
            reopened = (
                "  [re-opened: dismissed earlier, a decision changed since]"
                if conflict.status is ConflictStatus.REOPENED
                else ""
            )
            print(
                f"  {conflict.decision_a} <-> {conflict.decision_b} "
                f"({conflict.severity.value}): {conflict.explanation}{reopened}"
            )
    if since is not None:
        _print_all_decisions(view)
    print(_HINT)
    return EXIT_PASS


def _changed_rows(
    root: Path, view: LedgerView, changed: dict[str, str], decisions_dir: Path
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for summary in view.decisions:
        filename = decision_filename(summary.id)
        status_letter = changed.get(filename)
        if status_letter is None:
            continue
        label = (
            "superseded"
            if summary.status == DecisionStatus.SUPERSEDED.value
            else "added"
            if status_letter == "A"
            else "modified"
        )
        author = commit_author_for_path(root, str(decisions_dir / filename)) or "unknown"
        rows.append(
            {
                "id": summary.id,
                "choice": summary.choice or "",
                "status": label,
                "author": author,
            }
        )
    return sorted(rows, key=lambda row: row["id"])


def _since_payload(
    root: Path, view: LedgerView, changed: dict[str, str], since: str, decisions_dir: Path
) -> dict[str, object]:
    rows = _changed_rows(root, view, changed, decisions_dir)
    return {"ref": since, "count": len(rows), "decisions": rows}


def _print_since(
    root: Path, view: LedgerView, changed: dict[str, str], since: str, decisions_dir: Path
) -> None:
    rows = _changed_rows(root, view, changed, decisions_dir)
    print(f"since {since} — {len(rows)} decisions")
    for row in rows:
        print(f"  {row['status']:<11} {row['id']}  {row['choice']}  ({row['author']})")


def _print_all_decisions(view: LedgerView) -> None:
    """Show the fallback's complete ledger when the requested ref is unknowable."""
    if view.decisions:
        print("decisions:")
        for decision in view.decisions:
            print(f"  {decision.status:<11} {decision.id}  {decision.choice or ''}")


def _print_metrics(root: Path) -> None:
    # A disabled meter and a quiet fortnight both print zeros, and only one of them is
    # data. Saying which is the difference between "the agent never records decisions"
    # and "nobody turned the counter on" — a distinction the pilot's whole verdict
    # rests on, and one a reader cannot recover from the numbers alone.
    if not metrics_enabled(root):
        print("pilot metrics: DISABLED — nothing has been recorded, so these are not zeros.")
        print(f"  enable for this repo: add `metrics: true` to {METRICS_CONFIG_PATH}")
        print(f"  or per-process: export {METRICS_ENV_VAR}=1")
        print("  note: an editor-spawned MCP server needs the repo flag or its own env.")
        return
    events = load_metrics(root)
    counts = metric_counts(events)
    sources = {
        source: sum(
            1
            for event in events
            if event["event"] == MetricEvent.DECISION_RECORDED.value
            and event.get("source") == source
        )
        for source in ("harvested", "recorded")
    }
    why_events = [event for event in events if event["event"] == MetricEvent.WHY_INVOKED.value]
    precise = sum(1 for event in why_events if event.get("match") in {"symbol", "line"})
    coarse = sum(1 for event in why_events if event.get("match") == "file")
    misses = sum(1 for event in why_events if event.get("match") == "miss")
    near = sum(1 for event in why_events if event.get("match") == "near")
    why_total = len(why_events)
    precise_pct = round(100 * precise / why_total) if why_total else 0
    surfaced = counts[MetricEvent.CONFLICT_SURFACED.value]
    dismissed = counts[MetricEvent.CONFLICT_DISMISSED.value]
    dismissed_pct = round(100 * dismissed / surfaced) if surfaced else 0
    print("pilot metrics (14 days)")
    print(
        f"  decisions recorded          {counts[MetricEvent.DECISION_RECORDED.value]}"
        f"   (harvested {sources['harvested']}, recorded {sources['recorded']})"
    )
    print(f"  why invoked                 {why_total}   precise {precise} ({precise_pct}%)")
    print(f"                              coarse {coarse}  near {near}  miss {misses}")
    print(f"  conflicts surfaced          {surfaced}   dismissed {dismissed} ({dismissed_pct}%)")


def run_reject_cmd(*, root: Path, decision_id: str) -> int:
    """Delete a staged proposal (the reject side of propose -> confirm | reject)."""
    if not _DECISION_ID_RE.match(decision_id):
        print(f"error: invalid decision id: {decision_id!r}", file=sys.stderr)
        return EXIT_USAGE
    path = root / PROPOSED_DIR / decision_filename(decision_id)
    if not path.is_file():
        print(f"error: no proposed decision {decision_id!r} to reject", file=sys.stderr)
        return EXIT_USAGE
    path.unlink()
    # Deliberately no CONFLICT_DISMISSED here: rejecting a proposal is not dismissing
    # a conflict. Conflating them inflated the dismissal numerator with unrelated
    # actions. `reasonledger dismiss` is the one action that means "this hint is wrong".
    print(f"rejected {decision_id} (proposal deleted)")
    return EXIT_PASS
