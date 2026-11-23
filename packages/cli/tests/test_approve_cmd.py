"""``pending`` oversight: agents save drafts honestly; a person gives the verdict."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_cli.approve_cmd import run_approve_cmd
from reasonledger_cli.main import main
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, read_decision_file
from reasonledger_core.models.decision import (
    DecisionFrontmatter,
    DecisionOversight,
    DecisionStatus,
)
from reasonledger_mcp.tools import call_record_decision


def _record(root: Path, **extra: object) -> str:
    result = call_record_decision(
        root,
        context="Which store?",
        choice="Use sqlite",
        alternatives_rejected=["Postgres"],
        ai_tool="claude",
        model="claude-sonnet-5-5",
        **extra,
    )
    return str(result["decision_id"])


def _reviewed(root: Path) -> str:
    """A record a person has approved: recorded pending, then given a verdict."""
    decision_id = _record(root)
    assert (
        run_approve_cmd(root=root, decision_id=decision_id, verdict="reviewed", approved_by="alice")
        == 0
    )
    return decision_id


def _oversight(root: Path, decision_id: str) -> DecisionOversight:
    path = root / DECISIONS_DIR / decision_filename(decision_id)
    return read_decision_file(path).frontmatter.oversight


@pytest.mark.phase_3
def test_mcp_record_cannot_grant_verdict(tmp_path: Path) -> None:
    result = call_record_decision(
        tmp_path,
        context="Which store?",
        choice="Use sqlite",
        alternatives_rejected=["Postgres"],
        ai_tool="claude",
        model="claude-sonnet-5-5",
        approved_by="x",
        oversight="reviewed",
    )
    path = tmp_path / DECISIONS_DIR / decision_filename(str(result["decision_id"]))
    fm = read_decision_file(path).frontmatter
    assert fm.oversight is DecisionOversight.PENDING
    assert fm.approved_by is None and fm.approved_at is None
    assert any("reasonledger approve" in w and "ignored" in w for w in result["warnings"])
    assert "approved_by" not in path.read_text("utf-8")


@pytest.mark.phase_3
@pytest.mark.parametrize("verdict", ["reviewed", "modified", "rejected"])
def test_approve_moves_pending_to_a_verdict(tmp_path: Path, verdict: str) -> None:
    decision_id = _record(tmp_path)
    code = run_approve_cmd(
        root=tmp_path, decision_id=decision_id, verdict=verdict, approved_by="alice"
    )
    assert code == 0
    fm = read_decision_file(tmp_path / DECISIONS_DIR / decision_filename(decision_id)).frontmatter
    assert fm.oversight.value == verdict
    assert fm.approved_by == "alice"


@pytest.mark.phase_3
def test_approve_never_rewrites_an_existing_verdict(tmp_path: Path) -> None:
    decision_id = _reviewed(tmp_path)
    code = run_approve_cmd(
        root=tmp_path, decision_id=decision_id, verdict="rejected", approved_by="someone"
    )
    assert code == 2
    assert _oversight(tmp_path, decision_id) is DecisionOversight.REVIEWED


@pytest.mark.phase_3
def test_approve_needs_a_real_decision(tmp_path: Path) -> None:
    code = run_approve_cmd(
        root=tmp_path, decision_id="dec_missing", verdict="reviewed", approved_by="me"
    )
    assert code == 2


@pytest.mark.phase_3
def test_approve_defaults_to_the_git_identity_and_stamps_the_time(
    tmp_path: Path, git_identity: str
) -> None:
    decision_id = _record(tmp_path)
    assert main(["approve", decision_id, "--root", str(tmp_path)]) == 0
    fm = read_decision_file(tmp_path / DECISIONS_DIR / decision_filename(decision_id)).frontmatter
    assert fm.approved_by == git_identity and fm.approved_at is not None


@pytest.mark.phase_3
def test_approve_with_no_name_and_no_git_identity_is_refused(
    tmp_path: Path, no_git_identity: None, capsys: pytest.CaptureFixture[str]
) -> None:
    decision_id = _record(tmp_path)
    code = run_approve_cmd(
        root=tmp_path, decision_id=decision_id, verdict="reviewed", approved_by="  "
    )
    assert code == 2 and "--by" in capsys.readouterr().err
    assert _oversight(tmp_path, decision_id) is DecisionOversight.PENDING


@pytest.mark.phase_3
def test_supersede_names_the_decision_that_stands_and_who_chose_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    loser, winner = _reviewed(tmp_path), _reviewed(tmp_path)
    args = ["supersede", loser, "--by", "alice", "--root", str(tmp_path)]
    assert main([*args, "--successor", winner, "--reason", "  "]) == 2
    assert main([*args, "--successor", "dec_nope", "--reason", "Newer"]) == 2
    assert "no decision" in capsys.readouterr().err
    assert main([*args, "--successor", winner, "--reason", "Covers both"]) == 0
    assert f"{loser}: superseded by {winner}, chosen by alice" in capsys.readouterr().out
    fm = read_decision_file(tmp_path / DECISIONS_DIR / decision_filename(loser)).frontmatter
    assert (fm.status, fm.superseded_by) == (DecisionStatus.SUPERSEDED, winner)
    assert (fm.superseded_decided_by, fm.superseded_reason) == ("alice", "Covers both")
    assert fm.oversight is DecisionOversight.REVIEWED  # the approval stays as evidence
    assert main([*args, "--successor", winner, "--reason", "again"]) == 2
    assert "already superseded" in capsys.readouterr().err


@pytest.mark.phase_3
def test_retire_takes_a_decision_out_of_force_once_with_a_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    decision_id = _reviewed(tmp_path)
    args = ["retire", decision_id, "--by", "alice", "--root", str(tmp_path)]
    assert main([*args, "--reason", "  "]) == 2
    assert main([*args, "--reason", "The cache was removed"]) == 0
    fm = read_decision_file(tmp_path / DECISIONS_DIR / decision_filename(decision_id)).frontmatter
    assert (fm.status, fm.retired_by) == (DecisionStatus.RETIRED, "alice")
    assert fm.retired_reason == "The cache was removed" and fm.retired_at is not None
    assert fm.oversight is DecisionOversight.REVIEWED  # the approval stays as evidence
    assert main([*args, "--reason", "again"]) == 2
    assert "already retired" in capsys.readouterr().err
    main(["status", "--root", str(tmp_path)])
    assert "retired: 1" in capsys.readouterr().out


def _frontmatter(root: Path, decision_id: str) -> DecisionFrontmatter:
    return read_decision_file(root / DECISIONS_DIR / decision_filename(decision_id)).frontmatter


@pytest.mark.phase_3
def test_a_replacement_leaves_the_old_decision_in_force_until_a_person_approves_it(
    tmp_path: Path,
) -> None:
    old = _reviewed(tmp_path)
    new = _record(tmp_path, supersedes=old)

    assert _frontmatter(tmp_path, new).supersedes == old
    assert _frontmatter(tmp_path, new).recorded_at is not None
    assert _frontmatter(tmp_path, old).status is DecisionStatus.ACTIVE  # still authoritative

    assert (
        run_approve_cmd(root=tmp_path, decision_id=new, verdict="reviewed", approved_by="alice")
        == 0
    )
    assert _frontmatter(tmp_path, old).status is DecisionStatus.SUPERSEDED

    again = call_record_decision(
        tmp_path,
        context="Which store?",
        choice="Use postgres",
        alternatives_rejected=["sqlite"],
        ai_tool="claude",
        model="claude-sonnet-5-5",
        supersedes=old,
    )
    assert again["ok"] is False and "already superseded" in again["error"]
    assert len(list((tmp_path / DECISIONS_DIR).glob("dec_*.md"))) == 2  # nothing was written


@pytest.mark.phase_3
def test_a_rejected_replacement_leaves_the_old_decision_in_force(tmp_path: Path) -> None:
    old = _reviewed(tmp_path)
    new = _record(tmp_path, supersedes=old)

    assert (
        run_approve_cmd(root=tmp_path, decision_id=new, verdict="rejected", approved_by="alice")
        == 0
    )

    assert _frontmatter(tmp_path, old).status is DecisionStatus.ACTIVE


@pytest.mark.phase_3
@pytest.mark.parametrize("bad_id", ["../../evil", "dec_../x", "/etc/passwd", "dec_A1", "dec_", "x"])
def test_a_crafted_decision_id_writes_nothing(tmp_path: Path, bad_id: str) -> None:
    result = call_record_decision(
        tmp_path,
        context="Which store?",
        choice="Use sqlite",
        alternatives_rejected=["Postgres"],
        ai_tool="claude",
        model="claude-sonnet-5-5",
        decision_id=bad_id,
    )

    assert result["ok"] is False
    assert not list(tmp_path.rglob("*.md"))


@pytest.mark.phase_3
def test_a_decision_id_is_never_reused(tmp_path: Path) -> None:
    first = _record(tmp_path, decision_id="dec_fixed1")
    path = tmp_path / DECISIONS_DIR / decision_filename(first)
    before = path.read_bytes()

    clash = call_record_decision(
        tmp_path,
        context="Something else",
        choice="Overwrite it",
        alternatives_rejected=["Keep it"],
        ai_tool="claude",
        model="claude-sonnet-5-5",
        decision_id="dec_fixed1",
    )

    assert clash["ok"] is False and "already exists" in clash["error"]
    assert path.read_bytes() == before


@pytest.mark.phase_3
def test_status_and_gate_flag_pending_decisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    decision_id = _record(tmp_path)
    main(["status", "--root", str(tmp_path)])
    assert "await a human verdict" in capsys.readouterr().out
    main(["check", "--decisions", "--root", str(tmp_path)])
    assert decision_id in capsys.readouterr().err
