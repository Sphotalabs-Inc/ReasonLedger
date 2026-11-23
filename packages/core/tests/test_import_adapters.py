"""P0-4 S8: real extractor adapters — constrained output, validate-and-retry."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from reasonledger_core.importer.adapters import (
    EXTRACTION_TASK,
    ExtractorError,
    _validate_candidates,
    build_extractor,
)
from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.extractor import DecisionCandidate, Extractor
from reasonledger_core.importer.llm import anthropic_payload, openai_compatible_payload
from reasonledger_core.importer.scan import ImportSource

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "import"

SAMPLE_SOURCE = ImportSource(
    path="docs/policy.md",
    text="# Timestamps\nWe store all timestamps in UTC.",
)

EXPECTED_CANDIDATE = DecisionCandidate(
    context="Timestamp storage timezone policy",
    choice="UTC",
    source_ref="docs/policy.md#timestamps",
    alternatives_rejected=["server-local"],
    justifies=["backend/app/date_utils.py"],
    confidence="high",
)

MALFORMED_OPENAI_CONTENT = '{"decisions":[{"context":"x"}]}'


def _load_json(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text("utf-8"))
    return payload


def _anthropic_config() -> ExtractorConfig:
    return ExtractorConfig(
        provider=ExtractorProvider.ANTHROPIC,
        model="claude-sonnet-5",
        api_key_env="ANTHROPIC_API_KEY",
    )


def _openai_config() -> ExtractorConfig:
    return ExtractorConfig(
        provider=ExtractorProvider.OPENAI_COMPATIBLE,
        base_url="https://api.example.com/v1",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
    )


@pytest.mark.phase_3
def test_adapter_parses_recorded_anthropic_response() -> None:
    response = _load_json("anthropic_response.json")

    def fake_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        assert url.endswith("/v1/messages")
        return response

    extractor = build_extractor(_anthropic_config(), api_key="test-key", http_post=fake_post)
    candidates = extractor.extract(SAMPLE_SOURCE)
    assert candidates == [EXPECTED_CANDIDATE]


@pytest.mark.phase_3
def test_adapter_parses_recorded_openai_compatible_response() -> None:
    response = _load_json("openai_compatible_response.json")

    def fake_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        assert url.endswith("/chat/completions")
        return response

    extractor = build_extractor(_openai_config(), api_key="test-key", http_post=fake_post)
    candidates = extractor.extract(SAMPLE_SOURCE)
    assert candidates == [EXPECTED_CANDIDATE]


@pytest.mark.phase_3
def test_constrained_output_retry() -> None:
    valid = _load_json("openai_compatible_response.json")
    calls = 0

    def fake_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": MALFORMED_OPENAI_CONTENT,
                        }
                    }
                ]
            }
        return valid

    extractor = build_extractor(_openai_config(), api_key="test-key", http_post=fake_post)
    candidates = extractor.extract(SAMPLE_SOURCE)
    assert candidates == [EXPECTED_CANDIDATE]
    assert calls == 2


@pytest.mark.phase_3
def test_retry_exhausted_raises() -> None:
    def fake_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": MALFORMED_OPENAI_CONTENT,
                    }
                }
            ]
        }

    extractor = build_extractor(_openai_config(), api_key="test-key", http_post=fake_post)
    with pytest.raises(ExtractorError, match="extraction failed after retry"):
        extractor.extract(SAMPLE_SOURCE)


@pytest.mark.phase_3
def test_build_extractor_disabled_raises() -> None:
    with pytest.raises(ExtractorError, match="extraction is disabled"):
        build_extractor(ExtractorConfig())


@pytest.mark.phase_3
def test_adapter_never_calls_network_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_urlopen(*args: object, **kwargs: object) -> object:
        raise AssertionError("real network must not be called in CI")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)
    response = _load_json("anthropic_response.json")
    seen: list[str] = []

    def fake_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        seen.append(url)
        return response

    extractor = build_extractor(_anthropic_config(), api_key="test-key", http_post=fake_post)
    assert isinstance(extractor, Extractor)
    extractor.extract(SAMPLE_SOURCE)
    assert len(seen) == 1


@pytest.mark.phase_3
def test_anthropic_request_matches_fixture() -> None:
    expected_request = _load_json("anthropic_request.json")
    response = _load_json("anthropic_response.json")
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return response

    extractor = build_extractor(_anthropic_config(), api_key="secret-key", http_post=fake_post)
    extractor.extract(SAMPLE_SOURCE)
    assert captured["payload"] == expected_request
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers.get("x-api-key") == "secret-key"
    assert headers.get("anthropic-version")


@pytest.mark.phase_3
def test_openai_compatible_request_matches_fixture() -> None:
    expected_request = _load_json("openai_compatible_request.json")
    response = _load_json("openai_compatible_response.json")
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        payload: dict[str, object],
        headers: Mapping[str, str],
        timeout: float,
    ) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return response

    extractor = build_extractor(_openai_config(), api_key="secret-key", http_post=fake_post)
    extractor.extract(SAMPLE_SOURCE)
    assert captured["payload"] == expected_request
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers.get("Authorization") == "Bearer secret-key"


@pytest.mark.phase_3
def test_build_payload_helpers_unit() -> None:
    payload = {"decisions": [EXPECTED_CANDIDATE.model_dump(mode="json")]}
    assert _validate_candidates(payload) == [EXPECTED_CANDIDATE]
    with pytest.raises(ValidationError):
        _validate_candidates({"decisions": [{"context": "only context"}]})

    messages: list[dict[str, object]] = [{"role": "user", "content": "hello"}]
    assert anthropic_payload(EXTRACTION_TASK, model="claude-sonnet-5", messages=messages)[
        "tool_choice"
    ]
    assert openai_compatible_payload(EXTRACTION_TASK, model="m", messages=messages)[
        "response_format"
    ]
