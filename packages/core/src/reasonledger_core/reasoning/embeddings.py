"""Pluggable embeddings with a deterministic, network-free default.

Two backends, selected via ``Settings.embedding_provider``:

- ``deterministic`` — signed feature hash (CI/test default)
- ``local`` — ``bge-small-en-v1.5`` via ``fastembed`` (optional extra)

There is no remote backend: decision text is never sent over the network to embed it.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import re
from functools import lru_cache
from typing import Protocol, runtime_checkable

from reasonledger_core.links import INSTALL_DOCS_URL
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.reasoning.config import (
    DETERMINISTIC_MODEL_ID,
    EMBEDDING_DIM,
    EMBEDDING_PROVIDER_DETERMINISTIC,
    EMBEDDING_PROVIDER_LOCAL,
    LOCAL_MODEL_ID,
)
from reasonledger_core.settings import Settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")
LOCAL_EMBEDDER_INSTALL_HINT = (
    "pip install 'reasonledger[embeddings]' "
    "(in a ReasonLedger checkout: uv sync --all-packages --extra embeddings; "
    f"for a `uv tool` install see {INSTALL_DOCS_URL})"
)


@runtime_checkable
class Embedder(Protocol):
    """Maps text to a fixed-dimension unit vector."""

    model_id: str
    dim: int

    def embed(self, text: str) -> list[float]: ...


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


class DeterministicEmbedder:
    """Signed feature-hashing embedder — deterministic, offline, dependency-free."""

    def __init__(
        self,
        *,
        dim: int = EMBEDDING_DIM,
        model_id: str = DETERMINISTIC_MODEL_ID,
    ) -> None:
        self.dim = dim
        self.model_id = model_id

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        return _l2_normalize(vector)


class LocalEmbedder:
    """``bge-small-en-v1.5`` via fastembed (ONNX, CPU-only, no PyTorch)."""

    def __init__(self, *, model_id: str = LOCAL_MODEL_ID, dim: int = EMBEDDING_DIM) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            raise ImportError(
                f"Local embedder requires fastembed. Install with: {LOCAL_EMBEDDER_INSTALL_HINT}"
            ) from exc
        self.model_id = model_id
        self.dim = dim
        self._model = TextEmbedding(model_name=model_id)

    def embed(self, text: str) -> list[float]:
        # fastembed yields numpy scalars; the Embedder contract is plain floats, which the
        # on-disk vector cache needs to serialise.
        vector = [float(component) for component in next(iter(self._model.embed([text or ""])))]
        if len(vector) != self.dim:
            raise ValueError(f"local embedder returned dim {len(vector)}, expected {self.dim}")
        return _l2_normalize(vector)


def local_embedder_available() -> bool:
    """Whether the optional ``embeddings`` extra (fastembed) is installed."""
    return importlib.util.find_spec("fastembed") is not None


@lru_cache(maxsize=1)
def _shared_local_embedder() -> LocalEmbedder:
    """One loaded model per process: building it takes over a second, and a long-lived
    caller (the MCP server) resolves the embedder on every query. A failed build is not
    cached, so installing the extra mid-session takes effect on the next call."""
    return LocalEmbedder()


def get_embedder(*, settings: Settings | None = None) -> Embedder:
    """Resolve the active embedder from env-backed settings."""
    cfg = settings or Settings()
    provider = cfg.embedding_provider
    if provider == EMBEDDING_PROVIDER_DETERMINISTIC:
        return DeterministicEmbedder()
    if provider == EMBEDDING_PROVIDER_LOCAL:
        return _shared_local_embedder()
    raise ValueError(f"unsupported embedding_provider: {provider!r}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Dot product; inputs are expected to be L2-normalized."""
    return sum(x * y for x, y in zip(a, b, strict=True))


def decision_embed_text(record: DecisionRecord) -> str:
    """Concatenate the PII-free fields we embed for a decision."""
    fm = record.frontmatter
    parts = [
        fm.context or "",
        fm.choice or "",
        " ".join(fm.alternatives_rejected),
        " ".join(fm.justifies),
    ]
    return " ".join(part for part in parts if part).strip()


def embed_decision(embedder: Embedder, record: DecisionRecord) -> list[float]:
    return embedder.embed(decision_embed_text(record))
