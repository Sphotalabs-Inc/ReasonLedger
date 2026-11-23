"""P0-4 S4: extractor protocol + replay double."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.importer.extractor import Extractor, ReplayExtractor
from reasonledger_core.importer.scan import ImportSource

FIXTURE = (
    Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "import" / "extractor_replay.json"
)


@pytest.mark.phase_3
def test_replay_extractor_conforms_to_protocol() -> None:
    assert isinstance(ReplayExtractor({}), Extractor)


@pytest.mark.phase_3
def test_replay_extractor_returns_recorded_candidates() -> None:
    extractor = ReplayExtractor.from_fixture(FIXTURE)
    hits = extractor.extract(ImportSource(path="claude.md", text="..."))
    assert len(hits) == 1
    assert hits[0].choice == "UTC"
    assert hits[0].source_ref == "claude.md#timestamps"
    # A document with no recorded candidates yields nothing.
    assert extractor.extract(ImportSource(path="other.md", text="")) == []
