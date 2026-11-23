"""Per-repo conflict-detection tuning — `.reasonledger/conflict.yml`."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.reasoning.config import SHORTLIST_K
from reasonledger_core.reasoning.conflict_config import (
    CONFLICT_CONFIG_PATH,
    ConflictConfig,
    ConflictConfigError,
    effective_conflict_config,
    load_conflict_config,
    resolve_conflict_embedder,
    resolve_conflict_embedder_with_status,
    unavailable_provider_error,
    write_conflict_config,
)
from reasonledger_core.reasoning.embeddings import DeterministicEmbedder


@pytest.mark.phase_4
def test_defaults_when_absent(tmp_path: Path) -> None:
    config = load_conflict_config(tmp_path)
    assert config.context_similarity_gate is None  # the embedder's own floor applies
    assert config.shortlist_k == SHORTLIST_K
    assert config.judge_model is None
    assert config.embedding_provider is None


@pytest.mark.phase_4
def test_write_load_round_trip(tmp_path: Path) -> None:
    config = ConflictConfig(
        context_similarity_gate=0.5,
        shortlist_k=8,
        judge_model="claude-haiku-5",
        embedding_provider="local",
    )
    path = write_conflict_config(tmp_path, config)
    assert path == tmp_path / CONFLICT_CONFIG_PATH
    assert load_conflict_config(tmp_path) == config


@pytest.mark.phase_4
def test_write_omits_unset_provider(tmp_path: Path) -> None:
    """`embedding_provider: null` in the file would read back the same as absent,
    but the file should stay minimal when the value is genuinely unset."""
    write_conflict_config(tmp_path, ConflictConfig())
    text = (tmp_path / CONFLICT_CONFIG_PATH).read_text("utf-8")
    assert "embedding_provider" not in text


@pytest.mark.phase_4
def test_malformed_yaml_raises_from_load(tmp_path: Path) -> None:
    path = tmp_path / CONFLICT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("context_similarity_gate: [not, a, float]\n", encoding="utf-8")
    with pytest.raises(ConflictConfigError):
        load_conflict_config(tmp_path)


@pytest.mark.phase_4
def test_not_a_mapping_raises(tmp_path: Path) -> None:
    path = tmp_path / CONFLICT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ConflictConfigError):
        load_conflict_config(tmp_path)


@pytest.mark.phase_4
def test_effective_config_swallows_malformed_file(tmp_path: Path) -> None:
    """status/ui/import/check must not break over a bad conflict.yml."""
    path = tmp_path / CONFLICT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{{{ not yaml at all\n", encoding="utf-8")
    assert effective_conflict_config(tmp_path) == ConflictConfig()


@pytest.mark.phase_4
def test_out_of_range_gate_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ConflictConfig(context_similarity_gate=1.5)
    with pytest.raises(ValueError):
        ConflictConfig(shortlist_k=0)
    with pytest.raises(ValueError):
        ConflictConfig(judge_model="")


@pytest.mark.phase_4
def test_unknown_embedding_provider_rejected() -> None:
    with pytest.raises(ValueError):
        # Intentionally outside the Literal — this test exists to prove the *runtime*
        # validator rejects it, which is what protects a hand-edited conflict.yml.
        ConflictConfig(embedding_provider="magic")  # type: ignore[arg-type]


@pytest.mark.phase_4
def test_retired_ceiling_in_an_old_file_is_ignored(tmp_path: Path) -> None:
    """A conflict.yml written before the judge still loads: the dropped setting is
    ignored rather than turning the whole file into a parse error."""
    path = tmp_path / CONFLICT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "version: '1'\ncontext_similarity_gate: 0.4\nchoice_divergence_ceiling: 0.35\n",
        encoding="utf-8",
    )
    assert load_conflict_config(tmp_path).context_similarity_gate == 0.4


@pytest.mark.phase_4
def test_resolve_conflict_embedder_defaults_when_unset(tmp_path: Path) -> None:
    """No conflict.yml, no embedding_provider set: identical to plain get_embedder()."""
    embedder = resolve_conflict_embedder(tmp_path)
    assert isinstance(embedder, DeterministicEmbedder)


@pytest.mark.phase_4
def test_resolve_conflict_embedder_uses_deterministic_override(tmp_path: Path) -> None:
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="deterministic"))
    embedder = resolve_conflict_embedder(tmp_path)
    assert isinstance(embedder, DeterministicEmbedder)


@pytest.mark.phase_4
def test_resolve_conflict_embedder_uses_local_override(tmp_path: Path) -> None:
    """The real lever this whole feature exists for: swap the hash embedder for a
    genuine semantic model per repo, without touching RL_EMBEDDING_PROVIDER."""
    pytest.importorskip("fastembed")
    from reasonledger_core.reasoning.embeddings import LocalEmbedder

    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))
    embedder = resolve_conflict_embedder(tmp_path)
    assert isinstance(embedder, LocalEmbedder)


def _fail_with(exc: Exception) -> object:
    def _raise(**_: object) -> object:
        raise exc

    return _raise


@pytest.mark.phase_4
def test_missing_local_extra_degrades_with_install_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A teammate pulling a committed `local` choice without the extra must still get
    a working `status` — and be told why the hints got noisier."""
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))
    monkeypatch.setattr(
        "reasonledger_core.reasoning.conflict_config.get_embedder",
        _fail_with(ImportError("No module named 'fastembed'")),
    )
    embedder, status = resolve_conflict_embedder_with_status(tmp_path)
    assert isinstance(embedder, DeterministicEmbedder)
    assert status.requested == "local"
    assert status.model_id == embedder.model_id
    assert status.fallback_reason is not None
    assert "--extra embeddings" in status.fallback_reason
    assert isinstance(resolve_conflict_embedder(tmp_path), DeterministicEmbedder)


@pytest.mark.phase_4
def test_failed_model_start_degrades_and_names_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))
    monkeypatch.setattr(
        "reasonledger_core.reasoning.conflict_config.get_embedder",
        _fail_with(RuntimeError("model download blocked")),
    )
    _, status = resolve_conflict_embedder_with_status(tmp_path)
    assert status.fallback_reason is not None
    assert "RuntimeError: model download blocked" in status.fallback_reason


@pytest.mark.phase_4
def test_working_embedder_reports_no_fallback(tmp_path: Path) -> None:
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="deterministic"))
    embedder, status = resolve_conflict_embedder_with_status(tmp_path)
    assert status.requested == "deterministic"
    assert status.model_id == embedder.model_id
    assert status.fallback_reason is None


@pytest.mark.phase_4
def test_unavailable_provider_error_only_for_missing_local(monkeypatch: pytest.MonkeyPatch) -> None:
    target = "reasonledger_core.reasoning.conflict_config.local_embedder_available"
    monkeypatch.setattr(target, lambda: False)
    message = unavailable_provider_error("local")
    assert message is not None and "--extra embeddings" in message
    assert unavailable_provider_error("deterministic") is None
    assert unavailable_provider_error(None) is None
    monkeypatch.setattr(target, lambda: True)
    assert unavailable_provider_error("local") is None


@pytest.mark.phase_4
def test_write_refuses_a_missing_repo_root(tmp_path: Path) -> None:
    """A mistyped --root must not scatter a stray .reasonledger across the disk."""
    missing = tmp_path / "no-such-repo"
    with pytest.raises(ConflictConfigError, match="does not exist"):
        write_conflict_config(missing, ConflictConfig())
    assert not missing.exists()
