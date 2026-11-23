"""`rl why <file:line>` — map a code locus to the decisions that justify it."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from reasonledger_core.decisions.fingerprint import (
    Drift,
    parse_line_locus,
    read_lines,
    resolve_anchor,
)
from reasonledger_core.decisions.service import superseded_by_map
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.reasoning.symbols import symbol_at_line
from reasonledger_core.reasoning.why_nearby import find_nearby, nearby_payload


class WhyQueryError(ValueError):
    """Raised when a why target cannot be parsed."""


class MatchKind(StrEnum):
    """Precision of a `why` match."""

    SYMBOL = "symbol"
    LINE = "line"
    # The anchored code is still in the file, at a different place than the locus says.
    MOVED = "moved"
    FILE = "file"
    # The anchored code can no longer be found; the decision still covers the file.
    LOST = "lost"


# Most to least precise: members of MatchKind in declaration order.
MATCH_ORDER = tuple(MatchKind)


def match_rank(kind: MatchKind) -> int:
    return MATCH_ORDER.index(kind)


@dataclass(frozen=True)
class WhyHit:
    """A decision record and the precision of its match."""

    record: DecisionRecord
    match: MatchKind
    superseded_by: str | None = None


@dataclass(frozen=True)
class WhyTarget:
    path: str
    line: int | None
    symbol: str | None = None


def parse_target(raw: str) -> WhyTarget:
    """Parse ``path``, ``path:line``, or ``path::symbol``."""
    text = raw.strip()
    if not text:
        raise WhyQueryError("empty why target")
    path, symbol_sep, symbol = text.partition("::")
    if symbol_sep:
        return WhyTarget(path=path, line=None, symbol=symbol)
    path, sep, line_part = text.rpartition(":")
    if not sep:
        return WhyTarget(path=text, line=None)
    if line_part.isdigit():
        return WhyTarget(path=path, line=int(line_part))
    # A colon that isn't a line number (e.g. a Windows drive) — treat whole as path.
    return WhyTarget(path=text, line=None)


def _symbol_in_target(lines: list[str] | None, target: WhyTarget) -> str | None:
    if target.line is None or lines is None:
        return None
    return symbol_at_line("\n".join(lines), target.line, target.path)


def _matches_symbol(locus: str, target: WhyTarget, symbol: str | None) -> bool:
    path, separator, locus_symbol = locus.partition("::")
    if not separator or path != target.path:
        return False
    return locus_symbol == (target.symbol or symbol)


def _line_locus_kind(
    locus: str,
    target: WhyTarget,
    stored: str | None,
    lines: list[str] | None,
) -> MatchKind | None:
    """How a ``path:START-END`` locus matches the target, using its fingerprint when it has one."""
    parsed = parse_line_locus(locus)
    if parsed is None or parsed[0] != target.path:
        return None
    _, start, end = parsed
    if stored is not None and lines is not None:
        found = resolve_anchor(lines, start, end, stored)
        if found.state is Drift.LOST:
            return MatchKind.LOST
        start, end = found.start, found.end
        moved = found.state is Drift.MOVED
    else:
        moved = False
    if target.line is not None and not start <= target.line <= end:
        return None
    return MatchKind.MOVED if moved else MatchKind.LINE


def _record_kind(
    record: DecisionRecord, target: WhyTarget, symbol: str | None, lines: list[str] | None
) -> MatchKind | None:
    """The most precise way any of the record's loci matches the target."""
    hashes = record.frontmatter.anchor_hashes or {}
    kinds: list[MatchKind] = []
    for locus in record.frontmatter.justifies:
        if _matches_symbol(locus, target, symbol):
            kinds.append(MatchKind.SYMBOL)
        elif locus == target.path:
            kinds.append(MatchKind.FILE)
        elif (kind := _line_locus_kind(locus, target, hashes.get(locus), lines)) is not None:
            kinds.append(kind)
    return min(kinds, key=match_rank, default=None)


def resolve_why(
    records: Sequence[DecisionRecord],
    target: WhyTarget,
    *,
    root: Path | None = None,
) -> list[WhyHit]:
    """Return decisions whose loci match the target, labelled by match precision.

    The target file is read once, for symbols and for fingerprinted line anchors. Nothing is
    written: a moved anchor is reported, never rewritten into the decision file.
    """
    lines = read_lines(root, target.path) if root is not None else None
    target_symbol = _symbol_in_target(lines, target)
    superseded_map = superseded_by_map(records)
    hits: list[WhyHit] = []
    for record in records:
        kind = _record_kind(record, target, target_symbol, lines)
        if kind is not None:
            hits.append(
                WhyHit(
                    record=record,
                    match=kind,
                    superseded_by=superseded_map.get(record.frontmatter.id),
                )
            )
    hits.sort(key=lambda hit: hit.record.frontmatter.id)
    return hits


def locus_file(locus: str) -> str:
    """The file part of ``path``, ``path:START-END`` or ``path::symbol``."""
    file_part, separator, _ = locus.partition("::")
    if separator:
        return file_part
    head, _, tail = locus.rpartition(":")
    return head if head and tail.partition("-")[0].isdigit() else locus


def target_exists(root: Path, target: WhyTarget) -> bool:
    """Whether the queried path is a file inside ``root``, so a typo is not read as a miss."""
    candidate = (root / target.path).resolve()
    return candidate.is_relative_to(root.resolve()) and candidate.is_file()


def why_payload(
    target_raw: str,
    target: WhyTarget,
    hits: Sequence[WhyHit],
    *,
    root: Path,
    records: Sequence[DecisionRecord] | None = None,
) -> dict[str, object]:
    """The JSON shape `why --json` and the local UI share, so the two cannot drift.

    ``matched_loci`` are the record's anchors in the queried file, so a reader sees
    which part of the code the decision speaks to; ``path_exists`` lets a surface say
    "no such file" apart from "nothing recorded for this file". On a miss in a file that has
    decisions anchored elsewhere, ``nearby`` lists them (given ``records``), so a surface
    never reads as "nothing here" when something is.
    """
    exists = target_exists(root, target)
    near = (
        nearby_payload(find_nearby(records, target.path, target.line, root=root))
        if records is not None and not hits and exists
        else []
    )
    return {
        "target": target_raw,
        "count": len(hits),
        "path_exists": exists,
        "decisions": [
            {
                "id": hit.record.frontmatter.id,
                "status": hit.record.frontmatter.status.value,
                "superseded_by": hit.superseded_by,
                "retired_reason": hit.record.frontmatter.retired_reason,
                "superseded_reason": hit.record.frontmatter.superseded_reason,
                "context": hit.record.frontmatter.context,
                "choice": hit.record.frontmatter.choice,
                "assumptions": hit.record.frontmatter.assumptions,
                "alternatives_rejected": hit.record.frontmatter.alternatives_rejected,
                "oversight": hit.record.frontmatter.oversight.value,
                "proposed_by": (
                    hit.record.frontmatter.proposed_by.value
                    if hit.record.frontmatter.proposed_by
                    else None
                ),
                "justifies": hit.record.frontmatter.justifies,
                "matched_loci": [
                    locus
                    for locus in hit.record.frontmatter.justifies
                    if locus_file(locus) == target.path
                ],
                "match": hit.match.value,
            }
            for hit in hits
        ],
        "nearby": near,
    }
