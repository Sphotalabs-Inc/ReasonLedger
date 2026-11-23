"""Fold the parts of one feature back into it.

The layout signal sees every folder of three or more files as a module. Inside a feature that
makes a module of each widget: ``features/editor/components/bubble-menu`` is a part of the editor,
not a capability of the app. The folder tells them apart: a layer folder (components, providers,
hooks) is where a feature keeps its parts, so a layout-only proposal that sits directly in one,
inside a feature folder, is folded into the module named for that feature.

A folder of independent features (``src/core/*``, ``src/features/*``) is not a layer folder and
is left alone, and so are modules another signal also found.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Sequence
from pathlib import PurePosixPath

from reasonledger_core.modules.config import (
    BACKEND_DIRS,
    FOLD_DESCRIBED,
    FOLD_MIN_PARTS,
    FRONTEND_DIRS,
    GENERIC_SEGMENTS,
)
from reasonledger_core.modules.globs import PathMatcher, compress_paths
from reasonledger_core.modules.models import (
    Confidence,
    Module,
    ModuleKind,
    ModuleStatus,
    SignalKind,
    Tier,
)
from reasonledger_core.modules.resolve import slug
from reasonledger_core.modules.signals.convention import is_layer_name
from reasonledger_core.modules.tier_split import frontend_id
from reasonledger_core.modules.tiers import Tiers

_NOT_A_FEATURE = GENERIC_SEGMENTS | FRONTEND_DIRS | BACKEND_DIRS
_Folder = tuple[str, ...]


def _common_folder(paths: Sequence[str]) -> _Folder:
    folders = [PurePosixPath(p).parts[:-1] for p in paths]
    shared: list[str] = []
    for names in zip(*folders, strict=False):
        if len(set(names)) != 1:
            break
        shared.append(names[0])
    return tuple(shared)


def _feature_folder(folder: _Folder) -> _Folder | None:
    """The nearest folder at or above this one that names a feature, not a container or layer."""
    for index in range(len(folder) - 1, -1, -1):
        name = folder[index].lower()
        if name not in _NOT_A_FEATURE and not is_layer_name(name):
            return folder[: index + 1]
    return None


def _part_of(module: Module, paths: Sequence[str]) -> _Folder | None:
    """The feature folder this module is a part of, when it is a layout-only part of one."""
    if module.kind is not ModuleKind.FEATURE or module.status is not ModuleStatus.PROPOSED:
        return None
    if set(module.evidence) - {SignalKind.LAYOUT.value} or not paths:
        return None
    parent = _common_folder(paths)[:-1]
    if not parent or not is_layer_name(parent[-1]):
        return None
    return _feature_folder(parent)


def _described(feature: _Folder, parts: Sequence[Module], owned: dict[str, list[str]]) -> str:
    names = sorted(_common_folder(owned[m.id])[-1] for m in parts)
    shown = ", ".join(names[:FOLD_DESCRIBED])
    more = f" and {len(names) - FOLD_DESCRIBED} more" if len(names) > FOLD_DESCRIBED else ""
    return f"Folders under {'/'.join(feature)}: {shown}{more}"


def fold_parts(
    modules: Sequence[Module],
    files: Sequence[str],
    tiers: Tiers,
    taken: Collection[str] = (),
) -> list[Module]:
    """Fold layout-only parts of a feature into its module, or into a new one of three or more.

    ``taken`` are ids a new module must not reuse (modules a person already confirmed).
    """
    matcher = PathMatcher((m.id, m.paths) for m in modules)
    owned: dict[str, list[str]] = defaultdict(list)
    for path in files:
        if (module_id := matcher.module_of(path)) is not None:
            owned[module_id].append(path)
    groups: dict[tuple[Tier | None, _Folder], list[Module]] = defaultdict(list)
    for module in modules:
        if (feature := _part_of(module, owned[module.id])) is not None:
            groups[(module.tier, feature)].append(module)
    result = {m.id: m for m in modules}
    for (tier, feature), parts in groups.items():
        base = slug(feature[-1])
        target_id = frontend_id(base) if tier is Tier.FRONTEND else base
        target = result.get(target_id)
        if target_id in taken or (target is None and len(parts) < FOLD_MIN_PARTS):
            continue
        if target is not None and (
            target.status is not ModuleStatus.PROPOSED or target.tier is not tier
        ):
            continue
        folded = [m for m in parts if m.id != target_id]
        members = {p for m in [*folded, *([target] if target else [])] for p in owned[m.id]}
        paths = compress_paths(members, files)
        if target is not None:
            result[target_id] = target.model_copy(
                update={"paths": paths, "evidence": [*target.evidence, f"folded:{len(folded)}"]}
            )
        else:
            result[target_id] = Module(
                id=target_id,
                name=feature[-1] if target_id == base else f"{feature[-1]} UI",
                description=_described(feature, folded, owned),
                paths=paths,
                kind=ModuleKind.FEATURE,
                tier=tiers.of_files(members),
                status=ModuleStatus.PROPOSED,
                evidence=[SignalKind.LAYOUT.value, f"folded:{len(folded)}"],
                confidence=Confidence.LOW,
            )
        for module in folded:
            del result[module.id]
    return sorted(result.values(), key=lambda m: m.id)
