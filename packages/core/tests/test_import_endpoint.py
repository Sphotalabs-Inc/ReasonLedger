"""Phase 5 — where a model call may go: base URL rules, origin-bound consent, no redirects."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from pydantic import ValidationError
from reasonledger_core.consent import DataClass, destination, grant, missing_classes
from reasonledger_core.importer.config import (
    ConfigError,
    ExtractorConfig,
    ExtractorProvider,
    load_extractor_config,
)
from reasonledger_core.importer.endpoint import EndpointError, origin, validate_base_url
from reasonledger_core.importer.llm import LlmError, http_post_json

SECRET = "hunter2-not-a-real-password"


@pytest.mark.phase_5
@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/v1",
        "http://localhost:11434",
        "http://127.0.0.1:18080/v1",
        "http://[::1]:8080",
        "http://box.localhost",
    ],
)
def test_https_anywhere_and_http_only_on_this_machine_are_accepted(url: str) -> None:
    assert validate_base_url(url) == url


@pytest.mark.phase_5
@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("http://api.example.com/v1", "clear text"),
        ("http://192.168.1.20:11434", "clear text"),
        (f"https://user:{SECRET}@api.example.com/v1", "user name or password"),
        ("https://api.example.com/v1?key=abc", "query or fragment"),
        ("https://api.example.com/v1#frag", "query or fragment"),
        ("ftp://api.example.com", "http(s) URL"),
        ("api.example.com/v1", "http(s) URL"),
        ("https://api.example.com:99999", "not a valid URL"),
    ],
)
def test_an_unsafe_base_url_is_refused_without_echoing_it(url: str, reason: str) -> None:
    with pytest.raises(EndpointError) as caught:
        validate_base_url(url)
    assert reason in str(caught.value)
    assert SECRET not in str(caught.value)


@pytest.mark.phase_5
def test_the_config_refuses_an_unsafe_base_url_and_keeps_its_password_out_of_the_error(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError):
        ExtractorConfig(provider=ExtractorProvider.OPENAI_COMPATIBLE, base_url="http://x.test")

    path = tmp_path / ".reasonledger" / "config.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "extractor:\n  provider: openai_compatible\n  model: m\n"
        f"  base_url: https://me:{SECRET}@llm.example.com/v1\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as caught:
        load_extractor_config(tmp_path)
    assert "base_url" in str(caught.value) and SECRET not in str(caught.value)


@pytest.mark.phase_5
def test_origin_keeps_scheme_and_a_non_default_port() -> None:
    assert origin("https://API.Example.com/v1") == "https://api.example.com"
    assert origin("https://api.example.com:443/v1") == "https://api.example.com"
    assert origin("https://api.example.com:8443/v1") == "https://api.example.com:8443"
    assert origin("http://[::1]:8080") == "http://[::1]:8080"


@pytest.mark.phase_5
def test_consent_given_for_one_origin_does_not_cover_another_port_on_the_same_host(
    tmp_path: Path,
) -> None:
    def gateway(url: str) -> ExtractorConfig:
        return ExtractorConfig(
            provider=ExtractorProvider.OPENAI_COMPATIBLE, base_url=url, model="m"
        )

    grant(tmp_path, gateway("https://llm.example.com/v1"), [DataClass.REPO_TEXT])

    assert (
        missing_classes(tmp_path, gateway("https://llm.example.com/v2"), [DataClass.REPO_TEXT])
        == []
    )
    other_port = gateway("https://llm.example.com:8443/v1")
    assert destination(other_port) == "https://llm.example.com:8443"
    assert missing_classes(tmp_path, other_port, [DataClass.REPO_TEXT]) == [DataClass.REPO_TEXT]


class _Recorder(BaseHTTPRequestHandler):
    """Answers every request with a fixed status; records the headers it was sent."""

    status = 200
    location = ""
    seen: list[dict[str, str]]

    def _answer(self) -> None:
        type(self).seen.append(dict(self.headers))
        self.send_response(self.status)
        if self.location:
            self.send_header("Location", self.location)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    do_GET = do_POST = _answer

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib name
        return


@contextmanager
def _serve(handler: type[_Recorder]) -> Iterator[str]:
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def elsewhere() -> Iterator[tuple[str, type[_Recorder]]]:
    handler = type("Elsewhere", (_Recorder,), {"seen": []})
    with _serve(handler) as url:
        yield url, handler


@pytest.mark.phase_5
@pytest.mark.parametrize("status", [301, 302, 303])
def test_a_redirect_is_refused_so_the_api_key_never_follows_it(
    status: int, elsewhere: tuple[str, type[_Recorder]]
) -> None:
    target, landed = elsewhere
    redirector = type(
        "Redirector", (_Recorder,), {"seen": [], "status": status, "location": target + "/steal"}
    )
    with _serve(redirector) as url, pytest.raises(LlmError, match="redirect"):
        http_post_json(url, {"q": 1}, {"x-api-key": "sk-test-key"}, timeout=5)
    assert len(redirector.seen) == 1
    assert landed.seen == []
