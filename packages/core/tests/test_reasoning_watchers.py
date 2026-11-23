"""Phase 4 — staleness watchers: breach -> stale -> PR, rebuild determinism."""

from __future__ import annotations

import pytest
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.models.reasoning import WatcherStatus
from reasonledger_core.reasoning import (
    RecordingPROpener,
    build_stale_pr,
    parse_condition,
    rebuild_watchers,
)
from reasonledger_core.reasoning.watchers import WatcherConditionError, breached_watchers


def _record(watchers: list[str]) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id="dec_pg",
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            context="Primary datastore for orders",
            choice="PostgreSQL relational database",
            justifies=["orders/db.py:1-20"],
            watchers=watchers,
        ),
        body="",
    )


@pytest.mark.phase_4
def test_parse_condition_and_rejects_garbage() -> None:
    cond = parse_condition("postgres_version >= 15")
    assert cond.metric == "postgres_version"
    assert cond.op == ">="
    assert cond.threshold == 15.0
    with pytest.raises(WatcherConditionError):
        parse_condition("this is not a condition")


@pytest.mark.phase_4
def test_watcher_status_transitions() -> None:
    record = _record(["postgres_version >= 15"])
    healthy = rebuild_watchers(record, {"postgres_version": 20})
    assert healthy[0].status == WatcherStatus.HEALTHY
    drifting = rebuild_watchers(record, {"postgres_version": 15})
    assert drifting[0].status == WatcherStatus.DRIFTING
    stale = rebuild_watchers(record, {"postgres_version": 13})
    assert stale[0].status == WatcherStatus.STALE


@pytest.mark.phase_4
def test_breach_opens_stale_pr_with_status_diff() -> None:
    record = _record(["postgres_version >= 15"])
    watchers = rebuild_watchers(record, {"postgres_version": 13})
    breached = breached_watchers(watchers)
    assert len(breached) == 1

    opener = RecordingPROpener()
    draft = build_stale_pr(record, breached[0])
    ref = opener.open_pr(draft)

    assert draft.status_from == DecisionStatus.ACTIVE.value
    assert draft.status_to == DecisionStatus.STALE.value
    assert "status: stale" in draft.new_markdown
    assert draft.file_path == ".reasonledger/decisions/dec_pg.md"
    assert ref.number == 1
    assert opener.opened[0].draft.decision_id == "dec_pg"


@pytest.mark.phase_4
def test_rebuild_is_deterministic_after_state_reset() -> None:
    record = _record(["postgres_version >= 15", "replica_lag_ms <= 200"])
    source = {"postgres_version": 13, "replica_lag_ms": 50}
    first = rebuild_watchers(record, source)
    # "Delete" state and rebuild purely from the canonical decision + sources.
    second = rebuild_watchers(record, source)
    assert [w.model_dump() for w in first] == [w.model_dump() for w in second]
    assert first[0].status == WatcherStatus.STALE
    assert first[1].status == WatcherStatus.HEALTHY
