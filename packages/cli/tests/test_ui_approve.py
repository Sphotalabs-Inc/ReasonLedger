"""`reasonledger ui` approves a pending decision — the UI door onto `reasonledger approve`."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, read_decision_file
from reasonledger_core.models.decision import (
    DecisionFrontmatter,
    DecisionOversight,
    DecisionStatus,
)
from reasonledger_core.views import LedgerView
from reasonledger_mcp.tools import call_record_decision
from test_ui_server import _UiServer


@pytest.fixture
def ui(tmp_path: Path, git_identity: str) -> Iterator[_UiServer]:
    server = _UiServer(tmp_path)
    yield server
    server.close()


def _record_pending(root: Path) -> str:
    result = call_record_decision(
        root,
        context="Which store?",
        choice="Use sqlite",
        alternatives_rejected=["Postgres"],
        assumptions=["Single writer"],
        ai_tool="claude",
        model="claude-sonnet-5-5",
    )
    return str(result["decision_id"])


def _oversight(root: Path, decision_id: str) -> DecisionOversight:
    return read_decision_file(
        root / DECISIONS_DIR / decision_filename(decision_id)
    ).frontmatter.oversight


def _frontmatter(root: Path, decision_id: str) -> DecisionFrontmatter:
    return read_decision_file(root / DECISIONS_DIR / decision_filename(decision_id)).frontmatter


def _act(
    ui: _UiServer, decision_id: str, action: str, body: dict[str, object]
) -> tuple[int, dict[str, str]]:
    status, raw = ui.request(
        "POST", f"/api/decisions/{decision_id}/{action}", body=json.dumps(body).encode()
    )
    return status, json.loads(raw)


def _approve(
    ui: _UiServer, decision_id: str, body: dict[str, object]
) -> tuple[int, dict[str, str]]:
    return _act(ui, decision_id, "approve", body)


@pytest.mark.phase_3
def test_view_shows_an_agent_recorded_decision_as_pending(tmp_path: Path, ui: _UiServer) -> None:
    decision_id = _record_pending(tmp_path)
    status, raw = ui.request("GET", "/api/view")
    assert status == 200
    view = LedgerView.model_validate_json(raw)
    assert view.counts["pending_approval"] == 1
    assert view.counts["proposed"] == 0
    assert [(d.id, d.oversight) for d in view.decisions] == [(decision_id, "pending")]


@pytest.mark.phase_3
def test_view_carries_what_the_reviewer_is_vouching_for(tmp_path: Path, ui: _UiServer) -> None:
    """The card renders these from the API payload, so they must be in it."""
    _record_pending(tmp_path)
    _, raw = ui.request("GET", "/api/view")
    decision = LedgerView.model_validate_json(raw).decisions[0]
    assert decision.assumptions == ["Single writer"]
    assert decision.alternatives_rejected == ["Postgres"]


@pytest.mark.phase_3
def test_approve_gives_a_pending_decision_a_reviewed_verdict(
    tmp_path: Path, ui: _UiServer, git_identity: str
) -> None:
    decision_id = _record_pending(tmp_path)
    status, payload = _approve(ui, decision_id, {})
    assert status == 200
    assert payload == {"id": decision_id, "oversight": "reviewed", "approved_by": git_identity}
    assert _oversight(tmp_path, decision_id) is DecisionOversight.REVIEWED
    assert _frontmatter(tmp_path, decision_id).approved_at is not None

    _, raw = ui.request("GET", "/api/view")
    assert LedgerView.model_validate_json(raw).counts["pending_approval"] == 0


@pytest.mark.phase_3
def test_approve_never_rewrites_an_existing_verdict(tmp_path: Path, ui: _UiServer) -> None:
    decision_id = _record_pending(tmp_path)
    assert _approve(ui, decision_id, {})[0] == 200
    first = _frontmatter(tmp_path, decision_id)
    status, payload = _approve(ui, decision_id, {})
    assert status == 400
    assert "already reviewed" in payload["error"]
    assert _frontmatter(tmp_path, decision_id) == first


@pytest.mark.phase_3
def test_a_name_in_the_request_cannot_approve_as_someone_else(
    tmp_path: Path, ui: _UiServer, git_identity: str
) -> None:
    decision_id = _record_pending(tmp_path)
    status, payload = _approve(ui, decision_id, {"approved_by": "someone-else"})
    assert status == 200
    assert payload["approved_by"] == git_identity
    assert _frontmatter(tmp_path, decision_id).approved_by == git_identity


@pytest.mark.phase_3
def test_with_no_git_identity_nobody_can_approve_or_retire(
    tmp_path: Path, ui: _UiServer, no_git_identity: None
) -> None:
    decision_id = _record_pending(tmp_path)
    status, raw = ui.request("GET", "/api/identity")
    assert status == 200 and json.loads(raw)["name"] is None
    for action, body in (("approve", {"approved_by": "typed"}), ("retire", {"reason": "old"})):
        status, payload = _act(ui, decision_id, action, body)
        assert status == 400 and "git config user.name" in payload["error"], action
    fm = _frontmatter(tmp_path, decision_id)
    assert fm.oversight is DecisionOversight.PENDING and fm.status is DecisionStatus.ACTIVE


@pytest.mark.phase_3
def test_the_identity_endpoint_names_who_actions_are_recorded_as(
    ui: _UiServer, git_identity: str
) -> None:
    status, raw = ui.request("GET", "/api/identity")
    assert status == 200
    assert json.loads(raw) == {"name": git_identity, "source": "git", "hint": None}


@pytest.mark.phase_3
def test_retiring_keeps_the_record_and_its_approval_and_takes_it_out_of_force(
    tmp_path: Path, ui: _UiServer, git_identity: str
) -> None:
    decision_id = _record_pending(tmp_path)
    assert _approve(ui, decision_id, {})[0] == 200
    assert _act(ui, decision_id, "retire", {})[0] == 400  # a reason is required
    assert _act(ui, decision_id, "retire", {"reason": "  "})[0] == 400

    status, payload = _act(ui, decision_id, "retire", {"reason": "The service was removed"})
    assert status == 200
    assert payload == {"id": decision_id, "status": "retired", "retired_by": git_identity}
    fm = _frontmatter(tmp_path, decision_id)
    assert fm.status is DecisionStatus.RETIRED and fm.retired_at is not None
    assert fm.retired_reason == "The service was removed"
    assert (fm.oversight, fm.approved_by) == (DecisionOversight.REVIEWED, git_identity)

    status, payload = _act(ui, decision_id, "retire", {"reason": "again"})
    assert status == 400 and "already retired" in payload["error"]
    _, raw = ui.request("GET", "/api/view")
    view = LedgerView.model_validate_json(raw)
    assert (view.counts["retired"], view.counts["active"]) == (1, 0)
    assert view.decisions[0].retired_reason == "The service was removed"


@pytest.mark.phase_3
def test_superseding_from_the_ui_records_who_chose_and_leaves_the_winner_untouched(
    tmp_path: Path, ui: _UiServer, git_identity: str
) -> None:
    loser, winner = _record_pending(tmp_path), _record_pending(tmp_path)
    assert loser != winner
    winner_path = tmp_path / DECISIONS_DIR / decision_filename(winner)
    before = winner_path.read_bytes()
    assert _act(ui, loser, "supersede", {"successor": winner})[0] == 400  # a reason is required
    assert _act(ui, loser, "supersede", {"reason": "Newer"})[0] == 400  # and a successor
    status, payload = _act(ui, loser, "supersede", {"reason": "Newer", "successor": loser})
    assert status == 400 and "itself" in payload["error"]

    status, payload = _act(ui, loser, "supersede", {"reason": "Newer", "successor": winner})
    assert status == 200
    assert payload == {
        "id": loser,
        "status": "superseded",
        "superseded_by": winner,
        "superseded_decided_by": git_identity,
    }
    assert winner_path.read_bytes() == before
    fm = _frontmatter(tmp_path, loser)
    assert (fm.status, fm.superseded_reason) == (DecisionStatus.SUPERSEDED, "Newer")
    assert fm.superseded_at is not None
    status, payload = _act(ui, loser, "supersede", {"reason": "again", "successor": winner})
    assert status == 400 and "already superseded" in payload["error"]


@pytest.mark.phase_3
def test_a_retired_pending_decision_stops_waiting_on_a_person(
    tmp_path: Path, ui: _UiServer
) -> None:
    decision_id = _record_pending(tmp_path)
    assert _act(ui, decision_id, "retire", {"reason": "Recorded by mistake"})[0] == 200
    _, raw = ui.request("GET", "/api/view")
    assert LedgerView.model_validate_json(raw).counts["pending_approval"] == 0


@pytest.mark.phase_3
def test_view_says_who_recorded_a_decision_and_when(tmp_path: Path, ui: _UiServer) -> None:
    _record_pending(tmp_path)
    _, raw = ui.request("GET", "/api/view")
    decision = LedgerView.model_validate_json(raw).decisions[0]
    assert (decision.ai_tool, decision.model) == ("claude-code", "claude-sonnet-5-5")
    assert decision.recorded_at is not None and not decision.recorded_at_from_git


@pytest.mark.phase_3
def test_an_unknown_decision_action_is_404(tmp_path: Path, ui: _UiServer) -> None:
    assert _act(ui, _record_pending(tmp_path), "erase", {})[0] == 404


@pytest.mark.phase_3
@pytest.mark.parametrize("decision_id", ["dec_nosuch", "not-an-id", "..%2Fx"])
def test_approve_unknown_id_is_404(ui: _UiServer, decision_id: str) -> None:
    status, payload = _approve(ui, decision_id, {"approved_by": "alice"})
    assert status == 404
    assert payload["error"] == "unknown id"


@pytest.mark.phase_3
def test_approve_requires_token(tmp_path: Path, ui: _UiServer) -> None:
    decision_id = _record_pending(tmp_path)
    status, _ = ui.request(
        "POST",
        f"/api/decisions/{decision_id}/approve",
        body=json.dumps({"approved_by": "alice"}).encode(),
        token=None,
    )
    assert status == 403
    assert _oversight(tmp_path, decision_id) is DecisionOversight.PENDING


@pytest.mark.phase_3
def test_pending_review_is_explained_on_both_surfaces(tmp_path: Path, ui: _UiServer) -> None:
    """A state the page can show has to be explained on the page that shows it."""
    _record_pending(tmp_path)
    _, raw = ui.request("GET", "/", token=None)
    out = tmp_path / "ledger.html"
    assert main(["status", "--root", str(tmp_path), "--html", str(out)]) == EXIT_PASS
    for surface, html in (("live", raw.decode("utf-8")), ("export", out.read_text("utf-8"))):
        assert "<dt>pending review</dt>" in html, surface
    # The export carries the state in its bootstrap view, so its renderer can badge it.
    assert '"oversight":"pending"' in out.read_text("utf-8")
