"""Phase 5 — placing a decision by hand when its anchors cannot."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from modules_helpers import tree, write_files
from reasonledger_core.modules import Manifest, Module, load_manifest, write_manifest
from reasonledger_core.modules.config import MANIFEST_PATH
from reasonledger_core.modules.hand_placement import (
    AnchorState,
    PlacementError,
    anchor_state,
    clear_hand_placement,
    place_by_hand,
    stale_placements,
)
from reasonledger_core.modules.placement import place_decisions
from reasonledger_core.views.organize_files import load_records
from test_map_view import _decision

AT = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)


def _manifest() -> Manifest:
    return Manifest(
        modules=[
            Module(id="pages", name="Pages", paths=["app/pages/**"]),
            Module(id="billing", name="Billing", paths=["app/billing/**"]),
        ]
    )


def _repo(root: Path) -> None:
    write_files(root, {**tree("app/pages", 3), **tree("app/billing", 3)})


def _record(root: Path, decision_id: str):  # type: ignore[no-untyped-def]
    return next(r for r in load_records(root) if r.frontmatter.id == decision_id)


@pytest.mark.phase_5
def test_an_anchor_state_is_none_broken_or_anchored(tmp_path: Path) -> None:
    _repo(tmp_path)

    assert anchor_state(tmp_path, []) is AnchorState.NONE
    assert anchor_state(tmp_path, ["app/pages/gone.py:1-9"]) is AnchorState.BROKEN
    assert anchor_state(tmp_path, ["app/pages/gone.py", "app/pages/f0.py"]) is AnchorState.ANCHORED


@pytest.mark.phase_5
def test_a_decision_with_no_anchor_or_dead_anchors_can_be_placed_by_hand(tmp_path: Path) -> None:
    _repo(tmp_path)
    _decision(tmp_path, "dec_loose")
    _decision(tmp_path, "dec_dead", "app/pages/gone.py:1-9")

    manifest = place_by_hand(
        _manifest(), _record(tmp_path, "dec_loose"), tmp_path, ["billing"], "me", now=AT
    )
    manifest = place_by_hand(
        manifest, _record(tmp_path, "dec_dead"), tmp_path, ["pages", "billing"], "me", now=AT
    )

    placed = place_decisions(load_records(tmp_path), manifest, tmp_path)
    assert placed["dec_loose"].modules == ["billing"] and placed["dec_loose"].placed_by == "me"
    assert placed["dec_dead"].modules == ["billing", "pages"]  # replaces what its dead anchor said
    assert not placed["dec_loose"].unplaced and placed["dec_loose"].by_hand


@pytest.mark.phase_5
def test_a_dead_anchor_that_still_matches_a_module_glob_is_replaced_by_the_placement(
    tmp_path: Path,
) -> None:
    _repo(tmp_path)
    _decision(tmp_path, "dec_dead", "app/pages/gone.py:1-9")
    before = place_decisions(load_records(tmp_path), _manifest(), tmp_path)["dec_dead"]
    assert before.modules == ["pages"] and not before.by_hand  # by the glob, not by a live file

    manifest = place_by_hand(
        _manifest(), _record(tmp_path, "dec_dead"), tmp_path, ["billing"], "me"
    )

    assert place_decisions(load_records(tmp_path), manifest, tmp_path)["dec_dead"].modules == [
        "billing"
    ]


@pytest.mark.phase_5
def test_a_decision_with_a_working_anchor_is_never_placed_by_hand(tmp_path: Path) -> None:
    _repo(tmp_path)
    _decision(tmp_path, "dec_anchored", "app/pages/f0.py:1-9", "app/pages/gone.py")

    with pytest.raises(PlacementError, match="placed by that anchor"):
        place_by_hand(_manifest(), _record(tmp_path, "dec_anchored"), tmp_path, ["billing"], "me")


@pytest.mark.phase_5
def test_a_placement_that_breaks_a_rule_is_refused_with_the_reason(tmp_path: Path) -> None:
    _repo(tmp_path)
    _decision(tmp_path, "dec_loose")
    record = _record(tmp_path, "dec_loose")
    many = Manifest(
        modules=[Module(id=f"m{i}", name=f"M{i}", paths=[f"m{i}/**"]) for i in range(6)]
    )

    with pytest.raises(PlacementError, match="who is placing it"):
        place_by_hand(_manifest(), record, tmp_path, ["pages"], "  ")
    with pytest.raises(PlacementError, match="at least one"):
        place_by_hand(_manifest(), record, tmp_path, [], "me")
    with pytest.raises(PlacementError, match="no such module or bucket: ghost"):
        place_by_hand(_manifest(), record, tmp_path, ["pages", "ghost"], "me")
    with pytest.raises(PlacementError, match="cross-cutting"):
        place_by_hand(many, record, tmp_path, [f"m{i}" for i in range(5)], "me")


@pytest.mark.phase_5
def test_a_placement_stops_applying_when_the_decision_gains_a_working_anchor(
    tmp_path: Path,
) -> None:
    _repo(tmp_path)
    _decision(tmp_path, "dec_loose")
    manifest = place_by_hand(
        _manifest(), _record(tmp_path, "dec_loose"), tmp_path, ["billing"], "me"
    )
    _decision(tmp_path, "dec_loose", "app/pages/f0.py:1-9")  # edited: now anchored in pages

    records = load_records(tmp_path)
    assert place_decisions(records, manifest, tmp_path)["dec_loose"].modules == ["pages"]
    assert (
        "anchor that works"
        in stale_placements(manifest, {r.frontmatter.id: r for r in records}, tmp_path)["dec_loose"]
    )


@pytest.mark.phase_5
def test_a_placement_in_a_module_that_is_gone_is_skipped_and_reported(tmp_path: Path) -> None:
    _repo(tmp_path)
    _decision(tmp_path, "dec_loose")
    manifest = place_by_hand(
        _manifest(), _record(tmp_path, "dec_loose"), tmp_path, ["pages", "billing"], "me"
    )
    manifest = manifest.model_copy(
        update={"modules": [m for m in manifest.modules if m.id != "billing"]}
    )

    records = load_records(tmp_path)
    assert place_decisions(records, manifest, tmp_path)["dec_loose"].modules == ["pages"]
    assert stale_placements(manifest, {r.frontmatter.id: r for r in records}, tmp_path) == {
        "dec_loose": "module billing is gone"
    }
    assert place_decisions(records, manifest.model_copy(update={"modules": []}), tmp_path)[
        "dec_loose"
    ].unplaced


@pytest.mark.phase_5
def test_a_hand_placement_survives_the_manifest_and_clears(tmp_path: Path) -> None:
    _repo(tmp_path)
    _decision(tmp_path, "dec_b")
    _decision(tmp_path, "dec_a")
    manifest = place_by_hand(
        _manifest(), _record(tmp_path, "dec_b"), tmp_path, ["pages"], "me", now=AT
    )
    manifest = place_by_hand(
        manifest, _record(tmp_path, "dec_a"), tmp_path, ["billing"], "you", now=AT
    )

    write_manifest(tmp_path, manifest)

    assert list(yaml.safe_load((tmp_path / MANIFEST_PATH).read_text("utf-8"))["placements"]) == [
        "dec_a",
        "dec_b",
    ]
    assert load_manifest(tmp_path).placements["dec_a"].by == "you"
    cleared = clear_hand_placement(load_manifest(tmp_path), "dec_a")
    write_manifest(tmp_path, clear_hand_placement(cleared, "dec_b"))
    assert "placements" not in yaml.safe_load((tmp_path / MANIFEST_PATH).read_text("utf-8"))
    with pytest.raises(PlacementError, match="no hand placement"):
        clear_hand_placement(cleared, "dec_a")
