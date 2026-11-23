"""Phase 4 — dismissed conflict pairs: the human verdict on a similarity hint."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.reasoning.dismissals import (
    DISMISSED_PATH,
    Dismissal,
    DismissalError,
    add_dismissal,
    dismissal_still_applies,
    dismissed_fingerprints,
    dismissed_keys,
    load_dismissals,
    pair_fingerprint,
    pair_key,
    write_dismissals,
)


def _record(decision_id: str, *, context: str, choice: str, body: str = "") -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            context=context,
            choice=choice,
        ),
        body=body,
    )


@pytest.mark.phase_4
def test_pair_key_is_order_independent() -> None:
    assert pair_key("dec_bbb", "dec_aaa") == pair_key("dec_aaa", "dec_bbb")
    assert pair_key("dec_aaa", "dec_bbb") == "dec_aaa::dec_bbb"


@pytest.mark.phase_4
def test_add_dismissal_creates_then_is_idempotent(tmp_path: Path) -> None:
    entry, created = add_dismissal(
        tmp_path,
        decision_a="dec_bbb",
        decision_b="dec_aaa",
        reason="different services; the shared word is coincidental",
        dismissed_by="reviewer",
        dismissed_at=datetime.now(UTC),
    )
    assert created is True
    assert entry.pair == "dec_aaa::dec_bbb"

    # Re-dismissing the same pair, reported the other way round, is a no-op.
    again, created_again = add_dismissal(
        tmp_path,
        decision_a="dec_aaa",
        decision_b="dec_bbb",
        reason="a different reason entirely",
        dismissed_by="someone else",
    )
    assert created_again is False
    assert again.reason == entry.reason
    assert len(load_dismissals(tmp_path)) == 1


@pytest.mark.phase_4
def test_dismissal_requires_a_reason(tmp_path: Path) -> None:
    with pytest.raises(DismissalError):
        add_dismissal(tmp_path, decision_a="dec_a", decision_b="dec_b", reason="   ")


@pytest.mark.phase_4
def test_dismissal_reason_is_pii_linted(tmp_path: Path) -> None:
    """A dismissal is committed and shared — as exposed as a decision body."""
    with pytest.raises(DismissalError, match="PII"):
        add_dismissal(
            tmp_path,
            decision_a="dec_a",
            decision_b="dec_b",
            reason="checked with someone@example.com and it is fine",
        )
    assert not (tmp_path / DISMISSED_PATH).exists()


@pytest.mark.phase_4
def test_dismissed_keys_never_raises_on_malformed_file(tmp_path: Path) -> None:
    """status and CI must not die because the dismissal file is broken."""
    path = tmp_path / DISMISSED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("dismissed: [ this is not: valid: yaml", encoding="utf-8")

    assert dismissed_keys(tmp_path) == set()
    with pytest.raises(DismissalError):
        load_dismissals(tmp_path)


@pytest.mark.phase_4
def test_write_is_sorted_and_round_trips(tmp_path: Path) -> None:
    write_dismissals(
        tmp_path,
        [
            Dismissal(pair="dec_zzz::dec_yyy", reason="second"),
            Dismissal(pair="dec_aaa::dec_bbb", reason="first"),
        ],
    )
    raw = yaml.safe_load((tmp_path / DISMISSED_PATH).read_text("utf-8"))
    assert [entry["pair"] for entry in raw["dismissed"]] == [
        "dec_aaa::dec_bbb",
        "dec_zzz::dec_yyy",
    ]
    assert {entry.pair for entry in load_dismissals(tmp_path)} == {
        "dec_aaa::dec_bbb",
        "dec_zzz::dec_yyy",
    }


@pytest.mark.phase_4
def test_missing_file_is_empty_not_an_error(tmp_path: Path) -> None:
    assert load_dismissals(tmp_path) == []
    assert dismissed_keys(tmp_path) == set()


@pytest.mark.phase_4
def test_fingerprint_is_order_independent_and_content_scoped() -> None:
    left = _record("dec_aaa", context="Primary datastore for orders", choice="PostgreSQL")
    right = _record("dec_bbb", context="Primary datastore for orders", choice="MongoDB")

    assert pair_fingerprint(left, right) == pair_fingerprint(right, left)

    # The body is not a classifier input, so editing it must not invalidate a verdict.
    reworded = _record(
        "dec_bbb",
        context="Primary datastore for orders",
        choice="MongoDB",
        body="expanded rationale, no change to what was decided",
    )
    assert pair_fingerprint(left, reworded) == pair_fingerprint(left, right)

    # `choice` is, so changing it must.
    flipped = _record("dec_bbb", context="Primary datastore for orders", choice="PostgreSQL")
    assert pair_fingerprint(left, flipped) != pair_fingerprint(left, right)


@pytest.mark.phase_4
def test_dismissal_stops_applying_once_a_decision_changes(tmp_path: Path) -> None:
    """The regression: a stale verdict must not suppress a newly-real contradiction."""
    left = _record("dec_aaa", context="Retry policy for payments", choice="exponential backoff")
    right = _record("dec_bbb", context="Retry policy for billing exports", choice="fixed delay")

    add_dismissal(
        tmp_path,
        decision_a="dec_aaa",
        decision_b="dec_bbb",
        reason="different subsystems; the shared word is coincidental",
        fingerprint=pair_fingerprint(left, right),
    )
    stored = dismissed_fingerprints(tmp_path)[pair_key("dec_aaa", "dec_bbb")]

    # Unchanged: still suppressed.
    assert dismissal_still_applies(stored, pair_fingerprint(left, right)) is True

    # `dec_bbb` is edited onto the same subject with an opposing choice — a real
    # conflict now, and the old dismissal must no longer cover it.
    edited = _record("dec_bbb", context="Retry policy for payments", choice="no retries at all")
    assert dismissal_still_applies(stored, pair_fingerprint(left, edited)) is False


@pytest.mark.phase_4
def test_legacy_entry_without_fingerprint_keeps_suppressing(tmp_path: Path) -> None:
    """Upgrading must not re-open every previously settled pair."""
    write_dismissals(tmp_path, [Dismissal(pair="dec_aaa::dec_bbb", reason="judged long ago")])
    stored = dismissed_fingerprints(tmp_path)["dec_aaa::dec_bbb"]

    assert stored is None
    assert dismissal_still_applies(stored, "any-current-fingerprint") is True


@pytest.mark.phase_4
def test_redismissing_after_drift_replaces_the_stale_verdict(tmp_path: Path) -> None:
    """A re-opened pair must be settleable again, or it nags forever."""
    add_dismissal(
        tmp_path,
        decision_a="dec_aaa",
        decision_b="dec_bbb",
        reason="first verdict",
        fingerprint="fingerprint-before-the-edit",
    )

    # Same content -> no-op, original verdict preserved.
    entry, recorded = add_dismissal(
        tmp_path,
        decision_a="dec_aaa",
        decision_b="dec_bbb",
        reason="second verdict",
        fingerprint="fingerprint-before-the-edit",
    )
    assert recorded is False
    assert entry.reason == "first verdict"

    # Drifted content -> the fresh judgement replaces it, and does not duplicate.
    entry, recorded = add_dismissal(
        tmp_path,
        decision_a="dec_aaa",
        decision_b="dec_bbb",
        reason="still fine after the rewrite",
        fingerprint="fingerprint-after-the-edit",
    )
    assert recorded is True
    assert entry.reason == "still fine after the rewrite"
    assert len(load_dismissals(tmp_path)) == 1
    assert dismissed_fingerprints(tmp_path)["dec_aaa::dec_bbb"] == "fingerprint-after-the-edit"
