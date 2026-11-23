"""Whether a decision's anchor still points at something.

Only the file part is checked, never the line span: lines move constantly and flagging that would
be noise. A symbol anchor is checked when an extractor exists for the language; the extractors are
conservative (top-level functions and classes only), so a symbol they miss is looked for among every
declared name before it is called missing; when that is unsure too, the anchor is not flagged.
"""

from __future__ import annotations

from pathlib import Path

from reasonledger_core.decisions.fingerprint import (
    Drift,
    parse_line_locus,
    read_lines,
    resolve_anchor,
)
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.reasoning.symbols import declared_names, supports, symbol_exists
from reasonledger_core.repo_files import read_repo_text, resolves_inside

MISSING_FILE = "missing_file"
MISSING_SYMBOL = "missing_symbol"
ANCHOR_MOVED = "anchor_moved"
ANCHOR_LOST = "anchor_lost"


def locus_problem(root: Path, locus: str) -> str | None:
    """``missing_file`` or ``missing_symbol`` when the anchor points at nothing, else ``None``."""
    file_part, separator, symbol = locus.partition("::")
    if not separator:
        file_part = locus.rpartition(":")[0] or locus
    file_part = file_part.strip()
    if not file_part:
        return None
    path = root / file_part
    # A locus that resolves outside the repo names no file in it, wherever it points.
    if not path.exists() or not resolves_inside(root.resolve(), path):
        return MISSING_FILE
    if not separator or not supports(file_part):
        return None
    source = read_repo_text(root, file_part)
    if source is None:
        return None
    if symbol_exists(source, symbol, file_part):
        return None
    declared = declared_names(source, file_part)
    if declared is None or symbol.rpartition(".")[2] in declared:
        return None
    return MISSING_SYMBOL


def drifted_loci(
    root: Path, record: DecisionRecord, lines_cache: dict[str, list[str] | None]
) -> list[tuple[str, str]]:
    """``(locus, anchor_moved | anchor_lost)`` for fingerprinted line anchors that no longer
    hold. Reads each file once through ``lines_cache``; never writes.
    """
    drifted: list[tuple[str, str]] = []
    for locus, stored in (record.frontmatter.anchor_hashes or {}).items():
        parsed = parse_line_locus(locus)
        if parsed is None:
            continue
        path, start, end = parsed
        if path not in lines_cache:
            lines_cache[path] = read_lines(root, path)
        lines = lines_cache[path]
        if lines is None:
            continue  # a missing file is reported as orphaned, not as drift
        state = resolve_anchor(lines, start, end, stored).state
        if state is not Drift.INTACT:
            drifted.append((locus, ANCHOR_MOVED if state is Drift.MOVED else ANCHOR_LOST))
    return drifted
