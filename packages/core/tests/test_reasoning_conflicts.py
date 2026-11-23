"""Phase 4 — conflict detection quality gate + stub/replay classifiers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.reasoning import (
    DeterministicEmbedder,
    ReplayConflictClassifier,
    StubConflictClassifier,
    classify_pair,
    detect_conflicts,
    detect_conflicts_among,
)
from reasonledger_core.reasoning.config import (
    CONFLICT_SMOKE_FALSE_POSITIVE_MAX,
    CONFLICT_SMOKE_PRECISION_MIN,
    CONFLICT_SMOKE_RECALL_MIN,
)

_CONFLICTS = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "conflicts"
_LABELED = _CONFLICTS / "labeled_pairs.json"
_REPLAY = _CONFLICTS / "replay_verdicts.json"


def _record(spec: dict[str, Any]) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=spec["id"],
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            context=spec["context"],
            choice=spec["choice"],
        ),
        body="",
    )


def _scores(predictions: list[tuple[bool, bool]]) -> tuple[float, float, float]:
    tp = sum(1 for pred, label in predictions if pred and label)
    fp = sum(1 for pred, label in predictions if pred and not label)
    fn = sum(1 for pred, label in predictions if not pred and label)
    tn = sum(1 for pred, label in predictions if not pred and not label)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return precision, recall, fpr


@pytest.mark.phase_4
def test_conflict_smoke_thresholds_on_holdout_split() -> None:
    """Smoke test over 5 hand-written pairs — NOT a measure of conflict quality.

    Green here means the classifier has not regressed on a handful of obvious
    cases. It does not establish precision or recall: the split is 2 positive and
    3 negative, and the thresholds were tuned against the same ten pairs. Real
    quality is measured in the pilot, by the rate at
    which a human dismisses surfaced conflicts on their own repo.
    """
    pairs = json.loads(_LABELED.read_text("utf-8"))["pairs"]
    holdout = [p for p in pairs if p["split"] == "holdout"]
    assert any(p["is_conflict"] for p in holdout)
    assert any(not p["is_conflict"] for p in holdout)
    # Guard the claim itself: if the set ever grows, this test's name and the
    # SMOKE constants must be revisited rather than silently inheriting authority.
    assert len(holdout) < 50, "holdout set has grown — promote this to a real quality gate"

    embedder = DeterministicEmbedder()
    classifier = StubConflictClassifier()
    predictions: list[tuple[bool, bool]] = []
    for pair in holdout:
        verdict = classify_pair(embedder, classifier, _record(pair["a"]), _record(pair["b"]))
        predictions.append((verdict.is_conflict, bool(pair["is_conflict"])))

    precision, recall, fpr = _scores(predictions)
    assert precision >= CONFLICT_SMOKE_PRECISION_MIN, (precision, predictions)
    assert recall >= CONFLICT_SMOKE_RECALL_MIN, (recall, predictions)
    assert fpr <= CONFLICT_SMOKE_FALSE_POSITIVE_MAX, (fpr, predictions)


@pytest.mark.phase_4
def test_stub_flags_opposing_choice_and_ignores_agreement() -> None:
    embedder = DeterministicEmbedder()
    classifier = StubConflictClassifier()
    same_subject_opposite = classify_pair(
        embedder,
        classifier,
        _record({"id": "x", "context": "Primary datastore for orders", "choice": "PostgreSQL"}),
        _record({"id": "y", "context": "Primary datastore for orders", "choice": "MongoDB"}),
    )
    assert same_subject_opposite.is_conflict is True

    agreement = classify_pair(
        embedder,
        classifier,
        _record({"id": "x", "context": "Primary datastore for orders", "choice": "PostgreSQL"}),
        _record({"id": "y", "context": "Primary datastore for orders", "choice": "PostgreSQL"}),
    )
    assert agreement.is_conflict is False


@pytest.mark.phase_4
def test_stub_constructor_overrides_change_the_verdict() -> None:
    """A per-repo `.reasonledger/conflict.yml` override works by construction.

    Every other call site in this file constructs `StubConflictClassifier()`
    bare and must keep behaving exactly as before — this test is what proves
    the override path exists without touching that guarantee.
    """
    verdict = StubConflictClassifier().classify(
        _record({"id": "x", "context": "a", "choice": "a"}),
        _record({"id": "y", "context": "a", "choice": "a"}),
        context_similarity=0.5,
        choice_similarity=0.5,
    )
    # Default gate/ceiling: context 0.5 >= 0.20 and choice 0.5 > 0.35 ceiling -> no conflict.
    assert verdict.is_conflict is False

    loosened = StubConflictClassifier(choice_divergence_ceiling=0.9).classify(
        _record({"id": "x", "context": "a", "choice": "a"}),
        _record({"id": "y", "context": "a", "choice": "a"}),
        context_similarity=0.5,
        choice_similarity=0.5,
    )
    assert loosened.is_conflict is True

    tightened = StubConflictClassifier(context_sim_gate=0.9).classify(
        _record({"id": "x", "context": "a", "choice": "a"}),
        _record({"id": "y", "context": "a", "choice": "a"}),
        context_similarity=0.5,
        choice_similarity=0.1,
    )
    assert tightened.is_conflict is False


@pytest.mark.phase_4
def test_detect_conflicts_skips_self_and_sorts_by_score() -> None:
    embedder = DeterministicEmbedder()
    classifier = StubConflictClassifier()
    new = _record(
        {"id": "dec_new", "context": "Caching layer for catalog", "choice": "Redis cache"}
    )
    priors = [
        _record({"id": "dec_new", "context": "Caching layer for catalog", "choice": "Redis"}),
        _record(
            {"id": "dec_mem", "context": "Caching layer for catalog", "choice": "in-process memory"}
        ),
        _record(
            {"id": "dec_far", "context": "Public API interface style", "choice": "REST endpoints"}
        ),
    ]
    conflicts = detect_conflicts(new, priors, embedder=embedder, classifier=classifier)
    ids = {c.decision_b for c in conflicts}
    assert "dec_new" not in ids  # self skipped
    assert "dec_mem" in ids


@pytest.mark.phase_4
def test_replay_classifier_returns_recorded_verdicts() -> None:
    embedder = DeterministicEmbedder()
    classifier = ReplayConflictClassifier.from_fixture(_REPLAY)
    conflict = classify_pair(
        embedder,
        classifier,
        _record({"id": "dec_retry01", "context": "c", "choice": "a"}),
        _record({"id": "dec_retry_fixed", "context": "c", "choice": "b"}),
    )
    assert conflict.is_conflict is True
    assert conflict.severity.value == "high"

    unknown = classify_pair(
        embedder,
        classifier,
        _record({"id": "unknown_a", "context": "c", "choice": "a"}),
        _record({"id": "unknown_b", "context": "c", "choice": "b"}),
    )
    assert unknown.is_conflict is False


def _with(record: DecisionRecord, **updates: Any) -> DecisionRecord:
    return record.model_copy(update={"frontmatter": record.frontmatter.model_copy(update=updates)})


_DB_CONTEXT = "Primary datastore for the orders service"
_PG = _record({"id": "dec_pg", "context": _DB_CONTEXT, "choice": "PostgreSQL relational database"})
_MONGO = _record({"id": "dec_mongo", "context": _DB_CONTEXT, "choice": "MongoDB document store"})


@pytest.mark.phase_4
def test_live_opposing_pair_is_still_flagged() -> None:
    """Control for the two exclusions below: the same pair, both live, conflicts."""
    conflicts = detect_conflicts_among([_PG, _MONGO], classifier=StubConflictClassifier())
    assert [(c.decision_a, c.decision_b) for c in conflicts] == [("dec_pg", "dec_mongo")]


@pytest.mark.phase_4
def test_superseded_record_is_never_compared() -> None:
    retired = _with(_PG, status=DecisionStatus.SUPERSEDED)
    classifier = StubConflictClassifier()
    assert detect_conflicts_among([retired, _MONGO], classifier=classifier) == []
    assert detect_conflicts(_MONGO, [retired], classifier=classifier) == []
    assert detect_conflicts(retired, [_MONGO], classifier=classifier) == []


@pytest.mark.phase_4
def test_replacement_pair_is_not_a_conflict_even_before_status_flips() -> None:
    successor = _with(_MONGO, supersedes="dec_pg")
    classifier = StubConflictClassifier()
    assert detect_conflicts_among([_PG, successor], classifier=classifier) == []
    assert detect_conflicts(successor, [_PG], classifier=classifier) == []
