"""`reasonledger ui` — giving a decision with no module a home.

The list and the edits behind the Organize tab's "Unplaced decisions" entry and the Map's
"Decisions with no module" cards: place a decision by hand when no anchor works, or claim the
folder its anchors sit in when no module owns it. An edit returns
the manifest before and after, and the session writes it as one undoable step, like every other
edit in the workbench. The rules (who may be placed, how many modules) live in core, so the CLI
and the browser cannot disagree.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reasonledger_core.modules.digest import labelable_files
from reasonledger_core.modules.editing import create_module
from reasonledger_core.modules.hand_placement import clear_hand_placement, place_by_hand
from reasonledger_core.modules.labels import label_files
from reasonledger_core.modules.manifest import load_manifest
from reasonledger_core.modules.models import Manifest
from reasonledger_core.modules.suggest import CoChangeIndex
from reasonledger_core.views.homeless import HomelessView, homeless_view
from reasonledger_core.views.organize_files import load_records

from reasonledger_cli.ui_identity import acting_as


def _decision_id(body: dict[str, Any]) -> str:
    value = body.get("decision")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("decision is required")
    return value.strip()


def _modules(body: dict[str, Any]) -> list[str]:
    value = body.get("modules")
    if not isinstance(value, list) or not value or not all(isinstance(m, str) for m in value):
        raise ValueError("modules must be a list of module ids")
    return value


def view(root: Path, files: list[str], history: CoChangeIndex) -> HomelessView:
    return homeless_view(root, files, history)


def place(root: Path, body: dict[str, Any]) -> tuple[Manifest, Manifest, str]:
    """(before, after, message) for placing one decision; ``ValueError`` says what is wrong."""
    decision = _decision_id(body)
    record = next((r for r in load_records(root) if r.frontmatter.id == decision), None)
    if record is None:
        raise ValueError(f"no decision {decision}")
    before = load_manifest(root)
    modules = _modules(body)
    after = place_by_hand(before, record, root, modules, acting_as(root))
    return before, after, f"placed {decision} in {', '.join(dict.fromkeys(modules))}"


def unplace(root: Path, body: dict[str, Any]) -> tuple[Manifest, Manifest, str]:
    decision = _decision_id(body)
    before = load_manifest(root)
    return before, clear_hand_placement(before, decision), f"took back {decision}'s placement"


def _optional(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    return value.strip() if isinstance(value, str) else ""


def claim(root: Path, body: dict[str, Any]) -> tuple[Manifest, Manifest, str]:
    """Label a folder no module owns into ``target``, or into a new module called ``name``.

    The pattern may name a support folder (specs, docs, tests): a person choosing it is what
    brings those files into the map.
    """
    pattern, name, target = (_optional(body, key) for key in ("pattern", "name", "target"))
    if not pattern:
        raise ValueError("pattern is required")
    before = load_manifest(root)
    files = labelable_files(root, [pattern])
    if name:
        after, new_id = create_module(
            before, name, [pattern], files, by=acting_as(root), at=datetime.now(UTC)
        )
        return before, after, f"Created {new_id} from {pattern}"
    if not target:
        raise ValueError("choose a module or bucket, or name a new module")
    after, matched = label_files(before, [pattern], target, files)
    return before, after, f"Placed {len(matched)} file(s) from {pattern} in {target}"
