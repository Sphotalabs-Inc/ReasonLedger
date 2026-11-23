"""Orchestrate doc import: scan -> extract -> propose -> related-decisions-first report.

Fully deterministic with the replay extractor and committed (or injected) verdicts,
so the whole pipeline is provable offline before any real model (S8) is wired in.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.extractor import Extractor
from reasonledger_core.importer.outgoing import HeldSource, screen_sources
from reasonledger_core.importer.propose import ImportResult, propose_decisions
from reasonledger_core.importer.scan import ImportSource, scan_docs
from reasonledger_core.models.reasoning import Conflict
from reasonledger_core.reasoning.conflict_config import resolve_conflict_embedder
from reasonledger_core.reasoning.embeddings import Embedder
from reasonledger_core.reasoning.related import VerdictSource
from reasonledger_core.reasoning.verdicts import relate_in_repo


@dataclass
class ImportReport:
    """Related decisions first (the payoff), then the extraction/proposal summary.

    ``conflicts`` holds every shortlisted pair; each carries its ``relation``. ``held`` names
    the sources the pre-send check kept on this machine (only when the model is elsewhere).
    """

    conflicts: list[Conflict]
    result: ImportResult
    held: list[HeldSource] = field(default_factory=list)


def run_import(
    root: Path,
    *,
    extractor: Extractor,
    extracted_by: str,
    extracted_at: datetime | None = None,
    verdicts: VerdictSource | None = None,
    embedder: Embedder | None = None,
    only_paths: Collection[str] | None = None,
    extra_sources: Sequence[ImportSource] = (),
    screen_outgoing: bool = False,
) -> ImportReport:
    """Scan docs, stage extracted proposals, and report related decisions first.

    ``only_paths`` restricts the scan to the catch-up delta; related pairs are still
    found against the *whole* ledger, since a decision extracted from one doc
    can contradict one recorded from another. ``extra_sources`` carries prose that
    is not a file in the working tree — commit messages from a catch-up window.
    ``screen_outgoing`` is set when the extractor sends off this machine: a source matching
    the PII/secret patterns is then held back and never reaches the extractor.
    """
    when = extracted_at or datetime.now(UTC)
    active_embedder = embedder or resolve_conflict_embedder(root)

    sources = [*scan_docs(root, only_paths=only_paths), *extra_sources]
    held: list[HeldSource] = []
    if screen_outgoing:
        screened = screen_sources(sources)
        sources, held = screened.sendable, screened.held
    candidates = [candidate for source in sources for candidate in extractor.extract(source)]
    result = propose_decisions(candidates, root=root, extracted_by=extracted_by, extracted_at=when)

    ledger_dir = root / DECISIONS_DIR
    existing = load_decisions_from_dir(ledger_dir) if ledger_dir.is_dir() else []
    conflicts = relate_in_repo(
        root, result.records + existing, embedder=active_embedder, verdicts=verdicts
    )
    return ImportReport(conflicts=conflicts, result=result, held=held)
