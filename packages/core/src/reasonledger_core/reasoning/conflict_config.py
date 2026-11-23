"""Per-repo related-decision tuning: shortlist size and floor, embedder, judge model.

`reasoning/config.py`'s ``SHORTLIST_*`` constants are the tested, documented
defaults; nothing here changes what "default" means. This module adds an opt-in
override read from a committable ``.reasonledger/conflict.yml``, for repos whose
decision corpus needs a wider or narrower shortlist, a different embedder, or a
cheaper judge model than the importer's.

The file is its own concern, not a section of ``.reasonledger/config.yml``:
``importer.config.write_extractor_config`` overwrites that file wholesale, so
a second writer sharing it would silently erase whatever the other last
wrote.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from reasonledger_core.reasoning.config import SHORTLIST_K, SHORTLIST_K_MAX
from reasonledger_core.reasoning.embeddings import (
    LOCAL_EMBEDDER_INSTALL_HINT,
    DeterministicEmbedder,
    Embedder,
    get_embedder,
    local_embedder_available,
)
from reasonledger_core.settings import Settings

CONFLICT_CONFIG_PATH = Path(".reasonledger/conflict.yml")
CONFLICT_CONFIG_VERSION = "1"

EmbeddingProviderOverride = Literal["deterministic", "local"]


class ConflictConfigError(ValueError):
    """Raised when the conflict config file is malformed or a value is invalid."""


class ConflictConfig(BaseModel):
    """Per-repo override of the shortlist, the embedder and the judge model.

    Every field left unset falls back to a default: ``context_similarity_gate`` to
    the active embedder's floor (their similarity scales differ),
    ``embedding_provider`` to ``Settings``/``RL_EMBEDDING_PROVIDER``, and
    ``judge_model`` to the importer's configured model.
    """

    context_similarity_gate: float | None = Field(default=None, ge=0.0, le=1.0)
    shortlist_k: int = Field(default=SHORTLIST_K, ge=1, le=SHORTLIST_K_MAX)
    judge_model: str | None = Field(default=None, min_length=1)
    embedding_provider: EmbeddingProviderOverride | None = None


def load_conflict_config(root: Path) -> ConflictConfig:
    """Load the override from ``.reasonledger/conflict.yml`` (defaults if absent)."""
    path = root / CONFLICT_CONFIG_PATH
    if not path.is_file():
        return ConflictConfig()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConflictConfigError(f"cannot read {CONFLICT_CONFIG_PATH}: {exc}") from exc
    if raw is None:
        return ConflictConfig()
    if not isinstance(raw, dict):
        raise ConflictConfigError(f"{CONFLICT_CONFIG_PATH} must be a mapping")
    fields = {k: v for k, v in raw.items() if k != "version"}
    try:
        return ConflictConfig.model_validate(fields)
    except ValueError as exc:
        raise ConflictConfigError(f"invalid conflict config: {exc}") from exc


def effective_conflict_config(root: Path) -> ConflictConfig:
    """The config every detection call site should actually use. Never raises.

    Read on every `status`/`ui`/`import`/`check` run, so a malformed file must
    degrade to defaults rather than break the command. `reasonledger
    conflict-config` surfaces the real parse error instead, on the write path.
    """
    try:
        return load_conflict_config(root)
    except ConflictConfigError:
        return ConflictConfig()


def unavailable_provider_error(provider: str | None) -> str | None:
    """Why ``provider`` cannot be saved on this machine, or None if it can.

    Both config doors refuse up front, so a user never saves a choice that would
    silently degrade on the very next `status`. A committed file can still reach a
    teammate without the extra; `resolve_conflict_embedder_with_status` covers that.
    """
    if provider == "local" and not local_embedder_available():
        return f"the local embedder is not installed — run: {LOCAL_EMBEDDER_INSTALL_HINT}"
    return None


def write_conflict_config(root: Path, config: ConflictConfig) -> Path:
    """Persist the override, flat-keyed like ``dismissed.yml``.

    Refuses a missing repo root: creating it would scatter a stray `.reasonledger`
    wherever a mistyped ``--root`` points.
    """
    if not root.is_dir():
        raise ConflictConfigError(f"repo root does not exist: {root}")
    path = root / CONFLICT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": CONFLICT_CONFIG_VERSION,
        **config.model_dump(mode="json", exclude_none=True),
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


class EmbedderStatus(BaseModel):
    """What conflict detection asked for versus what it is actually running on.

    ``fallback_reason`` is set only when the requested backend could not be built
    and detection degraded to the deterministic hash embedder. Surfaces show it,
    because hash-based hints are far noisier and a user must not mistake them for
    the model they configured.
    """

    requested: EmbeddingProviderOverride
    model_id: str
    fallback_reason: str | None = None


def _fallback_reason(requested: str, exc: Exception) -> str:
    if isinstance(exc, ImportError):
        return f"the {requested} embedder is not installed — run: {LOCAL_EMBEDDER_INSTALL_HINT}"
    return f"the {requested} embedder could not start ({type(exc).__name__}: {exc})"


def resolve_conflict_embedder_with_status(
    root: Path, *, settings: Settings | None = None
) -> tuple[Embedder, EmbedderStatus]:
    """Build the embedder this repo's config selects, degrading instead of raising.

    An explicit `embedding_provider` in conflict.yml wins; otherwise the env-backed
    `RL_EMBEDDING_PROVIDER` decides, exactly as before. If an optional backend cannot
    be built — extra not installed, model download blocked, endpoint misconfigured —
    detection falls back to the deterministic embedder and the status says why,
    so `status`/`ui`/`import` keep working on a teammate's machine.
    """
    cfg = effective_conflict_config(root)
    base = settings or Settings()
    requested = cfg.embedding_provider or base.embedding_provider
    try:
        embedder = get_embedder(settings=base.model_copy(update={"embedding_provider": requested}))
    except Exception as exc:  # optional backends fail in many library-specific ways
        fallback = DeterministicEmbedder()
        return fallback, EmbedderStatus(
            requested=requested,
            model_id=fallback.model_id,
            fallback_reason=_fallback_reason(requested, exc),
        )
    return embedder, EmbedderStatus(requested=requested, model_id=embedder.model_id)


def resolve_conflict_embedder(root: Path, *, settings: Settings | None = None) -> Embedder:
    """The embedder alone, for callers that do not surface the fallback status."""
    return resolve_conflict_embedder_with_status(root, settings=settings)[0]
