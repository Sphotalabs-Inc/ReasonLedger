"""Phase 5 — the Unplaced decisions endpoints: list, place, take back, undo."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from reasonledger_core.modules import load_manifest
from test_ui_organize import _decision, _get, _post, repo, ui  # noqa: F401
from test_ui_server import _UiServer


@pytest.fixture
def loose(repo: Path) -> Path:  # noqa: F811
    _decision(repo, "dec_loose")  # no anchor at all
    _decision(repo, "dec_dead", "app/pages/gone.py:1-9")  # its only anchor is gone
    return repo


@pytest.fixture
def server(loose: Path, git_identity: str) -> Iterator[_UiServer]:
    server = _UiServer(loose)
    yield server
    server.close()


@pytest.mark.phase_5
def test_the_list_holds_only_decisions_that_anchors_cannot_place(server: _UiServer) -> None:
    status, view = _get(server, "/api/organize/decisions")

    assert status == 200 and view["waiting"] == 1 and view["stale"] == {}
    by_id = {d["id"]: d for d in view["items"]}
    assert set(by_id) == {"dec_loose", "dec_dead"}  # dec_both has working anchors
    assert [d["id"] for d in view["items"]] == ["dec_loose", "dec_dead"]  # waiting first
    assert (by_id["dec_loose"]["state"], by_id["dec_dead"]["state"]) == ("waiting", "guessed")
    assert by_id["dec_dead"]["modules"] == ["pages"]  # only its dead path matches the folder
    assert by_id["dec_loose"]["why"] == "it has no anchor"
    assert by_id["dec_dead"]["dead_anchors"] == ["app/pages/gone.py:1-9"]
    assert [i["module"] for i in by_id["dec_dead"]["ideas"]] == [
        "pages"
    ]  # the folder it pointed into


@pytest.mark.phase_5
def test_placing_writes_the_manifest_lists_it_as_placed_and_undo_takes_it_back(
    server: _UiServer, loose: Path, git_identity: str
) -> None:
    unplaced = _get(server, "/api/map")[1]["unplaced_decisions"]
    assert [d["id"] for d in unplaced] == ["dec_loose"]  # dec_dead sits in pages by its glob
    status, reply = _post(
        server, "place-decision", {"decision": "dec_loose", "modules": ["billing"], "by": "me"}
    )

    assert status == 200 and reply["message"] == "placed dec_loose in billing" and reply["can_undo"]
    assert load_manifest(loose).placements["dec_loose"].modules == ["billing"]
    view = _get(server, "/api/organize/decisions")[1]
    assert view["waiting"] == 0 and view["items"][-1]["id"] == "dec_loose"  # placed ones sort last
    assert view["items"][-1]["state"] == "hand" and view["items"][-1]["modules"] == ["billing"]
    assert view["items"][-1]["placed_by"] == git_identity  # the server's, not the request's
    assert _get(server, "/api/map")[1]["unplaced_decisions"] == []

    assert _post(server, "undo", {})[0] == 200
    assert load_manifest(loose).placements == {}


@pytest.mark.phase_5
def test_a_placement_can_be_taken_back(server: _UiServer, loose: Path) -> None:
    _post(server, "place-decision", {"decision": "dec_dead", "modules": ["pages"], "by": "me"})

    status, reply = _post(server, "unplace-decision", {"decision": "dec_dead"})

    assert status == 200 and reply["message"] == "took back dec_dead's placement"
    assert load_manifest(loose).placements == {}


@pytest.mark.phase_5
def test_a_placement_the_rules_forbid_is_refused_and_writes_nothing(
    server: _UiServer, loose: Path
) -> None:
    before = (loose / ".reasonledger" / "modules.yml").read_bytes()
    refusals = (
        ({"decision": "dec_both", "modules": ["billing"], "by": "me"}, "placed by that anchor"),
        ({"decision": "dec_loose", "modules": ["ghost"], "by": "me"}, "no such module or bucket"),
        ({"decision": "dec_nope", "modules": ["pages"], "by": "me"}, "no decision dec_nope"),
        ({"decision": "dec_loose", "modules": [], "by": "me"}, "modules must be a list"),
    )
    for body, message in refusals:
        status, reply = _post(server, "place-decision", body)
        assert status == 400 and message in reply["error"], (body, reply)
    assert (loose / ".reasonledger" / "modules.yml").read_bytes() == before


@pytest.fixture
def spec_decision(loose: Path) -> Path:
    spec = loose / "spec" / "01-plan.md"
    spec.parent.mkdir()
    spec.write_text("# plan\n", encoding="utf-8")
    _decision(loose, "dec_spec", "spec/01-plan.md:1-1")  # a live anchor in a folder nothing owns
    return loose


def _unplaced(server: _UiServer) -> dict[str, dict[str, object]]:
    return {d["id"]: d for d in _get(server, "/api/map")[1]["unplaced_decisions"]}


@pytest.mark.phase_5
def test_claiming_a_spec_folder_as_a_new_module_gives_its_decision_a_home(
    spec_decision: Path, server: _UiServer, git_identity: str
) -> None:
    assert _unplaced(server)["dec_spec"]["claimable"] == ["spec/**"]

    status, reply = _post(server, "claim", {"pattern": "spec/**", "name": "Specs"})

    assert status == 200 and reply["message"] == "Created specs from spec/**" and reply["can_undo"]
    stored = load_manifest(spec_decision)
    made = next(m for m in stored.modules if m.id == "specs")
    assert stored.labels == {"spec/**": "specs"} and made.confirmed_by == git_identity
    assert "dec_spec" not in _unplaced(server)
    page = _get(server, "/api/map/module?id=specs")[1]
    assert page["files"] == ["spec/01-plan.md"]
    assert [d["id"] for d in page["decisions"]] == ["dec_spec"]
    assert _post(server, "undo", {})[0] == 200
    assert "dec_spec" in _unplaced(server) and load_manifest(spec_decision).labels == {}


@pytest.mark.phase_5
def test_claiming_into_an_existing_module_and_what_is_refused(
    spec_decision: Path, server: _UiServer
) -> None:
    refusals = (
        ({"pattern": "nowhere/**", "target": "billing"}, "matches no source file"),
        ({"pattern": "spec/**", "target": "ghost"}, "no module or bucket named"),
        ({"pattern": "spec/**"}, "choose a module or bucket"),
        ({"target": "billing"}, "pattern is required"),
    )
    for body, message in refusals:
        status, reply = _post(server, "claim", body)
        assert status == 400 and message in reply["error"]
    assert load_manifest(spec_decision).labels == {}

    status, reply = _post(server, "claim", {"pattern": "spec/**", "target": "billing"})

    assert status == 200 and reply["message"] == "Placed 1 file(s) from spec/** in billing"
    assert "dec_spec" not in _unplaced(server)
