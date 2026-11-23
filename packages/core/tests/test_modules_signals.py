"""Phase 5 — module signals: each one on a synthetic repo, deterministic and offline."""

from __future__ import annotations

from pathlib import Path

import pytest
from modules_helpers import tree, write_files
from reasonledger_core.modules.config import (
    COCHANGE_EDGE_THRESHOLD,
    MAX_COMMITS_SCANNED,
    MAX_FILES_PER_COMMIT,
    MIN_COCHANGE_COMMITS,
    MIN_MODULE_FILES,
)
from reasonledger_core.modules.globs import PathMatcher, compress_paths, glob_regex
from reasonledger_core.modules.models import SignalKind
from reasonledger_core.modules.signals.cochange import (
    cochange_candidates,
    commit_scope,
)
from reasonledger_core.modules.signals.codeowners import codeowners_candidates
from reasonledger_core.modules.signals.layout import layout_candidates
from reasonledger_core.modules.signals.specs import spec_candidates
from reasonledger_core.modules.signals.workspace import workspace_candidates
from reasonledger_core.sync.repo import CommitChange


@pytest.mark.phase_5
def test_thresholds_are_pinned() -> None:
    """These move what a scan proposes; change them only with a recalibration."""
    assert (MAX_COMMITS_SCANNED, MAX_FILES_PER_COMMIT) == (5000, 50)
    assert (MIN_COCHANGE_COMMITS, COCHANGE_EDGE_THRESHOLD, MIN_MODULE_FILES) == (3, 0.5, 3)


@pytest.mark.phase_5
def test_glob_specificity_exact_beats_deep_beats_shallow() -> None:
    matcher = PathMatcher(
        [("wide", ["a/**"]), ("deep", ["a/b/**"]), ("one", ["a/b/keep.py"]), ("star", ["x/*.py"])]
    )
    assert matcher.module_of("a/z.py") == "wide"
    assert matcher.module_of("a/b/c/d.py") == "deep"
    assert matcher.module_of("a/b/keep.py") == "one"
    assert matcher.module_of("x/f.py") == "star"
    assert matcher.module_of("x/sub/f.py") is None
    assert glob_regex("f[1].py").match("f[1].py")  # brackets are literal, not a class


@pytest.mark.phase_5
def test_compress_uses_dir_globs_only_when_the_dir_holds_only_members() -> None:
    universe = ["a/x.py", "a/y.py", "b/p.py", "b/q.py", "c/k.py"]
    assert compress_paths(["a/x.py", "a/y.py", "b/p.py"], universe) == ["a/**", "b/p.py"]
    assert compress_paths(universe, universe) == ["a/**", "b/**", "c/**"]


@pytest.mark.phase_5
def test_workspace_manifests(tmp_path: Path) -> None:
    files = {
        **tree("packages/a", 3),
        **tree("packages/b", 3),
        **tree("packages/skip", 3),
        **tree("playground/p", 3),
        **tree("crates/c1", 3),
        **tree("svc/s1", 3),
    }
    write_files(
        tmp_path,
        {
            "package.json": '{"workspaces": {"packages": ["packages/*", "playground/*"]}}',
            "pnpm-workspace.yaml": "packages:\n  - 'packages/*'\n  - '!packages/skip'\n",
            "Cargo.toml": '[workspace]\nmembers = ["crates/*"]\n',
            "go.work": "go 1.22\nuse (\n\t./svc/s1\n)\n",
        },
    )
    found = {c.name for c in workspace_candidates(tmp_path, sorted(files))}
    # playground is support code, packages/skip is excluded, the rest are members
    assert found == {"a", "b", "c1", "s1"}
    assert all(
        c.signal is SignalKind.WORKSPACE for c in workspace_candidates(tmp_path, sorted(files))
    )


@pytest.mark.phase_5
def test_workspace_uv_members_and_exclude(tmp_path: Path) -> None:
    files = {**tree("libs/x", 3), **tree("libs/y", 3)}
    write_files(
        tmp_path,
        {"pyproject.toml": '[tool.uv.workspace]\nmembers = ["libs/*"]\nexclude = ["libs/y"]\n'},
    )
    assert [c.name for c in workspace_candidates(tmp_path, sorted(files))] == ["x"]


SPEC = """\
# Promo codes — behaviour spec

## 1. Purpose & scope

Owns **redemption** rules
and invites.

## 2. Key files

- **Routes**: `app/routes/promo_routes.py`
- **Services**: `app/services/promo_service.py`; also `sub_service.py::burn`
- **Models**: `app/models/promo/`; `dup.py` is ambiguous; `ghost.py` does not exist

## 3. Data model

- `app/util/dup.py`
"""


