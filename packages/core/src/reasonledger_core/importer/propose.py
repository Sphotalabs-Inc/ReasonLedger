"""Stage imported decisions for human confirmation — never auto-write the ledger.

Extracted candidates are written as ``proposed`` records to a staging directory.
A human promotes a proposal into the ledger (``confirm_proposed``); only then is
it a ``confirmed`` decision. This is the integrity gate for an evidence product.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    decision_filename,
    read_decision_file,
    render_decision_markdown,
    write_decision_file,
)
from reasonledger_core.decisions.ids import import_decision_id, supersede_decision_id
from reasonledger_core.importer.extractor import DecisionCandidate
from reasonledger_core.importer.scan import COMMIT_PATH_PREFIX
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionSource,
    DecisionStatus,
)
from reasonledger_core.privacy.pii_linter import PiiLintError, lint_decision_text
from reasonledger_core.repo_files import contained_dir

# Proposed records stage here until a human confirms them into DECISIONS_DIR.
PROPOSED_DIR = Path(".reasonledger/proposed")


@dataclass(frozen=True)
class SupersedeProposal:
    """A staged record that would replace an already-confirmed decision."""

    proposal_id: str
    supersedes: str
    source_ref: str


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    skipped_confirmed: int = 0
    superseded: list[SupersedeProposal] = field(default_factory=list)
    skipped_pii: list[str] = field(default_factory=list)
    proposed_ids: list[str] = field(default_factory=list)
    records: list[DecisionRecord] = field(default_factory=list)


class ImportConfirmError(ValueError):
    """Raised when a proposed record cannot be confirmed."""


def _decision_content(record: DecisionRecord) -> str:
    """Canonical key over the fields a re-extraction can legitimately change.

    Deliberately excludes lifecycle and provenance (``status``, ``confirmed_by``,
    ``extracted_at``, ...): a confirmed record always differs from a freshly
    proposed one there, so comparing rendered markdown would report every
    re-import as a change. Serialised rather than compared as a tuple because
    the same key also seeds the superseding record's id.
    """
    fm = record.frontmatter
    return json.dumps(
        {
            "context": fm.context,
            "choice": fm.choice,
            "confidence": fm.confidence,
            "alternatives_rejected": fm.alternatives_rejected,
            "assumptions": fm.assumptions,
            "justifies": fm.justifies,
            "body": record.body,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def build_proposed_record(
    candidate: DecisionCandidate,
    *,
    extracted_by: str,
    extracted_at: datetime,
) -> DecisionRecord:
    """Turn an extracted candidate into a ``proposed`` doc-import record.

    ``decided_at`` is intentionally left unset — a decision found today in an old
    doc was not decided today.
    """
    # Provenance distinguishes a curated doc from a commit message: both are prose,
    # but a reviewer weighs them differently, and the ledger must not blur that.
    source = (
        DecisionSource.COMMIT_IMPORT
        if candidate.source_ref.startswith(COMMIT_PATH_PREFIX)
        else DecisionSource.DOC_IMPORT
    )
    frontmatter = DecisionFrontmatter(
        id=import_decision_id(candidate.source_ref),
        ai_tool=AiTool.NONE,
        oversight=DecisionOversight.PENDING,
        status=DecisionStatus.PROPOSED,
        source=source,
        source_ref=candidate.source_ref,
        extracted_by=extracted_by,
        extracted_at=extracted_at,
        recorded_at=extracted_at,
        justifies=candidate.justifies,
        confidence=candidate.confidence,
        context=candidate.context,
        choice=candidate.choice,
        alternatives_rejected=candidate.alternatives_rejected,
        assumptions=candidate.assumptions,
    )
    return DecisionRecord(frontmatter=frontmatter, body="")


def propose_decisions(
    candidates: Iterable[DecisionCandidate],
    *,
    root: Path,
    extracted_by: str,
    extracted_at: datetime,
    proposed_dir: Path | None = None,
    decisions_dir: Path | None = None,
) -> ImportResult:
    """Write candidates as ``proposed`` records to staging (idempotent).

    Nothing is written to the ledger here; PII-tripping candidates are reported
    and skipped, never written.

    A candidate whose id is already **confirmed** is never re-staged under that
    id. Ids derive from ``source_ref``, so a second import over unchanged docs
    would otherwise resurrect every decision the reviewer already confirmed and
    leave the same id sitting in staging and the ledger at once.

    When the source changed underneath a confirmed decision, the new version is
    staged under its own content-derived id carrying ``supersedes``, so both
    records can coexist: confirming it retires the old one rather than
    overwriting it.
    """
    target_dir = contained_dir(root, proposed_dir or PROPOSED_DIR)
    ledger_dir = contained_dir(root, decisions_dir or DECISIONS_DIR)
    result = ImportResult()

    for candidate in candidates:
        record = build_proposed_record(
            candidate, extracted_by=extracted_by, extracted_at=extracted_at
        )
        try:
            lint_decision_text(record)
        except PiiLintError:
            result.skipped_pii.append(candidate.source_ref)
            continue

        confirmed_path = ledger_dir / decision_filename(record.frontmatter.id)
        if confirmed_path.is_file():
            confirmed_id = record.frontmatter.id
            content_key = _decision_content(record)
            if _decision_content(read_decision_file(confirmed_path)) == content_key:
                result.skipped_confirmed += 1
                continue
            record.frontmatter.id = supersede_decision_id(candidate.source_ref, content_key)
            record.frontmatter.supersedes = confirmed_id
            result.superseded.append(
                SupersedeProposal(
                    proposal_id=record.frontmatter.id,
                    supersedes=confirmed_id,
                    source_ref=candidate.source_ref,
                )
            )

        target_path = target_dir / decision_filename(record.frontmatter.id)
        rendered = render_decision_markdown(record)
        if target_path.is_file():
            if render_decision_markdown(read_decision_file(target_path)) == rendered:
                result.skipped_unchanged += 1
            else:
                write_decision_file(target_path, record)
                result.updated += 1
        else:
            write_decision_file(target_path, record)
            result.created += 1

        result.proposed_ids.append(record.frontmatter.id)
        result.records.append(record)

    return result


def confirm_proposed(
    decision_id: str,
    *,
    root: Path,
    confirmed_by: str,
    confirmed_at: datetime,
    proposed_dir: Path | None = None,
    decisions_dir: Path | None = None,
) -> DecisionRecord:
    """Promote a proposed record into the ledger as ``confirmed`` (human gate)."""
    staging = contained_dir(root, proposed_dir or PROPOSED_DIR)
    ledger = contained_dir(root, decisions_dir or DECISIONS_DIR)
    proposed_path = staging / decision_filename(decision_id)
    if not proposed_path.is_file():
        raise ImportConfirmError(f"no proposed decision {decision_id!r} to confirm")

    record = read_decision_file(proposed_path)
    superseded_id = record.frontmatter.supersedes
    superseded_path = ledger / decision_filename(superseded_id) if superseded_id else None
    if superseded_path is not None and not superseded_path.is_file():
        raise ImportConfirmError(
            f"{decision_id!r} supersedes {superseded_id!r}, which is not in the ledger"
        )

    record.frontmatter.status = DecisionStatus.CONFIRMED
    record.frontmatter.confirmed_by = confirmed_by
    # Confirming is the human verdict the proposal was waiting for.
    record.frontmatter.oversight = DecisionOversight.REVIEWED
    record.frontmatter.approved_by = confirmed_by
    record.frontmatter.approved_at = confirmed_at
    record.frontmatter.confirmed_at = confirmed_at

    # Order matters: the replacement is durable before the old record is retired,
    # so an interrupted confirm can leave two live records but never zero.
    write_decision_file(ledger / decision_filename(decision_id), record)
    if superseded_path is not None:
        replaced = read_decision_file(superseded_path)
        replaced.frontmatter.status = DecisionStatus.SUPERSEDED
        write_decision_file(superseded_path, replaced)
    proposed_path.unlink()
    return record
