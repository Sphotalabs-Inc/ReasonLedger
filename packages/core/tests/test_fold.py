"""Phase 5 — the scan folds the parts of one feature back into it."""

from __future__ import annotations

from pathlib import Path

import pytest
from modules_helpers import make_repo, tree
from reasonledger_core.modules import Manifest, Module, ModuleKind, ModuleStatus, scan_repo
from reasonledger_core.modules.fold import fold_parts
from reasonledger_core.modules.globs import PathMatcher
from reasonledger_core.modules.models import Confidence, Tier
from reasonledger_core.modules.tiers import Tiers

FEATURE = "apps/client/src/features/editor"
BACKEND = sorted(tree("apps/server/src/core/pages", 4, ".ts"))


def _part(folder: str, name: str, **kw: object) -> tuple[Module, list[str]]:
    files = sorted(tree(f"{folder}/{name}", 3, ".tsx"))
    module = Module(
        id=f"{name}-ui",
        name=name,
        paths=[f"{folder}/{name}/**"],
        kind=ModuleKind.FEATURE,
        tier=Tier.FRONTEND,
        status=ModuleStatus.PROPOSED,
        evidence=["layout"],
        confidence=Confidence.LOW,
        **kw,  # type: ignore[arg-type]
    )
    return module, files


def _fold(parts: list[tuple[Module, list[str]]], extra: list[Module] | None = None, **kw):  # type: ignore[no-untyped-def]
    files = sorted({f for _, fs in parts for f in fs} | set(BACKEND))
    modules = [*(m for m, _ in parts), *(extra or [])]
    return fold_parts(modules, files, Tiers(files), **kw), files


@pytest.mark.phase_5
def test_widgets_in_a_layer_folder_of_a_feature_become_one_module_for_that_feature() -> None:
    parts = [_part(f"{FEATURE}/components", n) for n in ("bubble-menu", "emoji-menu", "slash-menu")]

    modules, files = _fold(parts)

    (editor,) = modules
    assert (editor.id, editor.name, editor.tier) == ("editor-ui", "editor UI", Tier.FRONTEND)
    assert editor.evidence == ["layout", "folded:3"] and editor.confidence is Confidence.LOW
    assert editor.description == f"Folders under {FEATURE}: bubble-menu, emoji-menu, slash-menu"
    owner = PathMatcher([(editor.id, editor.paths)])
    assert all(owner.module_of(f) == "editor-ui" for _, fs in parts for f in fs)


@pytest.mark.phase_5
def test_a_module_already_named_for_the_feature_takes_even_one_part() -> None:
    editor = Module(
        id="editor-ui",
        name="editor",
        paths=[f"{FEATURE}/*.tsx"],
        kind=ModuleKind.FEATURE,
        tier=Tier.FRONTEND,
        status=ModuleStatus.PROPOSED,
        evidence=["layout", "convention"],
    )
    parts = [_part(f"{FEATURE}/components", "bubble-menu")]

    modules, _ = _fold(parts, [editor])

    (merged,) = modules
    assert merged.id == "editor-ui" and merged.evidence == ["layout", "convention", "folded:1"]
    assert merged.confidence == editor.confidence


@pytest.mark.phase_5
def test_two_parts_alone_do_not_earn_a_new_module() -> None:
    parts = [_part(f"{FEATURE}/components", n) for n in ("bubble-menu", "emoji-menu")]

    modules, _ = _fold(parts)

    assert sorted(m.id for m in modules) == ["bubble-menu-ui", "emoji-menu-ui"]


@pytest.mark.phase_5
def test_independent_features_in_a_plain_folder_stay_separate() -> None:
    parts = [_part("apps/client/src/features", n) for n in ("pages", "comments", "spaces")]

    modules, _ = _fold(parts)

    assert sorted(m.id for m in modules) == ["comments-ui", "pages-ui", "spaces-ui"]


@pytest.mark.phase_5
def test_features_in_a_layer_folder_at_the_app_root_are_features_not_parts() -> None:
    parts = [_part("apps/client/src/components", n) for n in ("clients", "offers", "orders")]

    modules, _ = _fold(parts)

    assert sorted(m.id for m in modules) == ["clients-ui", "offers-ui", "orders-ui"]


@pytest.mark.phase_5
def test_a_module_another_signal_also_found_is_not_folded() -> None:
    parts = [_part(f"{FEATURE}/components", n) for n in ("bubble-menu", "emoji-menu")]
    backed, files = _part(f"{FEATURE}/components", "slash-menu")
    backed = backed.model_copy(update={"evidence": ["layout", "cochange"]})

    modules, _ = _fold([*parts, (backed, files)])

    assert sorted(m.id for m in modules) == ["bubble-menu-ui", "emoji-menu-ui", "slash-menu-ui"]


@pytest.mark.phase_5
def test_a_confirmed_module_keeps_its_id_and_the_parts_stay_where_they_are() -> None:
    parts = [_part(f"{FEATURE}/components", n) for n in ("bubble-menu", "emoji-menu", "slash-menu")]

    modules, _ = _fold(parts, taken={"editor-ui"})

    assert len(modules) == 3


def _app(root: Path) -> Path:
    files: dict[str, str] = {}
    for widget in ("bubble", "emoji", "slash", "link"):
        files |= tree(f"apps/client/src/features/editor/components/{widget}", 3, ".tsx")
    for feature in ("pages", "comments", "spaces"):
        files |= tree(f"apps/client/src/features/{feature}", 4, ".tsx")
        files |= tree(f"apps/server/src/core/{feature}", 4, ".ts")
    return make_repo(root, [("init", files)])


@pytest.mark.phase_5
def test_scanning_an_app_folds_the_editor_widgets_and_keeps_the_features(tmp_path: Path) -> None:
    result = scan_repo(_app(tmp_path), manifest=Manifest())

    ids = {m.id for m in result.modules}
    assert ids == {
        "editor-ui",
        "pages",
        "comments",
        "spaces",
        "pages-ui",
        "comments-ui",
        "spaces-ui",
    }
    editor = next(m for m in result.modules if m.id == "editor-ui")
    owner = PathMatcher([(editor.id, editor.paths)])
    assert all(
        owner.module_of(f"apps/client/src/features/editor/components/{w}/f0.tsx") == "editor-ui"
        for w in ("bubble", "emoji", "slash", "link")
    )
