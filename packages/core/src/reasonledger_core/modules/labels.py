"""Labels: a person puts files into a module or a bucket, and the placement outlives a re-map."""

from __future__ import annotations

from collections.abc import Sequence

from reasonledger_core.modules.buckets import BUCKET_IDS, new_bucket
from reasonledger_core.modules.globs import glob_regex
from reasonledger_core.modules.models import Manifest


class LabelError(ValueError):
    """Raised when a label names nothing real."""


def require_target(manifest: Manifest, target: str) -> set[str]:
    """The ids of the manifest's modules; raises unless ``target`` is one of them or a bucket id."""
    known = {m.id for m in manifest.modules}
    if target not in known and target not in BUCKET_IDS:
        choices = ", ".join(sorted(known | BUCKET_IDS))
        raise LabelError(f"no module or bucket named {target!r}; choose one of: {choices}")
    return known


def label_files(
    manifest: Manifest, patterns: Sequence[str], target: str, files: Sequence[str]
) -> tuple[Manifest, list[str]]:
    """Record ``patterns`` as belonging to ``target``; return the manifest and the files they hit.

    The target is a module in the manifest or any bucket id (an absent bucket is created). A
    label that matches no source file is refused, so a typo cannot pass for a placement.
    """
    known = require_target(manifest, target)
    cleaned = [p.strip().removeprefix("./") for p in patterns if p.strip()]
    if not cleaned:
        raise LabelError("give at least one path or glob to label")
    matched: set[str] = set()
    for pattern in cleaned:
        regex = glob_regex(pattern)
        hits = {f for f in files if regex.match(f)}
        if not hits:
            raise LabelError(f"{pattern}: matches no source file")
        matched |= hits
    modules = manifest.modules if target in known else [*manifest.modules, new_bucket(target)]
    labels = {**manifest.labels, **dict.fromkeys(cleaned, target)}
    return manifest.model_copy(update={"modules": modules, "labels": labels}), sorted(matched)


def folder_pattern(path: str) -> str:
    """The label that claims a file's whole folder (``spec/a.md`` -> ``spec/**``).

    A file at the repo root has no folder to speak for, so it is its own pattern.
    """
    folder = path.rpartition("/")[0]
    return f"{folder}/**" if folder else path
