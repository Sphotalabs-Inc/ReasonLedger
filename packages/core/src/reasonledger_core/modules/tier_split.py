"""Keep frontend and backend apart when the scan proposes modules.

The signals know nothing about tiers: a spec lists a feature's backend and frontend files
together, a convention family or a co-change cluster spans both, a workspace package named
``client`` holds a whole tier. In a repo that has both tiers this module turns those claims into
what the model-first mapper already produces: ``credits`` for the backend half and
``credits-ui`` for the frontend half, and no module that mixes the two.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from reasonledger_core.modules.config import (
    BACKEND_DIRS,
    CORROBORATION_CONTAINMENT,
    FRONTEND_DIRS,
    LAYOUT_MIN_CHILDREN,
    MIN_MODULE_FILES,
    UI_SUFFIX,
)
from reasonledger_core.modules.models import Candidate, SignalKind, Tier
from reasonledger_core.modules.tiers import Tiers

_TIER_DIR_NAMES = FRONTEND_DIRS | BACKEND_DIRS
_DIRECTORY_SIGNALS = frozenset({SignalKind.WORKSPACE, SignalKind.LAYOUT})


def _is_container(candidate: Candidate) -> bool:
    return candidate.signal in _DIRECTORY_SIGNALS and candidate.name.lower() in _TIER_DIR_NAMES


def _root(container: Candidate) -> tuple[str, ...] | None:
    """The folders down to the directory the container is named after (``apps/client``)."""
    name = container.name.lower()
    for path in sorted(container.files):
        parts = PurePosixPath(path).parts[:-1]
        for index, part in enumerate(parts):
            if part.lower() == name:
                return parts[: index + 1]
    return None


def _is_tier_part(container: Candidate, candidates: Sequence[Candidate]) -> bool:
    """Whether the directory is a tier's own part of the app, not a capability.

    That is a folder nested inside a tier folder (``client/src/components/ui``: a layer), or a
    tier folder with at least a few features inside it.
    """
    root = _root(container)
    if root is None:
        return False
    if any(part.lower() in _TIER_DIR_NAMES for part in root[:-1]):
        return True
    prefix = "/".join(root) + "/"
    inside = sum(
        1
        for other in candidates
        if other is not container
        and not _is_container(other)
        and sum(f.startswith(prefix) for f in other.files)
        >= CORROBORATION_CONTAINMENT * len(other.files)
    )
    return inside >= LAYOUT_MIN_CHILDREN


def drop_tier_containers(candidates: Sequence[Candidate], tiers: Tiers) -> list[Candidate]:
    """A directory named for a tier (apps/client, backend/api) that is a tier's part, not a module.

    As one module it would swallow every file of the tier, and the features inside it could only
    corroborate it. Its files go to those features, or to the tier's shared bucket. A directory
    named for a tier that holds nothing to split (``packages/web`` with a few files) stays one
    module.
    """
    if not tiers.enabled:
        return list(candidates)
    return [c for c in candidates if not (_is_container(c) and _is_tier_part(c, candidates))]


def frontend_id(base: str) -> str:
    """The id of a frontend half: ``credits`` -> ``credits-ui``; ``web`` and ``admin-ui`` stay."""
    lowered = base.lower()
    return base if lowered in FRONTEND_DIRS or lowered.endswith(UI_SUFFIX) else base + UI_SUFFIX


def _frontend_half(candidate: Candidate, files: frozenset[str]) -> Candidate:
    base = candidate.id_hint or candidate.name
    named = frontend_id(base)
    return Candidate(
        name=candidate.name if named == base else f"{candidate.name} UI",
        signal=candidate.signal,
        files=files,
        id_hint=named,
        description=candidate.description,
        extras=candidate.extras,
        vendored=candidate.vendored,
    )


def _split(candidate: Candidate, tiers: Tiers) -> list[Candidate]:
    held: dict[Tier | None, set[str]] = {Tier.FRONTEND: set(), Tier.BACKEND: set(), None: set()}
    for path in candidate.files:
        held[tiers.of(path)].add(path)
    if not held[Tier.FRONTEND] and not held[Tier.BACKEND]:
        return [candidate]
    parts = [tier for tier in (Tier.BACKEND, Tier.FRONTEND) if len(held[tier]) >= MIN_MODULE_FILES]
    if not parts:
        return []  # a few strays from each tier: nothing a person would call a module
    held[parts[0]] |= held[None]  # files outside both tiers (migrations, scripts) go backend-first
    out: list[Candidate] = []
    for tier in parts:
        files = frozenset(held[tier])
        if tier is Tier.FRONTEND:
            out.append(_frontend_half(candidate, files))
        else:
            out.append(
                Candidate(
                    candidate.name,
                    candidate.signal,
                    files,
                    candidate.id_hint,
                    candidate.description,
                    candidate.extras,
                    candidate.vendored,
                )
            )
    return out


def split_by_tier(candidates: Sequence[Candidate], tiers: Tiers) -> list[Candidate]:
    """Every candidate becomes one backend and/or one frontend candidate. No-op without tiers."""
    if not tiers.enabled:
        return list(candidates)
    return [part for c in candidates for part in _split(c, tiers)]
