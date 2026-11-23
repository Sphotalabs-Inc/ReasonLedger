"""Memoising Embedder wrapper.

Conflict detection is all-pairs, and every pair re-embeds the same handful of
strings. Distinct texts across a view are 2N; naive evaluation issues 2N(N-1)
embed calls. This wrapper collapses the difference without changing any output.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from reasonledger_core.reasoning.embeddings import Embedder

CACHE_DIR = Path(".reasonledger/cache/embeddings")


def _key(model_id: str, text: str) -> str:
    return hashlib.sha256(f"{model_id}\x00{text}".encode()).hexdigest()


class CachingEmbedder:
    """Wraps an Embedder with an in-memory memo and an optional on-disk cache.

    Output is byte-identical to the wrapped embedder; only call count changes.
    """

    def __init__(self, inner: Embedder, *, root: Path | None = None) -> None:
        self._inner = inner
        self._memo: dict[str, list[float]] = {}
        self._root = root
        self.model_id = inner.model_id
        self.dim = inner.dim

    def embed(self, text: str) -> list[float]:
        key = _key(self.model_id, text)
        hit = self._memo.get(key)
        if hit is not None:
            return hit
        disk = self._read_disk(key)
        if disk is not None:
            self._memo[key] = disk
            return disk
        vector = self._inner.embed(text)
        self._memo[key] = vector
        self._write_disk(key, vector)
        return vector

    def _path(self, key: str) -> Path | None:
        if self._root is None:
            return None
        return self._root / CACHE_DIR / f"{key}.json"

    def _read_disk(self, key: str) -> list[float] | None:
        path = self._path(key)
        if path is None or not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, list) or len(data) != self.dim:
            return None
        return [float(value) for value in data]

    def _write_disk(self, key: str, vector: list[float]) -> None:
        path = self._path(key)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(vector), encoding="utf-8")
        except OSError:
            return
