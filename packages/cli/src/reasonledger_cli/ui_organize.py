"""`reasonledger ui` — the map workbench endpoints.

A person's edits to the module map, made from the browser through the same core functions the CLI
uses, so the two cannot drift. Each edit is one write of ``modules.yml``; the session keeps the
manifest from before it, so the last edits can be undone. Undo refuses when the file was changed
from anywhere else since, rather than overwrite that change.
"""

from __future__ import annotations

import hashlib
import re
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

from reasonledger_core.modules.config import MANIFEST_PATH
from reasonledger_core.modules.digest import source_files
from reasonledger_core.modules.editing import (
    ModuleEditError,
    confirm_modules,
    create_module,
    merge_modules,
    reject_module,
    rename_module,
)
from reasonledger_core.modules.labels import LabelError
from reasonledger_core.modules.manifest import ManifestError, load_manifest, write_manifest
from reasonledger_core.modules.models import Manifest
from reasonledger_core.modules.organize import (
    bulk_move,
    decline_placement,
    move_labels,
    preview_move,
    promote_rule,
    select_files,
)
from reasonledger_core.modules.suggest import CoChangeIndex, build_cochange_index
from reasonledger_core.sync.repo import head_commit
from reasonledger_core.views.inbox import InboxItem, collect_items, inbox_view
from reasonledger_core.views.organize_files import list_files, load_records

from reasonledger_cli import ui_decisions as decisions
from reasonledger_cli.ui_identity import acting_as

HTTP_OK = 200
HTTP_BAD = 400
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
UNDO_DEPTH = 50  # edits a session can step back through
_MODULE_ID = re.compile(r"^_?[a-z0-9][a-z0-9-]*$")

Reply = tuple[int, Any]


class _Step(NamedTuple):
    before: Manifest
    after_hash: str  # what modules.yml held right after the edit, to spot a change from elsewhere
    message: str


def _text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _id_list(body: dict[str, Any], key: str) -> list[str]:
    value = body.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{key} must be a list of module ids")
    return value


