"""Test-connection probe for BYOM extractor config."""

from __future__ import annotations

import time

from pydantic import BaseModel

from reasonledger_core.importer.adapters import ExtractorError, build_extractor
from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider, resolve_api_key
from reasonledger_core.importer.llm import ANTHROPIC_DEFAULT_MODEL, HttpPost
from reasonledger_core.importer.scan import ImportSource

PROBE_SOURCE = ImportSource(
    path="__probe__.md",
    text="Connection probe: this document contains no engineering decisions.",
)


class ProbeResult(BaseModel):
    ok: bool
    latency_ms: float | None
    model: str | None
    message: str


def _resolved_model(config: ExtractorConfig) -> str | None:
    if config.model:
        return config.model
    if config.provider is ExtractorProvider.ANTHROPIC:
        return ANTHROPIC_DEFAULT_MODEL
    return None


def _sanitize_message(message: str, api_key: str | None) -> str:
    if not api_key:
        return message
    return message.replace(api_key, "***")


def probe_connection(
    config: ExtractorConfig,
    *,
    api_key: str | None = None,
    http_post: HttpPost | None = None,
) -> ProbeResult:
    """Verify the configured provider returns schema-valid JSON (never raises)."""
    resolved_key = api_key if api_key is not None else resolve_api_key(config)
    model = _resolved_model(config)

    try:
        extractor = build_extractor(config, api_key=resolved_key, http_post=http_post)
    except ExtractorError as exc:
        return ProbeResult(
            ok=False,
            latency_ms=None,
            model=model,
            message=_sanitize_message(str(exc), resolved_key),
        )

    start = time.perf_counter()
    try:
        extractor.extract(PROBE_SOURCE)
    except ExtractorError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return ProbeResult(
            ok=False,
            latency_ms=elapsed_ms,
            model=model,
            message=_sanitize_message(str(exc), resolved_key),
        )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return ProbeResult(
            ok=False,
            latency_ms=elapsed_ms,
            model=model,
            message=_sanitize_message(f"connection failed: {exc}", resolved_key),
        )

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    model_label = model or "model"
    return ProbeResult(
        ok=True,
        latency_ms=elapsed_ms,
        model=model,
        message=(
            f"Connection OK — {model_label} returned schema-valid JSON ({elapsed_ms:.0f} ms)."
        ),
    )
