"""Bring-your-own-model config for the decision extractor.

Non-secret settings (provider, base_url, model) live in a committable
``.reasonledger/config.yml`` so a team shares the model choice. The API key is
referenced by env-var **name** and resolved at runtime — the secret value is
never held on the config object nor written to disk. ``ExtractorConfig`` has no
field that can hold a raw secret, which makes leaking one structurally
impossible.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError, field_validator

from reasonledger_core.importer.endpoint import validate_base_url

CONFIG_PATH = Path(".reasonledger/config.yml")


class ExtractorProvider(StrEnum):
    DISABLED = "disabled"  # default — import extraction is off until configured
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"  # OpenAI / Azure / gateways
    LOCAL = "local"  # Ollama / vLLM, in-boundary


class ExtractorConfig(BaseModel):
    """BYOM extractor config. Holds no secret — only the env-var name for the key."""

    provider: ExtractorProvider = ExtractorProvider.DISABLED
    base_url: str | None = None
    model: str | None = None
    api_key_env: str | None = None

    @field_validator("base_url")
    @classmethod
    def _checked_base_url(cls, value: str | None) -> str | None:
        return validate_base_url(value) if value else value


class ConfigError(ValueError):
    """Raised when the extractor config file is malformed."""


def load_extractor_config(root: Path, *, config_path: Path | None = None) -> ExtractorConfig:
    """Load extractor config from ``.reasonledger/config.yml`` (disabled if absent)."""
    path = root / (config_path or CONFIG_PATH)
    if not path.is_file():
        return ExtractorConfig()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid config YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("config.yml must be a mapping")
    section = data.get("extractor", {})
    if not isinstance(section, dict):
        raise ConfigError("config.yml 'extractor' must be a mapping")
    return parse_extractor_config(section)


def parse_extractor_config(values: Mapping[str, Any]) -> ExtractorConfig:
    """``values`` as a config, or ConfigError naming each problem without echoing the input."""
    try:
        return ExtractorConfig.model_validate(dict(values))
    except ValidationError as exc:
        # Built from each error's message alone: pydantic's own text echoes the input, and a
        # refused base_url may be refused precisely because it carries a password.
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigError(f"invalid extractor config: {problems}") from exc


def write_extractor_config(
    root: Path,
    config: ExtractorConfig,
    *,
    config_path: Path | None = None,
) -> Path:
    """Persist non-secret extractor config. There is no code path that writes a secret.

    Other top-level keys (``metrics``, anything a later version adds) are read back and
    preserved: this function owns the ``extractor`` section, not the file. Rewriting the
    whole document would silently delete a reader's opt-in the next time they touched
    their model settings — a data-loss bug that leaves no trace.
    """
    path = root / (config_path or CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            existing = None
        if isinstance(existing, dict):
            payload = {key: value for key, value in existing.items() if key != "extractor"}
    payload["extractor"] = config.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def extracted_by_label(config: ExtractorConfig) -> str:
    """The ``provider/model`` identity an import records as its extractor.

    Shared so the CLI's derived ``--extracted-by`` and the value the UI offers for
    copying cannot drift into recording two different extractors for one model.
    """
    if config.model:
        return f"{config.provider.value}/{config.model}"
    return config.provider.value


def resolve_api_key(
    config: ExtractorConfig,
    *,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Resolve the API key from the environment by name (never persisted)."""
    if not config.api_key_env:
        return None
    source = env if env is not None else os.environ
    return source.get(config.api_key_env)
