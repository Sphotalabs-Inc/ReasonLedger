"""Enforce metadata-only persistence — never store source code."""

from typing import Any

# Keys that must never appear in persisted ingest payloads.
FORBIDDEN_PERSISTED_KEYS: frozenset[str] = frozenset(
    {
        "source_code",
        "file_content",
        "diff_content",
        "patch",
        "raw_diff",
    }
)


def assert_metadata_only(payload: dict[str, Any]) -> None:
    """Raise if a payload attempts to persist forbidden source-code fields."""
    forbidden = FORBIDDEN_PERSISTED_KEYS.intersection(payload.keys())
    if forbidden:
        joined = ", ".join(sorted(forbidden))
        raise ValueError(f"source code persistence forbidden: {joined}")
