"""Buckets: where files no capability owns go, chosen by the architecture.

Shared frontend code (app shell, common components, API client) and shared backend helpers are a
layer, not a capability, so they are not modules. They are kept in a bucket instead, apart from
the capability modules, and a person can move any file with a label.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence

from reasonledger_core.modules.config import SHARED_BUCKET_ID, TOOLING_MODULE_ID
from reasonledger_core.modules.files import is_config_file, is_tooling
from reasonledger_core.modules.globs import compress_paths
from reasonledger_core.modules.models import Module, ModuleKind, ModuleStatus, Tier
from reasonledger_core.modules.tiers import Tiers

# bucket id -> its tier. The tooling bucket reuses the id the S32 tooling signal proposes.
_BUCKET_TIERS: dict[str, Tier | None] = {
    TOOLING_MODULE_ID: None,
    SHARED_BUCKET_ID: None,
    **{f"{SHARED_BUCKET_ID}-{tier.value}": tier for tier in Tier},
}
BUCKET_IDS: frozenset[str] = frozenset(_BUCKET_TIERS)


def bucket_of(path: str, tiers: Tiers) -> str:
    """Tooling (build, deploy, maintenance, root and app-root config), else shared code by tier."""
    if is_tooling(path) or "/" not in path or (tiers.at_root(path) and is_config_file(path)):
        return TOOLING_MODULE_ID
    tier = tiers.of(path)
    return f"{SHARED_BUCKET_ID}-{tier.value}" if tier else SHARED_BUCKET_ID


def new_bucket(bucket_id: str, paths: Iterable[str] = ()) -> Module:
    return Module(
        id=bucket_id,
        name=bucket_id.replace("-", " ").capitalize(),
        description="Files no capability owns, placed by the architecture",
        paths=sorted(paths),
        kind=ModuleKind.BUCKET,
        tier=_BUCKET_TIERS[bucket_id],
        status=ModuleStatus.PROPOSED,
    )


def bucket_modules(
    files: Sequence[str], universe: Collection[str], tiers: Tiers, existing: Sequence[Module] = ()
) -> list[Module]:
    """The buckets that hold ``files``; a bucket that already exists grows, it is not replaced."""
    grouped: dict[str, set[str]] = defaultdict(set)
    for path in files:
        grouped[bucket_of(path, tiers)].add(path)
    prior = {m.id: m for m in existing if m.kind is ModuleKind.BUCKET}
    buckets: list[Module] = []
    for bucket_id, members in sorted(grouped.items()):
        old = prior.get(bucket_id)
        paths = {*compress_paths(members, universe), *(old.paths if old else ())}
        buckets.append((old or new_bucket(bucket_id)).model_copy(update={"paths": sorted(paths)}))
    return buckets
