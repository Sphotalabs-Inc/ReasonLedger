"""Which tier a path belongs to, frontend or backend, decided from folder names alone."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import PurePosixPath

from reasonledger_core.modules.config import BACKEND_DIRS, FRONTEND_DIRS, TIER_DOMINANCE_SHARE
from reasonledger_core.modules.models import Tier


def _tier_folder(path: str) -> tuple[int, Tier] | None:
    """Position and tier of the first folder on the path whose name marks a tier."""
    for index, part in enumerate(PurePosixPath(path).parts[:-1]):
        name = part.lower()
        if name in FRONTEND_DIRS:
            return index, Tier.FRONTEND
        if name in BACKEND_DIRS:
            return index, Tier.BACKEND
    return None


def _folder_tier(path: str) -> Tier | None:
    found = _tier_folder(path)
    return found[1] if found else None


class Tiers:
    """Tier lookup for one repo. A repo with only one tier's folders has no tiers at all.

    A Java ``web`` package or a lone ``client`` folder does not make a frontend: both tiers
    must be present before either is believed.
    """

    def __init__(self, files: Iterable[str]) -> None:
        self.enabled = {_folder_tier(p) for p in files} >= {Tier.FRONTEND, Tier.BACKEND}

    def of(self, path: str) -> Tier | None:
        return _folder_tier(path) if self.enabled else None

    def at_root(self, path: str) -> bool:
        """Whether the file sits directly in its tier's folder, like apps/server/package.json."""
        found = _tier_folder(path) if self.enabled else None
        return found is not None and found[0] == len(PurePosixPath(path).parts) - 2

    def of_files(self, paths: Sequence[str] | set[str]) -> Tier | None:
        """The tier most of the files sit in, or None when no tier holds enough of them."""
        counts = Counter(tier for p in paths if (tier := self.of(p)))
        if not counts:
            return None
        tier, held = counts.most_common(1)[0]
        return tier if held / len(paths) >= TIER_DOMINANCE_SHARE else None
