"""Validate a proposed module map in code. Nothing a model or agent says is trusted as is."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence

from pydantic import BaseModel

from reasonledger_core.modules.buckets import BUCKET_IDS
from reasonledger_core.modules.config import BROAD_MODULE_SHARE, MIN_MODULE_FILES
from reasonledger_core.modules.globs import PathMatcher, compress_paths, glob_regex
from reasonledger_core.modules.models import Module, ModuleKind, ModuleStatus
from reasonledger_core.modules.tiers import Tiers

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_WILDCARDS = ("*", "?")


class ValidatedMap(BaseModel):
    modules: list[Module]
    placed: int
    total: int
    unplaced: list[str]
    issues: list[str]

    @property
    def coverage(self) -> float:
        return self.placed / self.total if self.total else 0.0


def _slug(name: str) -> str:
    return _NON_SLUG.sub("-", name.lower()).strip("-") or "module"


def _usable_patterns(raw: object, files: set[str], label: str, issues: list[str]) -> list[str]:
    """Patterns that name something real: explicit paths must exist, globs must match a file."""
    keep: list[str] = []
    dropped = 0
    for pattern in raw if isinstance(raw, list) else []:
        if not isinstance(pattern, str) or not pattern.strip():
            continue
        pattern = pattern.strip().removeprefix("./")
        if any(char in pattern for char in _WILDCARDS):
            regex = glob_regex(pattern)
            ok = any(regex.match(f) for f in files)
        else:
            ok = pattern in files
        if ok:
            keep.append(pattern)
        else:
            dropped += 1
    if dropped:
        issues.append(f"{label}: dropped {dropped} path(s) that match no file")
    return keep


def matching_files(patterns: object, source_files: Sequence[str]) -> tuple[list[str], list[str]]:
    """Files that usable patterns name, and the issues found while resolving them."""
    issues: list[str] = []
    usable = _usable_patterns(patterns, set(source_files), "paths", issues)
    matcher = PathMatcher([("m", usable)])
    return [f for f in source_files if matcher.module_of(f)], issues


def _unique_id(wanted: str, taken: Counter[str]) -> str:
    base = _slug(wanted)
    taken[base] += 1
    return base if taken[base] == 1 else f"{base}-{taken[base]}"


def validate_map(
    proposed: Sequence[Mapping[str, object]], source_files: Sequence[str], universe: Sequence[str]
) -> ValidatedMap:
    """Resolve, de-duplicate and check a proposal against the real file list.

    ``source_files`` are the files a map must cover; ``universe`` is every modelled file, used
    only to write compact globs (a directory glob never claims a neighbour's file).
    """
    files = set(source_files)
    tiers = Tiers(source_files)
    issues: list[str] = []
    taken: Counter[str] = Counter(dict.fromkeys(BUCKET_IDS, 1))  # buckets own their ids
    staged: list[tuple[str, Mapping[str, object], list[str]]] = []
    for entry in proposed:
        name = str(entry.get("name") or entry.get("id") or "")
        module_id = _unique_id(str(entry.get("id") or name), taken)
        patterns = _usable_patterns(entry.get("paths"), files, module_id, issues)
        if patterns:
            staged.append((module_id, entry, patterns))
        else:
            issues.append(f"{module_id}: dropped, no valid path")
    matcher = PathMatcher((module_id, patterns) for module_id, _, patterns in staged)
    members: dict[str, set[str]] = {module_id: set() for module_id, _, _ in staged}
    for path in source_files:
        owner = matcher.module_of(path)
        if owner:
            members[owner].add(path)
    modules: list[Module] = []
    for module_id, entry, _ in staged:
        owned = members[module_id]
        if len(owned) < MIN_MODULE_FILES:
            issues.append(f"{module_id}: dropped, only {len(owned)} file(s)")
            continue
        if len(owned) > BROAD_MODULE_SHARE * len(files):
            issues.append(f"{module_id}: broad, claims {len(owned)} of {len(files)} source files")
        kind = ModuleKind.FOUNDATION if entry.get("kind") == "foundation" else ModuleKind.FEATURE
        modules.append(
            Module(
                id=module_id,
                name=str(entry.get("name") or module_id),
                description=str(entry.get("description") or ""),
                paths=compress_paths(owned, universe),
                kind=kind,
                tier=tiers.of_files(owned),
                status=ModuleStatus.PROPOSED,
            )
        )
    final = PathMatcher((m.id, m.paths) for m in modules)
    unplaced = [path for path in source_files if final.module_of(path) is None]
    return ValidatedMap(
        modules=sorted(modules, key=lambda m: m.id),
        placed=len(files) - len(unplaced),
        total=len(files),
        unplaced=unplaced,
        issues=issues,
    )
