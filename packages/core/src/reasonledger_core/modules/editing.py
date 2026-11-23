"""A person's edits to the module map: confirm, rename, merge and reject.

Every function takes a manifest and returns a new one, or raises ``ModuleEditError`` before
changing anything, so a command either applies in full or not at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from difflib import get_close_matches

from reasonledger_core.modules.buckets import BUCKET_IDS
from reasonledger_core.modules.labels import label_files
from reasonledger_core.modules.manifest import reject
from reasonledger_core.modules.models import (
    Confidence,
    Manifest,
    Module,
    ModuleKind,
    ModuleStatus,
)
from reasonledger_core.modules.resolve import slug
from reasonledger_core.modules.tiers import Tiers

# Confidence from least to most trusted, to pick the more cautious of two modules when merging.
_TRUST = (Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH)


class ModuleEditError(ValueError):
    """Raised when an edit names nothing real or would break the map."""


def _find(manifest: Manifest, module_id: str) -> Module:
    found = next((m for m in manifest.modules if m.id == module_id), None)
    if found is None:
        close = get_close_matches(module_id, [m.id for m in manifest.modules], n=3)
        hint = f"; did you mean {', '.join(close)}?" if close else " (see `reasonledger modules`)"
        raise ModuleEditError(f"no module named {module_id!r}{hint}")
    return found


def _capability(manifest: Manifest, module_id: str, action: str) -> Module:
    module = _find(manifest, module_id)
    if module.kind is ModuleKind.BUCKET:
        raise ModuleEditError(
            f"{module_id} is a bucket, not a module: it cannot be {action}; "
            "use `reasonledger modules label` to move files in or out of it"
        )
    return module


def _replace(manifest: Manifest, old_id: str, module: Module) -> list[Module]:
    return [module if m.id == old_id else m for m in manifest.modules]


def high_confidence_ids(manifest: Manifest) -> list[str]:
    """Proposed modules the signals agree on strongly enough to confirm in bulk."""
    return [
        m.id
        for m in manifest.capabilities
        if m.status is ModuleStatus.PROPOSED and m.confidence is Confidence.HIGH
    ]


def confirm_modules(
    manifest: Manifest, module_ids: Sequence[str], *, by: str, at: datetime
) -> tuple[Manifest, list[str]]:
    """Mark modules confirmed by a person; return the manifest and the ids that changed.

    A module that is already confirmed is left exactly as it is, so confirming twice is harmless.
    """
    if not by.strip():
        raise ModuleEditError("say who is confirming with --by")
    wanted = [_find(manifest, module_id) for module_id in module_ids]
    changed = [m.id for m in wanted if m.status is not ModuleStatus.CONFIRMED]
    update = {"status": ModuleStatus.CONFIRMED, "confirmed_by": by.strip(), "confirmed_at": at}
    modules = [m.model_copy(update=update) if m.id in changed else m for m in manifest.modules]
    return manifest.model_copy(update={"modules": modules}), changed


def rename_module(manifest: Manifest, module_id: str, new_name: str) -> tuple[Manifest, str]:
    """Give a module a new name and the id that name makes; labels and suggestions follow it."""
    module = _capability(manifest, module_id, "renamed")
    name = new_name.strip()
    if not name:
        raise ModuleEditError("give the new name")
    new_id = slug(name)
    taken = {m.id for m in manifest.modules} | BUCKET_IDS
    if new_id != module_id and new_id in taken:
        raise ModuleEditError(f"{new_id!r} is already a module or a bucket; pick another name")
    renamed = module.model_copy(update={"id": new_id, "name": name})
    labels = {p: (new_id if t == module_id else t) for p, t in manifest.labels.items()}
    suggestions = [
        s.model_copy(update={"module": new_id}) if s.module == module_id else s
        for s in manifest.suggestions
    ]
    return (
        manifest.model_copy(
            update={
                "modules": _replace(manifest, module_id, renamed),
                "labels": labels,
                "suggestions": suggestions,
            }
        ),
        new_id,
    )


def merge_modules(manifest: Manifest, keep_id: str, absorb_id: str) -> Manifest:
    """Fold ``absorb_id`` into ``keep_id``: one module with both path sets.

    The kept module keeps its id, name, description and status. A confirmed module cannot be
    absorbed into a proposed one, because the result would lose the person's confirmation.
    """
    keep = _capability(manifest, keep_id, "merged")
    absorb = _capability(manifest, absorb_id, "merged")
    if keep_id == absorb_id:
        raise ModuleEditError("a module cannot be merged into itself")
    if absorb.status is ModuleStatus.CONFIRMED and keep.status is not ModuleStatus.CONFIRMED:
        raise ModuleEditError(
            f"{absorb_id} is confirmed and {keep_id} is not: merge it the other way round, "
            f"or confirm {keep_id} first"
        )
    trusted = [c for c in (keep.confidence, absorb.confidence) if c]
    merged = keep.model_copy(
        update={
            "paths": sorted({*keep.paths, *absorb.paths}),
            "description": keep.description or absorb.description,
            "tier": keep.tier if keep.tier == absorb.tier else None,
            "evidence": [*keep.evidence, *(e for e in absorb.evidence if e not in keep.evidence)],
            "confidence": min(trusted, key=_TRUST.index) if trusted else None,
        }
    )
    labels = {p: (keep_id if t == absorb_id else t) for p, t in manifest.labels.items()}
    suggestions = [
        s.model_copy(update={"module": keep_id}) if s.module == absorb_id else s
        for s in manifest.suggestions
    ]
    modules = [m for m in _replace(manifest, keep_id, merged) if m.id != absorb_id]
    return manifest.model_copy(
        update={"modules": modules, "labels": labels, "suggestions": suggestions}
    )


def reject_module(manifest: Manifest, module_id: str, reason: str = "") -> Manifest:
    """Turn a proposal down; it stays down while a later proposal covers about the same files."""
    module = _capability(manifest, module_id, "rejected")
    if module.status is ModuleStatus.CONFIRMED:
        raise ModuleEditError(
            f"{module_id} is confirmed, so it is not a proposal; "
            "remove it from .reasonledger/modules.yml if it should go"
        )
    return reject(manifest, module, reason.strip())


def create_module(
    manifest: Manifest,
    name: str,
    paths: Sequence[str],
    files: Sequence[str],
    *,
    by: str,
    at: datetime,
) -> tuple[Manifest, str]:
    """Make a confirmed module out of files a person picked, and return it with its id.

    The files are placed by labels, so they outrank whatever module held them and the new module
    survives the next map. A person made it, so it starts confirmed by them.
    """
    if not by.strip():
        raise ModuleEditError("say who is creating the module")
    title = name.strip()
    if not title:
        raise ModuleEditError("give the new module a name")
    new_id = slug(title)
    if new_id in {m.id for m in manifest.modules} | BUCKET_IDS:
        raise ModuleEditError(f"{new_id!r} is already a module or a bucket; pick another name")
    module = Module(
        id=new_id,
        name=title,
        paths=[],
        tier=Tiers(files).of_files(list(paths)),
        status=ModuleStatus.CONFIRMED,
        confirmed_by=by.strip(),
        confirmed_at=at,
    )
    base = manifest.model_copy(update={"modules": [*manifest.modules, module]})
    return label_files(base, paths, new_id, files)[0], new_id
