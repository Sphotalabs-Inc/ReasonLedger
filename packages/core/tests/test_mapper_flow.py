"""Phase 5 — propose, drift, refresh and the agent route, end to end with a stubbed provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from modules_helpers import git, make_repo, tree, write_files
from reasonledger_core.modules import (
    Confidence,
    Manifest,
    Module,
    ModuleStatus,
    PathMatcher,
    load_manifest,
    write_manifest,
)
from reasonledger_core.modules.agent_route import (
    mapping_task,
    modules_view,
    submit_map,
)
from reasonledger_core.modules.config import MANIFEST_PATH
from reasonledger_core.modules.digest import source_files
from reasonledger_core.modules.drift import detect_drift
from reasonledger_core.modules.manifest import paths_fingerprint
from reasonledger_core.modules.mapping import (
    accept_suggestions,
    apply_map,
    apply_refresh,
    propose_map,
    refresh_map,
)
from reasonledger_core.modules.models import RejectedModule
from test_mapper_core import Provider, local_mapper


def _repo(tmp_path: Path) -> Path:
    files = {
        "package.json": '{"workspaces": ["packages/*"]}',
        **tree("packages/api/src", 5),
        **tree("packages/web/src", 5),
        **tree("svc", 0),
    }
    return make_repo(tmp_path / "repo", [("init", files)])


def _mod(module_id: str, paths: list[str], **extra: object) -> dict[str, object]:
    return {
        "id": module_id,
        "name": module_id.title(),
        "kind": "feature",
        "description": f"the {module_id} capability",
        "paths": paths,
        **extra,
    }


def _confirmed(module_id: str, paths: list[str]) -> Module:
    return Module(id=module_id, name=module_id, paths=paths, status=ModuleStatus.CONFIRMED)


@pytest.mark.phase_5
def test_propose_validates_corroborates_and_records_who_proposed(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    provider = Provider(
        {
            "modules": [
                _mod("api", ["packages/api/**"]),
                _mod("web", ["packages/web/**", "ghost/**"]),
            ]
        }
    )
    outcome = propose_map(root, local_mapper(provider), Manifest(), "single")
    by_id = {m.id: m for m in outcome.validated.modules}
    assert (
        set(by_id) == {"api", "web"} and outcome.validated.coverage < 1.0
    )  # package.json unplaced
    assert any("dropped 1 path" in issue for issue in outcome.validated.issues)
    api = by_id["api"]
    assert api.evidence[0] == "model:openai_compatible:m" and "workspace" in api.evidence
    assert api.confidence is Confidence.HIGH  # workspace and layout both back it
    written = apply_map(Manifest(), outcome.validated.modules, "openai_compatible:m", root)
    assert written.mapped_by == "openai_compatible:m"
    assert written.mapped_at_commit == git(root, "rev-parse", "HEAD").strip()


@pytest.mark.phase_5
def test_a_new_map_never_alters_confirmed_modules_and_honours_rejections(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    kept = _confirmed(
        "api", ["packages/api/src/f0.py", "packages/api/src/f1.py", "packages/api/src/f2.py"]
    )
    refused = paths_fingerprint(["packages/web/**"])
    manifest = Manifest(
        modules=[kept], rejected=[RejectedModule(fingerprint=refused, paths=["packages/web/**"])]
    )
    provider = Provider(
        {"modules": [_mod("api", ["packages/api/**"]), _mod("web", ["packages/web/**"])]}
    )
    outcome = propose_map(root, local_mapper(provider), manifest, "single")
    written = apply_map(manifest, outcome.validated.modules, "m", root)
    # web was rejected and api stays as confirmed; what neither holds goes to the buckets
    assert [m.id for m in written.modules] == [
        "api",
        "shared-backend",
        "shared-frontend",
        "tooling",
    ]
    assert written.modules[0] == kept


@pytest.mark.phase_5
def test_drift_reports_only_what_no_module_claims(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    manifest = Manifest(
        modules=[_confirmed("api", ["packages/api/**"]), _confirmed("ghost", ["nowhere/**"])]
    )
    report = detect_drift(root, manifest, source_files(root))
    assert report.orphans == ["ghost"]
    assert sorted(report.unplaced) == sorted(
        ["package.json", *(f"packages/web/src/f{i}.py" for i in range(5))]
    )
    assert [g.name for g in report.groups] == ["web"]
    assert 0.5 < report.unplaced_share < 0.6
    # new files under an existing glob are not drift
    write_files(root, tree("packages/api/src/more", 4))
    assert len(detect_drift(root, manifest, source_files(root)).unplaced) == len(report.unplaced)


@pytest.mark.phase_5
def test_drift_since_the_mapped_commit_lists_only_what_arrived_after(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mapped = git(root, "rev-parse", "HEAD").strip()
    write_files(root, tree("svc/export", 3, ".py"))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "more")
    manifest = Manifest(mapped_at_commit=mapped, modules=[_confirmed("web", ["packages/web/**"])])
    report = detect_drift(root, manifest, source_files(root))
    assert sorted(report.new_since_map) == sorted(f"svc/export/f{i}.py" for i in range(3))


@pytest.mark.phase_5
def test_refresh_sends_only_unplaced_files_and_leaves_confirmed_alone(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    write_files(root, {f"svc/export_{n}_service.py": "" for n in ("a", "b", "c")})
    api = _confirmed("api", ["packages/api/**"])
    manifest = Manifest(modules=[api])
    provider = Provider(
        {
            "placements": [
                {"group": "web", "module": "new", "new_module_name": "Web app"},
                {"group": "export", "module": "api", "new_module_name": ""},
            ]
        },
        {"assignments": [{"file": "package.json", "module": "api"}]},
    )
    outcome = refresh_map(root, local_mapper(provider), manifest)
    sent = provider.prompts()
    assert "packages/api/src/f0.py" not in sent and "packages/web/src/f0.py" in sent
    # the model said "api" for the export group, but the names disagree: code makes it a new module
    assert [m.id for m in outcome.new_modules] == ["web-app", "export"]
    assert [(s.module, len(s.paths)) for s in outcome.suggestions] == [("api", 1)]
    assert outcome.unresolved == []
    written = apply_refresh(manifest, outcome, "m", root)
    assert written.modules[0] == api and len(written.modules) == 3 and len(written.suggestions) == 1
    # accepting is a person's explicit step; the confirmed module then grows
    grown = accept_suggestions(written, root, source_files(root))
    assert grown.suggestions == []
    api_after = next(m for m in grown.modules if m.id == "api")
    assert PathMatcher([(api_after.id, api_after.paths)]).module_of("package.json") == "api"


@pytest.mark.phase_5
def test_a_group_joins_an_existing_module_only_when_the_names_agree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    write_files(root, {f"svc/export_{n}_service.py": "" for n in ("a", "b", "c")})
    manifest = Manifest(
        modules=[_confirmed("api", ["packages/api/**"]), _confirmed("exports", ["nowhere/**"])]
    )
    provider = Provider(
        {
            "placements": [
                {"group": "web", "module": "api", "new_module_name": ""},
                {"group": "export", "module": "exports", "new_module_name": ""},
            ]
        },
        {"assignments": []},
    )
    outcome = refresh_map(root, local_mapper(provider), manifest)
    assert [m.id for m in outcome.new_modules] == ["web"]  # "web" is not "api"
    assert [(s.module, len(s.paths)) for s in outcome.suggestions] == [("exports", 3)]


@pytest.mark.phase_5
def test_agent_route_hands_out_the_digest_and_writes_validated_proposals(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    task = mapping_task(root)
    assert task["mode"] == "full" and "packages/api/src/" in str(task["digest"])
    assert "submit_module_map" in str(task["instructions"])
    bad = submit_map(root, [_mod("ghost", ["nope/**"])], "claude-code/test")
    assert bad["ok"] is False and not (root / MANIFEST_PATH).exists()  # nothing written
    good = submit_map(
        root,
        [_mod("api", ["packages/api/**"]), _mod("web", ["packages/web/**"])],
        "claude-code/test",
    )
    assert good["ok"] is True and good["modules"] == ["api", "web"]
    manifest = load_manifest(root)
    assert manifest.mapped_by == "claude-code/test"
    assert {m.status for m in manifest.modules} == {ModuleStatus.PROPOSED}


@pytest.mark.phase_5
def test_agent_route_delta_adds_new_modules_and_suggests_for_existing_ones(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    write_files(root, {f"svc/export_{n}.py": "" for n in ("a", "b", "c")})
    write_manifest(root, Manifest(modules=[_confirmed("api", ["packages/api/**"])]))
    delta = mapping_task(root, delta=True)
    assert delta["mode"] == "delta" and [m["id"] for m in delta["existing_modules"]] == ["api"]  # type: ignore[index, union-attr]
    assert "svc/export_a.py" in delta["unplaced_files"]  # type: ignore[operator]
    result = submit_map(
        root,
        [_mod("api", ["package.json"]), _mod("exports", ["svc/export_*"])],
        "claude-code/test",
        delta=True,
    )
    assert result["ok"] is True and result["suggestions"] == 1
    manifest = load_manifest(root)
    # web was left out, so its files wait in a bucket; package.json is a pending suggestion
    assert [m.id for m in manifest.modules] == ["api", "exports", "shared-frontend"]
    assert manifest.suggestions[0].module == "api" and manifest.suggestions[0].paths == [
        "package.json"
    ]
    view = modules_view(root)
    assert view["pending_suggestions"] == 1
    assert view["drift"]["unplaced"] == 1  # type: ignore[index]  # only package.json
    assert json.dumps(view)  # JSON-ready for the MCP tool
