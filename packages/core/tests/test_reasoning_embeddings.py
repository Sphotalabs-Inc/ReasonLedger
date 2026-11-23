"""Phase 4 — pluggable embedder selection and protocol conformance."""

from __future__ import annotations

import json
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from pydantic import ValidationError
from reasonledger_core.reasoning.cache import CACHE_DIR, CachingEmbedder
from reasonledger_core.reasoning.config import EMBEDDING_DIM, EMBEDDING_PROVIDER_DETERMINISTIC
from reasonledger_core.reasoning.embeddings import (
    DeterministicEmbedder,
    Embedder,
    LocalEmbedder,
    _shared_local_embedder,
    get_embedder,
)
from reasonledger_core.settings import Settings

_GOLDEN = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "reasoning"
_CORPUS = _GOLDEN / "decisions"
_PARAPHRASE = _GOLDEN / "paraphrase_queries.json"


def _assert_l2_normalized(vector: list[float], *, dim: int = EMBEDDING_DIM) -> None:
    assert len(vector) == dim
    norm = sum(component * component for component in vector) ** 0.5
    if all(component == 0.0 for component in vector):
        assert norm == 0.0
        return
    assert abs(norm - 1.0) < 1e-5


def _assert_embedder_protocol(embedder: Embedder) -> None:
    assert embedder.dim == EMBEDDING_DIM
    _assert_l2_normalized(embedder.embed("payment retry backoff strategy"))
    _assert_l2_normalized(embedder.embed(""))
    again = embedder.embed("payment retry backoff strategy")
    assert embedder.embed("payment retry backoff strategy") == again


@pytest.mark.phase_4
def test_embedder_selection_config() -> None:
    default = get_embedder()
    assert isinstance(default, DeterministicEmbedder)
    assert Settings().embedding_provider == EMBEDDING_PROVIDER_DETERMINISTIC

    local_settings = Settings(embedding_provider="local")
    try:
        local = get_embedder(settings=local_settings)
    except ImportError:
        with pytest.raises(ImportError, match="fastembed"):
            get_embedder(settings=local_settings)
    else:
        assert isinstance(local, LocalEmbedder)

    # Decision text is never sent over the network: there is no remote backend to select.
    with pytest.raises(ValidationError):
        Settings(embedding_provider="remote")  # type: ignore[arg-type]


@pytest.mark.phase_4
def test_embedder_protocol_conformance() -> None:
    _assert_embedder_protocol(DeterministicEmbedder())

    try:
        local = LocalEmbedder()
    except ImportError:
        pytest.skip("fastembed not installed")
    else:
        _assert_embedder_protocol(local)


class FakeTextEmbedding:
    """Stands in for fastembed's model: numpy float32 vectors, and a count of model loads."""

    loads = 0

    def __init__(self, *, model_name: str) -> None:
        type(self).loads += 1

    def embed(self, texts: list[str]) -> Iterator[np.ndarray]:
        for _ in texts:
            yield np.ones(EMBEDDING_DIM, dtype=np.float32)


@pytest.fixture
def fake_fastembed(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[FakeTextEmbedding]]:
    fake_module = types.ModuleType("fastembed")
    fake_module.TextEmbedding = FakeTextEmbedding  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fastembed", fake_module)
    FakeTextEmbedding.loads = 0
    _shared_local_embedder.cache_clear()
    yield FakeTextEmbedding
    _shared_local_embedder.cache_clear()


@pytest.mark.phase_4
def test_get_embedder_loads_the_local_model_once_per_process(
    fake_fastembed: type[FakeTextEmbedding],
) -> None:
    local = Settings(embedding_provider="local")

    assert get_embedder(settings=local) is get_embedder(settings=local)
    assert fake_fastembed.loads == 1


@pytest.mark.phase_4
def test_semantic_quality_local() -> None:
    pytest.importorskip("fastembed")
    from reasonledger_core.decisions import load_decisions_from_dir
    from reasonledger_core.reasoning import LocalEmbedder, semantic_search

    records = load_decisions_from_dir(_CORPUS)
    assert len(records) >= 4
    embedder = LocalEmbedder()
    cases = json.loads(_PARAPHRASE.read_text("utf-8"))["queries"]
    hits = 0
    for case in cases:
        results = semantic_search(embedder, case["query"], records, top_k=3)
        top_ids = [hit.decision_id for hit in results]
        if case["expected_match"] in top_ids:
            hits += 1
    rate = hits / len(cases)
    assert rate >= 0.90, (rate, hits, len(cases))


@pytest.mark.phase_4
def test_local_embedder_returns_plain_floats_the_disk_cache_can_store(tmp_path: Path) -> None:
    """fastembed yields numpy arrays; np.float32 is not JSON, and `judge` caches to disk.

    A stub stands in for the model, so this runs without the extra or a download.
    """
    np = pytest.importorskip("numpy")

    class _Model:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def embed(self, texts: list[str]) -> Iterator[object]:
            for _ in texts:
                yield np.arange(1, EMBEDDING_DIM + 1, dtype=np.float32)

    stub = types.ModuleType("fastembed")
    stub.TextEmbedding = _Model  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"fastembed": stub}):
        embedder = LocalEmbedder()

    assert all(type(component) is float for component in embedder.embed("anything"))
    CachingEmbedder(embedder, root=tmp_path).embed("anything")
    assert len(list((tmp_path / CACHE_DIR).glob("*.json"))) == 1
