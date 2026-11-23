"""Conflict classifiers and conflict-only detection over the related-decision shortlist.

A candidate pair is embedded, then handed to a pluggable classifier: a deterministic
stub (CI), a recorded-fixture replay, or the model judge (``reasoning.judge``). All
implement the ``ConflictClassifier`` protocol. Interactive surfaces use
``related.relate_decisions`` instead, which also reports pairs nobody has judged.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.models.reasoning import Conflict, ConflictVerdict, Relation, Severity
from reasonledger_core.reasoning.config import (
    CONFLICT_CHOICE_DIVERGENCE_CEILING,
    CONFLICT_CONTEXT_SIM_GATE,
    SEVERITY_HIGH_SCORE,
    SEVERITY_MEDIUM_SCORE,
    SHORTLIST_K,
)
from reasonledger_core.reasoning.embeddings import Embedder, cosine_similarity, get_embedder
from reasonledger_core.reasoning.related import (
    Candidate,
    VerdictSource,
    is_replacement_pair,
    is_retired,
    relate_decisions,
)


@runtime_checkable
class ConflictClassifier(Protocol):
    def classify(
        self,
        a: DecisionRecord,
        b: DecisionRecord,
        *,
        context_similarity: float,
        choice_similarity: float,
    ) -> ConflictVerdict: ...


def _severity_for(score: float) -> Severity:
    if score >= SEVERITY_HIGH_SCORE:
        return Severity.HIGH
    if score >= SEVERITY_MEDIUM_SCORE:
        return Severity.MEDIUM
    return Severity.LOW


class StubConflictClassifier:
    """Deterministic classifier: same subject + divergent choice => conflict.

    Score = context_similarity * (1 - choice_similarity). Two decisions on the
    same topic that pick opposing choices score high; agreements and unrelated
    decisions score low.

    The gate/ceiling default to the tested module constants; a caller passes
    overrides to apply a repo's `.reasonledger/conflict.yml` (see
    `reasoning.conflict_config.resolve_conflict_classifier`) without touching
    what every bare `StubConflictClassifier()` call — including the CI smoke
    test — is pinned against.
    """

    def __init__(
        self,
        *,
        context_sim_gate: float = CONFLICT_CONTEXT_SIM_GATE,
        choice_divergence_ceiling: float = CONFLICT_CHOICE_DIVERGENCE_CEILING,
    ) -> None:
        self._context_sim_gate = context_sim_gate
        self._choice_divergence_ceiling = choice_divergence_ceiling

    def classify(
        self,
        a: DecisionRecord,
        b: DecisionRecord,
        *,
        context_similarity: float,
        choice_similarity: float,
    ) -> ConflictVerdict:
        score = context_similarity * (1.0 - choice_similarity)
        is_conflict = (
            context_similarity >= self._context_sim_gate
            and choice_similarity <= self._choice_divergence_ceiling
        )
        explanation = (
            f"context similarity {context_similarity:.2f}, "
            f"choice divergence {1.0 - choice_similarity:.2f}"
        )
        return ConflictVerdict(
            is_conflict=is_conflict,
            severity=_severity_for(score),
            explanation=explanation,
            score=round(score, 6),
        )


def _field_similarity(embedder: Embedder, left: str | None, right: str | None) -> float:
    if not left or not right:
        return 0.0
    return cosine_similarity(embedder.embed(left), embedder.embed(right))


def classify_pair(
    embedder: Embedder,
    classifier: ConflictClassifier,
    a: DecisionRecord,
    b: DecisionRecord,
) -> ConflictVerdict:
    context_similarity = _field_similarity(embedder, a.frontmatter.context, b.frontmatter.context)
    choice_similarity = _field_similarity(embedder, a.frontmatter.choice, b.frontmatter.choice)
    return classifier.classify(
        a,
        b,
        context_similarity=context_similarity,
        choice_similarity=choice_similarity,
    )


def detect_conflicts(
    new: DecisionRecord,
    priors: Sequence[DecisionRecord],
    *,
    embedder: Embedder | None = None,
    classifier: ConflictClassifier,
) -> list[Conflict]:
    """Return conflicts between ``new`` and any contradicting prior decision.

    Superseded records and direct replacement pairs are never compared.
    """
    if is_retired(new):
        return []
    active = embedder or get_embedder()
    conflicts: list[Conflict] = []
    for prior in priors:
        if (
            prior.frontmatter.id == new.frontmatter.id
            or is_retired(prior)
            or is_replacement_pair(new, prior)
        ):
            continue
        verdict = classify_pair(active, classifier, new, prior)
        if verdict.is_conflict:
            conflicts.append(
                Conflict(
                    decision_a=new.frontmatter.id,
                    decision_b=prior.frontmatter.id,
                    severity=verdict.severity,
                    explanation=verdict.explanation,
                    score=verdict.score,
                )
            )
    conflicts.sort(key=lambda c: (-c.score, c.decision_b))
    return conflicts


def as_verdict_source(classifier: ConflictClassifier) -> VerdictSource:
    """Adapt a classifier that always answers into a source of verdicts."""

    def verdict(candidate: Candidate) -> ConflictVerdict:
        return classifier.classify(
            candidate.a,
            candidate.b,
            context_similarity=candidate.context_similarity,
            choice_similarity=candidate.choice_similarity,
        )

    return verdict


def detect_conflicts_among(
    records: Sequence[DecisionRecord],
    *,
    classifier: ConflictClassifier,
    embedder: Embedder | None = None,
    k: int = SHORTLIST_K,
    min_context_similarity: float | None = None,
) -> list[Conflict]:
    """The shortlisted pairs ``classifier`` calls conflicts, deterministically ordered.

    Superseded records and replacement pairs never reach the classifier (see
    ``related.shortlist``).
    """
    return [
        related
        for related in relate_decisions(
            records,
            verdicts=as_verdict_source(classifier),
            embedder=embedder,
            k=k,
            min_context_similarity=min_context_similarity,
        )
        if related.relation is Relation.CONFLICT
    ]
