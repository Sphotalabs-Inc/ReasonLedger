"""Phase 5 — the map workbench endpoints: file list, move preview, edits and undo."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from reasonledger_cli.main import main
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.modules import Manifest, Module, ModuleStatus, load_manifest, write_manifest
from reasonledger_core.modules.buckets import new_bucket
from reasonledger_core.modules.manifest import membership
from test_ui_server import _UiServer


def _decision(root: Path, decision_id: str, *loci: str) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            justifies=list(loci),
            context="Which timezone do timestamps use?",
            choice="UTC everywhere",
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for folder in ("pages", "billing", "common"):
        for index in range(3):
            path = tmp_path / "app" / folder / f"f{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x = 1\n", encoding="utf-8")
    write_manifest(
        tmp_path,
        Manifest(
            modules=[
                Module(id="pages", name="Pages", paths=["app/pages/**"]),
                Module(id="billing", name="Billing", paths=["app/billing/**"]),
                new_bucket("shared-backend", ["app/common/**"]),
            ]
        ),
    )
    _decision(tmp_path, "dec_both", "app/common/f0.py::helper", "app/pages/f0.py")
    return tmp_path


@pytest.fixture
def ui(repo: Path, git_identity: str) -> Iterator[_UiServer]:
    server = _UiServer(repo)
    yield server
    server.close()


def _get(ui: _UiServer, path: str) -> tuple[int, Any]:
    status, raw = ui.request("GET", path)
    return status, json.loads(raw)


def _post(ui: _UiServer, action: str, payload: dict[str, Any]) -> tuple[int, Any]:
    status, raw = ui.request("POST", f"/api/organize/{action}", body=json.dumps(payload).encode())
    return status, json.loads(raw)


def _owner_of(root: Path, path: str) -> str | None:
    return membership(load_manifest(root)).module_of(path)


@pytest.mark.phase_5
def test_the_file_list_filters_pages_and_refuses_bad_requests(ui: _UiServer) -> None:
    status, page = _get(ui, "/api/organize/files?module=pages")
    assert status == 200 and page["total"] == 3 and page["files"][0]["decisions"] in (0, 1)
    assert [f["path"] for f in page["files"]] == [f"app/pages/f{i}.py" for i in range(3)]
    assert _get(ui, "/api/organize/files?module=pages&q=f1")[1]["total"] == 1
    assert _get(ui, "/api/organize/files?module=pages&q=app/*/f2.py")[1]["total"] == 1
    assert _get(ui, "/api/organize/files?module=nowhere")[0] == 404
    assert _get(ui, "/api/organize/files?module=../x")[0] == 404
    assert _get(ui, "/api/organize/files?module=pages&offset=-1")[0] == 404
    assert _get(ui, "/api/organize/nothing")[0] == 404
    assert ui.request("GET", "/api/organize/files?module=pages", token=None)[0] == 403
    assert ui.request("POST", "/api/organize/move", body=b"{}", token="wrong")[0] == 403


@pytest.mark.phase_5
def test_a_preview_names_what_a_move_would_do_and_writes_nothing(ui: _UiServer, repo: Path) -> None:
    root = repo
    before = (root / ".reasonledger" / "modules.yml").read_bytes()
    status, impact = _post(
        ui, "preview", {"selection": {"paths": ["app/common/f0.py"]}, "target": "pages"}
    )
    assert (
        status == 200 and impact["moving"] == 1 and impact["from_modules"] == {"shared-backend": 1}
    )
    assert [d["decision_id"] for d in impact["decisions"]] == ["dec_both"]
    assert impact["decisions"][0]["after"] == ["pages"]
    assert (
        _post(ui, "preview", {"selection": {"paths": ["app/common/f0.py"]}, "target": "no"})[0]
        == 400
    )
    assert (root / ".reasonledger" / "modules.yml").read_bytes() == before


@pytest.mark.phase_5
def test_a_move_is_written_as_a_label_and_undo_puts_everything_back(
    ui: _UiServer, repo: Path
) -> None:
    root = repo
    original = (root / ".reasonledger" / "modules.yml").read_bytes()
    assert _get(ui, "/api/organize/state")[1] == {"can_undo": False, "last": None}
    status, reply = _post(
        ui,
        "move",
        {"selection": {"paths": ["app/common/f0.py", "app/common/f1.py"]}, "target": "pages"},
    )
    assert status == 200 and reply["message"] == "Moved 2 file(s) to pages" and reply["can_undo"]
    assert load_manifest(root).labels == {"app/common/f0.py": "pages", "app/common/f1.py": "pages"}
    pages = _get(ui, "/api/organize/files?module=pages")[1]
    assert pages["total"] == 5
    assert {f["path"]: f["pinned_by"] for f in pages["files"]}[
        "app/common/f0.py"
    ] == "app/common/f0.py"
    status, reply = _post(ui, "undo", {})
    assert status == 200 and reply["message"].startswith("Undid: Moved 2") and not reply["can_undo"]
    assert (root / ".reasonledger" / "modules.yml").read_bytes() == original
    assert _post(ui, "undo", {})[0] == 400  # nothing left to undo


@pytest.mark.phase_5
def test_undo_refuses_when_the_manifest_changed_somewhere_else(ui: _UiServer, repo: Path) -> None:
    root = repo
    _post(ui, "move", {"selection": {"paths": ["app/common/f0.py"]}, "target": "pages"})
    assert main(["modules", "label", "app/common/f2.py", "billing", "--root", str(root)]) == 0
    status, reply = _post(ui, "undo", {})
    assert status == 409 and "changed outside" in reply["error"]
    assert load_manifest(root).labels["app/common/f2.py"] == "billing"  # their edit was not undone


@pytest.mark.phase_5
def test_a_move_can_select_by_filter_and_a_rule_takes_the_folder(ui: _UiServer, repo: Path) -> None:
    root = repo
    status, _ = _post(
        ui, "move", {"selection": {"module": "shared-backend", "query": "f1"}, "target": "billing"}
    )
    assert status == 200 and load_manifest(root).labels == {"app/common/f1.py": "billing"}
    status, reply = _post(
        ui,
        "move",
        {
            "selection": {"paths": ["app/common/f0.py", "app/common/f2.py"]},
            "target": "pages",
            "rule": True,
        },
    )
    assert status == 200 and "app/common/**" in reply["message"]
    assert _owner_of(root, "app/common/f2.py") == "pages"
    assert (
        _post(ui, "move", {"selection": {"paths": ["app/pages/f0.py"]}, "target": "pages"})[0]
        == 400
    )


@pytest.mark.phase_5
def test_module_edits_apply_and_undo_in_reverse_order(ui: _UiServer, repo: Path) -> None:
    root = repo
    assert _post(ui, "confirm", {"ids": ["pages"]})[1]["message"] == "Confirmed pages"
    assert _post(ui, "confirm", {"ids": ["pages"]})[1]["message"] == "Already confirmed"
    assert _post(ui, "rename", {"id": "billing", "name": "Invoicing"})[0] == 200
    assert _post(ui, "reject", {"id": "invoicing", "reason": "noise"})[0] == 200
    ids = {m.id: m.status for m in load_manifest(root).modules}
    assert "invoicing" not in ids and ids["pages"] is ModuleStatus.CONFIRMED
    assert _post(ui, "undo", {})[1]["message"] == "Undid: Rejected invoicing"
    assert _post(ui, "undo", {})[1]["message"] == "Undid: Renamed billing to invoicing"
    assert "billing" in {m.id for m in load_manifest(root).modules}
    status, reply = _post(ui, "merge", {"keep": "pages", "absorb": "billing"})
    assert status == 200 and reply["message"] == "Merged billing into pages"
    assert _post(ui, "merge", {"keep": "pages", "absorb": "pages"})[0] == 400


@pytest.mark.phase_5
def test_a_new_module_from_a_selection_needs_a_name(ui: _UiServer, repo: Path) -> None:
    root = repo
    selection = {"paths": ["app/common/f0.py", "app/common/f1.py"]}
    assert _post(ui, "new-module", {"selection": selection})[0] == 400
    status, reply = _post(ui, "new-module", {"selection": selection, "name": "Webhooks"})
    assert status == 200 and reply["message"] == "Created webhooks from 2 file(s)"
    assert _owner_of(root, "app/common/f0.py") == "webhooks"
    assert _post(ui, "new-module", {"selection": selection, "name": "Pages", "by": "me"})[0] == 400


@pytest.mark.phase_5
def test_malformed_edit_requests_are_refused_not_crashed(ui: _UiServer) -> None:
    for action, payload in (
        ("move", {}),
        ("move", {"selection": "app/x.py", "target": "pages"}),
        ("move", {"selection": {"paths": "app/x.py"}, "target": "pages"}),
        ("move", {"selection": {"paths": ["gone.py"]}, "target": "pages"}),
        ("move", {"selection": {"paths": ["app/pages/f0.py"]}}),
        ("rename", {"id": "pages"}),
        ("confirm", {"ids": "pages", "by": "me"}),
    ):
        assert _post(ui, action, payload)[0] == 400, (action, payload)
    assert _post(ui, "teleport", {})[0] == 404


@pytest.fixture
def inbox_repo(tmp_path: Path) -> Path:
    """Pages (4 files, explicit), billing (a folder and a name family), and new files."""
    paths = {
        "pages": [f"app/pages/p{i}.py" for i in range(4)],
        "billing": ["app/billing/b0.py", "app/billing/b1.py", "x/invoice.py", "y/invoice_a.py"],
    }
    new = [
        "app/pages/new0.py",
        "app/pages/new1.py",
        "app/billing/invoice_export.py",
        "svc/export_a.py",
        "svc/export_b.py",
        "svc/export_c.py",
    ]
    for path in [*paths["pages"], *paths["billing"], *new]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n", encoding="utf-8")
    write_manifest(
        tmp_path,
        Manifest(
            modules=[
                Module(id=mid, name=mid.title(), paths=files, status=ModuleStatus.CONFIRMED)
                for mid, files in paths.items()
            ]
        ),
    )
    return tmp_path


@pytest.fixture
def inbox_ui(inbox_repo: Path, git_identity: str) -> Iterator[_UiServer]:
    server = _UiServer(inbox_repo)
    yield server
    server.close()


def _inbox(ui: _UiServer) -> dict[str, Any]:
    status, view = _get(ui, "/api/organize/inbox")
    assert status == 200
    return view


def _item(view: dict[str, Any], kind: str, target: str | None = None) -> dict[str, Any]:
    return next(i for i in view["items"] if i["kind"] == kind and i["target"] == target)


@pytest.mark.phase_5
def test_the_inbox_lists_suggestions_with_evidence_best_first(inbox_ui: _UiServer) -> None:
    view = _inbox(inbox_ui)
    assert view["counts"] == {"place": 2, "new-module": 1} and view["history"] is False
    first = view["items"][0]
    assert (first["kind"], first["target"], first["confidence"]) == ("place", "billing", "high")
    assert {e["kind"] for e in first["evidence"]} == {"siblings", "name"}
    pages = _item(view, "place", "pages")
    assert pages["files"] == ["app/pages/new0.py", "app/pages/new1.py"]
    assert (
        pages["rule"]["pattern"] == "app/pages/**"
    )  # the two share a folder, and a rule moves no other
    new = next(i for i in view["items"] if i["kind"] == "new-module")
    assert (new["name"], new["file_count"]) == ("Export", 3)
    assert inbox_ui.request("GET", "/api/organize/inbox", token=None)[0] == 403


@pytest.mark.phase_5
def test_accepting_a_suggestion_places_its_files_and_undo_takes_them_back(
    inbox_ui: _UiServer, inbox_repo: Path
) -> None:
    key = _item(_inbox(inbox_ui), "place", "pages")["key"]
    status, reply = _post(inbox_ui, "inbox-accept", {"key": key})
    assert status == 200 and reply["message"] == "Moved 2 file(s) to pages"
    assert load_manifest(inbox_repo).labels == {
        "app/pages/new0.py": "pages",
        "app/pages/new1.py": "pages",
    }
    assert "pages" not in {i["target"] for i in _inbox(inbox_ui)["items"]}
    assert _post(inbox_ui, "undo", {})[0] == 200
    assert load_manifest(inbox_repo).labels == {}
    assert _post(inbox_ui, "inbox-accept", {"key": key})[0] == 200  # the same card is valid again


@pytest.mark.phase_5
def test_a_suggestion_can_go_elsewhere_or_become_a_folder_rule(
    inbox_ui: _UiServer, inbox_repo: Path
) -> None:
    key = _item(_inbox(inbox_ui), "place", "pages")["key"]
    _post(inbox_ui, "inbox-accept", {"key": key, "target": "billing"})
    assert set(load_manifest(inbox_repo).labels.values()) == {"billing"}
    _post(inbox_ui, "undo", {})
    status, reply = _post(inbox_ui, "inbox-accept", {"key": key, "rule": True})
    assert status == 200 and "app/pages/**" in reply["message"]
    assert load_manifest(inbox_repo).labels == {"app/pages/**": "pages"}


@pytest.mark.phase_5
def test_declining_remembers_the_refusal_and_the_file_is_not_suggested_there_again(
    inbox_ui: _UiServer, inbox_repo: Path
) -> None:
    key = _item(_inbox(inbox_ui), "place", "pages")["key"]
    assert (
        _post(inbox_ui, "inbox-decline", {"key": key})[1]["message"]
        == "Declined pages for 2 file(s)"
    )
    assert load_manifest(inbox_repo).declined == {
        "app/pages/new0.py": ["pages"],
        "app/pages/new1.py": ["pages"],
    }
    view = _inbox(inbox_ui)
    assert "pages" not in {i["target"] for i in view["items"]}
    assert view["unsuggested"] == 2  # nothing else points anywhere for them now


@pytest.mark.phase_5
def test_a_group_of_new_files_becomes_a_module_signed_by_the_git_identity(
    inbox_ui: _UiServer, inbox_repo: Path, git_identity: str
) -> None:
    new = next(i for i in _inbox(inbox_ui)["items"] if i["kind"] == "new-module")
    # A name in the request is ignored: the server signs with its own identity.
    status, reply = _post(
        inbox_ui, "inbox-accept", {"key": new["key"], "name": "Exports", "by": "someone-else"}
    )
    assert status == 200 and reply["message"] == "Created exports from 3 file(s)"
    assert reply["module"] == "exports"
    made = next(m for m in load_manifest(inbox_repo).modules if m.id == "exports")
    assert made.confirmed_by == git_identity


@pytest.mark.phase_5
def test_hand_placed_files_offer_one_rule_and_accepting_it_tidies_the_labels(
    inbox_ui: _UiServer, inbox_repo: Path
) -> None:
    for name in ("export_a", "export_b", "export_c"):
        assert (
            _post(
                inbox_ui, "move", {"selection": {"paths": [f"svc/{name}.py"]}, "target": "billing"}
            )[0]
            == 200
        )
    rule = next(i for i in _inbox(inbox_ui)["items"] if i["kind"] == "rule")
    assert rule["target"] == "billing" and rule["rule"]["pattern"] == "svc/**"
    assert _post(inbox_ui, "inbox-accept", {"key": rule["key"]})[1]["message"].startswith(
        "Rule svc/**"
    )
    assert load_manifest(inbox_repo).labels == {"svc/**": "billing"}


@pytest.mark.phase_5
def test_accept_all_takes_only_high_confidence_suggestions_as_one_undoable_edit(
    inbox_ui: _UiServer, inbox_repo: Path
) -> None:
    status, reply = _post(inbox_ui, "inbox-accept-all", {})
    assert status == 200 and reply["message"].startswith("Placed 1 file(s) from 1 high")
    assert load_manifest(inbox_repo).labels == {"app/billing/invoice_export.py": "billing"}
    assert _post(inbox_ui, "inbox-accept-all", {})[0] == 400  # nothing high is left
    assert _post(inbox_ui, "undo", {})[1]["message"].startswith("Undid: Placed 1")
    assert load_manifest(inbox_repo).labels == {}


@pytest.mark.phase_5
def test_a_stale_or_unsuitable_inbox_action_is_refused(inbox_ui: _UiServer) -> None:
    status, reply = _post(inbox_ui, "inbox-accept", {"key": "place:pages:deadbeef"})
    assert status == 400 and "out of date" in reply["error"]
    assert _post(inbox_ui, "inbox-accept", {})[0] == 400
    new = next(i for i in _inbox(inbox_ui)["items"] if i["kind"] == "new-module")
    assert _post(inbox_ui, "inbox-decline", {"key": new["key"]})[0] == 400  # only a suggested home


@pytest.mark.phase_5
def test_accept_all_leaves_out_what_the_person_skipped(
    inbox_ui: _UiServer, inbox_repo: Path
) -> None:
    high = _item(_inbox(inbox_ui), "place", "billing")
    assert _inbox(inbox_ui)["high_places"] == 1
    assert _post(inbox_ui, "inbox-accept-all", {"skipped": [high["key"]]})[0] == 400
    assert (
        load_manifest(inbox_repo).labels == {}
    )  # the one high suggestion was skipped, so none moved


@pytest.mark.phase_5
def test_with_no_git_identity_nothing_is_signed(
    ui: _UiServer, repo: Path, no_git_identity: None
) -> None:
    before = (repo / ".reasonledger" / "modules.yml").read_bytes()
    status, reply = _post(ui, "confirm", {"ids": ["pages"], "by": "typed-name"})
    assert status == 400 and "git config user.name" in reply["error"]
    assert (repo / ".reasonledger" / "modules.yml").read_bytes() == before
