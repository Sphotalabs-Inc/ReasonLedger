"""Taking a ledger decision out of force: retired by a person, or superseded by a successor.

Neither rewrites what the record said or the verdict it was given. A decision that was
approved once and no longer applies stays in the ledger with its approval intact, and gains
who took it out of force, when, and why — the trail has to explain itself.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    decision_filename,
    read_decision_file,
    write_decision_file,
)
from reasonledger_core.models.decision import OUT_OF_FORCE, DecisionRecord, DecisionStatus
from reasonledger_core.privacy.pii_linter import lint_decision_text
from reasonledger_core.repo_files import contained_dir


class RetireError(ValueError):
    """The decision cannot be taken out of force."""


def _in_force(
    decision_id: str, *, root: Path, decisions_dir: Path | None
) -> tuple[Path, DecisionRecord]:
    path = contained_dir(root, decisions_dir or DECISIONS_DIR) / decision_filename(decision_id)
    if not path.is_file():
        raise RetireError(f"no decision {decision_id!r} in the ledger")
    record = read_decision_file(path)
    status = record.frontmatter.status
    if status in OUT_OF_FORCE:
        raise RetireError(f"{decision_id!r} is already {status.value}")
    return path, record


def require_in_force(decision_id: str, *, root: Path, decisions_dir: Path | None = None) -> None:
    """Raise RetireError unless ``decision_id`` is a ledger decision still in force."""
    _in_force(decision_id, root=root, decisions_dir=decisions_dir)


def retire_decision(
    decision_id: str,
    *,
    root: Path,
    retired_by: str,
    retired_at: datetime,
    reason: str,
    decisions_dir: Path | None = None,
) -> DecisionRecord:
    """Mark a decision ``retired``: no longer guidance, and nothing replaces it."""
    who, why = retired_by.strip(), reason.strip()
    if not who:
        raise RetireError("retired_by is required: who is retiring this decision?")
    if not why:
        raise RetireError("a reason is required: why does this decision no longer apply?")
    path, record = _in_force(decision_id, root=root, decisions_dir=decisions_dir)
    record.frontmatter.status = DecisionStatus.RETIRED
    record.frontmatter.retired_by = who
    record.frontmatter.retired_at = retired_at
    record.frontmatter.retired_reason = why
    lint_decision_text(record)
    write_decision_file(path, record)
    return record


def supersede_decision(
    decision_id: str,
    *,
    successor_id: str,
    root: Path,
    decided_by: str,
    superseded_at: datetime,
    reason: str,
    decisions_dir: Path | None = None,
) -> DecisionRecord:
    """Mark a decision ``superseded`` by another already in the ledger: a person chose one.

    Everything is written on the decision that lost. The one that stands is only read, so
    a verdict it already carries stays exactly as it was given.
    """
    who, why = decided_by.strip(), reason.strip()
    if not who:
        raise RetireError("decided_by is required: who chose between these decisions?")
    if not why:
        raise RetireError("a reason is required: why does the other decision stand?")
    if successor_id == decision_id:
        raise RetireError("a decision cannot supersede itself")
    path, record = _in_force(decision_id, root=root, decisions_dir=decisions_dir)
    # Pointing at a decision that is itself out of force would leave no guidance in force.
    require_in_force(successor_id, root=root, decisions_dir=decisions_dir)
    record.frontmatter.status = DecisionStatus.SUPERSEDED
    record.frontmatter.superseded_by = successor_id
    record.frontmatter.superseded_decided_by = who
    record.frontmatter.superseded_at = superseded_at
    record.frontmatter.superseded_reason = why
    lint_decision_text(record)
    write_decision_file(path, record)
    return record


def mark_superseded(
    decision_id: str, *, root: Path, decisions_dir: Path | None = None
) -> DecisionRecord:
    """Mark a decision ``superseded``; its successor names it in ``supersedes``."""
    path, record = _in_force(decision_id, root=root, decisions_dir=decisions_dir)
    record.frontmatter.status = DecisionStatus.SUPERSEDED
    write_decision_file(path, record)
    return record
