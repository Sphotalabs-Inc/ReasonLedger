"""LLM harvest replay — CI uses recorded fixtures only (no live network)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reasonledger_core.harvest.deterministic import harvest_from_fixture
from reasonledger_core.models.decision import DecisionFrontmatter, DecisionRecord


class LlmHarvestError(ValueError):
    """Raised when a recorded LLM harvest fixture is missing or invalid."""


def replay_llm_harvest(fixture_path: Path) -> DecisionRecord:
    """Replay a recorded LLM extraction response from disk."""
    if not fixture_path.is_file():
        raise LlmHarvestError(f"LLM harvest fixture not found: {fixture_path}")
    payload: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
    if "frontmatter" in payload and "body" in payload:
        return DecisionRecord(
            frontmatter=DecisionFrontmatter.model_validate(payload["frontmatter"]),
            body=str(payload["body"]),
        )
    # Fallback: recorded extractor output shaped like PR harvest input
    return harvest_from_fixture(payload)
