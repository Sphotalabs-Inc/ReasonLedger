"""Recorded-fixture conflict classifier — replays a real model's verdicts.

Mirrors the harvest LLM replay pattern: no live inference in CI. Verdicts are
keyed by the unordered decision-id pair so ordering never changes the result.
"""

from __future__ import annotations

import json
from pathlib import Path

from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.models.reasoning import ConflictVerdict, Severity


def _pair_key(a: str, b: str) -> str:
    return "::".join(sorted((a, b)))


class ReplayConflictClassifier:
    """Loads recorded verdicts keyed by decision-id pair."""

    def __init__(self, verdicts: dict[str, ConflictVerdict]) -> None:
        self._verdicts = verdicts

    @classmethod
    def from_fixture(cls, path: Path) -> ReplayConflictClassifier:
        data = json.loads(path.read_text(encoding="utf-8"))
        verdicts: dict[str, ConflictVerdict] = {}
        for row in data["pairs"]:
            key = _pair_key(row["decision_a"], row["decision_b"])
            verdicts[key] = ConflictVerdict(
                is_conflict=bool(row["is_conflict"]),
                severity=Severity(row.get("severity", "low")),
                explanation=row.get("explanation", ""),
                score=float(row.get("score", 0.0)),
            )
        return cls(verdicts)

    def classify(
        self,
        a: DecisionRecord,
        b: DecisionRecord,
        *,
        context_similarity: float,
        choice_similarity: float,
    ) -> ConflictVerdict:
        key = _pair_key(a.frontmatter.id, b.frontmatter.id)
        if key not in self._verdicts:
            return ConflictVerdict(
                is_conflict=False,
                severity=Severity.LOW,
                explanation="no recorded verdict for pair",
                score=0.0,
            )
        return self._verdicts[key]
