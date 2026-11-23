"""Directory layout: the weakest signal, but the only one a bare repo always has."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from pathlib import PurePosixPath

from reasonledger_core.modules.config import (
    CONTAINER_DIRS,
    GENERIC_SEGMENTS,
    LAYOUT_MAX_DEPTH,
    LAYOUT_MIN_CHILDREN,
    LAYOUT_WRAPPER_SHARE,
    LICENSE_FILE_PATTERN,
    MIN_MODULE_FILES,
    SUBSTRUCTURE_DIRS,
)
from reasonledger_core.modules.files import is_support_name, is_tooling_name
from reasonledger_core.modules.globs import ancestors
from reasonledger_core.modules.models import Candidate, SignalKind
from reasonledger_core.modules.signals.convention import is_layer_name


class _Tree:
    def __init__(self, files: Sequence[str]) -> None:
        self.total = Counter(d for path in files for d in ancestors(path))
        self.direct = Counter(PurePosixPath(path).parent.as_posix() for path in files)
        self.children: dict[str, list[str]] = {}
        for directory in sorted(self.total):
            parent = PurePosixPath(directory).parent.as_posix()
            self.children.setdefault("" if parent == "." else parent, []).append(directory)
        self.direct[""] = self.direct.pop(".", 0)

    def substantial(self, directory: str) -> list[str]:
        return [
            c
            for c in self.children.get(directory, [])
            if self.total[c] >= MIN_MODULE_FILES
            and not is_support_name(PurePosixPath(c).name)
            and not is_tooling_name(PurePosixPath(c).name)
        ]

    def peers(self, directory: str) -> list[str]:
        """Substantial children that can be modules in their own right (not sub-structure)."""
        return [
            c
            for c in self.substantial(directory)
            if PurePosixPath(c).name.lower() not in SUBSTRUCTURE_DIRS
        ]


def _is_wrapper(tree: _Tree, directory: str, kids: list[str]) -> bool:
    """A package directory whose code mostly sits in one child (``frontend`` -> ``src``)."""
    return any(tree.total[k] >= LAYOUT_WRAPPER_SHARE * tree.total[directory] for k in kids)


def _expand(tree: _Tree, directory: str, depth: int) -> list[tuple[str, bool]]:
    """(directory, direct_only) modules: descend through namespaces, stop at the first module.

    A namespace directory that also holds files of its own (a package's ``__init__``,
    ``settings.py``) yields one more module made of just those direct files.
    """
    kids = tree.peers(directory)
    name = _label(directory).lower()
    namespace = (
        directory == ""
        or name in CONTAINER_DIRS
        or len(kids) >= LAYOUT_MIN_CHILDREN
        or tree.direct[directory] < MIN_MODULE_FILES
        or _is_wrapper(tree, directory, kids)
    )
    if not kids or not namespace or depth >= LAYOUT_MAX_DEPTH:
        return [(directory, False)]
    found = [m for kid in kids for m in _expand(tree, kid, depth + 1)]
    own = (
        directory != ""
        and name not in CONTAINER_DIRS
        and tree.direct[directory] >= MIN_MODULE_FILES
    )
    return [*found, (directory, True)] if own else found


_LICENSE = re.compile(LICENSE_FILE_PATTERN, re.IGNORECASE)


def _has_license(files: Sequence[str], directory: str) -> bool:
    """A project copied in keeps its own LICENSE next to its code."""
    prefix = directory + "/"
    return any(
        f.startswith(prefix) and "/" not in f[len(prefix) :] and _LICENSE.match(f[len(prefix) :])
        for f in files
    )


def _label(directory: str) -> str:
    """Name a module after the nearest segment that says what it is, not where it sits."""
    parts = directory.split("/")
    return next((p for p in reversed(parts) if p.lower() not in GENERIC_SEGMENTS), parts[-1])


def layout_candidates(files: Sequence[str]) -> list[Candidate]:
    """Directories that look like modules; same-named ones across layers are one module."""
    tree = _Tree(files)
    by_name: dict[str, list[tuple[str, bool]]] = {}
    for directory, direct_only in (m for m in _expand(tree, "", 0) if m[0]):
        by_name.setdefault(_label(directory).lower(), []).append((directory, direct_only))
    out: list[Candidate] = []
    for name, entries in sorted(by_name.items()):
        if is_layer_name(name):
            continue  # hooks, api, services: a layer of the app, not a feature of it
        directories = [d for d, _ in entries]
        members = frozenset(
            p
            for p in files
            for d, direct_only in entries
            if p.startswith(d + "/") and (not direct_only or "/" not in p[len(d) + 1 :])
        )
        if len(members) >= MIN_MODULE_FILES:
            out.append(
                Candidate(
                    name=name,
                    signal=SignalKind.LAYOUT,
                    files=members,
                    extras=tuple(directories),
                    vendored=all(_has_license(files, d) for d in directories),
                )
            )
    return out
