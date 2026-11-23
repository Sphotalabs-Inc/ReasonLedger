"""P0-4 S7: BYOM extractor config — provider selection, secrets never on disk."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from reasonledger_core.importer.config import (
    ExtractorConfig,
    ExtractorProvider,
    load_extractor_config,
    resolve_api_key,
    write_extractor_config,
)


@pytest.mark.phase_3
def test_config_default_disabled(tmp_path: Path) -> None:
    # No config file → extraction disabled by default (opt-in).
    assert load_extractor_config(tmp_path).provider is ExtractorProvider.DISABLED


@pytest.mark.phase_3
def test_config_provider_selection(tmp_path: Path) -> None:
    (tmp_path / ".reasonledger").mkdir()
    (tmp_path / ".reasonledger" / "config.yml").write_text(
        "extractor:\n"
        "  provider: anthropic\n"
        "  model: claude-sonnet-5\n"
        "  api_key_env: ANTHROPIC_API_KEY\n",
        encoding="utf-8",
    )
    config = load_extractor_config(tmp_path)
    assert config.provider is ExtractorProvider.ANTHROPIC
    assert config.model == "claude-sonnet-5"
    assert config.api_key_env == "ANTHROPIC_API_KEY"


@pytest.mark.phase_3
def test_config_has_no_secret_field() -> None:
    # Structural guarantee: the config cannot hold a raw secret, only an env name.
    assert "api_key" not in ExtractorConfig.model_fields
    assert "api_key_env" in ExtractorConfig.model_fields


@pytest.mark.phase_3
def test_config_write_persists_no_secret(tmp_path: Path) -> None:
    config = ExtractorConfig(
        provider=ExtractorProvider.ANTHROPIC,
        model="claude-sonnet-5",
        api_key_env="ANTHROPIC_API_KEY",
    )
    path = write_extractor_config(tmp_path, config)
    text = path.read_text("utf-8")
    assert "ANTHROPIC_API_KEY" in text  # the env-var name is written
    assert "sk-" not in text  # no secret value shape ever reaches disk
    assert load_extractor_config(tmp_path) == config  # round-trips


@pytest.mark.phase_3
def test_writing_extractor_config_preserves_other_top_level_keys(tmp_path: Path) -> None:
    """This function owns the `extractor` section, not the whole file.

    `metrics: true` is the repo's opt-in to local pilot metrics. Rewriting the document
    wholesale would delete it the next time someone changed their model settings —
    silent data loss that turns the pilot's counters off with no trace.
    """
    path = tmp_path / ".reasonledger" / "config.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("metrics: true\nextractor:\n  provider: disabled\n", encoding="utf-8")

    write_extractor_config(
        tmp_path,
        ExtractorConfig(provider=ExtractorProvider.LOCAL, base_url="https://x.test", model="m"),
    )

    data = yaml.safe_load(path.read_text("utf-8"))
    assert data["metrics"] is True
    assert data["extractor"]["provider"] == "local"


@pytest.mark.phase_3
def test_resolve_api_key_from_env() -> None:
    config = ExtractorConfig(provider=ExtractorProvider.ANTHROPIC, api_key_env="MY_KEY")
    assert resolve_api_key(config, env={"MY_KEY": "sk-abc"}) == "sk-abc"
    assert resolve_api_key(config, env={}) is None
    # Disabled/unset config never resolves a key.
    assert resolve_api_key(ExtractorConfig(), env={"MY_KEY": "sk-abc"}) is None
