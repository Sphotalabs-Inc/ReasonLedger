"""Drift: what in the code no module accounts for, and which unplaced files look like a new module.

No model is involved. Files under an existing module's globs need nothing; only the files nothing
claims are reported, and code (not the model) decides whether they are enough for a new module.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from pydantic import BaseModel

from reasonledger_core.modules.config import GENERIC_PREFIXES, GENERIC_SEGMENTS, MIN_MODULE_FILES
from reasonledger_core.modules.manifest import membership
from reasonledger_core.modules.models import Manifest, ModuleKind
from reasonledger_core.modules.signals.convention import convention_candidates
from reasonledger_core.sync.repo import changed_paths_since

_WORDS = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")


class NewModuleGroup(BaseModel):
    name: str
    files: list[str]
    reason: str


class DriftReport(BaseModel):
    total: int
    unplaced: list[str]
    orphans: list[str]
    groups: list[NewModuleGroup]
    new_since_map: list[str]
    mapped_at_commit: str | None = None

    @property
    def unplaced_share(self) -> float:
        return len(self.unplaced) / self.total if self.total else 0.0


def lead_word(name: str) -> str:
    stem = PurePosixPath(name).name.split(".")[0]
    words = _WORDS.findall(stem)
    return words[0].lower() if words else ""


def _folder_label(folder: str) -> str:
    """Name a folder group after the nearest segment that says what it is (web/src -> web)."""
    parts = folder.split("/")
    return next((p for p in reversed(parts) if p.lower() not in GENERIC_SEGMENTS), parts[-1])


def candidate_groups(unplaced: Sequence[str], total: int | None = None) -> list[NewModuleGroup]:
    """Unplaced files that share a name prefix in one folder, then those sharing a folder.

    `total` is the size of the whole source tree: a feature family is judged against it, not
    against the handful of files that happen to be unplaced.
    """
    by_prefix: dict[tuple[str, str], list[str]] = defaultdict(list)
    for path in unplaced:
        lead = lead_word(path)
        if len(lead) >= 3 and lead not in GENERIC_PREFIXES:
            by_prefix[(PurePosixPath(path).parent.as_posix(), lead)].append(path)
    groups: list[NewModuleGroup] = []
    used: set[str] = set()
    for (folder, lead), files in sorted(by_prefix.items()):
        if len(files) >= MIN_MODULE_FILES:
            groups.append(
                NewModuleGroup(
                    name=lead,
                    files=sorted(files),
                    reason=f"{len(files)} files named {lead}_* in {folder}",
                )
            )
            used.update(files)
    by_folder: dict[str, list[str]] = defaultdict(list)
    for path in unplaced:
        if path not in used:
            by_folder[PurePosixPath(path).parent.as_posix()].append(path)
    for folder, files in sorted(by_folder.items()):
        if len(files) >= MIN_MODULE_FILES and folder != ".":
            name = _folder_label(folder)
            groups.append(
                NewModuleGroup(
                    name=name, files=sorted(files), reason=f"{len(files)} files in {folder}"
                )
            )
    claimed = {f for g in groups for f in g.files}
    return _with_families(groups, [p for p in unplaced if p not in claimed], total)


def _with_families(
    groups: list[NewModuleGroup], rest: Sequence[str], total: int | None
) -> list[NewModuleGroup]:
    """Add feature families repeated across layers (user.py, user_routes.py, user_service.py).

    A family with the name of an existing group joins it: the folder of user screens and the
    user model, route and service files are one new module.
    """
    by_name = {g.name: g for g in groups}
    for family in convention_candidates(list(rest), total):
        files = sorted(family.files)
        reason = f"{len(files)} files across {', '.join(family.extras)} named {family.name}"
        if family.name in by_name:
            joined = by_name[family.name]
            joined.files = sorted({*joined.files, *files})
            joined.reason += f"; plus {reason}"
        else:
            by_name[family.name] = NewModuleGroup(name=family.name, files=files, reason=reason)
    return sorted(by_name.values(), key=lambda g: g.name)


def detect_drift(root: Path, manifest: Manifest, source_files: Sequence[str]) -> DriftReport:
    matcher = membership(manifest)
    buckets = {m.id for m in manifest.modules if m.kind is ModuleKind.BUCKET}
    placed: dict[str, int] = {m.id: 0 for m in manifest.modules}
    unplaced: list[str] = []
    bucket_dirs: set[str] = set()
    for path in source_files:
        owner = matcher.module_of(path)
        if owner is None:
            unplaced.append(path)
        else:
            placed[owner] += 1
            if owner in buckets:
                bucket_dirs.add(PurePosixPath(path).parent.as_posix())
    # New files beside bucketed ones are more shared code, not a new capability.
    fresh = [p for p in unplaced if PurePosixPath(p).parent.as_posix() not in bucket_dirs]
    since: list[str] = []
    if manifest.mapped_at_commit:
        changed = changed_paths_since(root, manifest.mapped_at_commit)
        since = [p for p in unplaced if changed and p in set(changed)]
    return DriftReport(
        total=len(source_files),
        unplaced=unplaced,
        orphans=sorted(module for module, count in placed.items() if count == 0),
        groups=candidate_groups(fresh, len(source_files)),
        new_since_map=since,
        mapped_at_commit=manifest.mapped_at_commit,
    )
