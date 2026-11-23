"""Phase 5 — the model-free scan keeps frontend and backend apart."""

from __future__ import annotations

from pathlib import Path

import pytest
from modules_helpers import make_repo, tree
from reasonledger_core.modules import Confidence, Manifest, scan_repo
from reasonledger_core.modules.models import Candidate, SignalKind, Tier
from reasonledger_core.modules.resolve import resolve_modules
from reasonledger_core.modules.tier_split import drop_tier_containers, split_by_tier
from reasonledger_core.modules.tiers import Tiers


def _cand(name: str, signal: SignalKind, files: list[str], **kw: str) -> Candidate:
    return Candidate(name=name, signal=signal, files=frozenset(files), **kw)  # type: ignore[arg-type]


def _files(prefix: str, count: int) -> list[str]:
    return sorted(tree(prefix, count, ".ts"))


BACKEND = _files("backend/app/credits", 4)
FRONTEND = _files("frontend/src/credits", 4)
BOTH_TIERS = Tiers([*BACKEND, *FRONTEND])


@pytest.mark.phase_5
def test_a_candidate_spanning_both_tiers_becomes_a_backend_and_a_ui_module() -> None:
    migration = "migrations/001_credits.sql"
    spec = _cand("credits", SignalKind.SPECS, [*BACKEND, *FRONTEND, migration])

    back, front = split_by_tier([spec], BOTH_TIERS)

    assert (back.name, back.id_hint) == ("credits", None)
    assert (front.name, front.id_hint) == ("credits UI", "credits-ui")
    assert back.files == frozenset([*BACKEND, migration])  # files in neither tier go backend
    assert front.files == frozenset(FRONTEND)


@pytest.mark.phase_5
def test_strays_below_the_module_floor_are_dropped_not_folded_into_the_other_tier() -> None:
    stray = _files("frontend/src/credits", 2)
    spec = _cand("credits", SignalKind.SPECS, [*BACKEND, *stray])

    assert [c.files for c in split_by_tier([spec], BOTH_TIERS)] == [frozenset(BACKEND)]
    small = _cand("tiny", SignalKind.SPECS, [*BACKEND[:2], *stray])
    assert split_by_tier([small], BOTH_TIERS) == []


@pytest.mark.phase_5
def test_split_does_nothing_in_a_repo_with_only_one_tier() -> None:
    one_tier = Tiers(BACKEND)
    spec = _cand("credits", SignalKind.SPECS, [*BACKEND, *FRONTEND])

    assert split_by_tier([spec], one_tier) == [spec]
    assert drop_tier_containers([_cand("server", SignalKind.LAYOUT, BACKEND)], one_tier) == [
        _cand("server", SignalKind.LAYOUT, BACKEND)
    ]


@pytest.mark.phase_5
def test_a_frontend_half_is_not_suffixed_twice_or_when_named_for_the_tier() -> None:
    web = _cand("web", SignalKind.WORKSPACE, FRONTEND)
    already = _cand("admin-ui", SignalKind.LAYOUT, FRONTEND)

    (kept,) = split_by_tier([web], BOTH_TIERS)
    (same,) = split_by_tier([already], BOTH_TIERS)

    assert (kept.name, kept.id_hint) == ("web", "web")
    assert same.id_hint == "admin-ui"


@pytest.mark.phase_5
def test_a_tier_package_holding_features_is_dropped_and_one_holding_none_is_kept() -> None:
    inner = [_cand(n, SignalKind.LAYOUT, _files(f"backend/app/{n}", 3)) for n in "abc"]
    everything = frozenset(f for c in inner for f in c.files)
    package = _cand("backend", SignalKind.WORKSPACE, sorted(everything))
    tiers = Tiers([*everything, *FRONTEND])

    assert drop_tier_containers([package, *inner], tiers) == inner
    assert drop_tier_containers([package], tiers) == [package]


@pytest.mark.phase_5
def test_a_folder_nested_inside_a_tier_is_a_layer_not_a_module() -> None:
    kit = _cand("ui", SignalKind.LAYOUT, _files("apps/client/src/components/ui", 4))
    feature = _cand("credits", SignalKind.LAYOUT, BACKEND)

    assert drop_tier_containers([kit, feature], BOTH_TIERS) == [feature]


@pytest.mark.phase_5
def test_a_tier_folder_that_holds_features_is_dropped_even_when_the_layout_found_it() -> None:
    root_files = _files("frontend", 3)
    shell = _cand("frontend", SignalKind.LAYOUT, root_files)
    features = [_cand(n, SignalKind.LAYOUT, _files(f"frontend/src/{n}", 3)) for n in "abc"]

    assert drop_tier_containers([shell, *features], BOTH_TIERS) == features
    assert drop_tier_containers([shell], BOTH_TIERS) == [shell]


@pytest.mark.phase_5
def test_a_directory_and_a_convention_family_with_one_name_are_one_module() -> None:
    folder, family = _files("app/group", 6), _files("app/other", 3)
    modules = resolve_modules(
        [
            _cand("group", SignalKind.LAYOUT, folder),
            _cand("group", SignalKind.CONVENTION, family),
        ],
        [*folder, *family],
        [],
    )

    (module,) = modules
    assert module.id == "group" and module.confidence is Confidence.HIGH
    assert module.evidence == ["convention", "layout"]


@pytest.mark.phase_5
def test_modules_record_the_tier_most_of_their_files_sit_in() -> None:
    files = [*BACKEND, *FRONTEND]
    modules = resolve_modules(
        [
            _cand("credits", SignalKind.SPECS, BACKEND),
            _cand("credits-ui", SignalKind.SPECS, FRONTEND),
        ],
        files,
        [],
        Tiers(files),
    )

    assert {m.id: m.tier for m in modules} == {"credits": Tier.BACKEND, "credits-ui": Tier.FRONTEND}


def _monorepo(root: Path) -> Path:
    files: dict[str, str] = {"package.json": '{"workspaces": ["apps/*"]}\n'}
    for feature in ("pages", "comments", "spaces"):
        files |= tree(f"apps/client/src/features/{feature}", 4, ".tsx")
        files |= tree(f"apps/server/src/core/{feature}", 4, ".ts")
    return make_repo(root, [("init", files)])


@pytest.mark.phase_5
def test_scanning_a_monorepo_splits_each_app_into_its_features_by_tier(tmp_path: Path) -> None:
    result = scan_repo(_monorepo(tmp_path), manifest=Manifest())

    by_id = {m.id: m for m in result.modules}
    assert set(by_id) == {"pages", "comments", "spaces", "pages-ui", "comments-ui", "spaces-ui"}
    assert {m.tier for m in result.modules if m.id.endswith("-ui")} == {Tier.FRONTEND}
    assert {m.tier for m in result.modules if not m.id.endswith("-ui")} == {Tier.BACKEND}
    assert by_id["pages-ui"].paths == ["apps/client/src/features/pages/**"]
    assert by_id["pages"].paths == ["apps/server/src/core/pages/**"]
