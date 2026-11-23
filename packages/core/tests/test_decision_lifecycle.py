"""Out-of-force decisions and the who-and-when a card shows for every record."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    decision_filename,
    read_decision_file,
    write_decision_file,
)
from reasonledger_core.decisions.lifecycle import (
    RetireError,
    retire_decision,
    supersede_decision,
)
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.privacy.pii_linter import PiiLintError
from reasonledger_core.reasoning.related import is_retired
from reasonledger_core.views import build_ledger_view

AT = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
COMMITTED = "2026-03-04T05:06:07+00:00"


def _write(root: Path, decision_id: str, **fields: object) -> Path:
    frontmatter = DecisionFrontmatter(
        id=decision_id,
        ai_tool=AiTool.CLAUDE_CODE,
        model="test-model",
        oversight=DecisionOversight.PENDING,
        context="Which store?",
        choice="Use sqlite",
        **fields,  # type: ignore[arg-type]
    )
    path = root / DECISIONS_DIR / decision_filename(decision_id)
    write_decision_file(path, DecisionRecord(frontmatter=frontmatter, body=""))
    return path


def _git(root: Path, *args: str) -> None:
    identity = ["-c", "user.name=Committer", "-c", "user.email=committer@example.com"]
    env = {"GIT_AUTHOR_DATE": COMMITTED, "GIT_COMMITTER_DATE": COMMITTED, "PATH": "/usr/bin:/bin"}
    subprocess.run(["git", "-C", str(root), *identity, *args], check=True, env=env)


@pytest.mark.phase_3
def test_retire_needs_a_person_a_reason_and_a_decision_still_in_force(tmp_path: Path) -> None:
    path = _write(tmp_path, "dec_old1")
    for who, why in (("", "gone"), ("sam", "  ")):
        with pytest.raises(RetireError):
            retire_decision("dec_old1", root=tmp_path, retired_by=who, retired_at=AT, reason=why)
    with pytest.raises(RetireError, match="no decision"):
        retire_decision("dec_nope", root=tmp_path, retired_by="sam", retired_at=AT, reason="gone")
    with pytest.raises(PiiLintError):
        retire_decision(
            "dec_old1", root=tmp_path, retired_by="sam", retired_at=AT, reason="ask a@b.example"
        )
    assert read_decision_file(path).frontmatter.status is DecisionStatus.ACTIVE

    record = retire_decision(
        "dec_old1", root=tmp_path, retired_by="sam", retired_at=AT, reason="Service removed"
    )
    assert is_retired(record)
    assert read_decision_file(path).frontmatter.retired_at == AT
    with pytest.raises(RetireError, match="already retired"):
        retire_decision("dec_old1", root=tmp_path, retired_by="sam", retired_at=AT, reason="again")


def _supersede(
    root: Path, loser: str, winner: str, *, who: str = "sam", why: str = "Newer"
) -> None:
    supersede_decision(
        loser, successor_id=winner, root=root, decided_by=who, superseded_at=AT, reason=why
    )


@pytest.mark.phase_3
def test_supersede_needs_a_person_a_reason_and_two_different_decisions_in_force(
    tmp_path: Path,
) -> None:
    loser = _write(tmp_path, "dec_lose1")
    _write(tmp_path, "dec_win1")
    _write(tmp_path, "dec_gone1", status=DecisionStatus.RETIRED)
    for who, why in (("", "Newer"), ("sam", "  ")):
        with pytest.raises(RetireError):
            _supersede(tmp_path, "dec_lose1", "dec_win1", who=who, why=why)
    with pytest.raises(RetireError, match="itself"):
        _supersede(tmp_path, "dec_lose1", "dec_lose1")
    with pytest.raises(RetireError, match="no decision"):
        _supersede(tmp_path, "dec_lose1", "dec_nope")
    with pytest.raises(RetireError, match="already retired"):
        _supersede(tmp_path, "dec_lose1", "dec_gone1")
    with pytest.raises(RetireError, match="already retired"):
        _supersede(tmp_path, "dec_gone1", "dec_win1")
    with pytest.raises(PiiLintError):
        _supersede(tmp_path, "dec_lose1", "dec_win1", why="ask a@b.example")
    assert read_decision_file(loser).frontmatter.status is DecisionStatus.ACTIVE


@pytest.mark.phase_3
def test_superseding_writes_only_the_decision_that_lost_and_points_at_the_one_that_stands(
    tmp_path: Path,
) -> None:
    loser = _write(tmp_path, "dec_lose1")
    winner = _write(tmp_path, "dec_win1", approved_by="sam", approved_at=AT)
    before = winner.read_bytes()

    # A name that looks like an address is allowed as the person, as it is for approved_by.
    _supersede(tmp_path, "dec_lose1", "dec_win1", who="sam@example.com", why="Covers both cases")

    assert winner.read_bytes() == before
    fm = read_decision_file(loser).frontmatter
    assert (fm.status, fm.superseded_by) == (DecisionStatus.SUPERSEDED, "dec_win1")
    assert (fm.superseded_decided_by, fm.superseded_at) == ("sam@example.com", AT)
    assert fm.superseded_reason == "Covers both cases"
    with pytest.raises(RetireError, match="already superseded"):
        _supersede(tmp_path, "dec_lose1", "dec_win1")

    view = build_ledger_view(tmp_path)
    lost = {d.id: d for d in view.decisions}["dec_lose1"]
    assert (lost.superseded_by, lost.superseded_decided_by) == ("dec_win1", "sam@example.com")
    assert (lost.superseded_at, lost.superseded_reason) == (AT, "Covers both cases")
    # The one that lost stops waiting on anyone; the one that stands still does.
    assert (view.counts["superseded"], view.counts["pending_approval"]) == (1, 1)


@pytest.mark.phase_3
def test_an_out_of_force_decision_is_not_waiting_on_a_person(tmp_path: Path) -> None:
    _write(tmp_path, "dec_live1")
    _write(tmp_path, "dec_gone1", status=DecisionStatus.RETIRED)
    _write(tmp_path, "dec_gone2", status=DecisionStatus.SUPERSEDED)
    _write(tmp_path, "dec_next1", supersedes="dec_gone2", recorded_at=AT)

    view = build_ledger_view(tmp_path)

    assert view.counts["pending_approval"] == 2
    assert (view.counts["retired"], view.counts["superseded"]) == (1, 1)
    by_id = {d.id: d for d in view.decisions}
    assert by_id["dec_gone2"].superseded_by == "dec_next1"
    assert by_id["dec_next1"].recorded_at == AT and not by_id["dec_next1"].recorded_at_from_git


@pytest.mark.phase_3
def test_an_undated_record_shows_when_git_first_saw_it_and_says_so(tmp_path: Path) -> None:
    _write(tmp_path, "dec_committed")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "record a decision")
    _write(tmp_path, "dec_uncommitted")
    _write(tmp_path, "dec_dated", recorded_at=AT)

    by_id = {d.id: d for d in build_ledger_view(tmp_path).decisions}

    committed = by_id["dec_committed"]
    assert committed.recorded_at == datetime.fromisoformat(COMMITTED)
    assert committed.recorded_at_from_git
    assert by_id["dec_uncommitted"].recorded_at is None
    assert not by_id["dec_uncommitted"].recorded_at_from_git
    assert (by_id["dec_dated"].recorded_at, by_id["dec_dated"].recorded_at_from_git) == (AT, False)


@pytest.mark.phase_4
def test_retired_excluded_from_shortlist(tmp_path: Path) -> None:
    from reasonledger_core.reasoning.related import shortlist

    _write(tmp_path, "dec_live01")
    _write(tmp_path, "dec_live02")
    _write(tmp_path, "dec_gone01", status=DecisionStatus.RETIRED)
    _write(tmp_path, "dec_gone02", status=DecisionStatus.SUPERSEDED)
    records = load_decisions_from_dir(tmp_path / DECISIONS_DIR)
    pairs = shortlist(records)
    assert pairs  # the two live records still pair; only the out-of-force ones are dropped
    assert all(
        {c.a.frontmatter.id, c.b.frontmatter.id}.isdisjoint({"dec_gone01", "dec_gone02"})
        for c in pairs
    )
