"""P0-4 S9: test-connection probe — latency on success, graceful failures."""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from reasonledger_core.importer.adapters import ExtractorError
from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.probe import probe_connection

EMPTY_OPENAI_RESPONSE: dict[str, object] = {
    "choices": [{"message": {"role": "assistant", "content": '{"decisions":[]}'}}]
}


def _openai_config() -> ExtractorConfig:
    return ExtractorConfig(
        provider=ExtractorProvider.OPENAI_COMPATIBLE,
        base_url="https://api.example.com/v1",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
    )


@pytest.mark.phase_3
def test_probe_success_reports_latency() -> None:
    def fake_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        return EMPTY_OPENAI_RESPONSE

    result = probe_connection(_openai_config(), api_key="test-key", http_post=fake_post)
    assert result.ok is True
    assert result.latency_ms is not None
    assert result.latency_ms >= 0.0
    assert result.model == "gpt-4o-mini"
    assert "Connection OK" in result.message


@pytest.mark.phase_3
def test_probe_failure_is_graceful() -> None:
    secret = "secret-key-should-not-leak"

    def raise_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        raise ExtractorError(f"HTTP request failed: unauthorized Bearer {secret}")

    network = probe_connection(_openai_config(), api_key=secret, http_post=raise_post)
    assert network.ok is False
    assert network.message
    assert secret not in network.message

    calls = 0

    def malformed_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "choices": [
                {"message": {"role": "assistant", "content": '{"decisions":[{"context":"x"}]}'}}
            ]
        }

    malformed = probe_connection(_openai_config(), api_key=secret, http_post=malformed_post)
    assert malformed.ok is False
    assert malformed.message
    assert secret not in malformed.message
    assert calls == 2  # validate-and-retry exhausted

    disabled = probe_connection(ExtractorConfig())
    assert disabled.ok is False
    assert disabled.message
    assert "disabled" in disabled.message.lower()
