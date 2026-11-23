"""Co-change: files that keep changing together in git history belong together."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Sequence
from itertools import combinations
from pathlib import PurePosixPath

from reasonledger_core.modules.config import (
    COCHANGE_EDGE_THRESHOLD,
    COCHANGE_MIN_DIRECTORIES,
    COCHANGE_MIN_FILES,
    MAX_COMPONENT_SHARE,
    MAX_FILES_PER_COMMIT,
    MIN_COCHANGE_COMMITS,
    SCOPE_NAME_SHARE,
)
from reasonledger_core.modules.models import Candidate, SignalKind
from reasonledger_core.sync.repo import CommitChange

_SCOPE = re.compile(r"^\w+\(([^)]+)\)!?:")


def commit_scope(subject: str) -> str | None:
    """The conventional-commit scope: ``feat(core): x`` -> ``core``."""
    found = _SCOPE.match(subject)
    return found.group(1).split(",")[0].strip().lower() if found else None


class _Components:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self._parent.setdefault(item, item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, a: str, b: str) -> None:
        self._parent[self.find(a)] = self.find(b)

    def groups(self) -> list[set[str]]:
        found: dict[str, set[str]] = {}
        for item in list(self._parent):
            found.setdefault(self.find(item), set()).add(item)
        return list(found.values())


def _name(members: Collection[str], scopes: Counter[str], touching: int) -> str:
    """A scope most of the cluster's commits share, else its most common directory."""
    if scopes and touching:
        scope, count = scopes.most_common(1)[0]
        if count / touching >= SCOPE_NAME_SHARE:
            return scope
    dirs = Counter(PurePosixPath(f).parent.as_posix() for f in members)
    return PurePosixPath(dirs.most_common(1)[0][0]).name or "root"


def cochange_candidates(
    commits: Sequence[CommitChange], universe: Collection[str]
) -> list[Candidate]:
    known = set(universe)
    seen: Counter[str] = Counter()
    pairs: Counter[tuple[str, str]] = Counter()
    for commit in commits:
        files = sorted({f for f in commit.files if f in known})
        if not files or len(files) > MAX_FILES_PER_COMMIT:
            continue
        seen.update(files)
        pairs.update(combinations(files, 2))
    components = _Components()
    for (a, b), together in pairs.items():
        if (
            together >= MIN_COCHANGE_COMMITS
            and together / max(seen[a], seen[b]) >= COCHANGE_EDGE_THRESHOLD
        ):
            components.union(a, b)
    ceiling = MAX_COMPONENT_SHARE * len(known)
    groups = sorted(
        (
            g
            for g in components.groups()
            if COCHANGE_MIN_FILES <= len(g) <= ceiling
            and len({PurePosixPath(f).parent for f in g}) >= COCHANGE_MIN_DIRECTORIES
        ),
        key=lambda g: sorted(g)[0],
    )
    owner = {f: index for index, group in enumerate(groups) for f in group}
    scopes: list[Counter[str]] = [Counter() for _ in groups]
    touching = [0] * len(groups)
    for commit in commits:
        if len(commit.files) > MAX_FILES_PER_COMMIT:
            continue
        scope = commit_scope(commit.subject)
        for index in {owner[f] for f in commit.files if f in owner}:
            touching[index] += 1
            if scope:
                scopes[index][scope] += 1
    return [
        Candidate(
            name=_name(group, scopes[i], touching[i]),
            signal=SignalKind.COCHANGE,
            files=frozenset(group),
        )
        for i, group in enumerate(groups)
    ]
