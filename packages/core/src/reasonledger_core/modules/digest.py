"""The digest a mapper sees: source paths and route path strings. Never file contents.

Paths and HTTP route paths are metadata about the application's shape (spec/14 S41, consent class
``paths`` and ``routes``). Route paths are read from decorator and annotation lines only; no code,
comment or string other than the route itself leaves the machine.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from reasonledger_core.modules.config import (
    DIGEST_MAX_CHARS,
    MAX_ROUTES_IN_DIGEST,
    ROUTE_SCAN_MAX_BYTES,
)
from reasonledger_core.modules.files import is_support, modelled_files
from reasonledger_core.modules.globs import glob_regex
from reasonledger_core.modules.manifest import load_manifest

# Flask/FastAPI decorators, Express calls, Nest and Spring annotations: the path literal only.
_ROUTE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"""@\w+\.route\(\s*['"]([^'"]+)['"](?:\s*,\s*methods\s*=\s*\[([^\]]*)\])?"""),
    re.compile(r"""@\w+\.(get|post|put|patch|delete)\(\s*['"]([^'"]*)['"]""", re.IGNORECASE),
    re.compile(r"""\b(?:router|app)\.(get|post|put|patch|delete)\(\s*['"`]([^'"`]+)['"`]""", re.I),
    re.compile(r"""@(Get|Post|Put|Patch|Delete)Mapping\(\s*(?:value\s*=\s*)?["']([^"']*)["']"""),
    re.compile(r"""@(Get|Post|Put|Patch|Delete)\(\s*['"]([^'"]*)['"]\s*\)"""),
)
_ROUTE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt")


@dataclass(frozen=True)
class Digest:
    text: str
    source_files: tuple[str, ...]
    route_count: int
    truncated: bool


def _named_support(patterns: Iterable[str]) -> Callable[[str], bool]:
    """Whether a support file is one a person's label reaches.

    Only a pattern that itself runs through a support folder counts: ``spec/**`` brings the specs
    in, while ``packages/**`` never pulls in the tests below it.
    """
    rules = [glob_regex(p) for p in patterns if is_support(p)]
    return lambda path: any(rule.match(path) for rule in rules)


def source_files(root: Path) -> list[str]:
    """The files a map covers: modelled files that are not tests, docs or fixtures.

    A scan never proposes those, but a person may label them into a module, and then they count.
    """
    files, _ = modelled_files(root)
    labelled = _named_support(load_manifest(root).labels)
    return [f for f in files if not is_support(f) or labelled(f)]


def labelable_files(root: Path, patterns: Sequence[str]) -> list[str]:
    """What a person's label may claim: the map's files, and support files ``patterns`` name."""
    files, _ = modelled_files(root)
    wanted = _named_support([*load_manifest(root).labels, *patterns])
    return [f for f in files if not is_support(f) or wanted(f)]


def _method_and_path(groups: tuple[str, ...]) -> str:
    if (
        len(groups) == 2
        and groups[1]
        and groups[0].lower()
        in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
        }
    ):
        return f"{groups[0].upper()} {groups[1]}"
    path, methods = groups[0], groups[1] if len(groups) > 1 else ""
    verbs = re.sub(r"[\s'\"]", "", methods) or "GET"
    return f"{verbs} {path}"


def extract_routes(root: Path, files: Sequence[str]) -> list[str]:
    """``METHOD /path   [file]`` lines, sorted and unique, capped at ``MAX_ROUTES_IN_DIGEST``."""
    found: set[str] = set()
    for name in files:
        if not name.endswith(_ROUTE_SUFFIXES):
            continue
        path = root / name
        try:
            if path.stat().st_size > ROUTE_SCAN_MAX_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in _ROUTE_PATTERNS:
            for groups in pattern.findall(text):
                parts = groups if isinstance(groups, tuple) else (groups,)
                found.add(f"{_method_and_path(parts)}   [{name.rsplit('/', 1)[-1]}]")
    return sorted(found)[:MAX_ROUTES_IN_DIGEST]


def tree_text(files: Sequence[str]) -> str:
    by_dir: dict[str, list[str]] = defaultdict(list)
    for name in files:
        folder, _, leaf = name.rpartition("/")
        by_dir[folder or "."].append(leaf)
    return "\n".join(f"{d}/: {' '.join(sorted(n))}" for d, n in sorted(by_dir.items()))


def build_digest(root: Path, hints: Sequence[str] = ()) -> Digest:
    files = source_files(root)
    routes = extract_routes(root, files)
    parts = []
    if hints:
        parts.append(
            "MODULES THE OWNER EXPECTS (include each only if the code has it):\n" + ", ".join(hints)
        )
    parts.append("SOURCE FILES (folder: file names)\n" + tree_text(files))
    if routes:
        parts.append("HTTP ROUTES (METHOD path [file])\n" + "\n".join(routes))
    text = "\n\n".join(parts)
    truncated = len(text) > DIGEST_MAX_CHARS
    return Digest(
        text=text[:DIGEST_MAX_CHARS],
        source_files=tuple(files),
        route_count=len(routes),
        truncated=truncated,
    )