class OrganizeSession:
    """The workbench's state for one running UI: the undo stack, and a lock around every edit."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._undo: list[_Step] = []
        self._lock = threading.Lock()
        self._actions: dict[str, Callable[[dict[str, Any]], Reply]] = {
            "preview": self._preview,
            "move": self._move,
            "new-module": self._new_module,
            "rename": self._rename,
            "merge": self._merge,
            "reject": self._reject,
            "confirm": self._confirm,
            "undo": self._undo_last,
            "inbox-accept": self._inbox_accept,
            "inbox-decline": self._inbox_decline,
            "inbox-accept-all": self._inbox_accept_all,
            "place-decision": self._place_decision,
            "unplace-decision": self._unplace_decision,
            "claim": self._claim,
        }
        self._history_cache: tuple[str | None, CoChangeIndex] | None = None

    def get(self, name: str, query: dict[str, list[str]]) -> Reply:
        if name == "state":
            return HTTP_OK, self._state()
        if name == "inbox":
            try:
                view = inbox_view(
                    load_manifest(self._root), source_files(self._root), self._history()
                )
            except ManifestError as exc:
                return HTTP_BAD, {"error": str(exc)}
            return HTTP_OK, view.model_dump_json()
        if name == "decisions":
            try:
                found = decisions.view(self._root, source_files(self._root), self._history())
            except ManifestError as exc:
                return HTTP_BAD, {"error": str(exc)}
            return HTTP_OK, found.model_dump_json()
        if name != "files":
            return HTTP_NOT_FOUND, {"error": "not found"}
        module = (query.get("module") or [""])[0]
        text = (query.get("q") or [""])[0]
        raw_offset = (query.get("offset") or ["0"])[0]
        if not _MODULE_ID.match(module) or not raw_offset.isdigit():
            return HTTP_NOT_FOUND, {"error": "unknown module"}
        try:
            page = list_files(
                self._root,
                load_manifest(self._root),
                source_files(self._root),
                module=module,
                query=text,
                offset=int(raw_offset),
            )
        except ManifestError as exc:
            return HTTP_BAD, {"error": str(exc)}
        if page is None:
            return HTTP_NOT_FOUND, {"error": "unknown module"}
        return HTTP_OK, page.model_dump_json()

    def post(self, action: str, body: dict[str, Any]) -> Reply:
        handler = self._actions.get(action)
        if handler is None:
            return HTTP_NOT_FOUND, {"error": "not found"}
        try:
            with self._lock:
                return handler(body)
        except (ManifestError, ModuleEditError, LabelError, ValueError) as exc:
            return HTTP_BAD, {"error": str(exc)}

    def _state(self) -> dict[str, Any]:
        last = self._undo[-1].message if self._undo else None
        return {"can_undo": bool(self._undo), "last": last}

    def _history(self) -> CoChangeIndex:
        """Git history as a co-change index, read again only when HEAD has moved."""
        head = head_commit(self._root)
        if self._history_cache is None or self._history_cache[0] != head:
            self._history_cache = (head, build_cochange_index(self._root))
        return self._history_cache[1]

    def _item(self, body: dict[str, Any], manifest: Manifest, files: list[str]) -> InboxItem:
        key = _text(body, "key")
        items, _ = collect_items(manifest, files, self._history())
        found = next((i for i in items if i.key == key), None)
        if found is None:
            raise ValueError("That suggestion is out of date: the files changed. Reload the inbox.")
        return found

    def _hash(self) -> str:
        path = self._root / MANIFEST_PATH
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""

    def _commit(
        self, before: Manifest, after: Manifest, message: str, module: str | None = None
    ) -> Reply:
        """Write the edit and remember how to undo it; ``module`` is the one to show next."""
        write_manifest(self._root, after)
        self._undo = [*self._undo, _Step(before, self._hash(), message)][-UNDO_DEPTH:]
        return HTTP_OK, {"message": message, "module": module, **self._state()}

    def _selection(self, body: dict[str, Any], manifest: Manifest, files: list[str]) -> list[str]:
        raw = body.get("selection")
        if not isinstance(raw, dict):
            raise ValueError("give a selection")
        paths = raw.get("paths")
        if paths is not None and not (
            isinstance(paths, list) and all(isinstance(p, str) for p in paths)
        ):
            raise ValueError("selection paths must be a list of file paths")
        module, query = raw.get("module"), raw.get("query", "")
        if not isinstance(query, str) or not (module is None or isinstance(module, str)):
            raise ValueError("selection module and query must be text")
        chosen = select_files(manifest, files, paths=paths, module=module, query=query)
        if not chosen:
            raise ValueError("no files selected")
        return chosen

    def _preview(self, body: dict[str, Any]) -> Reply:
        manifest, files = load_manifest(self._root), source_files(self._root)
        selection = self._selection(body, manifest, files)
        impact = preview_move(
            manifest, files, selection, _text(body, "target"), load_records(self._root), self._root
        )
        return HTTP_OK, impact.model_dump()

    def _move(self, body: dict[str, Any]) -> Reply:
        manifest, files = load_manifest(self._root), source_files(self._root)
        selection = self._selection(body, manifest, files)
        target = _text(body, "target")
        as_rule = bool(body.get("rule"))
        updated, count, pattern = move_labels(manifest, files, selection, target, as_rule=as_rule)
        what = (
            f"rule {pattern} placing {count} file(s) in" if as_rule else f"moved {count} file(s) to"
        )
        return self._commit(manifest, updated, f"{what.capitalize()} {target}")

    def _new_module(self, body: dict[str, Any]) -> Reply:
        manifest, files = load_manifest(self._root), source_files(self._root)
        selection = self._selection(body, manifest, files)
        name = _text(body, "name")
        updated, new_id = create_module(
            manifest, name, selection, files, by=acting_as(self._root), at=datetime.now(UTC)
        )
        return self._commit(
            manifest, updated, f"Created {new_id} from {len(selection)} file(s)", new_id
        )

    def _rename(self, body: dict[str, Any]) -> Reply:
        manifest = load_manifest(self._root)
        module_id = _text(body, "id")
        updated, new_id = rename_module(manifest, module_id, _text(body, "name"))
        return self._commit(manifest, updated, f"Renamed {module_id} to {new_id}", new_id)

    def _merge(self, body: dict[str, Any]) -> Reply:
        manifest = load_manifest(self._root)
        keep, absorb = _text(body, "keep"), _text(body, "absorb")
        updated = merge_modules(manifest, keep, absorb)
        return self._commit(manifest, updated, f"Merged {absorb} into {keep}", keep)

    def _reject(self, body: dict[str, Any]) -> Reply:
        manifest = load_manifest(self._root)
        module_id = _text(body, "id")
        reason = body.get("reason")
        updated = reject_module(manifest, module_id, reason if isinstance(reason, str) else "")
        return self._commit(manifest, updated, f"Rejected {module_id}")

    def _confirm(self, body: dict[str, Any]) -> Reply:
        manifest = load_manifest(self._root)
        updated, changed = confirm_modules(
            manifest, _id_list(body, "ids"), by=acting_as(self._root), at=datetime.now(UTC)
        )
        if not changed:
            return HTTP_OK, {"message": "Already confirmed", **self._state()}
        return self._commit(manifest, updated, f"Confirmed {', '.join(changed)}")

    def _undo_last(self, _body: dict[str, Any]) -> Reply:
        if not self._undo:
            raise ValueError("nothing to undo")
        step = self._undo[-1]
        if self._hash() != step.after_hash:
            return HTTP_CONFLICT, {
                "error": "modules.yml changed outside this window since your last edit; "
                "reload the page before undoing"
            }
        write_manifest(self._root, step.before)
        self._undo = self._undo[:-1]
        return HTTP_OK, {"message": f"Undid: {step.message}", **self._state()}

    def _inbox_accept(self, body: dict[str, Any]) -> Reply:
        manifest, files = load_manifest(self._root), source_files(self._root)
        item = self._item(body, manifest, files)
        chosen = body.get("target")
        target = (
            chosen if isinstance(chosen, str) else (item.target if item.kind == "place" else None)
        )
        if item.kind in ("place", "new-module") and target:
            updated, count, pattern = move_labels(
                manifest, files, item.files, target, as_rule=bool(body.get("rule"))
            )
            what = (
                f"rule {pattern} placing {count} file(s) in"
                if pattern
                else f"moved {count} file(s) to"
            )
            return self._commit(manifest, updated, f"{what.capitalize()} {target}")
        if item.kind == "new-module":
            name = body.get("name") if isinstance(body.get("name"), str) else item.name
            updated, new_id = create_module(
                manifest,
                name or "",
                item.files,
                files,
                by=acting_as(self._root),
                at=datetime.now(UTC),
            )
            message = f"Created {new_id} from {len(item.files)} file(s)"
            return self._commit(manifest, updated, message, new_id)
        if item.kind == "rule" and item.rule and item.target:
            updated, count = promote_rule(manifest, files, item.rule.pattern, item.target)
            message = f"Rule {item.rule.pattern} now places {count} file(s) in {item.target}"
            return self._commit(manifest, updated, message)
        raise ValueError("a proposed module is confirmed or rejected from its own card")

    def _place_decision(self, body: dict[str, Any]) -> Reply:
        return self._commit(*decisions.place(self._root, body))

    def _unplace_decision(self, body: dict[str, Any]) -> Reply:
        return self._commit(*decisions.unplace(self._root, body))

    def _claim(self, body: dict[str, Any]) -> Reply:
        return self._commit(*decisions.claim(self._root, body))

    def _inbox_decline(self, body: dict[str, Any]) -> Reply:
        manifest, files = load_manifest(self._root), source_files(self._root)
        item = self._item(body, manifest, files)
        module = body.get("module") if isinstance(body.get("module"), str) else item.target
        if item.kind != "place" or not module:
            raise ValueError("only a suggested home can be declined")
        updated = decline_placement(manifest, item.files, module)
        return self._commit(manifest, updated, f"Declined {module} for {len(item.files)} file(s)")

    def _inbox_accept_all(self, body: dict[str, Any]) -> Reply:
        manifest, files = load_manifest(self._root), source_files(self._root)
        items, _ = collect_items(manifest, files, self._history())
        skipped = body.get("skipped")
        left = set(skipped) if isinstance(skipped, list) else set()
        sure = [
            i
            for i in items
            if i.kind == "place" and i.confidence == "high" and i.target and i.key not in left
        ]
        if not sure:
            raise ValueError("no high-confidence suggestion to accept")
        moves = [(i.files, i.target) for i in sure if i.target]
        updated, count = bulk_move(manifest, files, moves)
        return self._commit(
            manifest,
            updated,
            f"Placed {count} file(s) from {len(sure)} high-confidence suggestion(s)",
        )
