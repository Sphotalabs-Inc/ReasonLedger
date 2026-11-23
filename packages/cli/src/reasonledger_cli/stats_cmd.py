"""`reasonledger status --stats` — the ledger's composition, the numbers behind the UI strip."""

from __future__ import annotations

from pathlib import Path

from reasonledger_core.views import LedgerStats, build_ledger_view, build_stats
from reasonledger_core.views.map_view import load_map, overview

EXIT_PASS = 0

_BAR_WIDTH = 20
_BAR_FULL = "#"
_BAR_EMPTY = "."


def load_stats(root: Path) -> LedgerStats:
    return build_stats(build_ledger_view(root).decisions, overview(load_map(root)))


def _bar(part: int, whole: int) -> str:
    filled = round(_BAR_WIDTH * part / whole) if whole else 0
    return "[" + _BAR_FULL * filled + _BAR_EMPTY * (_BAR_WIDTH - filled) + "]"


def _percent(part: int, whole: int) -> int:
    return round(100 * part / whole) if whole else 0


def _print_modules(stats: LedgerStats) -> None:
    if not stats.mapped:
        print("modules: no module map yet - run `reasonledger map`")
        return
    print("modules (a decision anchored in two modules counts in both):")
    width = max((len(m.name) for m in stats.modules), default=0)
    top = max((m.decisions for m in stats.modules), default=0)
    for m in stats.modules:
        pending = f"  {m.pending} pending" if m.pending else ""
        print(
            f"  {m.name:<{width}}  {_bar(m.decisions, top)} {m.decisions:>3}{pending}"
            f"  {round(m.coverage * 100)}% of {m.files} files"
        )
    if stats.modules_without_decisions:
        print(f"note: {stats.modules_without_decisions} module(s) have no decision yet")


def run_stats(*, root: Path, as_json: bool) -> int:
    """Print the counts of decisions in force (read-only)."""
    stats = load_stats(root)
    if as_json:
        print(stats.model_dump_json(indent=2))
        return EXIT_PASS
    print(f"decisions in force: {stats.in_force}")
    print(
        f"review    {_bar(stats.judged, stats.in_force)} "
        f"{stats.judged} judged by a person  {stats.pending} pending"
        f"  ({_percent(stats.judged, stats.in_force)}% judged)"
    )
    print(
        f"proposed  {stats.proposed_human} by a person  {stats.proposed_ai} by an agent"
        f"  {stats.proposed_unset} not stated"
    )
    _print_modules(stats)
    return EXIT_PASS
