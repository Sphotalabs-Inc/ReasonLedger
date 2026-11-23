"""Phase 1 oversight classification golden tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from reasonledger_core.models.oversight import ChangeOversightInput, OversightClassification
from reasonledger_core.oversight.classify import classify_oversight

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "oversight" / "cases.json"


def _load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads(FIXTURES.read_text("utf-8"))
    return cases


@pytest.mark.phase_1
@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_oversight_golden_cases(case: dict[str, Any]) -> None:
    change = ChangeOversightInput.model_validate(case["input"])
    assert classify_oversight(change) == OversightClassification(case["expected"])
