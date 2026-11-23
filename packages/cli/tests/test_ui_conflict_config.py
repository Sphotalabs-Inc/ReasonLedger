"""Conflict-detection settings in the local UI — `/api/conflict-config`."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_cli.ui_html import assets_dir
from reasonledger_core.reasoning.conflict_config import (
    CONFLICT_CONFIG_PATH,
    ConflictConfig,
    load_conflict_config,
    write_conflict_config,
)
from test_ui_server import _UiServer

_LOCAL_AVAILABLE = "reasonledger_core.reasoning.conflict_config.local_embedder_available"


@pytest.fixture
def ui(tmp_path: Path) -> Iterator[_UiServer]:
    server = _UiServer(tmp_path)
    yield server
    server.close()


def _get(ui: _UiServer) -> tuple[int, dict[str, Any]]:
    status, raw = ui.request("GET", "/api/conflict-config")
    return status, json.loads(raw)


def _post(ui: _UiServer, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    status, raw = ui.request("POST", "/api/conflict-config", body=json.dumps(body).encode())
    return status, json.loads(raw)


@pytest.mark.phase_4
def test_get_returns_defaults_when_absent(ui: _UiServer) -> None:
    status, payload = _get(ui)
    assert status == 200
    assert payload["context_similarity_gate"] is None
    assert payload["shortlist_k"] == 5
    assert payload["judge_model"] is None
    assert payload["embedding_provider"] is None
    assert payload["embedding_providers"] == ["deterministic", "local"]


@pytest.mark.phase_4
def test_post_partial_update_preserves_other_fields(
    tmp_path: Path, ui: _UiServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_LOCAL_AVAILABLE, lambda: True)
    write_conflict_config(tmp_path, ConflictConfig(context_similarity_gate=0.4))

    status, payload = _post(ui, {"embedding_provider": "local"})
    assert status == 200
    assert payload["saved"] is True
    assert payload["context_similarity_gate"] == 0.4
    assert payload["embedding_provider"] == "local"

    reloaded = load_conflict_config(tmp_path)
    assert reloaded.context_similarity_gate == 0.4
    assert reloaded.embedding_provider == "local"


@pytest.mark.phase_4
def test_post_can_clear_embedding_provider_back_to_unset(tmp_path: Path, ui: _UiServer) -> None:
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))

    status, payload = _post(ui, {"embedding_provider": None})
    assert status == 200
    assert payload["embedding_provider"] is None
    assert load_conflict_config(tmp_path).embedding_provider is None


@pytest.mark.phase_4
def test_post_rejects_unknown_embedding_provider(tmp_path: Path, ui: _UiServer) -> None:
    status, payload = _post(ui, {"embedding_provider": "hackerman"})
    assert status == 400
    assert "hackerman" in payload["error"] or "embedding_provider" in payload["error"]
    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()


@pytest.mark.phase_4
def test_post_rejects_out_of_range_gate(tmp_path: Path, ui: _UiServer) -> None:
    status, payload = _post(ui, {"context_similarity_gate": 1.5})
    assert status == 400
    assert "error" in payload
    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()


@pytest.mark.phase_4
def test_malformed_conflict_config_reports_the_parse_error(tmp_path: Path, ui: _UiServer) -> None:
    path = tmp_path / CONFLICT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("context_similarity_gate: [not, a, float]\n", encoding="utf-8")

    status, payload = _get(ui)
    assert status == 500
    assert "Traceback" not in json.dumps(payload)


@pytest.mark.phase_4
def test_conflict_config_endpoints_require_token(tmp_path: Path, ui: _UiServer) -> None:
    routes = [("GET", "/api/conflict-config"), ("POST", "/api/conflict-config")]
    body = json.dumps({"context_similarity_gate": 0.5}).encode()

    for method, path in routes:
        payload = body if method == "POST" else None
        status, _ = ui.request(method, path, body=payload, token=None)
        assert status == 403, path
        status, _ = ui.request(method, path, body=payload, token="wrong-token")
        assert status == 403, path
        status, _ = ui.request(method, path, body=payload, origin="http://evil.example")
        assert status == 403, path

    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()


@pytest.mark.phase_4
def test_static_export_has_no_conflict_settings_panel(tmp_path: Path) -> None:
    out = tmp_path / "ledger.html"
    assert main(["status", "--root", str(tmp_path), "--html", str(out)]) == EXIT_PASS
    html = out.read_text("utf-8")

    assert "conflict_config.js" not in html
    for markup in ("<form", "<select", "<input", "<button"):
        assert markup not in html, markup

    body = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    for text in ("Conflict settings", "rl-conflict-settings"):
        assert text not in body, text


@pytest.mark.phase_4
def test_conflict_config_js_is_shipped() -> None:
    assert (assets_dir() / "conflict_config.js").is_file()


@pytest.mark.phase_4
def test_post_refuses_local_when_extra_missing(
    tmp_path: Path, ui: _UiServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_LOCAL_AVAILABLE, lambda: False)
    status, payload = _post(ui, {"embedding_provider": "local"})
    assert status == 400
    assert "--extra embeddings" in payload["error"]
    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()
