"""Phase 4 — the judge's labelled pairs, and its recorded verdicts replayed against them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.reasoning import ReplayConflictClassifier
from reasonledger_core.reasoning.config import (
    JUDGE_SMOKE_FALSE_POSITIVE_MAX,
    JUDGE_SMOKE_PRECISION_MIN,
    JUDGE_SMOKE_RECALL_MIN,
)
from reasonledger_core.reasoning.judge import agreement

_CONFLICTS = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "conflicts"
_PAIRS = _CONFLICTS / "judge_pairs.json"
_VERDICTS = _CONFLICTS / "judge_verdicts.json"


def _pairs() -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = json.loads(_PAIRS.read_text("utf-8"))["pairs"]
    return pairs


def _record(spec: dict[str, Any]) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=spec["id"],
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            context=spec["context"],
            choice=spec["choice"],
        ),
        body="",
    )


@pytest.mark.phase_4
def test_labelled_pairs_are_well_formed() -> None:
    pairs = _pairs()
    ids = [p["id"] for p in pairs] + [p[side]["id"] for p in pairs for side in ("a", "b")]
    assert len(ids) == len(set(ids))
    positives = sum(1 for p in pairs if p["is_conflict"])
    # Both classes well represented, so neither "always conflict" nor "never" passes.
    assert positives >= 8
    assert len(pairs) - positives >= 8


@pytest.mark.phase_4
def test_recorded_judge_meets_smoke_floors() -> None:
    if not _VERDICTS.is_file():
        pytest.skip("no recorded verdicts yet: run scripts/record_judge_verdicts.py")
    replay = ReplayConflictClassifier.from_fixture(_VERDICTS)
    predictions = [
        (
            replay.classify(
                _record(p["a"]), _record(p["b"]), context_similarity=1.0, choice_similarity=0.0
            ).is_conflict,
            bool(p["is_conflict"]),
        )
        for p in _pairs()
    ]
    precision, recall, false_positive_rate = agreement(predictions)
    assert precision >= JUDGE_SMOKE_PRECISION_MIN
    assert recall >= JUDGE_SMOKE_RECALL_MIN
    assert false_positive_rate <= JUDGE_SMOKE_FALSE_POSITIVE_MAX
