"""Phase 5 — repo_text is screened before it leaves the machine, and the preview is what is sent."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.importer.adapters import build_extractor
from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.extractor import DecisionCandidate, ReplayExtractor
from reasonledger_core.importer.outgoing import HeldSource, preview_repo_text, screen_sources
from reasonledger_core.importer.scan import ImportSource
from reasonledger_core.importer.service import run_import
from reasonledger_core.reasoning import DeterministicEmbedder

WHEN = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
CLEAN = "# Queue\nWe chose Postgres for jobs over Redis, to keep one datastore."
WITH_EMAIL = "# Owners\nAsk ops-lead@example.com before changing the queue."
WITH_KEY = "# Setup\nexport OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz012345"


def _repo(root: Path) -> None:
    (root / "docs").mkdir()
    (root / "docs" / "queue.md").write_text(CLEAN, encoding="utf-8")
    (root / "docs" / "owners.md").write_text(WITH_EMAIL, encoding="utf-8")
    (root / "docs" / "setup.md").write_text(WITH_KEY, encoding="utf-8")


class _Recording:
    """An extractor that finds nothing and remembers which sources reached it."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def extract(self, source: ImportSource) -> list[DecisionCandidate]:
        self.seen.append(source.path)
        return []


@pytest.mark.phase_5
def test_a_source_matching_the_patterns_is_held_whole_and_named_by_rule_only() -> None:
    screened = screen_sources(
        [
            ImportSource(path="docs/queue.md", text=CLEAN),
            ImportSource(path="docs/owners.md", text=WITH_EMAIL),
            ImportSource(path="git:abc123", text=WITH_KEY),
        ]
    )

    assert [source.path for source in screened.sendable] == ["docs/queue.md"]
    assert screened.held == [
        HeldSource(path="docs/owners.md", rules=("email",)),
        HeldSource(path="git:abc123", rules=("api_key",)),
    ]


@pytest.mark.phase_5
def test_import_to_a_model_elsewhere_never_hands_a_held_source_to_the_extractor(
    tmp_path: Path,
) -> None:
    _repo(tmp_path)
    extractor = _Recording()

    report = run_import(
        tmp_path,
        extractor=extractor,
        extracted_by="test",
        extracted_at=WHEN,
        embedder=DeterministicEmbedder(),
        screen_outgoing=True,
    )

    assert extractor.seen == ["docs/queue.md"]
    assert [item.path for item in report.held] == ["docs/owners.md", "docs/setup.md"]


@pytest.mark.phase_5
def test_a_model_on_this_machine_reads_every_source(tmp_path: Path) -> None:
    _repo(tmp_path)
    report = run_import(
        tmp_path,
        extractor=ReplayExtractor({}),
        extracted_by="test",
        extracted_at=WHEN,
        embedder=DeterministicEmbedder(),
    )
    assert report.held == []


@pytest.mark.phase_5
def test_the_preview_sample_is_byte_for_byte_the_message_the_extractor_sends(
    tmp_path: Path,
) -> None:
    _repo(tmp_path)
    sent: list[dict[str, object]] = []

    def capture(
        url: str, payload: dict[str, object], headers: Mapping[str, str], timeout: float
    ) -> dict[str, object]:
        sent.append(payload)
        return {"choices": [{"message": {"role": "assistant", "content": '{"decisions": []}'}}]}

    config = ExtractorConfig(
        provider=ExtractorProvider.OPENAI_COMPATIBLE,
        base_url="https://llm.example.com/v1",
        model="m",
    )
    run_import(
        tmp_path,
        extractor=build_extractor(config, api_key="test-key", http_post=capture),
        extracted_by="test",
        extracted_at=WHEN,
        embedder=DeterministicEmbedder(),
        screen_outgoing=True,
    )
    preview = preview_repo_text(tmp_path)

    assert (preview.docs, preview.commits) == (1, 0)
    assert [item.path for item in preview.held] == ["docs/owners.md", "docs/setup.md"]
    assert preview.sample_path == "docs/queue.md"
    messages = sent[0]["messages"]
    assert isinstance(messages, list)
    user = [m for m in messages if isinstance(m, dict) and m.get("role") == "user"]
    assert user[0]["content"] == preview.sample_message
    assert len(sent) == 1
