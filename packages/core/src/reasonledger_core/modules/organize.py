"""Moving files between modules, as a person does in the map workbench.

A move is a label: it pins the files to the target, outranks every module glob and survives the
next map. These helpers pick the files, say what a move would change before it is made, and offer
to turn a folder-sized move into a rule.
"""

from __future__ import annotations

import posixpath
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.modules.config import RULE_PROMOTION_MIN_LABELS
from reasonledger_core.modules.globs import PathMatcher, glob_regex
from reasonledger_core.modules.labels import label_files, require_target
from reasonledger_core.modules.manifest import membership
from reasonledger_core.modules.models import Manifest
from reasonledger_core.modules.placement import place_decisions
from reasonledger_core.reasoning.why import locus_file

UNPLACED = "_unplaced"  # the pseudo-module of files no module, bucket or label owns
MAX_SHIFTS_LISTED = 20  # decisions named in a preview; the rest are counted


class FolderRule(BaseModel):
    pattern: str  # dir/**
    extra_files: int  # files under it that the move does not already cover
    from_same_owner: int  # of those, held by the module(s) the selection comes from
    from_other_owner: int  # of those, held by some other module, which the rule would take too


class DecisionShift(BaseModel):
    decision_id: str
    before: list[str]  # module ids it belongs to now
    after: list[str]  # module ids it would belong to


class MoveImpact(BaseModel):
    moving: int  # files that would change owner
    already_there: int
    from_modules: dict[str, int]  # current owner (or _unplaced) -> files leaving it
    decisions: list[DecisionShift]  # at most MAX_SHIFTS_LISTED
    decisions_total: int
    rule: FolderRule | None


def path_filter(query: str) -> Callable[[str], bool]:
    """Match a path by substring, or by glob when the query has ``*`` or ``?``."""
    text = query.strip()
    if not text:
        return lambda path: True
    if "*" in text or "?" in text:
        regex = glob_regex(text)
        return lambda path: regex.match(path) is not None
    needle = text.lower()
    return lambda path: needle in path.lower()


def files_of(
    manifest: Manifest, files: Sequence[str], module: str, owner: PathMatcher | None = None
) -> list[str]:
    """The source files a module owns, or the unplaced ones for ``_unplaced``."""
    owner = owner or membership(manifest)
    if module == UNPLACED:
        return [p for p in files if owner.module_of(p) is None]
    return [p for p in files if owner.module_of(p) == module]


def select_files(
    manifest: Manifest,
    files: Sequence[str],
    *,
    paths: Sequence[str] | None = None,
    module: str | None = None,
    query: str = "",
) -> list[str]:
    """Explicit paths (only real source files count), or every file of a module matching a query."""
    if paths is not None:
        real = set(files)
        return [p for p in dict.fromkeys(paths) if p in real]
    if module is None:
        return []
    keep = path_filter(query)
    return [p for p in files_of(manifest, files, module) if keep(p)]


def folder_rule(
    manifest: Manifest, files: Sequence[str], selection: Sequence[str], target: str
) -> FolderRule | None:
    """A ``dir/**`` rule for a selection that shares a folder, with what it would also take."""
    parents = [p.rpartition("/")[0] for p in selection]
    if len(selection) < 2 or not all(parents):
        return None
    common = posixpath.commonpath(parents)
    if not common:
        return None
    owner = membership(manifest)
    chosen = set(selection)
    sources = {owner.module_of(p) for p in selection}
    extra = [
        f
        for f in files
        if f.startswith(common + "/") and f not in chosen and owner.module_of(f) != target
    ]
    same = sum(1 for f in extra if owner.module_of(f) in sources)
    return FolderRule(
        pattern=f"{common}/**",
        extra_files=len(extra),
        from_same_owner=same,
        from_other_owner=len(extra) - same,
    )


def preview_move(
    manifest: Manifest,
    files: Sequence[str],
    selection: Sequence[str],
    target: str,
    records: Sequence[DecisionRecord],
    root: Path,
) -> MoveImpact:
    """What moving ``selection`` into ``target`` would change, without changing anything.

    Raises ``LabelError`` when the target is not a module or bucket.
    """
    owner = membership(manifest)
    moving = [p for p in selection if owner.module_of(p) != target]
    leaving: dict[str, int] = {}
    for path in moving:
        key = owner.module_of(path) or UNPLACED
        leaving[key] = leaving.get(key, 0) + 1
    require_target(manifest, target)
    shifts: list[DecisionShift] = []
    if moving:
        after = label_files(manifest, moving, target, files)[0]
        before_at, after_at = (
            place_decisions(records, manifest, root),
            place_decisions(records, after, root),
        )
        shifts = [
            DecisionShift(decision_id=i, before=before_at[i].modules, after=after_at[i].modules)
            for i in before_at
            if before_at[i].modules != after_at[i].modules
        ]
    return MoveImpact(
        moving=len(moving),
        already_there=len(selection) - len(moving),
        from_modules=dict(sorted(leaving.items())),
        decisions=shifts[:MAX_SHIFTS_LISTED],
        decisions_total=len(shifts),
        rule=folder_rule(manifest, files, selection, target),
    )


