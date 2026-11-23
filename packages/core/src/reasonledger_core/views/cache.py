"""View-level cache for interactive callers (local UI).

Conflict detection dominates ``build_ledger_view`` cost. Interactive surfaces
re-request the same projection many times between ledger edits; this module
memoises by a cheap (count, max-mtime) fingerprint so repeat GETs stay cheap
without changing output semantics for CLI callers that still call
``build_ledger_view`` directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.reasoning.conflict_config import CONFLICT_CONFIG_PATH
from reasonledger_core.reasoning.dismissals import DISMISSED_PATH
from reasonledger_core.reasoning.verdicts import VERDICTS_PATH
from reasonledger_core.views.ledger import LedgerView, build_ledger_view

_VIEW_CACHE_LIMIT = 8
_view_cache: dict[tuple[object, ...], LedgerView] = {}


def ledger_fingerprint(root: Path) -> tuple[int, float]:
    """Cheap invalidation key: (file count, max mtime) across decisions + proposed.

    Deliberately not a content hash — this runs on every request and must stay
    O(files) with no content reads.

    dismissed.yml, conflict.yml and verdicts.yml all feed the same max_mtime rather
    than a separate count: none is a decision file, but each changes what `status`
    reports — a dismissal, a retuned shortlist, a new verdict — without touching
    DECISIONS_DIR/PROPOSED_DIR, so a fingerprint built only from those two
    directories would keep serving stale conflicts until an unrelated decision
    edit happened to invalidate the cache.
    """
    count = 0
    max_mtime = 0.0
    for rel in (DECISIONS_DIR, PROPOSED_DIR):
        directory = root / rel
        if not directory.is_dir():
            continue
        for path in directory.glob("*.md"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            count += 1
            if mtime > max_mtime:
                max_mtime = mtime
    for side_effect_path in (DISMISSED_PATH, CONFLICT_CONFIG_PATH, VERDICTS_PATH):
        try:
            side_mtime = (root / side_effect_path).stat().st_mtime
        except OSError:
            continue
        if side_mtime > max_mtime:
            max_mtime = side_mtime
    return count, max_mtime


def build_ledger_view_cached(
    root: Path,
    *,
    watch_values: Mapping[str, float] | None = None,
) -> LedgerView:
    """Cached wrapper for interactive callers. Recomputes only when the ledger changes."""
    resolved = root.resolve()
    watch_key = tuple(sorted((watch_values or {}).items()))
    key: tuple[object, ...] = (str(resolved), ledger_fingerprint(resolved), watch_key)
    hit = _view_cache.get(key)
    if hit is not None:
        return hit
    view = build_ledger_view(resolved, watch_values=watch_values)
    _view_cache[key] = view
    while len(_view_cache) > _VIEW_CACHE_LIMIT:
        _view_cache.pop(next(iter(_view_cache)))
    return view


def clear_view_cache() -> None:
    """Test helper — drop all cached views."""
    _view_cache.clear()
