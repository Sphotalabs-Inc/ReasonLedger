"""Phase 4 — semantic retrieval golden + deterministic embedder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.reasoning import (
    DeterministicEmbedder,
    embed_decision,
    semantic_search,
)
from reasonledger_core.reasoning.conflict_config import ConflictConfig, write_conflict_config
from reasonledger_core.reasoning.embeddings import cosine_similarity
from reasonledger_core.reasoning.retrieval import semantic_recall

_GOLDEN = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "reasoning"
_CORPUS = _GOLDEN / "decisions"
_QUERIES = _GOLDEN / "retrieval_queries.json"


@pytest.mark.phase_4
def test_deterministic_embedder_is_stable_and_normalized() -> None:
    embedder = DeterministicEmbedder()
    first = embedder.embed("redis shared cache store")
    second = embedder.embed("redis shared cache store")
    assert first == second
    norm = sum(component * component for component in first) ** 0.5
    assert abs(norm - 1.0) < 1e-9
    assert embedder.embed("") == [0.0] * embedder.dim


@pytest.mark.phase_4
def test_semantic_retrieval_matches_golden_top_hit() -> None:
    records = load_decisions_from_dir(_CORPUS)
    assert len(records) >= 4
    embedder = DeterministicEmbedder()
    cases = json.loads(_QUERIES.read_text("utf-8"))["queries"]
    for case in cases:
        hits = semantic_search(embedder, case["query"], records)
        assert hits, f"no hits for {case['query']!r}"
        assert hits[0].decision_id == case["expected_top"], (
            case["query"],
            [(h.decision_id, round(h.score, 3)) for h in hits],
        )


@pytest.mark.phase_4
def test_related_decisions_are_more_similar_than_unrelated() -> None:
    records = {r.frontmatter.id: r for r in load_decisions_from_dir(_CORPUS)}
    embedder = DeterministicEmbedder()
    cache = embed_decision(embedder, records["dec_cache01"])
    queue = embed_decision(embedder, records["dec_queue01"])
    auth = embed_decision(embedder, records["dec_auth01"])
    # Redis cache and Redis queue share vocabulary; auth is unrelated.
    assert cosine_similarity(cache, queue) > cosine_similarity(cache, auth)


@pytest.mark.phase_4
def test_semantic_recall_matches_golden_and_reports_no_fallback(tmp_path: Path) -> None:
    records = load_decisions_from_dir(_CORPUS)
    for case in json.loads(_QUERIES.read_text(encoding="utf-8"))["queries"]:
        hits, status = semantic_recall(tmp_path, records, case["query"])
        assert hits[0].frontmatter.id == case["expected_top"], case["query"]
        assert status.fallback_reason is None


@pytest.mark.phase_4
def test_semantic_recall_still_answers_when_the_configured_embedder_cannot_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _missing(*, settings: object = None) -> object:
        raise ImportError("No module named 'fastembed'")

    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))
    monkeypatch.setattr("reasonledger_core.reasoning.conflict_config.get_embedder", _missing)
    records = load_decisions_from_dir(_CORPUS)

    hits, status = semantic_recall(tmp_path, records, "redis shared cache store")

    assert hits
    assert status.requested == "local"
    assert status.fallback_reason is not None
