"""`reasonledger why`: the decisions that explain a line of code."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.metrics import MetricEvent, emit
from reasonledger_core.reasoning import find_nearby, parse_target, resolve_why, why_payload
from reasonledger_core.reasoning.why import WhyQueryError, match_rank, target_exists

from reasonledger_cli.why_render import ordered_hits, render_hit, render_miss

EXIT_PASS = 0
EXIT_USAGE = 2
MATCH_MISS = "miss"
MATCH_NEAR = "near"


def run_why(*, target_raw: str, root: Path, as_json: bool, short: bool = False) -> int:
    try:
        target = parse_target(target_raw)
    except WhyQueryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    records = load_decisions_from_dir(root / DECISIONS_DIR)
    hits = resolve_why(records, target, root=root)
    exists = target_exists(root, target)
    nearby = (
        find_nearby(records, target.path, target.line, root=root) if exists and not hits else None
    )
    near_something = nearby is not None and bool(nearby.anchors or nearby.out_of_force)
    best = min((hit.match for hit in hits), key=match_rank, default=None)
    # A near miss is a miss for the pilot's hit rate, counted apart so it does not flatter it.
    emit(
        root,
        MetricEvent.WHY_INVOKED,
        match=best.value if best else (MATCH_NEAR if near_something else MATCH_MISS),
    )

    if as_json:
        print(
            json.dumps(why_payload(target_raw, target, hits, root=root, records=records), indent=2)
        )
        return EXIT_PASS

    if not hits:
        if not exists:
            # A decision may still anchor a file that has since moved or been deleted, so
            # only a miss on a missing path is an error: that is a typo or a wrong root.
            print(
                f"error: no file at {target.path} in this repo "
                "(use a path relative to the repo root)",
                file=sys.stderr,
            )
            return EXIT_USAGE
        for line in render_miss(target, nearby, ledger_size=len(records)):
            print(line)
        return EXIT_PASS
    for hit in ordered_hits(hits):
        for line in render_hit(hit, target_raw, short=short):
            print(line)
    return EXIT_PASS
