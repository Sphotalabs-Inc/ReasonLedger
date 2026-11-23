"""`reasonledger ui` — the first-run checklist facts, consent, and the model-free quick map."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from reasonledger_core.importer.config import (
    ExtractorConfig,
    ExtractorProvider,
    write_extractor_config,
)
from reasonledger_mcp.tools import call_record_decision
from test_ui_server import _UiServer

CLOUD = ExtractorConfig(provider=ExtractorProvider.ANTHROPIC, model="claude-sonnet-5")
LOCAL = ExtractorConfig(
    provider=ExtractorProvider.LOCAL, base_url="http://localhost:11434", model="llama3.1"
)


@pytest.fixture
def ui(tmp_path: Path) -> Iterator[_UiServer]:
    server = _UiServer(tmp_path)
    yield server
    server.close()


def _get(ui: _UiServer, path: str) -> dict[str, object]:
    status, raw = ui.request("GET", path)
    assert status == 200, raw
    return json.loads(raw)


def _post(ui: _UiServer, path: str, body: dict[str, object]) -> tuple[int, dict[str, object]]:
    status, raw = ui.request("POST", path, body=json.dumps(body).encode())
    return status, json.loads(raw)


@pytest.mark.phase_5
def test_setup_facts_on_a_brand_new_repo(tmp_path: Path, ui: _UiServer) -> None:
    facts = _get(ui, "/api/setup")

    assert facts["ledger"] is False and facts["mcp_files"] == []
    assert facts["decisions"] == 0 and facts["proposals"] == 0
    assert facts["map"] == {"modules": 0, "confirmed": 0}
    model = facts["model"]
    assert (
        isinstance(model, dict) and model["configured"] is False and model["off_machine"] is False
    )


@pytest.mark.phase_5
def test_setup_facts_follow_the_repo_as_it_fills_in(tmp_path: Path, ui: _UiServer) -> None:
    (tmp_path / ".reasonledger").mkdir()
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")
    call_record_decision(
        tmp_path, context="Which store?", choice="sqlite", ai_tool="claude", model="m"
    )
    write_extractor_config(tmp_path, CLOUD)

    facts = _get(ui, "/api/setup")

    assert facts["ledger"] is True and facts["mcp_files"] == [".mcp.json"]
    assert facts["decisions"] == 1
    model = facts["model"]
    assert isinstance(model, dict)
    assert model["off_machine"] is True and model["destination"] == "https://api.anthropic.com"


@pytest.mark.phase_5
def test_consent_is_grantable_and_revocable_from_the_ui(tmp_path: Path, ui: _UiServer) -> None:
    write_extractor_config(tmp_path, CLOUD)

    before = _get(ui, "/api/consent")
    assert before["off_machine"] is True
    assert not any(item["allowed"] for item in before["classes"])  # type: ignore[index,union-attr]

    status, after = _post(ui, "/api/consent", {"action": "grant", "classes": ["paths"]})
    assert status == 200
    allowed = {item["id"] for item in after["classes"] if item["allowed"]}  # type: ignore[index,union-attr]
    assert allowed == {"paths"}

    status, cleared = _post(ui, "/api/consent", {"action": "revoke", "classes": []})
    assert status == 200 and not any(item["allowed"] for item in cleared["classes"])  # type: ignore[index,union-attr]


@pytest.mark.phase_5
def test_consent_refuses_nonsense_and_a_model_on_this_machine(
    tmp_path: Path, ui: _UiServer
) -> None:
    write_extractor_config(tmp_path, LOCAL)

    assert _post(ui, "/api/consent", {"action": "grant", "classes": ["paths"]})[0] == 400
    assert _post(ui, "/api/consent", {"action": "grant", "classes": ["bogus"]})[0] == 400
    assert _post(ui, "/api/consent", {"action": "grant"})[0] == 400


@pytest.mark.phase_5
def test_consent_and_scan_need_the_session_token(ui: _UiServer) -> None:
    for method, path in (
        ("GET", "/api/setup"),
        ("GET", "/api/consent"),
        ("POST", "/api/consent"),
        ("POST", "/api/map/scan"),
    ):
        status, _ = ui.request(method, path, body=b"{}" if method == "POST" else None, token=None)
        assert status == 403, (method, path)


@pytest.mark.phase_5
def test_quick_map_button_writes_a_map_the_map_tab_can_read(tmp_path: Path, ui: _UiServer) -> None:
    for folder in ("orders", "payments"):
        for index in range(4):
            path = tmp_path / "app" / folder / f"f{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x = 1\n", encoding="utf-8")
    assert _get(ui, "/api/map")["empty"] is True

    status, outcome = _post(ui, "/api/map/scan", {})

    assert status == 200 and outcome["proposed"] >= 1  # type: ignore[operator]
    assert _get(ui, "/api/map")["empty"] is False
