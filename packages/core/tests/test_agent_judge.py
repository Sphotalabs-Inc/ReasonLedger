"""Phase 5 — the agent route for judging: the user's coding agent judges related pairs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.reasoning import DeterministicEmbedder
from reasonledger_core.reasoning.agent_judge import judging_task, submit_verdicts
from reasonledger_core.reasoning.judge import pending_pairs
from reasonledger_core.reasoning.verdicts import load_verdicts

WHEN = datetime(2026, 10, 31, 12, 0, 0, tzinfo=UTC)
CONFLICT = {
    "same_question": True,
    "compatible": False,
    "question": "Which timezone are timestamps stored in?",
    "reason": "One stores UTC, the other server-local time.",
    "severity": "high",
}


def _record(decision_id: str, context: str, choice: str) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            status=DecisionStatus.ACTIVE,
            context=context,
            choice=choice,
        ),
        body="",
    )


def _seed(root: Path) -> None:
    for record in (
        _record("dec_utc", "Timestamp storage timezone policy", "UTC"),
        _record("dec_local", "Timestamp storage timezone policy", "server-local"),
        _record("dec_tz3", "Timestamp storage timezone rules", "UTC"),
    ):
        write_decision_file(root / DECISIONS_DIR / decision_filename(record.frontmatter.id), record)


def _answer(task: dict[str, object], index: int, **overrides: object) -> dict[str, object]:
    pair = task["pairs"][index]  # type: ignore[index]
    return {
        "decision_a": pair["decision_a"],
        "decision_b": pair["decision_b"],
        "fingerprint": pair["fingerprint"],
        **CONFLICT,
        **overrides,
    }


@pytest.mark.phase_5
def test_task_hands_out_pairs_with_the_rubric_and_counts(tmp_path: Path) -> None:
    _seed(tmp_path)
    task = judging_task(tmp_path, embedder=DeterministicEmbedder(), limit=2)

    assert task["returned"] == 2 and task["pending"] == 3
    assert "same_question" in str(task["instructions"]) and "submit_verdicts" in str(
        task["instructions"]
    )
    first = task["pairs"][0]  # type: ignore[index]
    assert set(first) == {"decision_a", "decision_b", "fingerprint", "a", "b"}
    assert set(first["a"]) == {"context", "choice"}


@pytest.mark.phase_5
def test_submitted_verdicts_are_stored_like_a_model_judges_them(tmp_path: Path) -> None:
    _seed(tmp_path)
    embedder = DeterministicEmbedder()
    task = judging_task(tmp_path, embedder=embedder)

    result = submit_verdicts(
        tmp_path,
        [_answer(task, 0), _answer(task, 1, same_question=False, compatible=True, severity="low")],
        "claude-code/test",
        embedder=embedder,
        now=lambda: WHEN,
    )

    assert (result["recorded"], result["conflicts"], result["remaining"]) == (2, 1, 1)
    assert result["rejected"] == []
    stored = load_verdicts(tmp_path)
    assert {v.model for v in stored.values()} == {"claude-code/test"}
    queue = pending_pairs(tmp_path, embedder=embedder)
    assert (len(queue.pending), queue.already_judged) == (1, 2)


@pytest.mark.phase_5
def test_unknown_repeated_and_invalid_answers_are_rejected_not_stored(tmp_path: Path) -> None:
    _seed(tmp_path)
    embedder = DeterministicEmbedder()
    task = judging_task(tmp_path, embedder=embedder)
    good = _answer(task, 0)

    result = submit_verdicts(
        tmp_path,
        [
            good,
            good,  # the same pair twice: the second is no longer pending
            {**CONFLICT, "decision_a": "dec_nope", "decision_b": "dec_utc"},
            _answer(task, 1, severity="catastrophic"),
        ],
        "claude-code/test",
        embedder=embedder,
    )

    assert result["recorded"] == 1
    assert len(result["rejected"]) == 3  # type: ignore[arg-type]
    assert len(load_verdicts(tmp_path)) == 1


@pytest.mark.phase_5
def test_verdict_on_a_pair_edited_since_the_task_is_rejected(tmp_path: Path) -> None:
    _seed(tmp_path)
    embedder = DeterministicEmbedder()
    task = judging_task(tmp_path, embedder=embedder, limit=1)
    stale = _answer(task, 0)

    edited = _record(str(stale["decision_a"]), "Timestamp storage timezone policy", "local time")
    write_decision_file(tmp_path / DECISIONS_DIR / decision_filename(edited.frontmatter.id), edited)

    result = submit_verdicts(tmp_path, [stale], "claude-code/test", embedder=embedder)
    assert result["recorded"] == 0 and len(result["rejected"]) == 1  # type: ignore[arg-type]
    assert load_verdicts(tmp_path) == {}


@pytest.mark.phase_5
def test_judged_by_is_required(tmp_path: Path) -> None:
    _seed(tmp_path)
    embedder = DeterministicEmbedder()
    task = judging_task(tmp_path, embedder=embedder)
    result = submit_verdicts(tmp_path, [_answer(task, 0)], "  ", embedder=embedder)
    assert result["recorded"] == 0 and load_verdicts(tmp_path) == {}


@pytest.mark.phase_5
def test_a_named_pair_is_the_only_pair_handed_out_and_the_agent_is_told_to_stop(
    tmp_path: Path,
) -> None:
    _seed(tmp_path)
    embedder = DeterministicEmbedder()
    first = judging_task(tmp_path, embedder=embedder)["pairs"][0]
    ids = (first["decision_b"], first["decision_a"])  # either order names the same pair

    task = judging_task(tmp_path, embedder=embedder, pair=ids)

    assert [(p["decision_a"], p["decision_b"]) for p in task["pairs"]] == [
        (first["decision_a"], first["decision_b"])
    ]
    assert "note" not in task
    assert "stop" in task["instructions"] and "next batch" not in task["instructions"]


@pytest.mark.phase_5
def test_a_pair_that_is_not_waiting_comes_back_empty_with_the_reason(tmp_path: Path) -> None:
    _seed(tmp_path)

    task = judging_task(tmp_path, embedder=DeterministicEmbedder(), pair=("dec_utc", "dec_missing"))

    assert task["pairs"] == [] and "not waiting for a verdict" in task["note"]


@pytest.mark.phase_5
def test_a_batch_task_tells_the_agent_to_continue_unless_the_user_limited_it(
    tmp_path: Path,
) -> None:
    _seed(tmp_path)

    task = judging_task(tmp_path, embedder=DeterministicEmbedder())

    assert "next batch" in task["instructions"] and "unless the user asked" in task["instructions"]


@pytest.mark.phase_5
def test_a_verdict_in_the_view_says_who_judged_it_and_when(tmp_path: Path) -> None:
    from reasonledger_core.views import build_ledger_view

    _seed(tmp_path)
    embedder = DeterministicEmbedder()
    task = judging_task(tmp_path, embedder=embedder)
    submit_verdicts(
        tmp_path, [_answer(task, 0)], "cursor/test-model", embedder=embedder, now=lambda: WHEN
    )

    view = build_ledger_view(tmp_path)
    judged = [c for c in view.conflicts if c.judged_by is not None]

    assert [(c.judged_by, c.judged_at) for c in judged] == [("cursor/test-model", WHEN)]
    unjudged = [c for c in view.related if c.judged_by is None]
    assert all(c.judged_at is None for c in unjudged)
