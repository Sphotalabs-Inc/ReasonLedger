"""Read and write ``.reasonledger/modules.yml`` — the committed source of truth for modules."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Sequence
from pathlib import Path

import yaml

from reasonledger_core.modules.buckets import BUCKET_IDS, new_bucket
from reasonledger_core.modules.config import (
    MANIFEST_PATH,
    MANIFEST_VERSION,
    REJECT_REAPPEAR_JACCARD,
)
from reasonledger_core.modules.globs import PathMatcher
from reasonledger_core.modules.models import Manifest, Module, ModuleStatus, RejectedModule

FINGERPRINT_LENGTH = 16
# libyaml's loader when PyYAML has it: the same safe subset, several times faster on a big map.
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class ManifestError(ValueError):
    """Raised when the manifest file is malformed."""


def paths_fingerprint(paths: Iterable[str]) -> str:
    """Identify a proposal by the paths it claims, so a rejection can recognise it again."""
    text = "\n".join(sorted(paths))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]


def load_manifest(root: Path) -> Manifest:
    """The manifest, or an empty one when the repo has none yet."""
    path = root / MANIFEST_PATH
    if not path.is_file():
        return Manifest(version=MANIFEST_VERSION)
    try:
        raw = yaml.load(path.read_text(encoding="utf-8"), Loader=_YAML_LOADER) or {}
        if not isinstance(raw, dict):
            raise ManifestError(f"{MANIFEST_PATH} must be a mapping")
        return Manifest.model_validate(raw)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise ManifestError(f"cannot read {MANIFEST_PATH}: {exc}") from exc


def write_manifest(root: Path, manifest: Manifest) -> Path:
    """Write atomically with a stable order, so an unchanged scan produces no diff."""
    path = root / MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_copy(
        update={
            "version": MANIFEST_VERSION,
            "modules": sorted(manifest.modules, key=lambda m: m.id),
            "rejected": sorted(manifest.rejected, key=lambda r: r.fingerprint),
        }
    ).model_dump(mode="json", exclude_none=True)
    for key in ("mapped_at_commit", "mapped_by"):
        if not payload.get(key):
            payload.pop(key, None)
    for key in ("hints", "suggestions", "labels", "declined", "placements"):
        if not payload.get(key):
            payload.pop(key, None)
    if "labels" in payload:
        payload["labels"] = dict(sorted(payload["labels"].items()))
    if "declined" in payload:
        payload["declined"] = {p: sorted(set(m)) for p, m in sorted(payload["declined"].items())}
    if "placements" in payload:
        payload["placements"] = dict(sorted(payload["placements"].items()))
    for module in payload["modules"]:
        for key in ("description", "color"):
            if not module.get(key):
                module.pop(key, None)
        if not module["evidence"]:
            module.pop("evidence")
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    temporary = path.with_suffix(".yml.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
    return path


def _files_matching(patterns: Iterable[str], files: Sequence[str]) -> set[str]:
    matcher = PathMatcher([("m", list(patterns))])
    return {path for path in files if matcher.module_of(path)}


def _refused(
    proposal: Module,
    rejected: Sequence[RejectedModule],
    rejected_files: Sequence[set[str]],
    files: Sequence[str],
) -> bool:
    """Whether a person already turned this proposal down, or one that covers nearly its files."""
    if any(r.fingerprint == paths_fingerprint(proposal.paths) for r in rejected):
        return True
    mine = _files_matching(proposal.paths, files)
    return any(
        len(mine & theirs) / len(mine | theirs) >= REJECT_REAPPEAR_JACCARD
        for theirs in rejected_files
        if mine | theirs
    )


def merge_proposals(
    manifest: Manifest, proposals: Iterable[Module], files: Sequence[str] = ()
) -> Manifest:
    """Keep every confirmed module as is; replace proposed ones with fresh proposals.

    A proposal a person already rejected stays down: the same paths, or, when ``files`` is given,
    a set of files that overlaps the rejected module's by at least ``REJECT_REAPPEAR_JACCARD``.
    A model proposes different paths on every run, so only the file overlap lets a rejection stick.
    """
    confirmed = [m for m in manifest.modules if m.status is ModuleStatus.CONFIRMED]
    taken = {m.id for m in confirmed}
    rejected_files = [_files_matching(r.paths, files) for r in manifest.rejected] if files else []
    fresh = [
        m
        for m in proposals
        if m.id not in taken and not _refused(m, manifest.rejected, rejected_files, files)
    ]
    merged = [*confirmed, *fresh]
    # A label into a bucket must keep its bucket even when the new map has nothing else for it.
    held = {m.id for m in merged}
    wanted = sorted({t for t in manifest.labels.values() if t in BUCKET_IDS and t not in held})
    return manifest.model_copy(update={"modules": [*merged, *(new_bucket(t) for t in wanted)]})


def membership(manifest: Manifest) -> PathMatcher:
    """Who owns a path: a person's labels first, then the most specific module glob."""
    known = {m.id for m in manifest.modules}
    return PathMatcher(
        ((m.id, m.paths) for m in manifest.modules),
        pinned=(
            (target, [pattern]) for pattern, target in manifest.labels.items() if target in known
        ),
    )


def dangling_labels(manifest: Manifest) -> list[str]:
    """Labels whose module is gone (a re-map replaced it); they place nothing until fixed."""
    known = {m.id for m in manifest.modules}
    return sorted(p for p, target in manifest.labels.items() if target not in known)


def reject(manifest: Manifest, module: Module, reason: str = "") -> Manifest:
    """Record a rejection and drop the module from the manifest."""
    entry = RejectedModule(
        fingerprint=paths_fingerprint(module.paths), paths=list(module.paths), reason=reason
    )
    kept = [m for m in manifest.modules if m.id != module.id]
    others = [r for r in manifest.rejected if r.fingerprint != entry.fingerprint]
    return manifest.model_copy(update={"modules": kept, "rejected": [*others, entry]})
