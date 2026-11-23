"""Build DecisionRecord from record_decision inputs and query stored records."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from reasonledger_core.decisions.fingerprint import fingerprint_loci
from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    DecisionIdError,
    decision_filename,
    parse_decision_markdown,
    read_decision_file,
    render_decision_markdown,
    write_decision_file,
)
from reasonledger_core.decisions.ids import generate_decision_id
from reasonledger_core.decisions.lifecycle import RetireError, mark_superseded, require_in_force
from reasonledger_core.metrics import MetricEvent, emit
from reasonledger_core.models.decision import (
    OUT_OF_FORCE,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    QueryDecisionsInput,
    RecordDecisionInput,
)
from reasonledger_core.privacy.pii_linter import lint_decision_text
from reasonledger_core.repo_files import contained_dir


def build_decision_record(
    inp: RecordDecisionInput, *, recorded_at: datetime | None = None
) -> DecisionRecord:
    decision_id = inp.decision_id or generate_decision_id()
    body = inp.body
    if body is None:
        parts = [f"## Context\n\n{inp.context}", f"## Choice\n\n{inp.choice}"]
        if inp.alternatives_rejected:
            alts = "\n".join(f"- {a}" for a in inp.alternatives_rejected)
            parts.append(f"## Alternatives rejected\n\n{alts}")
        if inp.assumptions:
            assumptions = "\n".join(f"- {a}" for a in inp.assumptions)
            parts.append(f"## Assumptions\n\n{assumptions}")
        body = "\n\n".join(parts)
    frontmatter = DecisionFrontmatter(
        id=decision_id,
        ai_tool=inp.ai_tool,
        model=inp.model,
        oversight=inp.resolved_oversight,
        proposed_by=inp.proposed_by,
        approved_by=inp.approved_by,
        approved_at=recorded_at if inp.approved_by else None,
        recorded_at=recorded_at,
        supersedes=inp.supersedes,
        justifies=list(inp.justifies),
        watchers=list(inp.watchers),
        confidence=inp.confidence,
        context=inp.context,
        choice=inp.choice,
        alternatives_rejected=list(inp.alternatives_rejected),
        assumptions=list(inp.assumptions),
    )
    record = DecisionRecord(frontmatter=frontmatter, body=body)
    lint_decision_text(record)
    return record


def record_decision_to_path(
    inp: RecordDecisionInput,
    *,
    root: Path,
    decisions_dir: Path | None = None,
    recorded_at: datetime | None = None,
) -> tuple[DecisionRecord, Path]:
    """Write a new record; one naming ``supersedes`` replaces that decision only once approved.

    The old decision stays in force and authoritative while the replacement is pending
    (``approve_decision`` completes the swap). An existing file is never overwritten.
    """
    record = build_decision_record(inp, recorded_at=recorded_at)
    record.frontmatter.anchor_hashes = fingerprint_loci(root, record.frontmatter.justifies)
    target_dir = contained_dir(root, decisions_dir or DECISIONS_DIR)
    path = target_dir / decision_filename(record.frontmatter.id)
    if path.exists():
        raise DecisionIdError(
            f"decision {record.frontmatter.id!r} already exists; ids are never reused"
        )
    if inp.supersedes:
        require_in_force(inp.supersedes, root=root, decisions_dir=decisions_dir)
    write_decision_file(path, record)
    reloaded = read_decision_file(path)
    if render_decision_markdown(reloaded) != render_decision_markdown(record):
        raise ValueError("decision round-trip mismatch after write")
    source = reloaded.frontmatter.source
    emit(
        root,
        MetricEvent.DECISION_RECORDED,
        source=source.value if source is not None else "recorded",
    )
    return reloaded, path


class ApproveError(ValueError):
    """The decision cannot take a human verdict."""


def approve_decision(
    decision_id: str,
    *,
    root: Path,
    verdict: DecisionOversight,
    approved_by: str,
    approved_at: datetime,
    decisions_dir: Path | None = None,
) -> DecisionRecord:
    """Turn a ``pending`` record into a human verdict; the only transition out of pending.

    Approved records are never rewritten here: a verdict is evidence, and changing one
    belongs in a new superseding record.
    """
    if verdict is DecisionOversight.PENDING:
        raise ApproveError("a verdict must be reviewed, modified or rejected")
    approver = approved_by.strip()
    if not approver:
        raise ApproveError("approved_by is required: who reviewed this decision?")
    path = contained_dir(root, decisions_dir or DECISIONS_DIR) / decision_filename(decision_id)
    if not path.is_file():
        raise ApproveError(f"no decision {decision_id!r} in the ledger")
    record = read_decision_file(path)
    current = record.frontmatter.oversight
    if current is not DecisionOversight.PENDING:
        raise ApproveError(f"{decision_id!r} is already {current.value}; only pending can change")
    record.frontmatter.oversight = verdict
    record.frontmatter.approved_by = approver
    record.frontmatter.approved_at = approved_at
    lint_decision_text(record)
    write_decision_file(path, record)
    replaced = record.frontmatter.supersedes
    if replaced and verdict is not DecisionOversight.REJECTED:
        _replace_if_in_force(replaced, root=root, decisions_dir=decisions_dir)
    return record


def _replace_if_in_force(decision_id: str, *, root: Path, decisions_dir: Path | None) -> None:
    """Take the replaced decision out of force; one a person already retired stays as it is."""
    try:
        mark_superseded(decision_id, root=root, decisions_dir=decisions_dir)
    except RetireError:
        return


def _path_matches(locus: str, path_filter: str) -> bool:
    file_part = locus.split(":", 1)[0]
    if path_filter.endswith("/**"):
        prefix = path_filter[:-3]
        return file_part == prefix or file_part.startswith(prefix.rstrip("/") + "/")
    if path_filter.endswith("*"):
        return file_part.startswith(path_filter[:-1])
    return file_part == path_filter or file_part.startswith(path_filter)


def _matches_query(record: DecisionRecord, query: QueryDecisionsInput) -> bool:
    needle = query.query.strip().lower()
    blob = " ".join(
        [
            record.frontmatter.id,
            record.frontmatter.context or "",
            record.frontmatter.choice or "",
            " ".join(record.frontmatter.justifies),
            " ".join(record.frontmatter.alternatives_rejected),
            record.body,
        ]
    ).lower()
    text_ok = not needle or needle in blob
    if not query.paths:
        return text_ok
    path_ok = any(
        _path_matches(locus, path_filter)
        for path_filter in query.paths
        for locus in record.frontmatter.justifies
    )
    return text_ok and path_ok


_NOT_APPROVED = frozenset({DecisionOversight.PENDING, DecisionOversight.REJECTED})


def query_decisions(
    records: Sequence[DecisionRecord],
    query: QueryDecisionsInput,
) -> list[DecisionRecord]:
    return [record for record in records if _matches_query(record, query)]


def superseded_by_map(records: Sequence[DecisionRecord]) -> dict[str, str]:
    """Map an old decision id to the id of the record that supersedes it.

    Two sources: a successor written to replace it names it in ``supersedes``, and a person
    choosing between two existing decisions writes ``superseded_by`` on the one that lost.
    A successor no person has approved (pending or rejected) replaces nothing yet, unless the
    old record already left force (a person's own act, or a record written before this rule).
    """
    left_force = {r.frontmatter.id for r in records if r.frontmatter.status in OUT_OF_FORCE}
    successors = {
        record.frontmatter.supersedes: record.frontmatter.id
        for record in records
        if record.frontmatter.supersedes
        and (
            record.frontmatter.oversight not in _NOT_APPROVED
            or record.frontmatter.supersedes in left_force
        )
    }
    chosen = {
        record.frontmatter.id: record.frontmatter.superseded_by
        for record in records
        if record.frontmatter.superseded_by
    }
    return {**successors, **chosen}


def load_decisions_from_dir(directory: Path) -> list[DecisionRecord]:
    if not directory.is_dir():
        return []
    return [read_decision_file(path) for path in sorted(directory.glob("dec_*.md"))]


def parse_decision_text(raw: str) -> DecisionRecord:
    return parse_decision_markdown(raw)
