"""Phase 4 — related-decision shortlist and the committed verdict store."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.models.reasoning import Relation, Severity
from reasonledger_core.reasoning import DeterministicEmbedder
from reasonledger_core.reasoning.dismissals import pair_fingerprint, pair_key
from reasonledger_core.reasoning.related import Candidate, relate_decisions, shortlist
from reasonledger_core.reasoning.verdicts import (
    PII_WITHHELD,
    VERDICTS_PATH,
    JudgeAnswer,
    StoredVerdict,
    VerdictsError,
    effective_verdicts,
    load_verdicts,
    stored_verdict_source,
    write_verdicts,
)

WHEN = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)


def _record(decision_id: str, context: str, choice: str, **extra: object) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            context=context,
            choice=choice,
            **extra,  # type: ignore[arg-type]
        ),
        body="",
    )


def _fan(n: int) -> list[DecisionRecord]:
    """``n`` decisions sharing most of their context wording, so all pairs are similar."""
    return [
        _record(f"dec_f{i:02d}", f"Storage retry policy for service {i}", f"choice {i}")
        for i in range(n)
    ]


@pytest.mark.phase_4
def test_shortlist_caps_neighbours_per_decision() -> None:
    records = _fan(12)
    pairs = shortlist(records, embedder=DeterministicEmbedder(), k=2, min_context_similarity=0.0)
    # All 66 pairs are similar. Each decision contributes its 2 nearest, so the union
    # is bounded by n*k. A decision many others pick (a hub) can still appear in more
    # than k pairs — the bound is on what each decision adds, not on how often it is
    # chosen.
    assert len(pairs) <= 12 * 2
    assert len(pairs) < 66


@pytest.mark.phase_4
def test_shortlist_floor_drops_dissimilar_pairs() -> None:
    a = _record("dec_a", "Timestamp storage timezone policy", "UTC")
    b = _record("dec_b", "Frontend bundler tooling", "vite")
    embedder = DeterministicEmbedder()
    assert shortlist([a, b], embedder=embedder, min_context_similarity=0.5) == []
    assert len(shortlist([a, b], embedder=embedder, min_context_similarity=-1.0)) == 1


@pytest.mark.phase_4
def test_shortlist_is_deterministic_and_skips_retired() -> None:
    records = _fan(6)
    retired = _record(
        "dec_old", "Storage retry policy for service 0", "x", status=DecisionStatus.SUPERSEDED
    )
    embedder = DeterministicEmbedder()
    first = shortlist([*records, retired], embedder=embedder)
    second = shortlist([*records, retired], embedder=embedder)
    ids = [(c.a.frontmatter.id, c.b.frontmatter.id) for c in first]
    assert ids == [(c.a.frontmatter.id, c.b.frontmatter.id) for c in second]
    assert all("dec_old" not in pair for pair in ids)


@pytest.mark.phase_4
def test_records_without_context_are_never_paired() -> None:
    bare = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id="dec_bare", ai_tool=AiTool.NONE, oversight=DecisionOversight.REVIEWED
        ),
        body="",
    )
    other = _record("dec_x", "anything", "y")
    assert (
        shortlist([bare, other], embedder=DeterministicEmbedder(), min_context_similarity=0.0) == []
    )


def _answer(*, conflict: bool) -> JudgeAnswer:
    return JudgeAnswer(
        same_question=True,
        compatible=not conflict,
        question="Which timezone are timestamps stored in?",
        reason="One stores UTC, the other server-local time.",
        severity=Severity.HIGH,
    )


def _stored(a: DecisionRecord, b: DecisionRecord, *, conflict: bool) -> StoredVerdict:
    return StoredVerdict(
        **_answer(conflict=conflict).model_dump(),
        decision_a=a.frontmatter.id,
        decision_b=b.frontmatter.id,
        fingerprint=pair_fingerprint(a, b),
        model="test-judge",
        judged_at=WHEN,
    )


_UTC = _record("dec_utc", "Timestamp storage timezone policy", "UTC")
_LOCAL = _record("dec_local", "Timestamp storage timezone policy", "server-local")


@pytest.mark.phase_4
def test_verdicts_round_trip_sorted(tmp_path: Path) -> None:
    verdicts = {pair_key("dec_utc", "dec_local"): _stored(_UTC, _LOCAL, conflict=True)}
    path = write_verdicts(tmp_path, verdicts)
    assert path == tmp_path / VERDICTS_PATH
    assert load_verdicts(tmp_path) == verdicts


@pytest.mark.phase_4
def test_malformed_verdicts_raise_on_load_but_not_for_views(tmp_path: Path) -> None:
    path = tmp_path / VERDICTS_PATH
    path.parent.mkdir(parents=True)
    path.write_text("verdicts: [{decision_a: only}]\n", encoding="utf-8")
    with pytest.raises(VerdictsError):
        load_verdicts(tmp_path)
    assert effective_verdicts(tmp_path) == {}


@pytest.mark.phase_4
def test_relations_follow_the_stored_verdict() -> None:
    embedder = DeterministicEmbedder()
    for conflict, relation in ((True, Relation.CONFLICT), (False, Relation.COMPATIBLE)):
        source = stored_verdict_source(
            {pair_key("dec_utc", "dec_local"): _stored(_UTC, _LOCAL, conflict=conflict)}
        )
        (pair,) = relate_decisions([_UTC, _LOCAL], verdicts=source, embedder=embedder)
        assert pair.relation is relation
    (unjudged,) = relate_decisions([_UTC, _LOCAL], verdicts=None, embedder=embedder)
    assert unjudged.relation is Relation.UNVERIFIED
    assert "not judged yet" in unjudged.explanation


@pytest.mark.phase_4
def test_verdict_on_old_text_does_not_apply() -> None:
    stored = {pair_key("dec_utc", "dec_local"): _stored(_UTC, _LOCAL, conflict=False)}
    edited = _record("dec_local", "Timestamp storage timezone policy", "user-local zone")
    source = stored_verdict_source(stored)
    assert (
        source(Candidate(a=_UTC, b=edited, context_similarity=1.0, choice_similarity=0.0)) is None
    )


@pytest.mark.phase_4
def test_model_wording_with_pii_is_withheld() -> None:
    answer = _answer(conflict=True).model_copy(
        update={"reason": "Ask jane.doe@example.com which zone she meant."}
    )
    linted = answer.linted()
    assert linted.reason == PII_WITHHELD
    assert linted.question == answer.question
