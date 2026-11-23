"""Phase 5 — tiers, buckets and labels."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from modules_helpers import git, make_repo, tree, write_files
from reasonledger_core.modules import (
    Manifest,
    Module,
    ModuleKind,
    ModuleStatus,
    load_manifest,
    write_manifest,
)
from reasonledger_core.modules.agent_route import modules_view, submit_map
from reasonledger_core.modules.buckets import bucket_of, new_bucket
from reasonledger_core.modules.config import MANIFEST_PATH, TIER_DOMINANCE_SHARE
from reasonledger_core.modules.digest import source_files
from reasonledger_core.modules.drift import detect_drift
from reasonledger_core.modules.files import modelled_files
from reasonledger_core.modules.labels import LabelError, label_files
from reasonledger_core.modules.manifest import dangling_labels, membership
from reasonledger_core.modules.mapper_check import validate_map
from reasonledger_core.modules.mapping import (
    accept_suggestions,
    apply_map,
    apply_refresh,
    bucket_sizes,
    propose_map,
    refresh_map,
    with_buckets,
)
from reasonledger_core.modules.models import Suggestion, Tier
from reasonledger_core.modules.tiers import Tiers
from test_mapper_core import Provider, local_mapper

TWO_TIERS = [
    *tree("backend/app/billing", 3),
    *tree("frontend/src/billing", 3, ".js"),
    "frontend/src/App.js",
    "frontend/src/components/common/Header.js",
    "frontend/src/components/common/Footer.js",
    "backend/app/utils.py",
    "backend/app/auditlog.py",
    "backend/scripts/migrate.py",
    ".gitignore",
    "qodana.yaml",
]


def _module(
    module_id: str,
    paths: list[str],
    status: ModuleStatus = ModuleStatus.CONFIRMED,
    kind: ModuleKind = ModuleKind.FEATURE,
) -> Module:
    return Module(id=module_id, name=module_id, paths=paths, status=status, kind=kind)


def _proposal(module_id: str, paths: list[str]) -> dict[str, object]:
    return {
        "id": module_id,
        "name": module_id,
        "kind": "feature",
        "description": "d",
        "paths": paths,
    }


@pytest.mark.phase_5
def test_tiers_need_both_frontend_and_backend_folders_and_the_first_name_decides() -> None:
    files = ["frontend/src/services/api/a.js", "backend/app/b.py", "tools/c.py"]
    tiers = Tiers(files)
    assert tiers.enabled
    assert tiers.of(files[0]) is Tier.FRONTEND  # frontend comes before api on the path
    assert tiers.of(files[1]) is Tier.BACKEND and tiers.of(files[2]) is None
    lone = Tiers(["src/web/Controller.java", "src/main/App.java"])  # a Java web package
    assert not lone.enabled and lone.of("src/web/Controller.java") is None
    assert TIER_DOMINANCE_SHARE == 0.6
    assert tiers.of_files(["backend/a.py", "backend/b.py", "backend/c.py", "x/y.py", "x/z.py"]) is (
        Tier.BACKEND
    )  # 3 of 5
    assert tiers.of_files(["backend/a.py", "backend/b.py", "x/c.py", "x/d.py", "x/e.py"]) is None
    assert tiers.of_files(["x/c.py"]) is None


@pytest.mark.phase_5
def test_a_validated_module_gets_its_tier_from_its_files_and_cannot_take_a_bucket_id() -> None:
    source = [
        *tree("backend/app/subs", 3),
        *tree("frontend/src/subs", 3, ".js"),
        *tree("backend/app/mixed", 2),
        *tree("frontend/src/mixed", 2, ".js"),
        *tree("ops", 3),
    ]
    result = validate_map(
        [
            _proposal("subs", ["backend/app/subs/**"]),
            _proposal("subs-ui", ["frontend/src/subs/**"]),
            _proposal("mixed", ["backend/app/mixed/**", "frontend/src/mixed/**"]),
            _proposal("tooling", ["ops/**"]),  # the bucket owns this id
        ],
        source,
        source,
    )
    tiers = {m.id: m.tier for m in result.modules}
    assert tiers == {
        "subs": Tier.BACKEND,
        "subs-ui": Tier.FRONTEND,
        "mixed": None,
        "tooling-2": None,
    }


@pytest.mark.phase_5
def test_files_no_module_owns_go_to_a_bucket_chosen_by_the_architecture() -> None:
    owners = [
        _module("billing", ["backend/app/billing/**"]),
        _module("billing-ui", ["frontend/**"]),
    ]
    owners[1] = _module("billing-ui", ["frontend/src/billing/**"])
    manifest = with_buckets(Manifest(modules=owners), TWO_TIERS, TWO_TIERS)
    buckets = {m.id: m for m in manifest.modules if m.kind is ModuleKind.BUCKET}
    assert {b.id: b.tier for b in buckets.values()} == {
        "shared-frontend": Tier.FRONTEND,
        "shared-backend": Tier.BACKEND,
        "tooling": None,
    }
    # shell and common components; helpers; a scripts folder and repo-root configuration
    assert bucket_sizes(manifest, TWO_TIERS) == {
        "shared-backend": 2,
        "shared-frontend": 3,
        "tooling": 3,
    }
    flat = ["app/a.py", "app/b.py", "app/c.py", "lib/d.py", "Makefile"]
    single = with_buckets(Manifest(modules=[_module("app", ["app/**"])]), flat, flat)
    assert bucket_sizes(single, flat) == {"shared": 1, "tooling": 1}  # no tiers in a flat repo


@pytest.mark.phase_5
def test_a_bucket_grows_and_a_pending_suggestion_keeps_its_file_out() -> None:
    first = with_buckets(
        Manifest(modules=[_module("billing", ["backend/app/billing/**"])]), TWO_TIERS, TWO_TIERS
    )
    confirmed = [
        m.model_copy(update={"status": ModuleStatus.CONFIRMED}) if m.id == "shared-backend" else m
        for m in first.modules
    ]
    manifest = first.model_copy(
        update={
            "modules": confirmed,
            "suggestions": [Suggestion(module="billing", paths=["backend/app/pending.py"])],
        }
    )
    files = [*TWO_TIERS, "backend/app/helpers.py", "backend/app/pending.py"]
    grown = with_buckets(manifest, files, files)
    owner = membership(grown)
    assert owner.module_of("backend/app/helpers.py") == "shared-backend"
    assert owner.module_of("backend/app/utils.py") == "shared-backend"  # what it had stays
    assert next(m for m in grown.modules if m.id == "shared-backend").status is (
        ModuleStatus.CONFIRMED
    )
    assert owner.module_of("backend/app/pending.py") is None  # waits for a person to accept


@pytest.mark.phase_5
def test_a_label_outranks_every_glob_and_refuses_what_matches_nothing() -> None:
    manifest = Manifest(modules=[_module("billing", ["backend/**"])])
    files = ["backend/app/date_utils.py", "backend/app/billing.py", "backend/app/other.py"]
    updated, hit = label_files(manifest, ["backend/app/date_utils.py"], "shared-backend", files)
    assert hit == ["backend/app/date_utils.py"]
    assert [m.id for m in updated.modules] == ["billing", "shared-backend"]  # absent bucket made
    owner = membership(updated)
    assert owner.module_of("backend/app/date_utils.py") == "shared-backend"
    assert owner.module_of("backend/app/billing.py") == "billing"
    globbed, hit = label_files(updated, ["backend/app/b*.py"], "billing", files)
    assert hit == ["backend/app/billing.py"] and globbed.labels["backend/app/b*.py"] == "billing"
    for patterns, target, message in (
        (["backend/app/date_utils.py"], "nowhere", "no module or bucket named"),
        (["gone.py"], "billing", "matches no source file"),
        ([], "billing", "at least one"),
    ):
        with pytest.raises(LabelError, match=message):
            label_files(manifest, patterns, target, files)


@pytest.mark.phase_5
def test_a_label_survives_a_remap_and_a_vanished_target_is_reported(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path / "repo", [("init", {**tree("app/billing", 3), "app/date_utils.py": ""})]
    )
    proposed = _module("billing", ["app/**"], ModuleStatus.PROPOSED)
    labelled, _ = label_files(
        Manifest(modules=[proposed]), ["app/date_utils.py"], "shared", source_files(root)
    )
    write_manifest(root, labelled)
    stored = load_manifest(root)
    assert stored.labels == {"app/date_utils.py": "shared"}
    provider = Provider({"modules": [_proposal("billing", ["app/**"])]})
    outcome = propose_map(root, local_mapper(provider), stored, "single")
    remapped = apply_map(
        stored, outcome.validated.modules, "m", root
    )  # billing is claiming it again
    assert membership(remapped).module_of("app/date_utils.py") == "shared"
    assert dangling_labels(remapped) == []
    gone = remapped.model_copy(update={"labels": {**remapped.labels, "app/other.py": "ghost"}})
    assert dangling_labels(gone) == ["app/other.py"]


@pytest.mark.phase_5
def test_the_manifest_keeps_tiers_buckets_and_sorted_labels_and_omits_empty_ones(
    tmp_path: Path,
) -> None:
    subs = _module("subs", ["a/**"]).model_copy(update={"tier": Tier.BACKEND})
    manifest = Manifest(
        modules=[subs, new_bucket("tooling")], labels={"z.py": "tooling", "a.py": "subs"}
    )
    write_manifest(tmp_path, manifest)
    raw = yaml.safe_load((tmp_path / MANIFEST_PATH).read_text("utf-8"))
    assert list(raw["labels"]) == ["a.py", "z.py"]
    assert raw["modules"][0]["tier"] == "backend" and "tier" not in raw["modules"][1]
    assert raw["modules"][1]["kind"] == "bucket"
    assert load_manifest(tmp_path) == manifest
    write_manifest(tmp_path, Manifest(modules=[subs]))
    assert "labels" not in yaml.safe_load((tmp_path / MANIFEST_PATH).read_text("utf-8"))


@pytest.mark.phase_5
def test_drift_counts_labels_as_placed_and_files_beside_bucketed_ones_as_shared(
    tmp_path: Path,
) -> None:
    write_files(
        tmp_path,
        {
            **dict.fromkeys(("frontend/src/common/A.js", "frontend/src/common/B.js"), ""),
            **tree("frontend/src/common", 3, ".js"),  # new files beside the bucketed ones
            **tree("backend/app/orders", 3),  # a folder nothing claims
            "backend/app/lonely.py": "",
        },
    )
    bucket = _module(
        "shared-frontend",
        ["frontend/src/common/A.js", "frontend/src/common/B.js"],
        kind=ModuleKind.BUCKET,
    )
    manifest = Manifest(
        modules=[bucket, new_bucket("shared-backend")],
        labels={"backend/app/lonely.py": "shared-backend"},
    )
    files = source_files(tmp_path)
    report = detect_drift(tmp_path, manifest, files)
    assert "backend/app/lonely.py" not in report.unplaced  # the label placed it
    assert len(report.unplaced) == 6
    assert [g.name for g in report.groups] == ["orders"]  # common/ is more shared code
    bare = detect_drift(tmp_path, Manifest(), files)
    assert any("frontend/src/common/f0.js" in g.files for g in bare.groups)


@pytest.mark.phase_5
def test_refresh_keeps_buckets_from_the_model_and_buckets_what_it_leaves(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path / "repo",
        [
            (
                "init",
                {
                    **tree("packages/api/src", 4),
                    **tree("packages/web/src", 4),
                    "package.json": "{}",
                },
            )
        ],
    )
    manifest = Manifest(
        modules=[
            _module("api", ["packages/api/**"]),
            _module("shared-backend", ["packages/api/src/f0.py"], kind=ModuleKind.BUCKET),
        ]
    )
    provider = Provider(
        {"placements": [{"group": "web", "module": "new", "new_module_name": "Web app"}]},
        {"assignments": []},
    )
    outcome = refresh_map(root, local_mapper(provider), manifest)
    assert "shared-backend" not in provider.prompts()  # a bucket is never offered
    assert [(m.id, m.tier) for m in outcome.new_modules] == [("web-app", Tier.FRONTEND)]
    assert outcome.unresolved == ["package.json"]
    written = apply_refresh(manifest, outcome, "m", root)
    assert bucket_sizes(written, source_files(root)) == {"shared-backend": 1, "tooling": 1}


@pytest.mark.phase_5
def test_accepting_a_suggestion_takes_the_file_out_of_its_bucket(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path / "repo",
        [("init", {**tree("app/orders", 3), "app/helpers.py": "", "app/utils.py": ""})],
    )
    manifest = Manifest(
        modules=[
            _module("orders", ["app/orders/**"]),
            _module("shared", ["app/helpers.py", "app/utils.py"], kind=ModuleKind.BUCKET),
        ],
        suggestions=[Suggestion(module="orders", paths=["app/helpers.py"])],
    )
    grown = accept_suggestions(manifest, root, source_files(root))
    by_id = {m.id: m for m in grown.modules}
    assert membership(grown).module_of("app/helpers.py") == "orders"
    assert by_id["shared"].paths == ["app/utils.py"]


@pytest.mark.phase_5
def test_the_agent_route_reports_tiers_and_buckets(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path / "repo",
        [
            (
                "init",
                {
                    **tree("backend/app/subs", 3),
                    **tree("frontend/src/subs", 3, ".js"),
                    "frontend/src/App.js": "",
                },
            )
        ],
    )
    result = submit_map(
        root,
        [
            _proposal("subs", ["backend/app/subs/**"]),
            _proposal("subs-ui", ["frontend/src/subs/**"]),
        ],
        "claude-code/test",
    )
    assert result["ok"] is True and result["buckets"] == {"shared-frontend": 1}
    view = modules_view(root)
    tiers = {m["id"]: m["tier"] for m in view["modules"]}  # type: ignore[attr-defined, union-attr]
    assert tiers == {"subs": "backend", "subs-ui": "frontend", "shared-frontend": "frontend"}
    assert view["dangling_labels"] == [] and view["drift"]["unplaced"] == 0  # type: ignore[index]


@pytest.mark.phase_5
def test_an_apps_own_config_files_are_tooling_but_its_source_files_stay_shared() -> None:
    config = [
        "apps/server/package.json",
        "apps/server/.gitignore",
        "apps/server/nest-cli.json",
        "apps/server/eslint.config.mjs",
        "apps/server/Dockerfile",
        "apps/client/index.html",
        "apps/client/vite.config.ts",
    ]
    shared = {
        "apps/server/src/main.ts": "shared-backend",
        "apps/server/run.py": "shared-backend",  # source in the app folder is code, not config
        "apps/server/src/package.json": "shared-backend",  # config only counts at the app root
        "apps/client/src/App.tsx": "shared-frontend",
        "apps/client/src/data/seed.json": "shared-frontend",
        "apps/client/public/index.html": "shared-frontend",
    }
    tiers = Tiers([*config, *shared])
    assert {path: bucket_of(path, tiers) for path in config} == dict.fromkeys(config, "tooling")
    assert {path: bucket_of(path, tiers) for path in shared} == shared


@pytest.mark.phase_5
def test_a_submodule_is_a_directory_pointer_and_not_a_source_file(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path / "repo",
        [("init", {"apps/server/src/main.ts": "", ".gitmodules": "[submodule]\n"})],
    )
    pointer = f"160000,{git(root, 'rev-parse', 'HEAD').strip()},apps/server/src/ee"
    git(root, "update-index", "--add", "--cacheinfo", pointer)
    assert "apps/server/src/ee" in git(root, "ls-files")  # git lists it like a file
    files, from_git = modelled_files(root)
    assert from_git and files == [".gitmodules", "apps/server/src/main.ts"]
