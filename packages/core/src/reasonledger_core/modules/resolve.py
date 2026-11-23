"""Turn signals into proposed modules: merge agreement, assign each file once, grade confidence."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field

from reasonledger_core.modules.config import (
    BOUNDARY_AGREEMENT_JACCARD,
    CORROBORATION_CONTAINMENT,
    FOUNDATION_DEPENDENT_SHARE,
    FOUNDATION_DEPENDENTS,
    FOUNDATION_MIN_SHARED_COMMITS,
    FOUNDATION_NAME_HINTS,
    MAX_FILES_PER_COMMIT,
    MIN_MODULE_FILES,
    MIN_REMAINDER_SHARE,
    PLATFORM_MODULE_IDS,
)
from reasonledger_core.modules.globs import compress_paths
from reasonledger_core.modules.models import (
    SIGNAL_PRIORITY,
    SINGLE_SIGNAL_MEDIUM,
    Candidate,
    Confidence,
    Module,
    ModuleKind,
    ModuleStatus,
    SignalKind,
)
from reasonledger_core.modules.tiers import Tiers
from reasonledger_core.sync.repo import CommitChange

# Which signal wins a contested file: declared, then packages and specs people wrote.
_CLASS: dict[SignalKind, int] = {
    SignalKind.DECLARED: 0,
    SignalKind.WORKSPACE: 1,
    SignalKind.SPECS: 1,
    SignalKind.CONVENTION: 2,
    SignalKind.CODEOWNERS: 2,
    SignalKind.COCHANGE: 3,
    SignalKind.LAYOUT: 4,
    SignalKind.TOOLING: 4,
}
_WEAK_CLASS = 3
_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    return _NON_SLUG.sub("-", name.lower()).strip("-") or "module"


@dataclass
class _Group:
    primary: Candidate
    signals: set[SignalKind] = field(default_factory=set)
    description: str = ""
    extra_files: frozenset[str] = frozenset()

    @property
    def files(self) -> frozenset[str]:
        return self.primary.files | self.extra_files

    @property
    def rank(self) -> int:
        return min(_CLASS[s] for s in self.signals)


def _jaccard(a: Collection[str], b: Collection[str]) -> float:
    union = len(set(a) | set(b))
    return len(set(a) & set(b)) / union if union else 0.0


def _platform_home(groups: Sequence[_Group]) -> _Group | None:
    """The proposed platform module that tooling files belong to, if the scan found one."""
    by_id = {slug(g.primary.id_hint or g.primary.name): g for g in groups}
    return next((by_id[i] for i in PLATFORM_MODULE_IDS if i in by_id), None)


_CORROBORATING = (SignalKind.CONVENTION, SignalKind.COCHANGE, SignalKind.LAYOUT)


def _corroborated(groups: Sequence[_Group], candidate: Candidate) -> _Group | None:
    """A group that already holds nearly all of this candidate's files and outranks it.

    A convention family, co-change cluster or directory that sits inside a module is independent
    evidence for it (it does not widen it), so the module's confidence rises.
    """
    if candidate.signal not in _CORROBORATING or not candidate.files:
        return None
    rank = _CLASS[candidate.signal]
    hosts = [g for g in groups if g.rank < rank]
    best = max(hosts, key=lambda g: len(g.files & candidate.files), default=None)
    if (
        best
        and len(best.files & candidate.files) / len(candidate.files) >= CORROBORATION_CONTAINMENT
    ):
        return best
    return None


def _same_name(groups: Sequence[_Group], candidate: Candidate) -> _Group | None:
    """A group another signal already named like this candidate: one name is one module.

    Two candidates from the same signal stay apart (``one/utils`` and ``two/utils`` are two
    packages); a convention family and a directory with the same name are one feature.
    """
    wanted = slug(candidate.id_hint or candidate.name)
    return next(
        (
            g
            for g in groups
            if candidate.signal not in g.signals
            and slug(g.primary.id_hint or g.primary.name) == wanted
        ),
        None,
    )


def _merge(candidates: Sequence[Candidate]) -> list[_Group]:
    """Candidates whose files mostly coincide are one module with several signals behind it."""
    ordered = sorted(
        candidates,
        key=lambda c: (SIGNAL_PRIORITY.index(c.signal), -len(c.files), c.name),
    )
    groups: list[_Group] = []
    for candidate in ordered:
        home = _platform_home(groups) if candidate.signal is SignalKind.TOOLING else None
        if home is not None:
            home.signals.add(SignalKind.TOOLING)
            home.extra_files = home.extra_files | candidate.files
            continue
        host = _corroborated(groups, candidate)
        if host is not None:
            host.signals.add(candidate.signal)
            continue
        named = _same_name(groups, candidate)
        if named is not None:
            named.signals.add(candidate.signal)
            named.extra_files = named.extra_files | candidate.files
            named.description = named.description or candidate.description
            continue
        best = max(groups, key=lambda g: _jaccard(g.files, candidate.files), default=None)
        if best and _jaccard(best.files, candidate.files) >= BOUNDARY_AGREEMENT_JACCARD:
            best.signals.add(candidate.signal)
            best.description = best.description or candidate.description
        else:
            groups.append(_Group(candidate, {candidate.signal}, candidate.description))
    return groups


def _assign(groups: Sequence[_Group]) -> dict[int, set[str]]:
    """Each file goes to one group: the strongest signal, then the smallest, then by name."""
    claims: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        for path in group.files:
            claims[path].append(index)
    owned: dict[int, set[str]] = defaultdict(set)
    for path, contenders in claims.items():
        winner = min(
            contenders,
            key=lambda i: (groups[i].rank, len(groups[i].files), groups[i].primary.name, i),
        )
        owned[winner].add(path)
    return owned


def _settle(groups: list[_Group]) -> tuple[list[_Group], dict[int, set[str]]]:
    """Dissolve groups that keep too little, then re-assign, until nothing changes."""
    while True:
        owned = _assign(groups)
        kept = [
            (index, group)
            for index, group in enumerate(groups)
            if len(owned.get(index, ())) >= MIN_MODULE_FILES
            and (
                group.rank < _WEAK_CLASS
                or len(owned[index]) >= MIN_REMAINDER_SHARE * len(group.files)
            )
        ]
        if len(kept) == len(groups):
            return groups, owned
        groups = [group for _, group in kept]


def _unique_ids(groups: Sequence[_Group]) -> list[str]:
    taken: Counter[str] = Counter()
    ids: list[str] = []
    for group in groups:
        base = slug(group.primary.id_hint or group.primary.name)
        taken[base] += 1
        ids.append(base if taken[base] == 1 else f"{base}-{taken[base]}")
    return ids


def _dependents(owner: dict[str, str], commits: Sequence[CommitChange]) -> dict[str, int]:
    """For each module, how many other modules' commits routinely touch it as well.

    A foundation is something other modules keep changing alongside; "routinely" is a
    share of the *other* module's commits, so a large module does not look like a base
    just because it is busy.
    """
    touched: Counter[str] = Counter()
    shared: Counter[tuple[str, str]] = Counter()
    for commit in commits:
        if len(commit.files) > MAX_FILES_PER_COMMIT:
            continue
        modules = sorted({owner[f] for f in commit.files if f in owner})
        touched.update(modules)
        for a in modules:
            for b in modules:
                if a != b:
                    shared[(a, b)] += 1  # a's commit also touched b
    dependents: Counter[str] = Counter()
    for (a, b), count in shared.items():
        if (
            count >= FOUNDATION_MIN_SHARED_COMMITS
            and count / touched[a] >= FOUNDATION_DEPENDENT_SHARE
        ):
            dependents[b] += 1
    return dict(dependents)


def _confidence(signals: Collection[SignalKind]) -> Confidence:
    if len(signals) >= 2:
        return Confidence.HIGH
    return Confidence.MEDIUM if next(iter(signals)) in SINGLE_SIGNAL_MEDIUM else Confidence.LOW


def _is_foreign(group: _Group) -> bool:
    """A directory only the layout noticed, carrying its own LICENSE: a project copied in."""
    return group.signals == {SignalKind.LAYOUT} and group.primary.vendored


def resolve_modules(
    candidates: Sequence[Candidate],
    universe: Sequence[str],
    commits: Sequence[CommitChange],
    tiers: Tiers | None = None,
) -> list[Module]:
    """``commits`` are used only to find foundations; pass none to propose them by name alone.

    With ``tiers``, each module records the tier most of its files sit in.
    """
    groups, owned = _settle([g for g in _merge(candidates) if not _is_foreign(g)])
    ids = _unique_ids(groups)
    owner = {path: ids[i] for i, paths in owned.items() for path in paths}
    dependents = _dependents(owner, commits)
    modules: list[Module] = []
    for index, group in enumerate(groups):
        module_id = ids[index]
        evidence = [s.value for s in SIGNAL_PRIORITY if s in group.signals]
        hint = bool(set(module_id.split("-")) & FOUNDATION_NAME_HINTS)
        wide = dependents.get(module_id, 0) >= FOUNDATION_DEPENDENTS
        if hint:
            evidence.append("name-hint")
        if wide:
            evidence.append(f"dependents:{dependents[module_id]}")
        modules.append(
            Module(
                id=module_id,
                name=group.primary.name,
                description=group.description,
                paths=compress_paths(owned[index], universe),
                kind=ModuleKind.FOUNDATION if hint or wide else ModuleKind.FEATURE,
                tier=tiers.of_files(owned[index]) if tiers else None,
                status=ModuleStatus.PROPOSED,
                evidence=evidence,
                confidence=_confidence(group.signals),
            )
        )
    return sorted(modules, key=lambda m: m.id)
