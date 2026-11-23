"""Where a new file probably belongs, and why.

No model is called. The evidence is what the code can compute from the repo: the files beside the
new one, a name word it shares with a module's files, and the files it changed together with in git
history. Each kind adds to a module's score; two kinds agreeing makes a suggestion "high". Nothing
is applied here: a person accepts, and an accepted placement becomes a label, which is itself
evidence for the next new file.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from reasonledger_core.modules.config import (
    ALTERNATIVE_SCORE_SHARE,
    COCHANGE_WEIGHT,
    GENERIC_PREFIXES,
    MAX_COMMITS_SCANNED,
    MAX_FILES_PER_COMMIT,
    MEDIUM_SCORE,
    MIN_COCHANGE_COMMITS,
    MIN_FOLDER_SIBLINGS,
    NAME_FAMILY_MIN_FILES,
    NAME_FAMILY_SHARE,
    NAME_WEIGHT,
    SIBLING_MAJORITY,
    SIBLING_WEIGHT,
)
from reasonledger_core.modules.drift import lead_word
from reasonledger_core.modules.manifest import membership
from reasonledger_core.modules.models import Confidence, Manifest, Tier
from reasonledger_core.modules.tiers import Tiers
from reasonledger_core.sync.repo import recent_commit_changes

EvidenceKind = Literal["siblings", "name", "cochange"]
_WEIGHT: Mapping[str, float] = {
    "siblings": SIBLING_WEIGHT,
    "name": NAME_WEIGHT,
    "cochange": COCHANGE_WEIGHT,
}
MIN_NAME_WORD = 3  # shorter leading words (f0, ui) say nothing


class Evidence(BaseModel):
    kind: EvidenceKind
    text: str
    strength: float  # 0 to 1: how lopsided the evidence is


class PlacementGroup(BaseModel):
    """New files in one folder that point at one module."""

    module: str
    confidence: Confidence
    files: list[str]
    evidence: list[Evidence]  # of the strongest file; the group shares its folder
    alternative: str | None = None  # a close runner-up, when there is one


class CoChangeIndex(BaseModel):
    """For each file, the other files of every commit it changed in (names only)."""

    commits: dict[str, list[list[str]]] = {}

    def of(self, path: str) -> list[list[str]]:
        return self.commits.get(path, [])


def build_cochange_index(root: Path) -> CoChangeIndex:
    """History as a file -> commits index. Bulk commits (renames, formatters) are left out."""
    changes = recent_commit_changes(root, limit=MAX_COMMITS_SCANNED) or []
    index: dict[str, list[list[str]]] = defaultdict(list)
    for change in changes:
        if len(change.files) > MAX_FILES_PER_COMMIT:
            continue
        for path in change.files:
            index[path].append(list(change.files))
    return CoChangeIndex(commits=dict(index))


def _folder(path: str) -> str:
    return path.rpartition("/")[0]


def _siblings(
    path: str, folders: Mapping[str, Counter[str]], names: Mapping[str, str]
) -> dict[str, Evidence]:
    beside = folders.get(_folder(path), Counter())
    total = sum(beside.values())
    if total < MIN_FOLDER_SIBLINGS:
        return {}
    return {
        module: Evidence(
            kind="siblings",
            text=f"{count} of {total} files beside it are in {names[module]}",
            strength=count / total,
        )
        for module, count in beside.items()
        if count / total > SIBLING_MAJORITY
    }


def _name_family(
    path: str,
    words: Mapping[str, Counter[str]],
    names: Mapping[str, str],
    compatible: Callable[[str], bool],
) -> dict[str, Evidence]:
    """Modules whose files share the new file's leading name word, among those on its side."""
    word = lead_word(path)
    family = Counter({m: n for m, n in words.get(word, Counter()).items() if compatible(m)})
    if not family or len(word) < MIN_NAME_WORD or word in GENERIC_PREFIXES:
        return {}
    total = sum(family.values())
    return {
        module: Evidence(
            kind="name",
            text=f"its name shares '{word}' with {count} files in {names[module]}",
            strength=count / total,
        )
        for module, count in family.items()
        if count >= NAME_FAMILY_MIN_FILES and count / total >= NAME_FAMILY_SHARE
    }


