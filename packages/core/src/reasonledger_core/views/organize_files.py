"""The file list of the map workbench: one module's files, a page at a time.

Each row carries what helps a person decide where a file belongs: whether they placed it by hand,
how many decisions anchor it, and, where most files beside it sit in another module, a hint.
Everything is computed from the manifest, the files and the decisions: no model is called.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.modules.config import MIN_FOLDER_SIBLINGS, SIBLING_MAJORITY
from reasonledger_core.modules.globs import glob_regex
from reasonledger_core.modules.manifest import membership
from reasonledger_core.modules.models import Manifest, ModuleKind
from reasonledger_core.modules.organize import UNPLACED, decision_counts, files_of, path_filter

PAGE_SIZE = 300  # rows per request; a person narrows with the filter, or loads the next page


class SiblingHint(BaseModel):
    module: str
    name: str
    agree: int  # files beside this one that are in that module
    total: int  # files beside this one


class FileRow(BaseModel):
    path: str
    pinned_by: str | None = None  # the label that places it, when a person did
    decisions: int = 0
    hint: SiblingHint | None = None


class FilePage(BaseModel):
    module: str
    total: int  # files matching the filter
    offset: int
    files: list[FileRow]


def load_records(root: Path) -> list[DecisionRecord]:
    directory = root / DECISIONS_DIR
    return load_decisions_from_dir(directory) if directory.is_dir() else []


def _hint(
    path: str, owner_id: str | None, folder: Counter[str | None], manifest: Manifest
) -> SiblingHint | None:
    """Where most of the files beside this one live, when that is a different module."""
    names = {m.id: m for m in manifest.modules}
    beside = Counter(folder)
    beside[owner_id] -= 1
    total = sum(beside.values())
    if total < MIN_FOLDER_SIBLINGS:
        return None
    candidates = [
        (count, module_id)
        for module_id, count in beside.items()
        if module_id and module_id != owner_id and names[module_id].kind is not ModuleKind.BUCKET
    ]
    if not candidates:
        return None
    count, module_id = max(candidates)
    if count / total <= SIBLING_MAJORITY:
        return None
    return SiblingHint(module=module_id, name=names[module_id].name, agree=count, total=total)


def list_files(
    root: Path,
    manifest: Manifest,
    files: Sequence[str],
    *,
    module: str,
    query: str = "",
    offset: int = 0,
    records: Sequence[DecisionRecord] | None = None,
) -> FilePage | None:
    """One page of a module's files, or ``None`` when there is no such module."""
    if module != UNPLACED and module not in {m.id for m in manifest.modules}:
        return None
    keep = path_filter(query)
    owner = membership(manifest)
    matching = [p for p in files_of(manifest, files, module, owner) if keep(p)]
    page = matching[offset : offset + PAGE_SIZE]
    folders: dict[str, Counter[str | None]] = defaultdict(Counter)
    for path in files:
        folders[path.rpartition("/")[0]][owner.module_of(path)] += 1
    counts = decision_counts(load_records(root) if records is None else records)
    pins = [(glob_regex(pattern), pattern, target) for pattern, target in manifest.labels.items()]
    rows = [
        FileRow(
            path=path,
            pinned_by=next((p for regex, p, t in pins if t == module and regex.match(path)), None),
            decisions=counts.get(path, 0),
            hint=_hint(
                path,
                module if module != UNPLACED else None,
                folders[path.rpartition("/")[0]],
                manifest,
            ),
        )
        for path in page
    ]
    return FilePage(module=module, total=len(matching), offset=offset, files=rows)
