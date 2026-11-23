"""Decision extractor protocol + deterministic replay double (CI: no live LLM).

``Extractor`` is the seam every real adapter (S8: anthropic / openai / local)
slots into. ``ReplayExtractor`` replays recorded output so the whole import
pipeline is provable offline before any model is wired in.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from reasonledger_core.importer.scan import ImportSource


class DecisionCandidate(BaseModel):
    """A decision an extractor believes a document describes.

    ``source_ref`` MUST uniquely locate the decision within the repo (path plus
    heading/anchor). It is the stable key for the record id, so re-import is
    idempotent — a duplicate ref collides by design.
    """

    context: str
    choice: str
    source_ref: str
    alternatives_rejected: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    justifies: list[str] = Field(default_factory=list)
    confidence: str | None = None


@runtime_checkable
class Extractor(Protocol):
    """Extracts candidate decisions from a document."""

    def extract(self, source: ImportSource) -> list[DecisionCandidate]: ...


class ReplayExtractor:
    """Replays recorded extraction output keyed by document path (offline)."""

    def __init__(self, by_path: dict[str, list[DecisionCandidate]]) -> None:
        self._by_path = by_path

    @classmethod
    def from_fixture(cls, fixture_path: Path) -> ReplayExtractor:
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        by_path = {
            path: [DecisionCandidate.model_validate(item) for item in candidates]
            for path, candidates in raw.items()
        }
        return cls(by_path)

    def extract(self, source: ImportSource) -> list[DecisionCandidate]:
        return list(self._by_path.get(source.path, []))