def move_labels(
    manifest: Manifest,
    files: Sequence[str],
    selection: Sequence[str],
    target: str,
    *,
    as_rule: bool = False,
) -> tuple[Manifest, int, str]:
    """Pin the selection to ``target``; return the manifest, files moved and what was written.

    With ``as_rule`` the label is the selection's folder glob, so later files in it follow.
    """
    owner = membership(manifest)
    moving = [p for p in selection if owner.module_of(p) != target]
    patterns = moving
    if as_rule:
        rule = folder_rule(manifest, files, selection, target)
        if rule is None:
            raise ValueError("the selection does not share a folder to make a rule of")
        patterns = [rule.pattern]
    if not patterns:
        raise ValueError("nothing to move: every file is already there")
    updated, matched = label_files(manifest, patterns, target, files)
    return updated, len(matched), patterns[0] if as_rule else ""


def decision_counts(records: Sequence[DecisionRecord]) -> Mapping[str, int]:
    """How many decisions anchor each file (any status), for the file list."""
    counts: dict[str, int] = {}
    for record in records:
        for path in {locus_file(locus) for locus in record.frontmatter.justifies}:
            counts[path] = counts.get(path, 0) + 1
    return counts


class RulePromotion(BaseModel):
    pattern: str  # dir/**
    target: str
    labelled: list[str]  # the files a person placed there one by one
    extra_files: int  # other files in the folder that no module owns yet, which the rule takes


def promotion_candidates(manifest: Manifest, files: Sequence[str]) -> list[RulePromotion]:
    """Folders where a person has placed files one by one, with a rule that would say it once.

    Offered only when nothing else in the folder belongs to another module, so the rule changes
    no file that has a home.
    """
    owner = membership(manifest)
    real = set(files)
    by_folder: dict[tuple[str, str], list[str]] = defaultdict(list)
    for pattern, target in manifest.labels.items():
        if pattern in real and owner.module_of(pattern) == target:
            by_folder[(pattern.rpartition("/")[0], target)].append(pattern)
    found: list[RulePromotion] = []
    for (folder, target), paths in sorted(by_folder.items()):
        pattern = f"{folder}/**"
        if not folder or len(paths) < RULE_PROMOTION_MIN_LABELS or pattern in manifest.labels:
            continue
        others = [f for f in files if f.startswith(folder + "/") and f not in set(paths)]
        if any(owner.module_of(f) not in (None, target) for f in others):
            continue
        extra = sum(1 for f in others if owner.module_of(f) is None)
        found.append(
            RulePromotion(pattern=pattern, target=target, labelled=sorted(paths), extra_files=extra)
        )
    return found


def promote_rule(
    manifest: Manifest, files: Sequence[str], pattern: str, target: str
) -> tuple[Manifest, int]:
    """Replace one-by-one labels with a folder rule; return the manifest and the files it covers."""
    updated, matched = label_files(manifest, [pattern], target, files)
    regex = glob_regex(pattern)
    labels = {
        p: t
        for p, t in updated.labels.items()
        if not (t == target and "*" not in p and "?" not in p and regex.match(p))
    }
    return updated.model_copy(update={"labels": labels}), len(matched)


def decline_placement(manifest: Manifest, paths: Sequence[str], module: str) -> Manifest:
    """Remember that these files are not to be suggested for ``module`` again."""
    require_target(manifest, module)
    declined = {p: list(m) for p, m in manifest.declined.items()}
    for path in paths:
        declined[path] = sorted({*declined.get(path, []), module})
    return manifest.model_copy(update={"declined": declined})


def bulk_move(
    manifest: Manifest, files: Sequence[str], moves: Sequence[tuple[Sequence[str], str]]
) -> tuple[Manifest, int]:
    """Several moves as one edit; a move whose files are already there is skipped."""
    total = 0
    for paths, target in moves:
        try:
            manifest, count, _ = move_labels(manifest, files, paths, target)
        except ValueError as exc:
            if "already there" not in str(exc):
                raise
            continue
        total += count
    if not total:
        raise ValueError("nothing to move: every file is already there")
    return manifest, total
