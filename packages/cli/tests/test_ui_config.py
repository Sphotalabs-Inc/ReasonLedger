"""S16: model configuration in the local UI.

The whole point of these tests is the negative space. This is the one UI path that sits
next to a secret, so most of what follows asserts what the server *cannot* be made to
do: return a key, store one, or reach the network without an explicit click.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from reasonledger_cli import ui_config
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_cli.ui_html import assets_dir
from reasonledger_core.importer.config import (
    CONFIG_PATH,
    ExtractorConfig,
    ExtractorProvider,
    load_extractor_config,
    write_extractor_config,
)
from reasonledger_core.importer.probe import ProbeResult
from test_ui_server import _UiServer

FAKE_KEY = "sk-live-do-not-leak-0123456789"
KEY_ENV = "RL_TEST_API_KEY"


@pytest.fixture
def ui(tmp_path: Path) -> Iterator[_UiServer]:
    server = _UiServer(tmp_path)
    yield server
    server.close()


def _get_config(ui: _UiServer) -> tuple[int, dict[str, Any]]:
    status, raw = ui.request("GET", "/api/config")
    return status, json.loads(raw)


def _post_config(ui: _UiServer, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    status, raw = ui.request("POST", "/api/config", body=json.dumps(body).encode())
    return status, json.loads(raw)


@pytest.mark.phase_3
def test_get_config_returns_provider_without_secret(
    tmp_path: Path, ui: _UiServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Presence is a boolean. Not a prefix, not a suffix, not a length."""
    monkeypatch.setenv(KEY_ENV, FAKE_KEY)
    write_extractor_config(
        tmp_path,
        ExtractorConfig(
            provider=ExtractorProvider.ANTHROPIC,
            model="claude-sonnet-4-5",
            api_key_env=KEY_ENV,
        ),
    )

    status, raw = ui.request("GET", "/api/config")
    assert status == 200
    body = raw.decode("utf-8")
    payload = json.loads(body)

    assert payload["provider"] == "anthropic"
    assert payload["model"] == "claude-sonnet-4-5"
    assert payload["api_key_env"] == KEY_ENV
    assert payload["api_key_present"] is True

    assert FAKE_KEY not in body
    # No fragment of it either — a prefix or a length is still a disclosure.
    for size in range(6, len(FAKE_KEY)):
        assert FAKE_KEY[:size] not in body
        assert FAKE_KEY[-size:] not in body


@pytest.mark.phase_3
def test_get_config_defaults_to_disabled(ui: _UiServer) -> None:
    """A fresh repo has no config.yml. That is the default state, not an error."""
    status, payload = _get_config(ui)
    assert status == 200
    assert payload["provider"] == "disabled"
    assert payload["api_key_present"] is False
    assert payload["providers"] == ["anthropic", "openai_compatible", "local"]
    assert "disabled" not in payload["providers"]


@pytest.mark.phase_3
def test_post_config_writes_yaml(tmp_path: Path, ui: _UiServer) -> None:
    status, payload = _post_config(
        ui,
        {
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "base_url": "https://gateway.internal/v1",
            "api_key_env": "OPENAI_API_KEY",
        },
    )
    assert status == 200
    assert payload["saved"] is True
    assert payload["path"] == str(tmp_path / CONFIG_PATH)

    # The other door onto the same file has to read back exactly what the UI wrote.
    reloaded = load_extractor_config(tmp_path)
    assert reloaded.provider is ExtractorProvider.OPENAI_COMPATIBLE
    assert reloaded.model == "gpt-4o-mini"
    assert reloaded.base_url == "https://gateway.internal/v1"
    assert reloaded.api_key_env == "OPENAI_API_KEY"


@pytest.mark.phase_3
def test_post_config_import_command_carries_the_saved_extractor(
    tmp_path: Path, ui: _UiServer
) -> None:
    """The copyable command must name the model that was just saved."""
    _, payload = _post_config(ui, {"provider": "anthropic", "model": "claude-sonnet-4-5"})
    assert "--extracted-by anthropic/claude-sonnet-4-5" in payload["import_command"]
    assert str(tmp_path) in payload["import_command"]


@pytest.mark.phase_3
@pytest.mark.parametrize("field", ["api_key", "apiKey", "key", "token", "secret", "API-KEY"])
def test_post_config_rejects_raw_secret_field(tmp_path: Path, ui: _UiServer, field: str) -> None:
    """Refused, never silently dropped.

    Dropping it would let a user believe a key was saved when it went nowhere — and
    would invite a later contributor to "fix" that by persisting it.
    """
    status, payload = _post_config(
        ui, {"provider": "anthropic", "model": "claude-sonnet-4-5", field: FAKE_KEY}
    )
    assert status == 400
    assert field in payload["error"]

    assert not (tmp_path / CONFIG_PATH).exists()
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    for path in written:
        assert FAKE_KEY not in path.read_text(encoding="utf-8", errors="ignore"), path


@pytest.mark.phase_3
def test_post_config_rejects_unknown_provider(tmp_path: Path, ui: _UiServer) -> None:
    write_extractor_config(tmp_path, ExtractorConfig(provider=ExtractorProvider.ANTHROPIC))
    before = (tmp_path / CONFIG_PATH).read_text("utf-8")

    status, payload = _post_config(ui, {"provider": "hackerman"})
    assert status == 400
    assert "hackerman" in payload["error"]
    assert "anthropic, openai_compatible, local" in payload["error"]
    assert (tmp_path / CONFIG_PATH).read_text("utf-8") == before

    status, payload = _post_config(ui, {"model": "claude-sonnet-4-5"})
    assert status == 400
    assert "provider required" in payload["error"]


