"""The inbox of the map workbench: what needs a person's decision, best first.

Four kinds of item: new files with a suggested home, a folder of hand-placed files that could be one
rule, a group of new files that looks like a module of its own, and a proposed module waiting to be
confirmed. Everything comes from the manifest, the files and git history; no model is called, and
nothing here changes anything.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel

from reasonledger_core.modules.config import INBOX_MAX_ITEMS
from reasonledger_core.modules.drift import candidate_groups
from reasonledger_core.modules.manifest import membership
from reasonledger_core.modules.models import Confidence, Manifest
from reasonledger_core.modules.organize import FolderRule, folder_rule, promotion_candidates
from reasonledger_core.modules.review import next_up, pending_queue
from reasonledger_core.modules.suggest import CoChangeIndex, suggest_placements

INBOX_FILES_SHOWN = 30  # files listed on a card; the card still knows all of them
Kind = Literal["place", "new-module", "rule", "proposal"]
_KIND_ORDER: dict[str, int] = {"place": 0, "rule": 1, "new-module": 2, "proposal": 3}
_CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}


class EvidenceView(BaseModel):
    kind: str
    text: str


class InboxItem(BaseModel):
    key: str
    kind: Kind
    confidence: str  # high | medium | low
    title: str
    files: list[str]
    file_count: int
    target: str | None = None  # the module it would go to, or the proposed module itself
    target_name: str | None = None
    alternative: str | None = None
    alternative_name: str | None = None
    name: str | None = None  # a new module's suggested name
    evidence: list[EvidenceView]
    rule: FolderRule | None = None  # a folder rule that moves nothing that has a home


class InboxView(BaseModel):
    items: list[InboxItem]
    total: int  # items before the cap
    counts: dict[str, int]
    unsuggested: int  # new files with no suggestion and no group
    history: bool  # whether git history was there to read for co-change evidence
    proposals_waiting: int = 0  # proposed modules behind the few shown, as in the confirm queue
    high_places: int = 0  # high-confidence suggested homes, whether or not they are listed


def _key(kind: str, target: str | None, files: Sequence[str]) -> str:
    digest = hashlib.sha256("\n".join(sorted(files)).encode("utf-8")).hexdigest()[:8]
    return f"{kind}:{target or ''}:{digest}"


def _order(item: InboxItem) -> tuple[int, int, int, int, str]:
    """A rule offer first (it comes from what the person just did), then by trust, kind and size."""
    return (
        0 if item.kind == "rule" else 1,
        _CONFIDENCE_ORDER[item.confidence],
        _KIND_ORDER[item.kind],
        -item.file_count,
        item.key,
    )


def _place_items(
    manifest: Manifest, files: Sequence[str], history: CoChangeIndex | None
) -> tuple[list[InboxItem], list[str]]:
    names = {m.id: m.name for m in manifest.modules}
    groups, unsuggested = suggest_placements(manifest, files, history)
    items: list[InboxItem] = []
    for group in groups:
        rule = folder_rule(manifest, files, group.files, group.module)
        folder = group.files[0].rpartition("/")[0] or "the repo root"
        plural = "" if len(group.files) == 1 else "s"
        items.append(
            InboxItem(
                key=_key("place", group.module, group.files),
                kind="place",
                confidence=group.confidence.value,
                title=f"{len(group.files)} new file{plural} in {folder}",
                files=group.files,
                file_count=len(group.files),
                target=group.module,
                target_name=names[group.module],
                alternative=group.alternative,
                alternative_name=names.get(group.alternative or ""),
                evidence=[EvidenceView(kind=e.kind, text=e.text) for e in group.evidence],
                rule=rule if rule and rule.from_other_owner == 0 else None,
            )
        )
    return items, unsuggested


def _rule_items(manifest: Manifest, files: Sequence[str]) -> list[InboxItem]:
    names = {m.id: m.name for m in manifest.modules}
    return [
        InboxItem(
            key=_key("rule", p.target, p.labelled),
            kind="rule",
            confidence=Confidence.MEDIUM.value,
            title=f"{len(p.labelled)} files you placed by hand in {p.target}: one rule?",
            files=p.labelled,
            file_count=len(p.labelled),
            target=p.target,
            target_name=names.get(p.target),
            evidence=[
                EvidenceView(kind="rule", text=f"{p.pattern} would say it once"),
                EvidenceView(
                    kind="rule", text=f"{p.extra_files} other file(s) in it have no home yet"
                ),
            ],
            rule=FolderRule(
                pattern=p.pattern, extra_files=p.extra_files, from_same_owner=0, from_other_owner=0
            ),
        )
        for p in promotion_candidates(manifest, files)
    ]


def _file_counts(manifest: Manifest, files: Sequence[str]) -> Counter[str]:
    owner = membership(manifest)
    return Counter(m for p in files if (m := owner.module_of(p)))


def _proposal_items(manifest: Manifest, files: Sequence[str]) -> list[InboxItem]:
    counts = _file_counts(manifest, files)
    return [
        InboxItem(
            key=_key("proposal", module.id, [module.id]),
            kind="proposal",
            confidence=(module.confidence or Confidence.LOW).value,
            title=f"{module.name} is proposed: {counts[module.id]} files",
            files=[],
            file_count=counts[module.id],
            target=module.id,
            target_name=module.name,
            evidence=[
                EvidenceView(
                    kind="proposal", text=f"backed by {', '.join(module.evidence) or 'the mapper'}"
                )
            ],
        )
        for module in next_up(pending_queue(manifest, counts))[0]
    ]


def collect_items(
    manifest: Manifest, files: Sequence[str], history: CoChangeIndex | None = None
) -> tuple[list[InboxItem], int]:
    """Every item with its full file list, best first, and how many new files fit nothing."""
    items, unsuggested = _place_items(manifest, files, history)
    new_modules = candidate_groups(unsuggested, len(files))
    for new in new_modules:
        items.append(
            InboxItem(
                key=_key("new-module", None, new.files),
                kind="new-module",
                confidence=Confidence.LOW.value,
                title=f"{len(new.files)} new files look like a module of their own",
                files=sorted(new.files),
                file_count=len(new.files),
                name=new.name.replace("-", " ").replace("_", " ").title(),
                evidence=[EvidenceView(kind="group", text=new.reason)],
            )
        )
    items += _rule_items(manifest, files) + _proposal_items(manifest, files)
    items.sort(key=_order)
    return items, len(unsuggested) - sum(len(g.files) for g in new_modules)


def inbox_view(
    manifest: Manifest,
    files: Sequence[str],
    history: CoChangeIndex | None = None,
    skipped: Sequence[str] = (),
) -> InboxView:
    """The inbox as the screen shows it: capped, with long file lists shortened."""
    items, left_over = collect_items(manifest, files, history)
    waiting = next_up(pending_queue(manifest, _file_counts(manifest, files)))[1]
    hidden = set(skipped)
    shown = [i for i in items if i.key not in hidden]
    counts: Counter[str] = Counter(i.kind for i in shown)
    return InboxView(
        items=[
            i.model_copy(update={"files": i.files[:INBOX_FILES_SHOWN]})
            for i in shown[:INBOX_MAX_ITEMS]
        ],
        total=len(shown),
        counts=dict(counts),
        unsuggested=left_over,
        proposals_waiting=waiting,
        high_places=sum(1 for i in shown if i.kind == "place" and i.confidence == "high"),
        history=history is not None and bool(history.commits),
    )
