"""`reasonledger ui` — the summary strip's numbers, the same count `status --stats` prints."""

from __future__ import annotations

from pathlib import Path

from reasonledger_core.views import build_ledger_view_cached, build_stats
from reasonledger_core.views.map_view import load_map, overview

HTTP_OK = 200


def handle_get_stats(root: Path) -> tuple[int, str]:
    stats = build_stats(build_ledger_view_cached(root).decisions, overview(load_map(root)))
    return HTTP_OK, stats.model_dump_json()
