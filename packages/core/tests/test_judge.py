"""Phase 4 — the related-decision judge, with recorded provider responses (no network)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.llm import InvalidResponse, LlmError
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.models.reasoning import Relation, Severity
from reasonledger_core.reasoning import DeterministicEmbedder
from reasonledger_core.reasoning.dismissals import add_dismissal, pair_fingerprint, pair_key
from reasonledger_core.reasoning.judge import (
    JUDGE_TASK,
    build_judge_prompt,
    build_model_judge,
    judge_pending,
    pending_pairs,
)
from reasonledger_core.reasoning.verdicts import VERDICTS_PATH, load_verdicts

WHEN = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
CONFLICT = {
    "same_question": True,
    "compatible": False,
    "question": "Which timezone are timestamps stored in?",
    "reason": "One stores UTC, the other server-local time.",
    "severity": "high",
}
COMPATIBLE = {**CONFLICT, "same_question": False, "compatible": True, "severity": "low"}


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


def _openai_reply(answer: object) -> dict[str, object]:
    return {"choices": [{"message": {"role": "assistant", "content": json.dumps(answer)}}]}


def _openai_judge(replies: list[dict[str, object]], seen: list[dict[str, object]]) -> object:
    def post(
        url: str, payload: dict[str, object], headers: Mapping[str, str], timeout: float
    ) -> dict[str, object]:
        seen.append(payload)
        return replies.pop(0)

    config = ExtractorConfig(
        provider=ExtractorProvider.OPENAI_COMPATIBLE, base_url="https://judge.test/v1", model="m"
    )
    return build_model_judge(config, http_post=post)


_UTC = _record("dec_utc", "Timestamp storage timezone policy", "UTC")
_LOCAL = _record("dec_local", "Timestamp storage timezone policy", "server-local")


@pytest.mark.phase_4
def test_prompt_carries_only_ids_context_and_choice() -> None:
    prompt = build_judge_prompt(_UTC, _LOCAL)
    assert "dec_utc" in prompt and "dec_local" in prompt
    assert "Context: Timestamp storage timezone policy" in prompt
    assert "Choice: server-local" in prompt


@pytest.mark.phase_4
def test_openai_compatible_judge_sends_strict_schema_and_parses() -> None:
    seen: list[dict[str, object]] = []
    judge = _openai_judge([_openai_reply(CONFLICT)], seen)
    answer = judge.judge(_UTC, _LOCAL)  # type: ignore[attr-defined]
    assert answer.is_conflict and answer.severity is Severity.HIGH
    response_format = seen[0]["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["json_schema"]["name"] == JUDGE_TASK.schema_name


@pytest.mark.phase_4
def test_anthropic_judge_uses_forced_tool() -> None:
    seen: list[dict[str, object]] = []

    def post(
        url: str, payload: dict[str, object], headers: Mapping[str, str], timeout: float
    ) -> dict[str, object]:
        seen.append(payload)
        return {"content": [{"type": "tool_use", "name": JUDGE_TASK.name, "input": COMPATIBLE}]}

    config = ExtractorConfig(provider=ExtractorProvider.ANTHROPIC, model="claude-sonnet-5")
    judge = build_model_judge(config, api_key="k", http_post=post, model="claude-haiku-5")
    answer = judge.judge(_UTC, _LOCAL)
    assert not answer.is_conflict
    assert seen[0]["model"] == "claude-haiku-5"  # judge_model override wins
    assert seen[0]["tool_choice"] == {"type": "tool", "name": JUDGE_TASK.name}


@pytest.mark.phase_4
def test_invalid_answer_is_retried_once_then_fails() -> None:
    seen: list[dict[str, object]] = []
    bad = _openai_reply({"same_question": "maybe"})
    judge = _openai_judge([bad, _openai_reply(CONFLICT)], seen)
    assert judge.judge(_UTC, _LOCAL).is_conflict  # type: ignore[attr-defined]
    assert len(seen) == 2
    judge = _openai_judge([bad, bad], [])
    with pytest.raises(InvalidResponse):
        judge.judge(_UTC, _LOCAL)  # type: ignore[attr-defined]


@pytest.mark.phase_4
def test_disabled_provider_cannot_build_a_judge() -> None:
    with pytest.raises(LlmError):
        build_model_judge(ExtractorConfig())


def _seed(root: Path) -> None:
    for record in (_UTC, _LOCAL, _record("dec_tz3", "Timestamp storage timezone rules", "UTC")):
        write_decision_file(root / DECISIONS_DIR / decision_filename(record.frontmatter.id), record)


@pytest.mark.phase_4
def test_judge_pending_saves_each_verdict_and_skips_judged(tmp_path: Path) -> None:
    _seed(tmp_path)
    embedder = DeterministicEmbedder()
    queue = pending_pairs(tmp_path, embedder=embedder)
    assert queue.already_judged == 0 and len(queue.pending) == 3

    judge = _openai_judge([_openai_reply(CONFLICT), _openai_reply(COMPATIBLE)], [])
    report = judge_pending(tmp_path, judge=judge, embedder=embedder, limit=2, now=lambda: WHEN)  # type: ignore[arg-type]
    assert (report.judged, report.conflicts, report.compatible) == (2, 1, 1)
    stored = load_verdicts(tmp_path)
    assert len(stored) == 2
    assert {v.model for v in stored.values()} == {"m"}

    queue = pending_pairs(tmp_path, embedder=embedder)
    assert (len(queue.pending), queue.already_judged) == (1, 2)


@pytest.mark.phase_4
def test_a_run_can_be_narrowed_to_one_pair_and_stopped_between_pairs(tmp_path: Path) -> None:
    _seed(tmp_path)
    embedder = DeterministicEmbedder()
    judge = _openai_judge([_openai_reply(COMPATIBLE), _openai_reply(CONFLICT)], [])

    one = judge_pending(
        tmp_path,
        judge=judge,  # type: ignore[arg-type]
        embedder=embedder,
        only=pair_key("dec_local", "dec_utc"),
        now=lambda: WHEN,
    )
    assert (one.pending, one.judged) == (3, 1)
    assert list(load_verdicts(tmp_path)) == [pair_key("dec_utc", "dec_local")]

    # Asked before each pair: the first is judged and saved, the second is never sent.
    answers = iter([True, False])
    seen: list[str] = []
    stopped = judge_pending(
        tmp_path,
        judge=judge,  # type: ignore[arg-type]
        embedder=embedder,
        before_each=lambda candidate: seen.append(candidate.a.frontmatter.id) or next(answers),
        now=lambda: WHEN,
    )
    assert (stopped.pending, stopped.judged, stopped.conflicts) == (2, 1, 1)
    assert len(load_verdicts(tmp_path)) == 2
    assert len(seen) == 2  # handed both pairs; only the first was sent


@pytest.mark.phase_4
def test_failed_pair_is_reported_never_stored(tmp_path: Path) -> None:
    _seed(tmp_path)
    results: list[Relation | None] = []

    def post(
        url: str, payload: dict[str, object], headers: Mapping[str, str], timeout: float
    ) -> dict[str, object]:
        raise LlmError("HTTP request failed: connection refused")

    config = ExtractorConfig(
        provider=ExtractorProvider.LOCAL, base_url="http://localhost:11434", model="llama3.1"
    )
    judge = build_model_judge(config, http_post=post)
    report = judge_pending(
        tmp_path,
        judge=judge,
        embedder=DeterministicEmbedder(),
        on_result=lambda candidate, relation, note: results.append(relation),
    )
    assert report.judged == 0 and len(report.failed) == 3
    assert results == [None, None, None]
    assert not (tmp_path / VERDICTS_PATH).exists()


@pytest.mark.phase_4
def test_dismissed_pair_is_not_judged(tmp_path: Path) -> None:
    """A dismissal outranks a model, so judging the pair would only spend a call."""
    _seed(tmp_path)
    add_dismissal(
        tmp_path,
        decision_a="dec_local",
        decision_b="dec_utc",
        reason="different services",
        fingerprint=pair_fingerprint(_LOCAL, _UTC),
    )
    embedder = DeterministicEmbedder()
    queue = pending_pairs(tmp_path, embedder=embedder)
    assert (len(queue.pending), queue.already_judged, queue.dismissed) == (2, 0, 1)
    assert queue.shortlisted == 3

    seen: list[dict[str, object]] = []
    judge = _openai_judge([_openai_reply(COMPATIBLE), _openai_reply(COMPATIBLE)], seen)
    report = judge_pending(tmp_path, judge=judge, embedder=embedder, now=lambda: WHEN)  # type: ignore[arg-type]
    assert (report.judged, report.dismissed, len(seen)) == (2, 1, 2)


@pytest.mark.phase_4
def test_dismissal_lapses_when_a_decision_changes(tmp_path: Path) -> None:
    """A dismissal judged the decisions as they read then (dec_afepr6): edit one, judge again."""
    _seed(tmp_path)
    add_dismissal(
        tmp_path,
        decision_a="dec_local",
        decision_b="dec_utc",
        reason="different services",
        fingerprint=pair_fingerprint(_LOCAL, _UTC),
    )
    edited = _record("dec_local", "Timestamp storage timezone policy", "the requester's zone")
    write_decision_file(tmp_path / DECISIONS_DIR / decision_filename("dec_local"), edited)
    queue = pending_pairs(tmp_path, embedder=DeterministicEmbedder())
    assert (len(queue.pending), queue.dismissed) == (3, 0)
