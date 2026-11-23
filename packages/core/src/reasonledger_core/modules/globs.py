"""Path globs for the manifest: ``*`` within a segment, ``**`` across, longest wins."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Collection, Iterable
from functools import lru_cache

GLOB_CACHE_SIZE = 16_384  # a map holds a few thousand patterns; each is compiled once


@lru_cache(maxsize=GLOB_CACHE_SIZE)
def glob_regex(pattern: str) -> re.Pattern[str]:
    """Compile ``dir/**``, ``a/*.py`` or an exact path. Only ``*``, ``**`` and ``?`` are special."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif char == "*":
            out.append("[^/]*")
            i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    return re.compile("".join(out) + r"\Z")


def specificity(pattern: str) -> tuple[int, int]:
    """Longer literal prefix wins, then the longer pattern: ``a/b/**`` beats ``a/**``."""
    wildcard = min((pattern.find(c) for c in "*?" if c in pattern), default=len(pattern))
    return wildcard, len(pattern)


def _is_literal(pattern: str) -> bool:
    return "*" not in pattern and "?" not in pattern


class _RuleSet:
    """Rules in precedence order: an exact path is looked up, only real globs are matched.

    The order is the one that decides ties: a longer literal prefix, then a longer pattern, then
    the greater module id. An exact path and a glob compete by that same order, so the answer is
    the same as trying every rule in turn, without trying the thousands of exact paths a map
    holds once buckets and labels name files one by one.
    """

    def __init__(self, module_paths: Iterable[tuple[str, Collection[str]]]) -> None:
        ranked = sorted(
            (
                (specificity(pattern), pattern, module_id)
                for module_id, patterns in module_paths
                for pattern in patterns
            ),
            key=lambda rule: (rule[0], rule[2]),
            reverse=True,
        )
        self._exact: dict[str, tuple[int, str]] = {}
        self._globs: list[tuple[int, str, str]] = []
        for rank, (_, pattern, module_id) in enumerate(ranked):
            if _is_literal(pattern):
                self._exact.setdefault(pattern, (rank, module_id))
            else:
                self._globs.append((rank, pattern, module_id))

    def find(self, path: str) -> str | None:
        best = self._exact.get(path)
        for rank, pattern, module_id in self._globs:
            if best is not None and rank > best[0]:
                break
            if glob_regex(pattern).match(path):
                return module_id
        return best[1] if best else None


class PathMatcher:
    """Maps a repo path to the id of the module whose most specific glob matches it.

    ``pinned`` rules (a person's labels) are tried first, whatever their specificity.
    """

    def __init__(
        self,
        module_paths: Iterable[tuple[str, Collection[str]]],
        pinned: Iterable[tuple[str, Collection[str]]] = (),
    ) -> None:
        self._pinned = _RuleSet(pinned)
        self._rules = _RuleSet(module_paths)
        self._seen: dict[str, str | None] = {}

    def module_of(self, path: str) -> str | None:
        if path not in self._seen:
            self._seen[path] = self._pinned.find(path) or self._rules.find(path)
        return self._seen[path]


def ancestors(path: str) -> list[str]:
    """Directories above ``path``, shallowest first: ``a/b/c.py`` -> ``a``, ``a/b``."""
    parts = path.split("/")[:-1]
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def compress_paths(members: Collection[str], universe: Collection[str]) -> list[str]:
    """Express ``members`` as ``dir/**`` where a directory holds only members, else file paths.

    "Only members" is judged against ``universe`` (every modelled file), so a glob never
    claims a file that belongs to a neighbouring module.
    """
    member_set = set(members)
    total = Counter(d for path in universe for d in ancestors(path))
    held = Counter(d for path in member_set for d in ancestors(path))
    full = {d for d, count in held.items() if total[d] == count}
    covered_by: set[str] = set()
    globs: list[str] = []
    for directory in sorted(full, key=lambda d: d.count("/")):
        if any(parent in covered_by for parent in ancestors(directory + "/x")[:-1]):
            continue
        covered_by.add(directory)
        globs.append(f"{directory}/**")
    loose = [p for p in member_set if not any(d in covered_by for d in ancestors(p))]
    return sorted(globs) + sorted(loose)
