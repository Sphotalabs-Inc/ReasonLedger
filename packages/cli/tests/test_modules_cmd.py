"""Phase 5 — `reasonledger modules`: list, confirm, rename, merge, reject and label."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_cli.main import main
from reasonledger_core.modules import (
    Manifest,
    Module,
    ModuleStatus,
    load_manifest,
    write_manifest,
)
from reasonledger_core.modules.models import Confidence
from test_ui_organize import _decision


def _repo(root: Path) -> Path:
    for name in ("f0.py", "f1.py", "f2.py", "date_utils.py"):
        path = root / "app" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n", encoding="utf-8")
    write_manifest(root, Manifest(modules=[Module(id="app", name="App", paths=["app/**"])]))
    return root


@pytest.mark.phase_5
def test_label_saves_the_placement_and_refuses_what_matches_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    assert main(["modules", "label", "--root", str(root), "app/date_utils.py", "shared"]) == 0
    assert "labelled 1 file(s) as shared" in capsys.readouterr().out
    stored = load_manifest(root)
    assert stored.labels == {"app/date_utils.py": "shared"}
    assert "shared" in {m.id for m in stored.modules}  # the bucket was made for the label
    refusals = (
        (["nope.py", "shared"], "matches no source file"),
        (["app/f0.py", "nowhere"], "no module or bucket named"),
        (["shared"], "at least one path or glob"),  # a target and nothing to label
    )
    for items, message in refusals:
        assert main(["modules", "label", "--root", str(root), *items]) == 2
        assert message in capsys.readouterr().err
    assert load_manifest(root).labels == stored.labels  # a refusal changes nothing


@pytest.mark.phase_5
def test_label_may_name_a_support_folder_a_scan_leaves_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    for name in ("spec/01-plan.md", "app/tests/test_f0.py"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("x\n", encoding="utf-8")
    assert main(["modules", "label", "--root", str(root), "spec/**", "app"]) == 0
    assert "labelled 1 file(s) as app" in capsys.readouterr().out
    # A glob that only passes over a support folder still leaves it out.
    assert main(["modules", "label", "--root", str(root), "app/**", "shared"]) == 0
    assert "labelled 4 file(s) as shared" in capsys.readouterr().out


@pytest.mark.phase_5
def test_drift_names_labels_whose_module_is_gone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    manifest = load_manifest(root)
    write_manifest(root, manifest.model_copy(update={"labels": {"app/date_utils.py": "ghost"}}))
    main(["map", "--root", str(root), "--drift"])
    assert "labels pointing at a module that is gone: app/date_utils.py" in capsys.readouterr().out


def _queue_repo(root: Path) -> Path:
    """Seven proposals: two high confidence (p1 is larger), one medium, four low."""
    confidence = {
        "p1": Confidence.HIGH,
        "p2": Confidence.HIGH,
        "p3": Confidence.MEDIUM,
        "p4": Confidence.LOW,
        "p5": Confidence.LOW,
        "p6": Confidence.LOW,
        "p7": Confidence.LOW,
    }
    modules = []
    for module_id, level in confidence.items():
        for index in range(4 if module_id == "p1" else 3):
            path = root / "app" / module_id / f"f{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x = 1\n", encoding="utf-8")
        modules.append(
            Module(
                id=module_id,
                name=module_id.upper(),
                paths=[f"app/{module_id}/**"],
                confidence=level,
            )
        )
    write_manifest(root, Manifest(modules=modules))
    return root


def _ids(root: Path) -> dict[str, ModuleStatus]:
    return {m.id: m.status for m in load_manifest(root).modules}


@pytest.mark.phase_5
def test_the_list_shows_the_next_five_most_trusted_and_says_how_many_wait(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _queue_repo(tmp_path)
    assert main(["modules", "--root", str(root)]) == 0  # a bare `modules` lists
    out = capsys.readouterr().out
    assert "0 confirmed, 7 proposed" in out and "showing 5 of 7" in out
    assert "2 more waiting" in out and "p7" not in out and "p6" not in out
    assert out.index("p1 ") < out.index("p2 ") < out.index("p3 ") < out.index("p4 ")
    assert main(["modules", "list", "--all", "--root", str(root)]) == 0
    assert "showing 7 of 7" in capsys.readouterr().out
    assert main(["modules", "--all", "--root", str(root)]) == 0
    assert "p7" in capsys.readouterr().out


@pytest.mark.phase_5
def test_confirm_names_who_confirmed_and_bulk_confirm_takes_only_high_confidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _queue_repo(tmp_path)
    assert main(["modules", "confirm", "p3", "--by", "alice", "--root", str(root)]) == 0
    assert "confirmed 1: p3" in capsys.readouterr().out
    assert main(["modules", "confirm", "--all-high", "--by", "alice", "--root", str(root)]) == 0
    assert "confirmed 2: p1, p2" in capsys.readouterr().out
    statuses = _ids(root)
    assert [i for i, s in statuses.items() if s is ModuleStatus.CONFIRMED] == ["p1", "p2", "p3"]
    stored = {m.id: m for m in load_manifest(root).modules}
    assert stored["p1"].confirmed_by == "alice" and stored["p1"].confirmed_at is not None
    assert main(["modules", "confirm", "p1", "--by", "alice", "--root", str(root)]) == 0
    assert "already confirmed" in capsys.readouterr().out
    assert main(["modules", "list", "--root", str(root)]) == 0
    listed = capsys.readouterr().out
    assert "3 confirmed, 4 proposed" in listed and "by alice" in listed


@pytest.mark.phase_5
def test_confirm_refuses_without_a_name_a_target_or_a_real_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], no_git_identity: None
) -> None:
    root = _queue_repo(tmp_path)
    assert main(["modules", "confirm", "p1", "--root", str(root)]) == 2
    assert "--by" in capsys.readouterr().err  # nobody is on record as having looked
    assert main(["modules", "confirm", "--by", "me", "--root", str(root)]) == 2
    assert "name the modules to confirm" in capsys.readouterr().err
    assert main(["modules", "confirm", "p1", "ghost", "--by", "me", "--root", str(root)]) == 2
    assert "no module named 'ghost'" in capsys.readouterr().err
    assert _ids(root)["p1"] is ModuleStatus.PROPOSED  # all or nothing


@pytest.mark.phase_5
def test_rename_merge_and_reject_edit_the_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _queue_repo(tmp_path)
    assert main(["modules", "label", "app/p3/f0.py", "p3", "--root", str(root)]) == 0
    capsys.readouterr()
    assert main(["modules", "rename", "p3", "Data", "extraction", "--root", str(root)]) == 0
    renamed = capsys.readouterr().out
    assert "renamed p3 to data-extraction" in renamed and "still a proposal" in renamed
    assert load_manifest(root).labels == {"app/p3/f0.py": "data-extraction"}
    assert main(["modules", "merge", "p4", "p5", "--root", str(root)]) == 0
    assert "merged p5 into p4" in capsys.readouterr().out
    assert main(["modules", "reject", "p6", "--reason", "generated", "--root", str(root)]) == 0
    assert "rejected p6" in capsys.readouterr().out
    after = load_manifest(root)
    assert sorted(m.id for m in after.modules) == ["data-extraction", "p1", "p2", "p4", "p7"]
    assert after.rejected[0].reason == "generated"
    main(["modules", "confirm", "p1", "--by", "me", "--root", str(root)])
    capsys.readouterr()
    assert main(["modules", "reject", "p1", "--root", str(root)]) == 2
    assert "is confirmed" in capsys.readouterr().err


@pytest.mark.phase_5
def test_place_and_unplace_a_decision_that_has_no_working_anchor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], no_git_identity: None
) -> None:
    root = _repo(tmp_path)
    _decision(root, "dec_loose")
    _decision(root, "dec_anchored", "app/f0.py:1-9")
    base = ["modules", "place", "--root", str(root), "--by", "me"]

    assert main([*base, "dec_loose", "app"]) == 0
    assert "placed dec_loose in app" in capsys.readouterr().out
    placement = load_manifest(root).placements["dec_loose"]
    assert (placement.modules, placement.by) == (["app"], "me")

    refusals = (
        (["dec_anchored", "app"], "placed by that anchor"),
        (["dec_loose", "ghost"], "no such module or bucket: ghost"),
        (["dec_nope", "app"], "no decision dec_nope"),
    )
    for items, message in refusals:
        assert main([*base, *items]) == 2
        assert message in capsys.readouterr().err
    assert main(["modules", "place", "--root", str(root), "dec_loose", "app"]) == 2
    assert "--by" in capsys.readouterr().err  # who places it is not optional

    assert main(["modules", "unplace", "--root", str(root), "dec_loose"]) == 0
    assert load_manifest(root).placements == {}
    assert main(["modules", "unplace", "--root", str(root), "dec_loose"]) == 2
    assert "no hand placement" in capsys.readouterr().err


@pytest.mark.phase_5
def test_modules_list_says_when_a_hand_placement_no_longer_applies(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path)
    _decision(root, "dec_loose")
    main(["modules", "place", "--root", str(root), "--by", "me", "dec_loose", "app"])
    _decision(root, "dec_loose", "app/f0.py:1-9")  # edited: a working anchor now places it
    capsys.readouterr()

    main(["modules", "list", "--root", str(root)])

    assert "hand placement of dec_loose no longer applies" in capsys.readouterr().out


@pytest.mark.phase_5
def test_modules_confirm_defaults_to_git_identity(tmp_path: Path, git_identity: str) -> None:
    root = _queue_repo(tmp_path)
    assert main(["modules", "confirm", "p1", "--root", str(root)]) == 0
    confirmed = {m.id: m for m in load_manifest(root).modules}["p1"]
    assert confirmed.confirmed_by == git_identity
