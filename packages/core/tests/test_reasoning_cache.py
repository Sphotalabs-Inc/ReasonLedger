"""Phase 4 — cached embeddings preserve conflict results."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.reasoning.cache import CACHE_DIR, CachingEmbedder, _key
from reasonledger_core.reasoning.conflicts import StubConflictClassifier, detect_conflicts_among


class CountingEmbedder:
    """Deterministic test embedder that records calls to its inner implementation."""

    model_id = "counting-v1"
    dim = 8

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return [float(value) for value in hashlib.sha256(text.encode()).digest()[: self.dim]]


def _record(index: int) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=f"dec_{index:03}",
            ai_tool=AiTool.CURSOR,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            context=f"Context for subject {index}",
            choice=f"Choice {index}",
        ),
        body="",
    )


@pytest.mark.phase_4
def test_conflict_embedding_calls_are_linear() -> None:
    records = [_record(index) for index in range(50)]
    inner = CountingEmbedder()

    detect_conflicts_among(
        records,
        classifier=StubConflictClassifier(),
        embedder=CachingEmbedder(inner),
    )

    assert inner.calls <= 4 * len(records)


@pytest.mark.phase_4
def test_cached_output_is_identical() -> None:
    records = [_record(index) for index in range(5)]

    uncached = detect_conflicts_among(
        records,
        classifier=StubConflictClassifier(),
        embedder=CountingEmbedder(),
    )
    cached = detect_conflicts_among(
        records,
        classifier=StubConflictClassifier(),
        embedder=CachingEmbedder(CountingEmbedder()),
    )

    assert cached == uncached


@pytest.mark.phase_4
def test_disk_cache_survives_new_instance(tmp_path: Path) -> None:
    text = "A decision about retries"
    first = CountingEmbedder()
    CachingEmbedder(first, root=tmp_path).embed(text)
    assert first.calls == 1

    second = CountingEmbedder()
    cached = CachingEmbedder(second, root=tmp_path)

    assert cached.embed(text) == CachingEmbedder(first, root=tmp_path).embed(text)
    assert second.calls == 0


@pytest.mark.phase_4
def test_corrupt_cache_entry_is_a_miss(tmp_path: Path) -> None:
    text = "A decision about cache recovery"
    key = _key(CountingEmbedder.model_id, text)
    cache_path = tmp_path / CACHE_DIR / f"{key}.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("not json", encoding="utf-8")
    inner = CountingEmbedder()

    expected = [float(value) for value in hashlib.sha256(text.encode()).digest()[: inner.dim]]
    assert CachingEmbedder(inner, root=tmp_path).embed(text) == expected
    assert inner.calls == 1
