"""Phase 5 — resolving signals into modules, the manifest, and scanning real (tiny) repos."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from modules_helpers import git, make_repo, tree, write_files
from reasonledger_core.modules import (
    Confidence,
    Manifest,
    ManifestError,
    Module,
    ModuleKind,
    ModuleStatus,
    load_manifest,
    merge_proposals,
    reject,
    scan_repo,
    write_manifest,
)
from reasonledger_core.modules.config import FOUNDATION_DEPENDENTS, MANIFEST_PATH
from reasonledger_core.modules.manifest import paths_fingerprint
from reasonledger_core.modules.models import Candidate, SignalKind
from reasonledger_core.modules.resolve import resolve_modules, slug
from reasonledger_core.sync.repo import CommitChange, recent_commit_changes


def _cand(name: str, signal: SignalKind, files: list[str], **kw: str) -> Candidate:
    return Candidate(name=name, signal=signal, files=frozenset(files), **kw)  # type: ignore[arg-type]


def _files(prefix: str, count: int) -> list[str]:
    return sorted(tree(prefix, count))


@pytest.mark.phase_5
def test_agreeing_signals_become_one_high_confidence_module() -> None:
    files = _files("svc/billing", 5)
    modules = resolve_modules(
        [
            _cand("billing", SignalKind.WORKSPACE, files),
            _cand("billing", SignalKind.LAYOUT, files),
            _cand("solo", SignalKind.LAYOUT, _files("solo", 4)),
        ],
        files + _files("solo", 4) + _files("svc/other", 3),
        [],
    )
    by_id = {m.id: m for m in modules}
    assert by_id["billing"].confidence is Confidence.HIGH
    assert by_id["billing"].evidence == ["workspace", "layout"]
    assert by_id["solo"].confidence is Confidence.LOW
    assert by_id["billing"].paths == ["svc/billing/**"]


@pytest.mark.phase_5
def test_confidence_bands_follow_agreement() -> None:
    files = [*_files("a", 4), *_files("b", 4), *_files("c", 4)]
    modules = resolve_modules(
        [
            _cand("a", SignalKind.SPECS, _files("a", 4), id_hint="a"),
            _cand("b", SignalKind.COCHANGE, _files("b", 4)),
            _cand("c", SignalKind.LAYOUT, _files("c", 4)),
        ],
        files,
        [],
    )
    assert {m.id: m.confidence for m in modules} == {
        "a": Confidence.MEDIUM,  # one strong signal
        "b": Confidence.LOW,  # co-change alone
        "c": Confidence.LOW,  # layout alone
    }


@pytest.mark.phase_5
def test_each_file_lands_in_one_module_and_the_stronger_signal_wins() -> None:
    wide = _files("app", 12)
    inner = wide[:3]
    modules = resolve_modules(
        [_cand("app", SignalKind.LAYOUT, wide), _cand("feature", SignalKind.SPECS, inner)],
        wide,
        [],
    )
    owned = {m.id: set(m.paths) for m in modules}
    assert owned["feature"] == set(inner)
    # the layout remainder kept 9 of 12 files (75%), above MIN_REMAINDER_SHARE, so it stays
    assert owned["app"] == set(wide[3:])
    assert not owned["feature"] & owned["app"]


@pytest.mark.phase_5
def test_a_weak_candidate_that_is_mostly_claimed_elsewhere_dissolves() -> None:
    wide = _files("app", 10)
    modules = resolve_modules(
        [_cand("app", SignalKind.LAYOUT, wide), _cand("spec", SignalKind.SPECS, wide[:8])],
        wide,
        [],
    )
    assert [m.id for m in modules] == ["spec"]  # 2 of 10 files left: not a module


@pytest.mark.phase_5
def test_ids_are_unique_and_slugged() -> None:
    first, second = _files("one/utils", 3), _files("two/utils", 3)
    modules = resolve_modules(
        [
            _cand("Utils", SignalKind.WORKSPACE, first),
            _cand("utils", SignalKind.WORKSPACE, second),
        ],
        first + second,
        [],
    )
    assert sorted(m.id for m in modules) == ["utils", "utils-2"]
    assert slug("Admin & System!") == "admin-system"


@pytest.mark.phase_5
def test_foundations_by_name_hint_and_by_dependents() -> None:
    base = _files("base", 4)
    features = {f"feat{i}": _files(f"feat{i}", 3) for i in range(FOUNDATION_DEPENDENTS)}
    universe = base + [f for files in features.values() for f in files]
    cands = [_cand("dates", SignalKind.WORKSPACE, base)] + [
        _cand(name, SignalKind.WORKSPACE, files) for name, files in features.items()
    ]
    # every feature's commits also touch the base: it is what they all change alongside
    commits = [
        CommitChange(f"c{n}{i}", "x", (files[0], base[0]))
        for i, files in enumerate(features.values())
        for n in range(3)
    ]
    quiet = {m.id: m for m in resolve_modules(cands, universe, [])}
    assert quiet["dates"].kind is ModuleKind.FOUNDATION and "name-hint" in quiet["dates"].evidence
    assert quiet["feat0"].kind is ModuleKind.FEATURE
    renamed = [_cand("ledger", SignalKind.WORKSPACE, base), *cands[1:]]
    loud = {m.id: m for m in resolve_modules(renamed, universe, commits)}
    assert loud["ledger"].kind is ModuleKind.FOUNDATION
    assert f"dependents:{FOUNDATION_DEPENDENTS}" in loud["ledger"].evidence
    assert loud["feat0"].kind is ModuleKind.FEATURE  # nobody depends on a feature


def _module(module_id: str, *paths: str, status: ModuleStatus = ModuleStatus.PROPOSED) -> Module:
    return Module(id=module_id, name=module_id.title(), paths=list(paths), status=status)


@pytest.mark.phase_5
def test_manifest_round_trips_and_rewrites_identically(tmp_path: Path) -> None:
    manifest = Manifest(
        modules=[
            _module("zeta", "z/**"),
            Module(
                id="alpha",
                name="Alpha",
                description="First",
                paths=["a/**"],
                kind=ModuleKind.FOUNDATION,
                status=ModuleStatus.CONFIRMED,
                confirmed_by="someone",
                evidence=["specs"],
                confidence=Confidence.HIGH,
            ),
        ]
    )
    path = write_manifest(tmp_path, manifest)
    first = path.read_bytes()
    loaded = load_manifest(tmp_path)
    assert [m.id for m in loaded.modules] == ["alpha", "zeta"]  # stable order
    write_manifest(tmp_path, loaded)
    assert path.read_bytes() == first
    assert not list(path.parent.glob("*.tmp"))
    assert load_manifest(tmp_path / "missing").modules == []


@pytest.mark.phase_5
def test_malformed_manifest_names_the_problem(tmp_path: Path) -> None:
    write_files(tmp_path, {str(MANIFEST_PATH): "modules: [1, 2]\n"})
    with pytest.raises(ManifestError, match="modules.yml"):
        load_manifest(tmp_path)


@pytest.mark.phase_5
def test_merge_keeps_confirmed_replaces_proposed_and_honours_rejections() -> None:
    kept = _module("kept", "k/**", status=ModuleStatus.CONFIRMED)
    manifest = Manifest(modules=[kept, _module("stale", "s/**")])
    refused = _module("refused", "r/**")
    manifest = reject(
        manifest.model_copy(update={"modules": [*manifest.modules, refused]}), refused
    )
    assert paths_fingerprint(["r/**"]) in {r.fingerprint for r in manifest.rejected}
    merged = merge_proposals(
        manifest, [_module("fresh", "f/**"), _module("refused", "r/**"), _module("kept", "x/**")]
    )
    assert [m.id for m in merged.modules] == ["kept", "fresh"]  # stale gone, refused stays down
    assert merged.modules[0] is kept or merged.modules[0] == kept  # confirmed untouched


def _app_repo(tmp_path: Path) -> Path:
    api = tree("packages/api/src", 4)
    web = tree("packages/web/src", 4)
    return make_repo(
        tmp_path / "repo",
        [
            ("init", {"package.json": '{"workspaces": ["packages/*"]}', **api, **web}),
            ("feat(api): more", {"packages/api/src/f0.py": "x = 1\n"}),
            ("docs: readme", {"README.md": "# app\n"}),
        ],
    )


@pytest.mark.phase_5
def test_scan_proposes_workspace_modules_and_counts_files(tmp_path: Path) -> None:
    result = scan_repo(_app_repo(tmp_path), manifest=Manifest())
    assert [m.id for m in result.modules] == ["api", "web"]
    assert all(m.confidence is Confidence.HIGH for m in result.modules)  # workspace + layout
    assert result.files_per_module == {"api": 4, "web": 4}
    assert result.unplaced_files == 2  # package.json and README.md
    assert result.commits_scanned == 3 and result.limitations == []


@pytest.mark.phase_5
def test_scan_is_idempotent_and_does_not_churn_the_manifest(tmp_path: Path) -> None:
    repo = _app_repo(tmp_path)
    first = scan_repo(repo)
    write_manifest(repo, merge_proposals(load_manifest(repo), first.modules))
    snapshot = (repo / MANIFEST_PATH).read_bytes()
    second = scan_repo(repo)
    write_manifest(repo, merge_proposals(load_manifest(repo), second.modules))
    assert [m.model_dump() for m in first.modules] == [m.model_dump() for m in second.modules]
    assert (repo / MANIFEST_PATH).read_bytes() == snapshot


@pytest.mark.phase_5
def test_confirmed_modules_win_and_are_not_proposed_again(tmp_path: Path) -> None:
    repo = _app_repo(tmp_path)
    mine = Module(
        id="backend",
        name="Backend",
        paths=["packages/api/**"],
        status=ModuleStatus.CONFIRMED,
        confirmed_by="me",
    )
    result = scan_repo(repo, manifest=Manifest(modules=[mine]))
    assert result.modules[0] == mine and [m.id for m in result.modules] == ["backend", "web"]
    assert result.files_per_module["backend"] == 4


@pytest.mark.phase_5
def test_scan_outside_git_degrades_and_says_so(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    write_files(root, {**tree("src/alpha", 4), **tree("src/beta", 4), ".gitignore": "ignored/\n"})
    result = scan_repo(root, manifest=Manifest())
    assert {m.id for m in result.modules} == {"alpha", "beta"}
    assert result.commits_scanned == 0
    assert any("not a git repository" in line for line in result.limitations)


@pytest.mark.phase_5
def test_scan_reports_a_shallow_clone_and_squash_history(tmp_path: Path) -> None:
    source = make_repo(
        tmp_path / "src",
        [
            (f"feat: thing (#{n})", {f"packages/p/f{n}.py": f"{n}\n", "package.json": "{}"})
            for n in range(6)
        ],
    )
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "2", f"file://{source}", str(clone)], check=True
    )
    result = scan_repo(clone, manifest=Manifest())
    text = " | ".join(result.limitations)
    assert "shallow clone" in text and "squash-merged" in text
    assert result.commits_scanned == 2


@pytest.mark.phase_5
def test_commit_history_lists_names_only_and_treats_a_rename_as_two_paths(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "r", [("add", {"old.py": "x = 1\n" * 20})])
    git(repo, "mv", "old.py", "new.py")
    git(repo, "commit", "-q", "-m", "rename")
    latest = recent_commit_changes(repo, limit=1)
    assert latest is not None and set(latest[0].files) == {"old.py", "new.py"}


@pytest.mark.phase_5
def test_a_container_directory_is_not_proposed_alongside_the_modules_inside_it() -> None:
    wide = _files("backend", 10)
    modules = resolve_modules(
        [_cand("backend", SignalKind.LAYOUT, wide), _cand("promo", SignalKind.SPECS, wide[:5])],
        wide,
        [],
    )
    assert [m.id for m in modules] == ["promo"]  # backend keeps 5 of 10: it is a container


@pytest.mark.phase_5
def test_convention_and_cochange_back_a_module_that_contains_them() -> None:
    wide = _files("app", 8)
    modules = resolve_modules(
        [
            _cand("promo", SignalKind.SPECS, wide),
            _cand("promo-code", SignalKind.CONVENTION, wide[:3]),
            _cand("other", SignalKind.CONVENTION, [*wide[6:], "elsewhere/x.py", "elsewhere/y.py"]),
        ],
        [*wide, "elsewhere/x.py", "elsewhere/y.py"],
        [],
    )
    by_id = {m.id: m for m in modules}
    assert by_id["promo"].evidence == ["specs", "convention"]
    assert by_id["promo"].confidence is Confidence.HIGH
    assert by_id["promo"].paths == ["app/**"]  # backing evidence does not widen the module
    assert "other" not in by_id  # mostly outside: not corroboration, and too few files left


@pytest.mark.phase_5
def test_tooling_folds_into_platform_or_stands_alone_as_a_foundation() -> None:
    platform = _files("backend/core", 4)
    ops = [*_files("deploy", 2), *_files("backend/cleanup_scripts", 2)]
    with_platform = resolve_modules(
        [
            _cand("Platform", SignalKind.SPECS, platform, id_hint="platform"),
            _cand("Tooling", SignalKind.TOOLING, ops, id_hint="tooling"),
        ],
        [*platform, *ops],
        [],
    )
    (module,) = with_platform
    assert module.id == "platform" and module.evidence[:2] == ["specs", "tooling"]
    assert set(module.paths) == {"backend/**", "deploy/**"}
    alone = resolve_modules([_cand("Tooling", SignalKind.TOOLING, ops, id_hint="tooling")], ops, [])
    assert [(m.id, m.kind) for m in alone] == [("tooling", ModuleKind.FOUNDATION)]


@pytest.mark.phase_5
def test_a_directory_with_its_own_license_that_only_layout_noticed_is_vendored() -> None:
    files = [*_files("vendor_lib", 4), "vendor_lib/LICENSE", *_files("app", 4)]
    from reasonledger_core.modules.signals.layout import layout_candidates

    found = {c.name: c for c in layout_candidates(sorted(files))}
    assert found["vendor_lib"].vendored and not found["app"].vendored
    modules = resolve_modules(list(found.values()), sorted(files), [])
    assert [m.id for m in modules] == ["app"]
