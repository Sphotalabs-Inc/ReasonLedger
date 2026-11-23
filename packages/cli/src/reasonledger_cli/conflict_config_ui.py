"""Config endpoints for `reasonledger ui` — the UI door onto `.reasonledger/conflict.yml`.

`reasonledger conflict-config` is the other door; both write through the same
core functions, so the two surfaces cannot disagree about what `status`/`ui`
will do with a threshold. Mirrors `ui_config.py`'s shape for the extractor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError
from reasonledger_core.reasoning.conflict_config import (
    ConflictConfig,
    ConflictConfigError,
    load_conflict_config,
    unavailable_provider_error,
    write_conflict_config,
)

_EMBEDDING_PROVIDER_CHOICES = ("deterministic", "local")

JsonResponse = tuple[int, dict[str, Any]]


def config_payload(config: ConflictConfig) -> dict[str, Any]:
    return {
        "context_similarity_gate": config.context_similarity_gate,
        "shortlist_k": config.shortlist_k,
        "judge_model": config.judge_model,
        "embedding_provider": config.embedding_provider,
        "embedding_providers": list(_EMBEDDING_PROVIDER_CHOICES),
    }


def handle_get_conflict_config(root: Path) -> JsonResponse:
    """GET /api/conflict-config — surfaces a malformed file rather than hiding it.

    `status`/`ui`'s own conflict detection falls back to defaults silently on a
    bad file (it must not break those commands); this panel is where a broken
    override is actually supposed to become visible, so it does not repeat that
    fallback.
    """
    try:
        config = load_conflict_config(root)
    except ConflictConfigError as exc:
        return 500, {"error": str(exc)}
    return 200, config_payload(config)


def handle_post_conflict_config(root: Path, body: dict[str, Any]) -> JsonResponse:
    """POST /api/conflict-config — merge-update: only touch fields present in the body."""
    try:
        current = load_conflict_config(root)
    except ConflictConfigError as exc:
        return 500, {"error": str(exc)}

    updates = current.model_dump()
    if "context_similarity_gate" in body:
        updates["context_similarity_gate"] = body["context_similarity_gate"]
    for name in ("shortlist_k", "judge_model"):
        if name in body:
            updates[name] = body[name]
    if "embedding_provider" in body:
        provider = body["embedding_provider"]
        if provider is not None and provider not in _EMBEDDING_PROVIDER_CHOICES:
            choices = ", ".join(_EMBEDDING_PROVIDER_CHOICES)
            return 400, {"error": f"embedding_provider must be one of: {choices}"}
        unavailable = unavailable_provider_error(provider)
        if unavailable:
            return 400, {"error": unavailable}
        updates["embedding_provider"] = provider

    try:
        config = ConflictConfig.model_validate(updates)
    except ValidationError as exc:
        return 400, {"error": str(exc)}

    path = write_conflict_config(root, config)
    return 200, {"saved": True, "path": str(path), **config_payload(config)}


__all__ = [
    "config_payload",
    "handle_get_conflict_config",
    "handle_post_conflict_config",
]
