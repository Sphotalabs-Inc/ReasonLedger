"""Layer convention: one feature, one name, repeated across model/route/service folders.

Most backends are layered: ``models/promo_code.py``, ``routes/promo_code_routes.py``,
``services/promo_code_service.py``. The folders are the layers; the repeated name is the
feature. Grouping files by that name across at least two layers gives a feature slice
without reading a line of code, in any language that follows the convention (Rails,
Spring, Express, Django, ASP.NET).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import PurePosixPath

from reasonledger_core.modules.config import (
    CONVENTION_MIN_LAYERS,
    GENERIC_STEMS,
    LAYER_DIRS,
    MAX_COMPONENT_SHARE,
    MIN_MODULE_FILES,
    NON_FEATURE_LAYERS,
    STEM_PREFIX_WORDS,
    STEM_SUFFIX_WORDS,
)
from reasonledger_core.modules.files import is_support, is_tooling
from reasonledger_core.modules.models import Candidate, SignalKind

_WORDS = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
_INDEX_NAMES = frozenset({"index", "__init__", "mod", "main"})


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def is_layer_name(name: str) -> bool:
    return _singular(name.lower()) in NON_FEATURE_LAYERS


def layer_of(path: str) -> str | None:
    """The nearest enclosing folder that names a layer (``services`` -> ``service``)."""
    for part in reversed(PurePosixPath(path).parts[:-1]):
        name = _singular(part.lower())
        if name in LAYER_DIRS:
            return name
    return None


def stem_of(path: str) -> list[str]:
    """The feature words in a file's name, without layer words: UserService.ts -> ["user"]."""
    posix = PurePosixPath(path)
    base = posix.name.split(".")[0]
    source = posix.parent.name if base.lower() in _INDEX_NAMES else base
    words = [w.lower() for w in _WORDS.findall(source)]
    while len(words) > 1 and words[-1] in STEM_SUFFIX_WORDS:
        words.pop()
    if len(words) > 1 and words[0] in STEM_PREFIX_WORDS:
        words.pop(0)
    if words:
        words[-1] = _singular(words[-1])
    return words


def convention_candidates(files: Sequence[str], total: int | None = None) -> list[Candidate]:
    """Families repeated across layers; `total` is the repo size if `files` is a remainder."""
    families: dict[str, list[str]] = defaultdict(list)
    layers: dict[str, set[str]] = defaultdict(set)
    words: dict[str, list[str]] = {}
    for path in files:
        if is_support(path) or is_tooling(path):
            continue
        layer = layer_of(path)
        stem = stem_of(path)
        key = "".join(stem)
        if layer is None or len(key) < 3 or key in GENERIC_STEMS or stem == [layer]:
            continue
        families[key].append(path)
        layers[key].add(layer)
        words.setdefault(key, stem)
    ceiling = MAX_COMPONENT_SHARE * (total or len(files))
    return [
        Candidate(
            name="-".join(words[key]),
            signal=SignalKind.CONVENTION,
            files=frozenset(members),
            extras=tuple(sorted(layers[key])),
        )
        for key, members in sorted(families.items())
        if len(layers[key]) >= CONVENTION_MIN_LAYERS and MIN_MODULE_FILES <= len(members) <= ceiling
    ]
