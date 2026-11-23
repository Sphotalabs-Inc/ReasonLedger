"""Semantic retrieval over decision embeddings (pre-decision query)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.models.reasoning import SemanticHit
from reasonledger_core.reasoning.cache import CachingEmbedder
from reasonledger_core.reasoning.config import SEMANTIC_MIN_SCORE, SEMANTIC_TOP_K
from reasonledger_core.reasoning.conflict_config import (
    EmbedderStatus,
    resolve_conflict_embedder_with_status,
)
from reasonledger_core.reasoning.embeddings import (
    Embedder,
    cosine_similarity,
    embed_decision,
    get_embedder,
)


def rank_by_similarity(
    query_vector: list[float],
    candidates: Sequence[tuple[str, list[float]]],
    *,
    top_k: int = SEMANTIC_TOP_K,
    min_score: float = SEMANTIC_MIN_SCORE,
) -> list[SemanticHit]:
    """Return the top-k candidates by cosine similarity above ``min_score``."""
    scored = [
        SemanticHit(decision_id=decision_id, score=cosine_similarity(query_vector, vector))
        for decision_id, vector in candidates
    ]
    scored = [hit for hit in scored if hit.score >= min_score]
    scored.sort(key=lambda hit: (-hit.score, hit.decision_id))
    return scored[:top_k]


def semantic_search(
    embedder: Embedder,
    query: str,
    records: Sequence[DecisionRecord],
    *,
    top_k: int = SEMANTIC_TOP_K,
    min_score: float = SEMANTIC_MIN_SCORE,
) -> list[SemanticHit]:
    """Embed ``query`` and rank ``records`` against it (in-memory convenience)."""
    query_vector = embedder.embed(query)
    candidates = [(record.frontmatter.id, embed_decision(embedder, record)) for record in records]
    return rank_by_similarity(query_vector, candidates, top_k=top_k, min_score=min_score)


def semantic_query_decisions(
    records: Sequence[DecisionRecord],
    query: str,
    *,
    top_k: int = SEMANTIC_TOP_K,
    embedder: Embedder | None = None,
) -> list[DecisionRecord]:
    """Return records ranked by semantic similarity to ``query`` (best first)."""
    active = embedder or get_embedder()
    by_id = {record.frontmatter.id: record for record in records}
    hits = semantic_search(active, query, records, top_k=top_k)
    return [by_id[hit.decision_id] for hit in hits]


def semantic_recall(
    root: Path,
    records: Sequence[DecisionRecord],
    query: str,
    *,
    top_k: int = SEMANTIC_TOP_K,
) -> tuple[list[DecisionRecord], EmbedderStatus]:
    """Rank ``records`` against ``query`` with the embedder this repo's config selects.

    The embedder and its on-disk vector cache are the ones `status`, `judge` and `check`
    use, so recall and conflict hints agree and a decision is embedded once per machine,
    not once per query. The status says whether the configured backend could not be
    built and recall degraded to the hash embedder, so the caller can surface it.
    """
    embedder, status = resolve_conflict_embedder_with_status(root)
    hits = semantic_query_decisions(
        records, query, top_k=top_k, embedder=CachingEmbedder(embedder, root=root)
    )
    return hits, status
