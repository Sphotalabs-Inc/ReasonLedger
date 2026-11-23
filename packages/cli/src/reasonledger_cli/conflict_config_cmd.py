"""`reasonledger conflict-config` — per-repo related-decision tuning."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError
from reasonledger_core.reasoning.conflict_config import (
    ConflictConfig,
    ConflictConfigError,
    load_conflict_config,
    unavailable_provider_error,
    write_conflict_config,
)

EXIT_PASS = 0
EXIT_USAGE = 2

EMBEDDING_PROVIDER_CHOICES = ["deterministic", "local"]


def add_conflict_config_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = sub.add_parser(
        "conflict-config",
        help="Tune the related-decision shortlist, embedder and judge model for this repo",
    )
    parser.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Application repo root (default: cwd)"
    )
    parser.add_argument(
        "--context-similarity-gate",
        type=float,
        help="Minimum context similarity for a pair to be shortlisted (default: per embedder)",
    )
    parser.add_argument(
        "--shortlist-k",
        type=int,
        help="Nearest neighbours each decision contributes to the shortlist (default: 5)",
    )
    parser.add_argument(
        "--judge-model",
        help="Model that judges pairs (default: the model `reasonledger config` set)",
    )
    parser.add_argument(
        "--embedding-provider",
        choices=EMBEDDING_PROVIDER_CHOICES,
        help="Embedder for the shortlist (default: RL_EMBEDDING_PROVIDER, or deterministic)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Print the effective config (works even with no file, or a malformed one)",
    )


def _print_effective(cfg: ConflictConfig) -> None:
    gate = cfg.context_similarity_gate
    print(f"context_similarity_gate: {gate if gate is not None else '(unset — per embedder)'}")
    print(f"shortlist_k: {cfg.shortlist_k}")
    print(f"judge_model: {cfg.judge_model or '(unset — the model `reasonledger config` set)'}")
    print(f"embedding_provider: {cfg.embedding_provider or '(unset — RL_EMBEDDING_PROVIDER)'}")


def run_conflict_config(
    *,
    root: Path,
    context_similarity_gate: float | None = None,
    shortlist_k: int | None = None,
    judge_model: str | None = None,
    embedding_provider: str | None = None,
    show: bool = False,
) -> int:
    """Show or merge-update ``.reasonledger/conflict.yml``. Returns a process exit code.

    A write only touches the fields a flag was actually given for — tuning one
    threshold should not require restating the other two.

    Both ``--show`` and a write surface a malformed existing file as an error
    rather than pretending it says the defaults. `status`/`ui`/`import`/`check`
    all fall back to defaults silently on a bad file (see
    ``effective_conflict_config`` — those commands must not break over it), which
    means this command is the one place a broken override actually gets noticed.
    Swallowing the error here too would hide the exact thing a user reaching for
    ``--show`` is trying to find out: is my override even being honored.
    """
    if show:
        try:
            _print_effective(load_conflict_config(root))
        except ConflictConfigError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE
        return EXIT_PASS

    if all(
        value is None
        for value in (context_similarity_gate, shortlist_k, judge_model, embedding_provider)
    ):
        print(
            "error: nothing to set — pass --context-similarity-gate, --shortlist-k, "
            "--judge-model and/or --embedding-provider, or use --show",
            file=sys.stderr,
        )
        return EXIT_USAGE

    try:
        current = load_conflict_config(root)
    except ConflictConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    updates: dict[str, object] = current.model_dump()
    if context_similarity_gate is not None:
        updates["context_similarity_gate"] = context_similarity_gate
    if shortlist_k is not None:
        updates["shortlist_k"] = shortlist_k
    if judge_model is not None:
        updates["judge_model"] = judge_model
    if embedding_provider is not None:
        unavailable = unavailable_provider_error(embedding_provider)
        if unavailable:
            print(f"error: {unavailable}", file=sys.stderr)
            return EXIT_USAGE
        updates["embedding_provider"] = embedding_provider

    try:
        new_config = ConflictConfig.model_validate(updates)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    try:
        path = write_conflict_config(root, new_config)
    except ConflictConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"wrote {path}")
    _print_effective(new_config)
    return EXIT_PASS