@pytest.mark.phase_5
def test_specs_key_files_resolve_paths_dirs_and_unique_basenames(tmp_path: Path) -> None:
    code = [
        "app/routes/promo_routes.py",
        "app/services/promo_service.py",
        "app/services/sub_service.py",
        "app/models/promo/a.py",
        "app/models/promo/b.py",
        "app/util/dup.py",
        "app/other/dup.py",
    ]
    specs = {
        "specs/modules/promo-codes.md": SPEC,
        "specs/modules/_TEMPLATE.md": "# t\n",
        "specs/modules/empty.md": "# Empty — behaviour spec\n\n## 2. Key files\n\nnone\n",
    }
    write_files(tmp_path, {**dict.fromkeys(code, ""), **specs})
    (found,) = spec_candidates(tmp_path, sorted([*code, *specs]))
    assert found.id_hint == "promo-codes" and found.name == "Promo codes"
    assert found.files == {
        "app/routes/promo_routes.py",
        "app/services/promo_service.py",
        "app/services/sub_service.py",
        "app/models/promo/a.py",
        "app/models/promo/b.py",
    }  # not the ambiguous dup.py, not the file named only after the section
    assert (
        found.description == "Promo codes. Owns redemption rules and invites"
    )  # the trailing full stop is trimmed


@pytest.mark.phase_5
def test_codeowners_groups_by_owner_and_skips_the_catch_all(tmp_path: Path) -> None:
    files = sorted({**tree("billing", 4), **tree("auth", 4), **tree("misc", 20)})
    write_files(
        tmp_path,
        {".github/CODEOWNERS": "* @org/everyone\n/billing/ @org/payments\nauth/ @org/identity\n"},
    )
    names = {c.name: len(c.files) for c in codeowners_candidates(tmp_path, files)}
    assert names == {"payments": 4, "identity": 4}  # "everyone" owns most files: not discriminating


@pytest.mark.phase_5
def test_layout_descends_containers_merges_layers_and_skips_substructure() -> None:
    files = sorted(
        {
            **tree("packages/api", 4),
            **tree("packages/web", 4),
            **tree("app/orders", 3),
            **tree("app/graphql/orders", 3),
            **tree("app/payments", 3),
            **tree("app/payments/migrations", 4),
            **tree("app/shipping", 3),
            **tree("docs/guide", 5),
            **tree("tests/unit", 5),
        }
    )
    found = {c.name: c for c in layout_candidates(files)}
    assert {"api", "web", "orders", "payments", "shipping"} <= set(found)
    assert "migrations" not in found and "docs" not in found and "tests" not in found
    assert len(found["orders"].files) == 6  # app/orders and app/graphql/orders are one module
    assert any(f.startswith("app/payments/migrations/") for f in found["payments"].files)


@pytest.mark.phase_5
def test_layout_gives_a_namespace_directorys_own_files_a_module() -> None:
    files = sorted(
        {**tree("core", 3), **tree("core/a", 3), **tree("core/b", 3), **tree("core/c", 3)}
    )
    found = {c.name: c.files for c in layout_candidates(files)}
    assert found["core"] == {f"core/f{i}.py" for i in range(3)}  # only its direct files
    assert set(found) == {"core", "a", "b", "c"}


def _commit(subject: str, *files: str) -> CommitChange:
    return CommitChange(sha=subject, subject=subject, files=files)


@pytest.mark.phase_5
def test_cochange_links_files_that_keep_changing_together() -> None:
    feature = ["api/routes.py", "svc/logic.py", "model/row.py", "web/page.js", "web/form.js"]
    other = [f"lib/x{i}.py" for i in range(20)]
    commits = [_commit("feat(promo): x", *feature) for _ in range(MIN_COCHANGE_COMMITS)]
    commits += [_commit("fix: y", "lib/a.py", "lib/b.py")] * 2  # below the minimum
    universe = feature + other
    (found,) = cochange_candidates(commits, universe)
    assert found.files == frozenset(feature) and found.signal is SignalKind.COCHANGE
    assert found.name == "promo"  # the scope every commit shared


@pytest.mark.phase_5
def test_cochange_ignores_bulk_commits_and_single_directory_clusters() -> None:
    bulk = [f"m{i}/f.py" for i in range(MAX_FILES_PER_COMMIT + 1)]
    inside_one_dir = [f"one/f{i}.py" for i in range(6)]
    commits = [_commit("chore: format", *bulk)] * 5 + [_commit("x", *inside_one_dir)] * 5
    assert cochange_candidates(commits, bulk + inside_one_dir) == []


