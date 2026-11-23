"""Phase 5 — the quick map: a first module map with no model and nothing sent."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.modules.manifest import load_manifest
from reasonledger_core.modules.quick_map import MAPPED_BY, quick_map


def _app(root: Path) -> None:
    for folder in ("orders", "payments", "accounts"):
        for index in range(4):
            path = root / "app" / folder / f"{folder}_{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x = 1\n", encoding="utf-8")


@pytest.mark.phase_5
def test_quick_map_writes_proposals_without_any_model(tmp_path: Path) -> None:
    _app(tmp_path)

    outcome = quick_map(tmp_path)

    manifest = load_manifest(tmp_path)
    assert outcome.files_total == 12 and outcome.proposed >= 1
    assert manifest.mapped_by == MAPPED_BY
    assert {m.status.value for m in manifest.modules} <= {"proposed", "confirmed"}


@pytest.mark.phase_5
def test_quick_map_is_repeatable_and_keeps_what_a_person_confirmed(tmp_path: Path) -> None:
    _app(tmp_path)
    quick_map(tmp_path)
    manifest = load_manifest(tmp_path)
    first = next(m for m in manifest.modules if m.status.value == "proposed")
    from reasonledger_core.modules.manifest import write_manifest
    from reasonledger_core.modules.models import ModuleStatus

    confirmed = manifest.model_copy(
        update={
            "modules": [
                m.model_copy(update={"status": ModuleStatus.CONFIRMED}) if m.id == first.id else m
                for m in manifest.modules
            ]
        }
    )
    write_manifest(tmp_path, confirmed)

    quick_map(tmp_path)

    kept = next(m for m in load_manifest(tmp_path).modules if m.id == first.id)
    assert kept.status is ModuleStatus.CONFIRMED


@pytest.mark.phase_5
def test_quick_map_reports_the_buckets_that_hold_what_no_module_owns(tmp_path: Path) -> None:
    _app(tmp_path)
    (tmp_path / "run.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text("all:\n", encoding="utf-8")

    outcome = quick_map(tmp_path)

    assert outcome.buckets.get("tooling", 0) >= 1
    assert sum(outcome.buckets.values()) + outcome.placed == outcome.files_total
