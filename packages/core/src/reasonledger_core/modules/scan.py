"""Scan a repo: read it, gather signals, propose modules. Local, offline, model-free."""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

from reasonledger_core.modules.config import MAX_COMMITS_SCANNED, SQUASH_SUBJECT_SHARE
from reasonledger_core.modules.files import is_support, modelled_files
from reasonledger_core.modules.fold import fold_parts
from reasonledger_core.modules.globs import PathMatcher
from reasonledger_core.modules.manifest import load_manifest
from reasonledger_core.modules.models import (
    Candidate,
    Manifest,
    ModuleStatus,
    ScanResult,
)
from reasonledger_core.modules.resolve import resolve_modules
from reasonledger_core.modules.signals.cochange import cochange_candidates
from reasonledger_core.modules.signals.codeowners import codeowners_candidates
from reasonledger_core.modules.signals.convention import convention_candidates
from reasonledger_core.modules.signals.layout import layout_candidates
from reasonledger_core.modules.signals.specs import spec_candidates
from reasonledger_core.modules.signals.tooling import tooling_candidates
from reasonledger_core.modules.signals.workspace import workspace_candidates
from reasonledger_core.modules.tier_split import drop_tier_containers, split_by_tier
from reasonledger_core.modules.tiers import Tiers
from reasonledger_core.sync.repo import CommitChange, is_shallow, recent_commit_changes

_SQUASH_SUFFIX = ("(#",)


def _history(root: Path, from_git: bool, limitations: list[str]) -> tuple[list[CommitChange], bool]:
    """Recent commits, and whether the history is squash-merged."""
    if not from_git:
        limitations.append(
            "not a git repository: file list is a directory walk (.gitignore is not applied) "
            "and co-change is unavailable"
        )
        return [], False
    commits = recent_commit_changes(root, limit=MAX_COMMITS_SCANNED)
    if commits is None:
        limitations.append(
            "git history could not be read (error or timeout): co-change is unavailable"
        )
        return [], False
    if not commits:
        limitations.append("no commit history yet: co-change is unavailable")
        return [], False
    if is_shallow(root):
        limitations.append(f"shallow clone: co-change sees only the last {len(commits)} commits")
    squashed = sum(1 for c in commits if c.subject.rstrip().endswith(")") and "(#" in c.subject)
    is_squash = squashed / len(commits) >= SQUASH_SUBJECT_SHARE
    if is_squash:
        limitations.append(
            "history is squash-merged: co-change reflects whole pull requests, and foundations "
            "are proposed from names alone (which modules depend on which cannot be seen)"
        )
    return commits, is_squash


def _without(candidates: list[Candidate], claimed: set[str]) -> list[Candidate]:
    if not claimed:
        return candidates
    return [
        Candidate(c.name, c.signal, c.files - claimed, c.id_hint, c.description, c.extras)
        for c in candidates
    ]


def scan_repo(root: Path, *, manifest: Manifest | None = None) -> ScanResult:
    """Propose modules for ``root``; confirmed modules in the manifest are kept as they are."""
    started = time.perf_counter()
    manifest = manifest if manifest is not None else load_manifest(root)
    files, from_git = modelled_files(root)
    limitations: list[str] = []
    commits, is_squash = _history(root, from_git, limitations)

    confirmed = [m for m in manifest.modules if m.status is ModuleStatus.CONFIRMED]
    declared = PathMatcher((m.id, m.paths) for m in confirmed)
    claimed = {path for path in files if declared.module_of(path)}
    free = [path for path in files if path not in claimed]

    tiers = Tiers([p for p in files if not is_support(p)])
    # Split first: a feature found in both tiers is one directory candidate until it is split,
    # and only its backend half sits inside the backend package.
    candidates = drop_tier_containers(
        split_by_tier(
            [
                *workspace_candidates(root, free),
                *spec_candidates(root, free),
                *convention_candidates(free),
                *codeowners_candidates(root, free),
                *layout_candidates(free),
                *tooling_candidates(free),
                *cochange_candidates(commits, [p for p in free if not is_support(p)]),
            ],
            tiers,
        ),
        tiers,
    )
    proposals = fold_parts(
        resolve_modules(candidates, files, [] if is_squash else commits, tiers),
        files,
        tiers,
        taken={m.id for m in confirmed},
    )
    modules = sorted([*confirmed, *proposals], key=lambda m: m.id)

    matcher = PathMatcher((m.id, m.paths) for m in modules)
    counts = Counter(matcher.module_of(path) for path in files)
    unplaced = counts.pop(None, 0)
    support = sum(1 for path in files if is_support(path) and not matcher.module_of(path))
    placed = {module: count for module, count in counts.items() if module is not None}
    return ScanResult(
        modules=modules,
        files_total=len(files),
        files_per_module=dict(sorted(placed.items())),
        unplaced_files=unplaced - support,
        support_files=support,
        commits_scanned=len(commits),
        limitations=limitations,
        seconds=round(time.perf_counter() - started, 3),
    )
