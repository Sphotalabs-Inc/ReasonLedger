"""Orchestrate the model-first mapper: propose, validate, corroborate, refresh, accept."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from reasonledger_core.modules.buckets import bucket_modules
from reasonledger_core.modules.config import CORROBORATION_CONTAINMENT, MIN_MODULE_FILES
from reasonledger_core.modules.digest import build_digest, source_files
from reasonledger_core.modules.drift import DriftReport, detect_drift
from reasonledger_core.modules.files import modelled_files
from reasonledger_core.modules.globs import PathMatcher, compress_paths
from reasonledger_core.modules.llm_mapper import LlmMapper, MapMode
from reasonledger_core.modules.manifest import membership, merge_proposals
from reasonledger_core.modules.mapper_check import ValidatedMap, validate_map
from reasonledger_core.modules.models import (
    Confidence,
    Manifest,
    Module,
    ModuleKind,
    ModuleStatus,
    Suggestion,
)
from reasonledger_core.modules.resolve import slug
from reasonledger_core.modules.scan import scan_repo
from reasonledger_core.modules.tiers import Tiers
from reasonledger_core.sync.repo import head_commit


class MapOutcome(BaseModel):
    validated: ValidatedMap
    mapper: str
    mode: str
    digest_chars: int
    routes: int
    truncated: bool


class RefreshOutcome(BaseModel):
    drift: DriftReport
    new_modules: list[Module]
    suggestions: list[Suggestion]
    unresolved: list[str]


def _members(modules: list[Module], files: list[str]) -> dict[str, set[str]]:
    matcher = PathMatcher((m.id, m.paths) for m in modules)
    owned: dict[str, set[str]] = {m.id: set() for m in modules}
    for path in files:
        owner = matcher.module_of(path)
        if owner:
            owned[owner].add(path)
    return owned


def corroborate(proposed: list[Module], root: Path, files: list[str], by: str) -> list[Module]:
    """Add the S32 signals that independently back a proposal, and grade its confidence.

    A signal backs a proposal when the proposal holds nearly all of that signal's module; the
    proposal itself is never widened. Evidence names who proposed it.
    """
    scanned = [m for m in scan_repo(root, manifest=Manifest()).modules if m.evidence]
    mine = _members(proposed, files)
    theirs = _members(scanned, files)
    graded: list[Module] = []
    for module in proposed:
        backing: set[str] = set()
        for other in scanned:
            held = theirs[other.id]
            if len(held) >= MIN_MODULE_FILES and (
                len(held & mine[module.id]) / len(held) >= CORROBORATION_CONTAINMENT
            ):
                backing.update(e for e in other.evidence if ":" not in e and e != "name-hint")
        confidence = (
            Confidence.HIGH
            if len(backing) >= 2
            else Confidence.MEDIUM
            if backing
            else Confidence.LOW
        )
        graded.append(
            module.model_copy(
                update={"evidence": [f"model:{by}", *sorted(backing)], "confidence": confidence}
            )
        )
    return graded


def propose_map(
    root: Path, mapper: LlmMapper, manifest: Manifest, mode: MapMode = "auto"
) -> MapOutcome:
    digest = build_digest(root, manifest.hints)
    raw = mapper.propose(digest, mode)
    files, _ = modelled_files(root)
    validated = validate_map(raw, digest.source_files, files)
    validated.modules = corroborate(validated.modules, root, list(digest.source_files), mapper.name)
    return MapOutcome(
        validated=validated,
        mapper=mapper.name,
        mode=mapper.default_mode() if mode == "auto" else mode,
        digest_chars=len(digest.text),
        routes=digest.route_count,
        truncated=digest.truncated,
    )


def with_buckets(manifest: Manifest, files: Sequence[str], universe: Sequence[str]) -> Manifest:
    """Put every file no module, label or pending suggestion owns into a bucket.

    A pending suggestion keeps its files out: accepting it later must not leave a file in two
    modules. Buckets that exist grow; a person's labels are never undone.
    """
    owners = membership(manifest)
    pending = PathMatcher([("pending", [p for s in manifest.suggestions for p in s.paths])])
    leftover = [p for p in files if owners.module_of(p) is None and pending.module_of(p) is None]
    if not leftover:
        return manifest
    buckets = bucket_modules(leftover, universe, Tiers(files), manifest.modules)
    replaced = {b.id for b in buckets}
    kept = [m for m in manifest.modules if m.id not in replaced]
    return manifest.model_copy(update={"modules": [*kept, *buckets]})


def bucket_sizes(manifest: Manifest, files: Sequence[str]) -> dict[str, int]:
    """How many source files each bucket holds."""
    owners = membership(manifest)
    buckets = {m.id for m in manifest.modules if m.kind is ModuleKind.BUCKET}
    sizes = Counter(o for p in files if (o := owners.module_of(p)) and o in buckets)
    return dict(sorted(sizes.items()))


def apply_map(manifest: Manifest, modules: list[Module], mapped_by: str, root: Path) -> Manifest:
    """Write proposals; confirmed and rejected entries are untouched (merge_proposals)."""
    universe, _ = modelled_files(root)
    files = source_files(root)
    merged = with_buckets(merge_proposals(manifest, modules, files), files, universe)
    return merged.model_copy(update={"mapped_by": mapped_by, "mapped_at_commit": head_commit(root)})


_WORD = re.compile(r"[a-z0-9]+")


def _stem(word: str) -> str:
    return word[:-1] if word.endswith("s") and len(word) > 3 else word


def _names_agree(group: str, module_id: str, manifest: Manifest) -> bool:
    """Whether a group's name shares a word with the module's id or name."""
    module = next(m for m in manifest.modules if m.id == module_id)
    theirs = {_stem(w) for w in _WORD.findall(f"{module.id} {module.name}".lower())}
    return bool({_stem(w) for w in _WORD.findall(group.lower())} & theirs)


def refresh_map(root: Path, mapper: LlmMapper, manifest: Manifest) -> RefreshOutcome:
    """Send only unplaced files. Code finds the candidate groups; the model places or names them."""
    files = source_files(root)
    drift = detect_drift(root, manifest, files)
    universe, _ = modelled_files(root)
    new_modules: list[Module] = []
    suggestions: list[Suggestion] = []
    handled: set[str] = set()
    tiers = Tiers(files)
    capable = manifest.capabilities  # buckets are never a place a model may put files
    known = {m.id for m in capable}
    if drift.groups and capable:
        by_name = {g.name: g for g in drift.groups}
        for placement in mapper.place_groups(capable, drift.groups):
            group = by_name[placement.group]
            # A model may fold a group into an existing module only when their names agree;
            # otherwise the group is its own proposal. Small models never volunteer "new".
            merge = placement.module in known and _names_agree(
                group.name, placement.module, manifest
            )
            if not merge:
                name = placement.new_module_name or group.name
                new_modules.append(
                    Module(
                        id=slug(name),
                        name=name,
                        paths=compress_paths(group.files, universe),
                        kind=ModuleKind.FEATURE,
                        tier=tiers.of_files(group.files),
                        status=ModuleStatus.PROPOSED,
                        evidence=[f"model:{mapper.name}", "drift"],
                        confidence=Confidence.LOW,
                    )
                )
                handled.update(group.files)
            else:
                suggestions.append(
                    Suggestion(
                        module=placement.module,
                        paths=group.files,
                        reason=group.reason,
                        by=mapper.name,
                    )
                )
                handled.update(group.files)
    loose = [p for p in drift.unplaced if p not in handled]
    if loose and capable:
        listing = "\n".join(f"- {m.id}: {m.description}" for m in capable)
        owned = mapper.assign(listing, [m.id for m in capable], loose)
        for module_id, paths in owned.items():
            suggestions.append(
                Suggestion(
                    module=module_id, paths=sorted(paths), reason="placed by name", by=mapper.name
                )
            )
            handled.update(paths)
    unresolved = [p for p in drift.unplaced if p not in handled]
    return RefreshOutcome(
        drift=drift,
        new_modules=new_modules,
        suggestions=suggestions,
        unresolved=unresolved,
    )


def apply_refresh(
    manifest: Manifest, outcome: RefreshOutcome, mapped_by: str, root: Path
) -> Manifest:
    taken = {m.id for m in manifest.modules}
    added = [m for m in outcome.new_modules if m.id not in taken]
    updated = manifest.model_copy(
        update={
            "modules": [*manifest.modules, *added],
            "suggestions": [*manifest.suggestions, *outcome.suggestions],
            "mapped_by": mapped_by,
            "mapped_at_commit": head_commit(root),
        }
    )
    universe, _ = modelled_files(root)
    return with_buckets(updated, source_files(root), universe)


def accept_suggestions(manifest: Manifest, root: Path, files: list[str]) -> Manifest:
    """A person's explicit step: grow modules by the files suggested for them."""
    universe, _ = modelled_files(root)
    suggested = PathMatcher([("s", [p for s in manifest.suggestions for p in s.paths])])
    moved = {f for f in files if suggested.module_of(f)}  # a bucket gives these up
    modules = []
    for module in manifest.modules:
        extra = [p for s in manifest.suggestions if s.module == module.id for p in s.paths]
        held = _members([module], files)[module.id]
        if module.kind is ModuleKind.BUCKET and held & moved:
            modules.append(
                module.model_copy(update={"paths": compress_paths(held - moved, universe)})
            )
        elif extra:
            modules.append(
                module.model_copy(update={"paths": compress_paths(held | set(extra), universe)})
            )
        else:
            modules.append(module)
    return manifest.model_copy(update={"modules": modules, "suggestions": []})
