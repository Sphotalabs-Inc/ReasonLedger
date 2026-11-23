"""Anchors that survive edits: fingerprint the lines a decision explains, find them again later.

A ``path:START-END`` locus is a raw line range, and it drifts the moment lines are added above
it. At record time we store a truncated hash of the normalised lines (blank lines and trailing
whitespace ignored); at read time, if the stored range no longer hashes the same, a window of
the same number of non-blank lines is slid over the file. Exactly one match means the code
*moved*; none, or several, means the anchor is *lost* and the decision falls back to file level.

A truncated hash is not source code, so AGENTS §7 (never store source) still holds. Nothing here
writes a decision file: reading must never rewrite the ledger.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from reasonledger_core.repo_files import read_repo_text

HASH_PREFIX = "sha256:"
HASH_HEX_CHARS = 16
# A longer block is not slid: the search is quadratic in block size, and a block this big is
# rarely moved intact. Its fingerprint still tells intact from changed.
MAX_SLIDE_LINES = 200
_LINE_LOCUS = re.compile(r"^(?P<path>.+):(?P<start>\d+)(?:-(?P<end>\d+))?$")


class Drift(StrEnum):
    INTACT = "intact"
    MOVED = "moved"
    LOST = "lost"


@dataclass(frozen=True)
class Resolution:
    state: Drift
    start: int
    end: int


def parse_line_locus(locus: str) -> tuple[str, int, int] | None:
    """``(path, start, end)`` for ``path:START-END`` or ``path:LINE``; None for any other locus."""
    if "::" in locus:
        return None
    match = _LINE_LOCUS.match(locus)
    if match is None:
        return None
    start = int(match["start"])
    end = int(match["end"] or start)
    return (match["path"], start, end) if 0 < start <= end else None


def _normalise(lines: Sequence[str]) -> list[str]:
    stripped = (line.rstrip() for line in lines)
    return [line for line in stripped if line.strip()]


def _digest(normalised: Sequence[str]) -> str:
    joined = "\n".join(normalised).encode("utf-8")
    return HASH_PREFIX + hashlib.sha256(joined).hexdigest()[:HASH_HEX_CHARS]


def fingerprint_range(lines: Sequence[str], start: int, end: int) -> str | None:
    """The fingerprint of 1-based inclusive ``start``-``end``; None when it holds no code."""
    normalised = _normalise(lines[start - 1 : end])
    return _digest(normalised) if normalised else None


def read_lines(root: Path, relative: str) -> list[str] | None:
    """The file's lines, or None when it is outside ``root``, missing or not text."""
    text = read_repo_text(root, relative)
    return text.splitlines() if text is not None else None


def fingerprint_loci(root: Path, loci: Sequence[str]) -> dict[str, str] | None:
    """Locus -> fingerprint for every line-range locus whose file can be read, else None."""
    hashes: dict[str, str] = {}
    cache: dict[str, list[str] | None] = {}
    for locus in loci:
        parsed = parse_line_locus(locus)
        if parsed is None:
            continue
        path, start, end = parsed
        if path not in cache:
            cache[path] = read_lines(root, path)
        lines = cache[path]
        digest = fingerprint_range(lines, start, end) if lines is not None else None
        if digest is not None:
            hashes[locus] = digest
    return hashes or None


def resolve_anchor(lines: Sequence[str], start: int, end: int, stored: str) -> Resolution:
    """Where the fingerprinted block is now: where it was, somewhere unique, or nowhere sure."""
    if fingerprint_range(lines, start, end) == stored:
        return Resolution(Drift.INTACT, start, end)
    code = [
        (number, text) for number, line in enumerate(lines, 1) if (text := line.rstrip()).strip()
    ]
    found: set[tuple[int, int]] = set()
    for size in range(min(end - start + 1, MAX_SLIDE_LINES), 0, -1):
        for first in range(len(code) - size + 1):
            window = code[first : first + size]
            if _digest([text for _, text in window]) == stored:
                found.add((window[0][0], window[-1][0]))
    if len(found) == 1:
        ((new_start, new_end),) = found
        return Resolution(Drift.MOVED, new_start, new_end)
    return Resolution(Drift.LOST, start, end)
