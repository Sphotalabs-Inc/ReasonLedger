"""What to say when `why` finds nothing at the asked place but the file has decisions elsewhere.

A miss that reads "nothing is recorded" is false when the file holds a decision anchored at
other lines, and a reader who believes it stops trusting `why`. This module finds those
anchors so every surface (CLI, UI, JSON) can name them instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from reasonledger_core.decisions.fingerprint import parse_line_locus, read_lines
from reasonledger_core.models.decision import OUT_OF_FORCE, DecisionRecord
from reasonledger_core.reasoning.symbols import SymbolSpan, extract_symbols, supports

NEARBY_LIMIT = 5
NEARBY_CHOICE_CHARS = 100
WHY_COMMAND = "reasonledger why"
_SYMBOL_SEPARATOR = "::"


@dataclass(frozen=True)
class NearbyAnchor:
    """One decision anchored in the asked file, and the command that would hit it."""

    decision_id: str
    locus: str
    status: str
    choice: str
    command: str
    distance: int | None

    @property
    def in_force(self) -> bool:
        return self.status not in {s.value for s in OUT_OF_FORCE}


@dataclass(frozen=True)
class Nearby:
    """In-force anchors (nearest first, at most ``NEARBY_LIMIT``) and the ones left out."""

    anchors: tuple[NearbyAnchor, ...]
    more: int
    out_of_force: tuple[NearbyAnchor, ...]

    def count_status(self, status: str) -> int:
        return sum(1 for anchor in self.out_of_force if anchor.status == status)


def first_line(text: str, limit: int = NEARBY_CHOICE_CHARS) -> str:
    head = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return head if len(head) <= limit else head[: limit - 1].rstrip() + "…"


def _gap(line: int, start: int, end: int) -> int:
    return 0 if start <= line <= end else min(abs(line - start), abs(line - end))


def _symbol_span(spans: Sequence[SymbolSpan], symbol: str) -> SymbolSpan | None:
    return next((span for span in spans if span.name == symbol), None)


def _describe(
    locus: str, path: str, line: int | None, spans: Sequence[SymbolSpan]
) -> tuple[int | None, str]:
    """(distance from the asked line, command that would hit this anchor)."""
    ranged = parse_line_locus(locus)
    if ranged is not None:
        _, start, end = ranged
        distance = _gap(line, start, end) if line is not None else None
        return distance, f"{WHY_COMMAND} {path}:{start}"
    _, separator, symbol = locus.partition(_SYMBOL_SEPARATOR)
    if separator:
        span = _symbol_span(spans, symbol)
        distance = _gap(line, span.start, span.end) if span and line is not None else None
        return distance, f"{WHY_COMMAND} {locus}"
    return 0, f"{WHY_COMMAND} {path}"


def _anchor_in(
    record: DecisionRecord, path: str, line: int | None, spans: Sequence[SymbolSpan]
) -> NearbyAnchor | None:
    """The record's anchor in ``path`` that is nearest the asked line, if it has one."""
    candidates = [
        (*_describe(locus, path, line, spans), locus)
        for locus in record.frontmatter.justifies
        if locus.partition(_SYMBOL_SEPARATOR)[0] == path or _is_line_locus_of(locus, path)
    ]
    if not candidates:
        return None
    distance, command, locus = min(candidates, key=lambda c: (c[0] is None, c[0] or 0, c[2]))
    return NearbyAnchor(
        decision_id=record.frontmatter.id,
        locus=locus,
        status=record.frontmatter.status.value,
        choice=first_line(record.frontmatter.choice or ""),
        command=command,
        distance=distance,
    )


def _is_line_locus_of(locus: str, path: str) -> bool:
    parsed = parse_line_locus(locus)
    return parsed is not None and parsed[0] == path


def find_nearby(
    records: Sequence[DecisionRecord], path: str, line: int | None, *, root: Path
) -> Nearby:
    """Decisions anchored somewhere in ``path``, nearest the asked ``line`` first."""
    lines = read_lines(root, path)
    spans = extract_symbols("\n".join(lines), path) if lines is not None and supports(path) else []
    found = [a for r in records if (a := _anchor_in(r, path, line, spans)) is not None]
    live = sorted(
        (a for a in found if a.in_force),
        key=lambda a: (a.distance is None, a.distance or 0, a.decision_id),
    )
    gone = sorted((a for a in found if not a.in_force), key=lambda a: a.decision_id)
    return Nearby(
        anchors=tuple(live[:NEARBY_LIMIT]),
        more=max(0, len(live) - NEARBY_LIMIT),
        out_of_force=tuple(gone),
    )


def nearby_payload(nearby: Nearby) -> list[dict[str, str]]:
    """The ``nearby`` list of ``why --json``: in-force entries, then those out of force."""
    return [
        {
            "id": a.decision_id,
            "locus": a.locus,
            "status": a.status,
            "choice": a.choice,
            "command": a.command,
        }
        for a in (*nearby.anchors, *nearby.out_of_force)
    ]