@pytest.mark.phase_3
def test_config_endpoints_require_token(tmp_path: Path, ui: _UiServer) -> None:
    routes = [("GET", "/api/config"), ("POST", "/api/config"), ("POST", "/api/config/test")]
    body = json.dumps({"provider": "anthropic"}).encode()

    for method, path in routes:
        payload = body if method == "POST" else None
        status, _ = ui.request(method, path, body=payload, token=None)
        assert status == 403, path
        status, _ = ui.request(method, path, body=payload, token="wrong-token")
        assert status == 403, path
        status, _ = ui.request(method, path, body=payload, origin="http://evil.example")
        assert status == 403, path

    assert not (tmp_path / CONFIG_PATH).exists()

    # Mutations stay POST-only; the PUT/DELETE guards must not have grown a config door.
    for method in ("PUT", "DELETE"):
        status, _ = ui.request(method, "/api/config", body=body)
        assert status == 405, method


@pytest.mark.phase_3
def test_config_test_endpoint_uses_probe(
    tmp_path: Path, ui: _UiServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The probe is the only outbound call, and it is stubbed here — CI never dials out."""
    status, raw = ui.request("POST", "/api/config/test", body=b"{}")
    assert status == 400
    assert "disabled" in json.loads(raw)["error"]

    write_extractor_config(
        tmp_path,
        ExtractorConfig(provider=ExtractorProvider.ANTHROPIC, model="claude-sonnet-4-5"),
    )

    calls: list[ExtractorConfig] = []

    def fake_probe(config: ExtractorConfig) -> ProbeResult:
        calls.append(config)
        return ProbeResult(ok=True, latency_ms=12.0, model=config.model, message="Connection OK")

    monkeypatch.setattr(ui_config, "probe_connection", fake_probe)

    status, raw = ui.request("POST", "/api/config/test", body=b"{}")
    assert status == 200
    assert json.loads(raw) == {"ok": True, "message": "Connection OK"}
    assert [c.model for c in calls] == ["claude-sonnet-4-5"]


@pytest.mark.phase_3
def test_config_test_never_fires_without_an_explicit_request(
    tmp_path: Path, ui: _UiServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loading the page or reading/saving config must not probe a provider."""
    write_extractor_config(
        tmp_path, ExtractorConfig(provider=ExtractorProvider.ANTHROPIC, model="claude-sonnet-4-5")
    )
    probed: list[ExtractorConfig] = []

    def recording_probe(config: ExtractorConfig) -> ProbeResult:
        probed.append(config)
        return ProbeResult(ok=True, latency_ms=1.0, model=config.model, message="unexpected")

    monkeypatch.setattr(ui_config, "probe_connection", recording_probe)

    ui.request("GET", "/", token=None)
    ui.request("GET", "/api/config")
    ui.request("GET", "/api/view")
    _post_config(ui, {"provider": "anthropic", "model": "claude-sonnet-4-5"})

    assert probed == []


@pytest.mark.phase_3
def test_malformed_config_reports_the_parse_error(tmp_path: Path, ui: _UiServer) -> None:
    """A broken config.yml is a 500 with the parse message — never a stack trace."""
    path = tmp_path / CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("extractor: [not, a, mapping]\n", encoding="utf-8")

    for method, route in (("GET", "/api/config"), ("POST", "/api/config/test")):
        status, raw = ui.request(method, route, body=b"{}" if method == "POST" else None)
        assert status == 500, route
        assert "extractor" in json.loads(raw)["error"]
        assert "Traceback" not in raw.decode("utf-8")


@pytest.mark.phase_3
def test_static_export_has_no_settings_panel(tmp_path: Path) -> None:
    """No server to save to, so the export must carry no form and no config.js."""
    out = tmp_path / "ledger.html"
    assert main(["status", "--root", str(tmp_path), "--html", str(out)]) == EXIT_PASS
    html = out.read_text("utf-8")

    assert "config.js" not in html
    assert "/api/" not in html
    # No control of any kind: an export has no server, so every one would be dead.
    for markup in ("<form", "<select", "<input", "<button"):
        assert markup not in html, markup

    # The inlined stylesheet still carries the panel's (inert) rules, as it already does
    # for Refresh and the why form. Nothing outside it may mention the panel.
    body = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    for text in ("Model settings", "Test connection", "api_key_env", "rl-settings"):
        assert text not in body, text


@pytest.mark.phase_3
def test_config_js_never_names_a_key_shaped_placeholder() -> None:
    """The field is a variable *name*. A `sk-…` placeholder would invite pasting a key."""
    source = (assets_dir() / "config.js").read_text("utf-8")
    assert "ANTHROPIC_API_KEY" in source
    assert "sk-" not in source
    assert "not the key itself" in source
    assert "The key is never saved to disk." in source


@pytest.mark.phase_5
def test_post_config_refuses_a_clear_text_or_credentialed_base_url(
    tmp_path: Path, ui: _UiServer
) -> None:
    for base_url in ("http://gateway.internal/v1", "https://me:pw-123456@gateway.internal/v1"):
        status, payload = _post_config(
            ui, {"provider": "openai_compatible", "model": "m", "base_url": base_url}
        )
        assert status == 400
        assert "base_url" in payload["error"] and "pw-123456" not in payload["error"]
    assert not (tmp_path / CONFIG_PATH).exists()
