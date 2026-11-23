"""Compare who a record says gave a verdict with who committed it. Git only, no network.

A name in a decision file is self-reported. When a verdict arrives in a diff, the author of the
commit that carried it is the independent witness; a mismatch is evidence worth a reviewer's
look, not proof of fraud (squash merges, bots and name variants all differ), so callers decide
whether it blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    DecisionFormatError,
    parse_decision_markdown,
    read_decision_file,
)
from reasonledger_core.models.decision import DecisionFrontmatter
from reasonledger_core.sync.repo import (
    decision_files_changed_since,
    file_at_ref,
    last_author_since,
)

# Frontmatter field naming the person, and the field whose change means that person acted.
_NAMED_FIELDS = (
    ("approved_by", ("oversight", "approved_by")),
    ("confirmed_by", ("confirmed_by",)),
    ("retired_by", ("retired_by",)),
    ("superseded_decided_by", ("superseded_decided_by",)),
)


@dataclass(frozen=True)
class IdentityMismatch:
    decision_id: str
    field: str
    recorded: str
    committer: str

    def describe(self) -> str:
        return (
            f"{self.decision_id}: {self.field} is {self.recorded!r} but the commit that added "
            f"it was authored by {self.committer!r}"
        )


def _same_person(recorded: str, author: str) -> bool:
    return recorded.strip().casefold() == author.strip().casefold()


def _before(root: Path, base: str, filename: str) -> DecisionFrontmatter | None:
    raw = file_at_ref(root, base, f"{DECISIONS_DIR.as_posix()}/{filename}")
    if raw is None:
        return None
    try:
        return parse_decision_markdown(raw).frontmatter
    except DecisionFormatError:
        return None


def identity_mismatches(root: Path, base: str) -> list[IdentityMismatch]:
    """Verdict names added or changed since ``base`` that differ from the committing author.

    Records changed only in the working tree have no commit to compare and are skipped.
    """
    changed = decision_files_changed_since(root, base, DECISIONS_DIR) or {}
    found: list[IdentityMismatch] = []
    for filename, status in sorted(changed.items()):
        path = root / DECISIONS_DIR / filename
        if status == "D" or not path.is_file():
            continue
        now = read_decision_file(path).frontmatter
        before = _before(root, base, filename)
        author = last_author_since(root, base, f"{DECISIONS_DIR.as_posix()}/{filename}")
        if author is None:
            continue
        for name_field, watched in _NAMED_FIELDS:
            recorded = getattr(now, name_field)
            moved = before is None or any(getattr(now, f) != getattr(before, f) for f in watched)
            if recorded and moved and not _same_person(recorded, author):
                found.append(IdentityMismatch(now.id, name_field, recorded, author))
    return found
