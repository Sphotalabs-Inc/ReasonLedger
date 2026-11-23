"""Related decisions: shortlist candidate pairs by similarity, then attach what is known.

Embeddings answer "do these two decisions share a topic?", which is cheap and useful
for finding candidates but cannot say whether two answers contradict each other. So
each decision contributes only its nearest neighbours by context, and every pair is
reported with its relation: judged a conflict, judged compatible, or not judged yet.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from reasonledger_core.models.decision import OUT_OF_FORCE, DecisionRecord
from reasonledger_core.models.reasoning import Conflict, ConflictVerdict, Relation, Severity
from reasonledger_core.reasoning.config import (
    SHORTLIST_K,
    SHORTLIST_MIN_CONTEXT_SIM,
    SHORTLIST_MIN_CONTEXT_SIM_UNKNOWN,
)
from reasonledger_core.reasoning.embeddings import Embedder, cosine_similarity, get_embedder


@dataclass(frozen=True)
class Candidate:
    """A shortlisted pair and the similarities that put it on the list."""

    a: DecisionRecord
    b: DecisionRecord
    context_similarity: float
    choice_similarity: float


# Returns the verdict for a candidate, or None when nobody has judged it.
VerdictSource = Callable[[Candidate], ConflictVerdict | None]

_RELATION_ORDER = {Relation.CONFLICT: 0, Relation.UNVERIFIED: 1, Relation.COMPATIBLE: 2}


def is_retired(record: DecisionRecord) -> bool:
    """A superseded or retired decision is settled history, not a live position to contradict."""
    return record.frontmatter.status in OUT_OF_FORCE


def is_replacement_pair(a: DecisionRecord, b: DecisionRecord) -> bool:
    """One record names the other as the decision it replaces.

    Covers a successor that is still a proposal, or a ledger where the old record's
    status was never flipped: the pair is "same question, new answer" by design.
    """
    return a.frontmatter.supersedes == b.frontmatter.id or (
        b.frontmatter.supersedes == a.frontmatter.id
    )


def min_context_similarity_for(embedder: Embedder) -> float:
    """The shortlist floor for this embedder's similarity scale."""
    return SHORTLIST_MIN_CONTEXT_SIM.get(embedder.model_id, SHORTLIST_MIN_CONTEXT_SIM_UNKNOWN)


def shortlist(
    records: Sequence[DecisionRecord],
    *,
    embedder: Embedder | None = None,
    k: int = SHORTLIST_K,
    min_context_similarity: float | None = None,
) -> list[Candidate]:
    """Each live decision's ``k`` nearest neighbours by context, as unordered pairs.

    Superseded records are dropped before embedding and a record is never paired
    with the one it replaces. Records without a context have nothing to compare.
    Output order follows the input order, so callers that sort records get a
    deterministic list.
    """
    live = [record for record in records if not is_retired(record)]
    active = embedder or get_embedder()
    floor = (
        min_context_similarity
        if min_context_similarity is not None
        else min_context_similarity_for(active)
    )
    context_vecs = [_embed(active, record.frontmatter.context) for record in live]
    choice_vecs = [_embed(active, record.frontmatter.choice) for record in live]
    context_sims = pairwise_similarities(context_vecs)
    choice_sims = pairwise_similarities(choice_vecs)

    with_context = [index for index, vector in enumerate(context_vecs) if vector is not None]
    pairs: set[tuple[int, int]] = set()
    for i in with_context:
        ranked = sorted(
            (j for j in with_context if j != i),
            key=lambda j: (-context_sims[i][j], live[j].frontmatter.id),
        )
        taken = 0
        for j in ranked:
            if taken == k or context_sims[i][j] < floor:
                break
            if is_replacement_pair(live[i], live[j]):
                continue
            pairs.add((min(i, j), max(i, j)))
            taken += 1
    return [
        Candidate(
            a=live[i],
            b=live[j],
            context_similarity=context_sims[i][j],
            choice_similarity=choice_sims[i][j],
        )
        for i, j in sorted(pairs)
    ]


def relate_decisions(
    records: Sequence[DecisionRecord],
    *,
    verdicts: VerdictSource | None,
    embedder: Embedder | None = None,
    k: int = SHORTLIST_K,
    min_context_similarity: float | None = None,
) -> list[Conflict]:
    """Every shortlisted pair with its relation: conflicts first, then by score."""
    related = [
        _as_related(candidate, verdicts(candidate) if verdicts else None)
        for candidate in shortlist(
            records, embedder=embedder, k=k, min_context_similarity=min_context_similarity
        )
    ]
    related.sort(key=lambda c: (_RELATION_ORDER[c.relation], -c.score, c.decision_a, c.decision_b))
    return related


def _as_related(candidate: Candidate, verdict: ConflictVerdict | None) -> Conflict:
    a_id, b_id = candidate.a.frontmatter.id, candidate.b.frontmatter.id
    similarity = round(candidate.context_similarity, 6)
    if verdict is None:
        return Conflict(
            decision_a=a_id,
            decision_b=b_id,
            severity=Severity.LOW,
            explanation=f"similar context ({candidate.context_similarity:.2f}); not judged yet",
            score=similarity,
            relation=Relation.UNVERIFIED,
        )
    if verdict.is_conflict:
        return Conflict(
            decision_a=a_id,
            decision_b=b_id,
            severity=verdict.severity,
            explanation=verdict.explanation,
            score=verdict.score,
            relation=Relation.CONFLICT,
            judged_by=verdict.judged_by,
            judged_at=verdict.judged_at,
        )
    return Conflict(
        decision_a=a_id,
        decision_b=b_id,
        severity=Severity.LOW,
        explanation=verdict.explanation,
        score=similarity,
        relation=Relation.COMPATIBLE,
        judged_by=verdict.judged_by,
        judged_at=verdict.judged_at,
    )


def _embed(embedder: Embedder, text: str | None) -> list[float] | None:
    return embedder.embed(text) if text else None


def pairwise_similarities(vectors: Sequence[list[float] | None]) -> list[list[float]]:
    """Symmetric similarity matrix; missing vectors → 0.0.

    Uses a matrix product when NumPy is available (same float results as the pure
    Python path for L2-normalized vectors).
    """
    size = len(vectors)
    matrix = [[0.0] * size for _ in range(size)]
    present = [(index, vector) for index, vector in enumerate(vectors) if vector is not None]
    if len(present) < 2:
        return matrix

    try:
        import numpy as np
    except ImportError:
        for left_i, (i, left) in enumerate(present):
            for j, right in present[left_i + 1 :]:
                score = cosine_similarity(left, right)
                matrix[i][j] = score
                matrix[j][i] = score
        return matrix

    indexes = [index for index, _ in present]
    stacked = np.asarray([vector for _, vector in present], dtype=np.float64)
    sims = stacked @ stacked.T
    for row_i, i in enumerate(indexes):
        for col_i, j in enumerate(indexes):
            if i == j:
                continue
            matrix[i][j] = float(sims[row_i, col_i])
    return matrix
