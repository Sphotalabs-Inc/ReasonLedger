"""`reasonledger ui` — the module map endpoints. Read-only; no model is called."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from reasonledger_core.views import build_ledger_view_cached
from reasonledger_core.views.map_view import load_map, module_page, overview

HTTP_OK = 200
HTTP_NOT_FOUND = 404
_MODULE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def handle_get_map(root: Path) -> tuple[int, str]:
    return HTTP_OK, overview(load_map(root)).model_dump_json()


def handle_get_module(root: Path, module_id: str) -> tuple[int, dict[str, Any] | str]:
    if not _MODULE_ID.match(module_id):
        return HTTP_NOT_FOUND, {"error": "unknown module"}
    # Conflicts are the verdicts already committed; the same cached view the Review tab builds.
    page = module_page(load_map(root, build_ledger_view_cached(root).conflicts), module_id)
    if page is None:
        return HTTP_NOT_FOUND, {"error": "unknown module"}
    return HTTP_OK, page.model_dump_json()