def _cochange(
    path: str, history: CoChangeIndex, owners: Mapping[str, str | None], names: Mapping[str, str]
) -> dict[str, Evidence]:
    commits = history.of(path)
    together: Counter[str] = Counter()
    for files in commits:
        modules = {owners.get(other) for other in files if other != path} - {None}
        together.update(m for m in modules if m)
    return {
        module: Evidence(
            kind="cochange",
            text=f"changed with files of {names[module]} in {count} of {len(commits)} commits",
            strength=count / len(commits),
        )
        for module, count in together.items()
        if count >= MIN_COCHANGE_COMMITS
    }


def _same_tier(file_tier: Tier | None, module_tier: Tier | None) -> bool:
    """Frontend and backend stay apart: a file is never suggested across the two."""
    return file_tier is None or module_tier is None or file_tier is module_tier


def _compatible(
    file_tier: Tier | None, module_tiers: Mapping[str, Tier | None]
) -> Callable[[str], bool]:
    return lambda module: _same_tier(file_tier, module_tiers.get(module))


def _grade(evidence: Sequence[Evidence]) -> tuple[float, Confidence]:
    score = sum(_WEIGHT[e.kind] * e.strength for e in evidence)
    if len({e.kind for e in evidence}) >= 2:
        return score, Confidence.HIGH
    return score, Confidence.MEDIUM if score >= MEDIUM_SCORE else Confidence.LOW


class _Candidate(BaseModel):
    module: str
    score: float
    confidence: Confidence
    evidence: list[Evidence]


def _rank(found: Mapping[str, list[Evidence]]) -> list[_Candidate]:
    ranked = [
        _Candidate(module=m, score=score, confidence=conf, evidence=ev)
        for m, ev in found.items()
        for score, conf in [_grade(ev)]
    ]
    return sorted(ranked, key=lambda c: (-c.score, c.module))


_RANK = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


def suggest_placements(
    manifest: Manifest, files: Sequence[str], history: CoChangeIndex | None = None
) -> tuple[list[PlacementGroup], list[str]]:
    """Groups of unplaced files with a suggested home, best first, and the files with none."""
    owner = membership(manifest)
    owners = {p: owner.module_of(p) for p in files}
    names = {m.id: m.name for m in manifest.modules}
    module_tiers = {m.id: m.tier for m in manifest.modules}
    tiers = Tiers(files)
    folders: dict[str, Counter[str]] = defaultdict(Counter)
    words: dict[str, Counter[str]] = defaultdict(Counter)
    for path, module in owners.items():
        if module:
            folders[_folder(path)][module] += 1
            words[lead_word(path)][module] += 1
    history = history or CoChangeIndex()
    grouped: dict[tuple[str, str], list[tuple[str, _Candidate, str | None]]] = defaultdict(list)
    unsuggested: list[str] = []
    for path in (p for p, module in owners.items() if module is None):
        found: dict[str, list[Evidence]] = defaultdict(list)

        compatible = _compatible(tiers.of(path), module_tiers)
        for evidence in (
            _siblings(path, folders, names),
            _name_family(path, words, names, compatible),
            _cochange(path, history, owners, names),
        ):
            for module, item in evidence.items():
                found[module].append(item)
        declined = set(manifest.declined.get(path, []))
        ranked = _rank({m: ev for m, ev in found.items() if m not in declined and compatible(m)})
        if not ranked:
            unsuggested.append(path)
            continue
        runner = (
            ranked[1].module
            if len(ranked) > 1 and ranked[1].score >= ALTERNATIVE_SCORE_SHARE * ranked[0].score
            else None
        )
        grouped[(ranked[0].module, _folder(path))].append((path, ranked[0], runner))
    groups = []
    for (module, _), members in grouped.items():
        best = max(members, key=lambda m: m[1].score)
        groups.append(
            PlacementGroup(
                module=module,
                confidence=best[1].confidence,
                files=sorted(m[0] for m in members),
                evidence=best[1].evidence,
                alternative=best[2],
            )
        )
    groups.sort(key=lambda g: (_RANK[g.confidence], -len(g.files), g.module, g.files[0]))
    return groups, sorted(unsuggested)