@pytest.mark.phase_5
def test_cochange_drops_a_cluster_that_is_everything() -> None:
    names = [f"d{i % 3}/f{i}.py" for i in range(10)]
    commits = [_commit("everything", *names)] * 4
    assert cochange_candidates(commits, names) == []  # one component, over MAX_COMPONENT_SHARE


@pytest.mark.phase_5
def test_commit_scope_parsing() -> None:
    assert commit_scope("feat(core): add") == "core"
    assert commit_scope("fix(api,web)!: boom") == "api"
    assert commit_scope("update readme") is None


@pytest.mark.phase_5
def test_modelled_files_skip_secrets_generated_output_and_test_named_dirs(tmp_path: Path) -> None:
    from reasonledger_core.modules.files import is_support, modelled_files

    write_files(
        tmp_path,
        {
            "app/.env": "SECRET=1\n",
            "app/.env.production": "SECRET=2\n",
            "app/main.py": "",
            "pkg.egg-info/PKG-INFO": "",
            "uv.lock": "",
            "logo.png": "",
        },
    )
    files, from_git = modelled_files(tmp_path)
    assert files == ["app/main.py"] and not from_git
    assert is_support("test_pdfs/a.pdf") and is_support("tests-build/x.rs")
    assert is_support("crates/tokio-test/src/lib.rs") and not is_support("app/latest/x.py")


@pytest.mark.phase_5
def test_layout_skips_test_named_directories_and_model_binaries(tmp_path: Path) -> None:
    from reasonledger_core.modules.files import modelled_files

    write_files(tmp_path, {**tree("svc/orders", 4), **tree("test_pdfs", 5), "svc/m.onnx": ""})
    files, _ = modelled_files(tmp_path)
    assert "svc/m.onnx" not in files
    assert {c.name for c in layout_candidates(files)} == {"orders"}


@pytest.mark.phase_5
def test_convention_groups_a_feature_across_layers() -> None:
    from reasonledger_core.modules.signals.convention import (
        convention_candidates,
        layer_of,
        stem_of,
    )

    assert stem_of("app/routes/promo_code_routes.py") == ["promo", "code"]
    assert stem_of("src/services/PromoCodeService.ts") == ["promo", "code"]
    assert stem_of("app/views/users/index.html.erb") == ["user"]  # a view folder names the feature
    assert stem_of("src/hooks/useUser.js") == ["user"]
    assert layer_of("backend/app/models/firestore/promo_code.py") == "model"
    assert layer_of("util/x.py") is None
    files = sorted(
        {
            "app/models/promo_code.py": "",
            "app/routes/promo_code_routes.py": "",
            "app/services/promo_code_service.py": "",
            "app/models/user.py": "",
            "app/services/user_service.py": "",
            "app/models/helpers.py": "",
            "app/services/index.py": "",
            "tests/models/promo_code_test.py": "",
        }
    )
    found = {c.name: c for c in convention_candidates(files)}
    assert set(found) == {"promo-code"}  # user is in 2 files; tests are support code
    assert found["promo-code"].extras == ("model", "route", "service")
    assert found["promo-code"].signal is SignalKind.CONVENTION


@pytest.mark.phase_5
def test_tooling_candidates_collect_deploy_and_script_dirs_but_not_tests() -> None:
    from reasonledger_core.modules.signals.tooling import tooling_candidates

    files = [
        *tree("deploy", 2),
        *tree("backend/cleanup_scripts", 2),
        *tree("tests/scripts", 3),
        *tree("app/core", 3),
    ]
    (found,) = tooling_candidates(sorted(files))
    assert found.signal is SignalKind.TOOLING and found.id_hint == "tooling"
    assert all(f.startswith(("deploy/", "backend/cleanup_scripts/")) for f in found.files)
    assert tooling_candidates(sorted(tree("deploy", 2))) == []  # below the module minimum


@pytest.mark.phase_5
def test_layout_expands_wrapper_directories_and_skips_layer_named_ones() -> None:
    files = sorted(
        {
            "web/package.json": "",
            "web/README.md": "",
            "web/.eslintrc.js": "",
            **tree("web/src/components/billing", 4),
            **tree("web/src/components/admin", 4),
            **tree("web/src/components/auth", 4),
            **tree("web/src/hooks", 4),
        }
    )
    names = {c.name for c in layout_candidates(files)}
    assert {"billing", "admin", "auth"} <= names  # web -> src -> components -> features
    assert "hooks" not in names  # a layer, not a feature
