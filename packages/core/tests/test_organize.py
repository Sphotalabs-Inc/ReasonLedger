"""Phase 5 — moving files, the move preview and the workbench file list."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from modules_helpers import tree, write_files
from reasonledger_core.modules import Manifest, Module, ModuleKind, ModuleStatus
from reasonledger_core.modules.buckets import new_bucket
from reasonledger_core.modules.editing import ModuleEditError, create_module
from reasonledger_core.modules.labels import LabelError
from reasonledger_core.modules.manifest import membership
from reasonledger_core.modules.models import Tier
from reasonledger_core.modules.organize import (
    UNPLACED,
    folder_rule,
    move_labels,
    path_filter,
    preview_move,
    select_files,
)
from reasonledger_core.views.organize_files import PAGE_SIZE, list_files, load_records
from test_map_view import _decision

AT = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
FILES = [
    *tree("app/pages", 4),
    "app/pages/stray.py",
    *tree("app/billing", 3),
    *tree("app/common", 3),
    "app/orphan.py",
]


def _manifest() -> Manifest:
    return Manifest(
        modules=[
            Module(id="pages", name="Pages", paths=["app/pages/**"], tier=Tier.BACKEND),
            Module(id="billing", name="Billing", paths=["app/billing/**", "app/pages/stray.py"]),
            new_bucket("shared-backend", ["app/common/**"]),
        ]
    )


def _owner(manifest: Manifest, path: str) -> str | None:
    return membership(manifest).module_of(path)


@pytest.mark.phase_5
def test_a_filter_matches_by_substring_or_by_glob() -> None:
    assert path_filter("")("anything") and path_filter("  ")("anything")
    assert path_filter("PAGES")("app/pages/f0.py") and not path_filter("billing")("app/pages/f0.py")
    assert path_filter("app/*/f0.py")("app/pages/f0.py")
    assert not path_filter("app/*/f0.py")("app/pages/deep/f0.py")
    assert path_filter("app/**/f?.py")("app/pages/deep/f0.py")


@pytest.mark.phase_5
def test_a_selection_is_explicit_real_files_or_a_modules_files_that_match_a_query() -> None:
    manifest = _manifest()
    assert select_files(
        manifest, FILES, paths=["app/pages/f0.py", "gone.py", "app/pages/f0.py"]
    ) == ["app/pages/f0.py"]
    assert select_files(manifest, FILES, paths=["app/*"]) == []  # a glob is not a file
    assert select_files(manifest, FILES, module="pages", query="f1") == ["app/pages/f1.py"]
    assert select_files(manifest, FILES, module=UNPLACED) == ["app/orphan.py"]
    assert select_files(manifest, FILES) == []


@pytest.mark.phase_5
def test_a_move_preview_names_the_files_the_decisions_and_the_target_before_anything_changes() -> (
    None
):
    manifest = _manifest()
    selection = ["app/common/f0.py", "app/common/f1.py", "app/pages/f0.py"]
    impact = preview_move(manifest, FILES, selection, "pages", [], Path("."))
    assert (impact.moving, impact.already_there) == (2, 1)
    assert impact.from_modules == {"shared-backend": 2}
    with pytest.raises(LabelError, match="no module or bucket named 'ghost'"):
        preview_move(manifest, FILES, selection, "ghost", [], Path("."))
    with pytest.raises(LabelError, match="no module or bucket named 'ghost'"):
        preview_move(
            manifest, FILES, ["app/pages/f0.py"], "ghost", [], Path(".")
        )  # nothing to move still checks
    assert _owner(manifest, "app/common/f0.py") == "shared-backend"  # a preview writes nothing


@pytest.mark.phase_5
def test_a_move_preview_lists_the_decisions_that_would_change_module(tmp_path: Path) -> None:
    write_files(tmp_path, dict.fromkeys(FILES, ""))
    _decision(tmp_path, "dec_both", "app/common/f0.py::helper", "app/pages/f0.py")
    _decision(tmp_path, "dec_stays", "app/billing/f0.py")
    _decision(tmp_path, "dec_loose")
    records = load_records(tmp_path)
    impact = preview_move(_manifest(), FILES, ["app/common/f0.py"], "pages", records, tmp_path)
    assert impact.decisions_total == 1
    shift = impact.decisions[0]
    assert shift.decision_id == "dec_both"
    assert (shift.before, shift.after) == (["pages", "shared-backend"], ["pages"])


@pytest.mark.phase_5
def test_a_folder_move_offers_a_rule_and_says_what_else_it_would_take() -> None:
    manifest = _manifest()
    rule = folder_rule(manifest, FILES, ["app/pages/f0.py", "app/pages/f1.py"], "billing")
    assert rule is not None and rule.pattern == "app/pages/**"
    # f2, f3 sit in the same module as the selection; stray.py is billing's already
    assert (rule.extra_files, rule.from_same_owner, rule.from_other_owner) == (2, 2, 0)
    wider = folder_rule(manifest, FILES, ["app/common/f0.py", "app/pages/f0.py"], "billing")
    assert wider is not None and wider.pattern == "app/**"  # the nearest shared folder
    assert (wider.extra_files, wider.from_same_owner, wider.from_other_owner) == (6, 5, 1)
    assert folder_rule(manifest, FILES, ["app/pages/f0.py"], "billing") is None  # one file
    assert folder_rule(manifest, FILES, ["setup.py", "app/pages/f0.py"], "billing") is None
    crossing = folder_rule(
        manifest, FILES, ["app/pages/f0.py", "app/pages/f1.py"], "shared-backend"
    )
    assert crossing is not None and crossing.from_other_owner == 1  # stray.py belongs to billing


@pytest.mark.phase_5
def test_a_move_pins_each_file_and_a_rule_pins_the_folder() -> None:
    manifest = _manifest()
    moved, count, written = move_labels(
        manifest, FILES, ["app/common/f0.py", "app/common/f1.py"], "pages"
    )
    assert (count, written) == (2, "")
    assert moved.labels == {"app/common/f0.py": "pages", "app/common/f1.py": "pages"}
    assert (
        _owner(moved, "app/common/f0.py") == "pages"
        and _owner(moved, "app/common/f2.py") == "shared-backend"
    )
    ruled, count, written = move_labels(
        manifest, FILES, ["app/common/f0.py", "app/common/f1.py"], "pages", as_rule=True
    )
    assert (count, written) == (3, "app/common/**")  # the rule takes the whole folder
    assert _owner(ruled, "app/common/f2.py") == "pages"
    with pytest.raises(ValueError, match="already there"):
        move_labels(manifest, FILES, ["app/pages/f0.py"], "pages")
    with pytest.raises(ValueError, match="share a folder"):
        move_labels(manifest, FILES, ["app/common/f0.py"], "pages", as_rule=True)


@pytest.mark.phase_5
def test_a_new_module_from_a_selection_is_confirmed_by_its_maker_and_keeps_its_files() -> None:
    manifest = _manifest()
    updated, new_id = create_module(
        manifest, " Webhooks ", ["app/common/f0.py", "app/common/f1.py"], FILES, by=" me ", at=AT
    )
    assert new_id == "webhooks"
    made = next(m for m in updated.modules if m.id == "webhooks")
    assert (made.status, made.confirmed_by, made.confirmed_at) == (ModuleStatus.CONFIRMED, "me", AT)
    assert made.kind is ModuleKind.FEATURE and made.paths == []  # its files come from labels
    assert _owner(updated, "app/common/f0.py") == "webhooks"
    assert _owner(updated, "app/common/f2.py") == "shared-backend"
    for name, by, message in (
        ("Pages", "me", "already a module"),
        ("Tooling", "me", "already a module or a bucket"),
        ("  ", "me", "a name"),
        ("Fresh", " ", "who is creating"),
    ):
        with pytest.raises(ModuleEditError, match=message):
            create_module(manifest, name, ["app/common/f0.py"], FILES, by=by, at=AT)


@pytest.mark.phase_5
def test_the_file_list_shows_hand_placed_files_decision_counts_and_sibling_hints(
    tmp_path: Path,
) -> None:
    write_files(tmp_path, dict.fromkeys(FILES, ""))
    _decision(tmp_path, "dec_a", "app/pages/f0.py", "app/billing/f0.py:3-9")
    _decision(tmp_path, "dec_b", "app/billing/f0.py::charge")
    manifest = _manifest().model_copy(update={"labels": {"app/billing/f2.py": "billing"}})
    billing = list_files(tmp_path, manifest, FILES, module="billing")
    assert billing is not None and billing.total == 4
    rows = {r.path: r for r in billing.files}
    assert rows["app/billing/f2.py"].pinned_by == "app/billing/f2.py"  # placed by hand
    assert rows["app/billing/f1.py"].pinned_by is None
    assert rows["app/billing/f0.py"].decisions == 2  # two decisions anchor this file
    stray = rows["app/pages/stray.py"]
    assert stray.hint is not None and (stray.hint.module, stray.hint.agree, stray.hint.total) == (
        "pages",
        4,
        4,
    )  # the four files beside it are in pages
    assert rows["app/billing/f1.py"].hint is None  # its neighbours are its own module
    common = list_files(tmp_path, manifest, FILES, module="shared-backend", query="f1")
    assert common is not None and [r.path for r in common.files] == ["app/common/f1.py"]
    assert common.files[0].hint is None  # a bucket's neighbours are all buckets


@pytest.mark.phase_5
def test_the_file_list_covers_unplaced_files_pages_and_unknown_modules(tmp_path: Path) -> None:
    files = [f"app/n{i}.py" for i in range(PAGE_SIZE + 5)]
    manifest = _manifest()
    first = list_files(tmp_path, manifest, files, module=UNPLACED)
    assert first is not None and first.total == PAGE_SIZE + 5 and len(first.files) == PAGE_SIZE
    second = list_files(tmp_path, manifest, files, module=UNPLACED, offset=PAGE_SIZE)
    assert second is not None and len(second.files) == 5 and second.offset == PAGE_SIZE
    assert list_files(tmp_path, manifest, files, module="nowhere") is None
