"""scripts/check_release_tag.py — a tag may only release the version the packages declare.

The script runs in the release workflow before anything is built. What decides whether it stops
a release is plain logic, so it is checked here with no network and no uv.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_release_tag.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
VERSION = "0.3.0a6"
LOCKSTEP = {"reasonledger-core": VERSION, "reasonledger": VERSION, "reasonledger-mcp": VERSION}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_release_tag", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_release_tag"] = module
    spec.loader.exec_module(module)
    return module


tag_check = _load()


@pytest.mark.phase_3
def test_a_tag_naming_the_shared_version_passes() -> None:
    tag_check.check_tag(f"v{VERSION}", LOCKSTEP)


@pytest.mark.phase_3
def test_a_tag_for_another_version_is_refused_and_names_both() -> None:
    with pytest.raises(tag_check.TagError) as refused:
        tag_check.check_tag("v0.3.0a7", LOCKSTEP)
    message = str(refused.value)
    assert "0.3.0a7" in message
    assert VERSION in message


@pytest.mark.phase_3
def test_one_package_left_behind_is_refused() -> None:
    behind = {**LOCKSTEP, "reasonledger-mcp": "0.3.0a4"}
    with pytest.raises(tag_check.TagError, match="reasonledger-mcp 0.3.0a4"):
        tag_check.check_tag(f"v{VERSION}", behind)


@pytest.mark.phase_3
@pytest.mark.parametrize("tag", [VERSION, f"release-{VERSION}", f"v{VERSION}-rc1", "v"])
def test_a_tag_that_is_not_exactly_v_plus_the_version_is_refused(tag: str) -> None:
    with pytest.raises(tag_check.TagError):
        tag_check.check_tag(tag, LOCKSTEP)


@pytest.mark.phase_3
def test_the_real_packages_declare_one_version_between_them() -> None:
    versions = tag_check.package_versions()
    assert set(versions) == set(LOCKSTEP)
    assert len(set(versions.values())) == 1, versions


@pytest.mark.phase_3
def test_main_exits_nonzero_for_a_tag_that_disagrees(capsys: pytest.CaptureFixture[str]) -> None:
    assert tag_check.main(["v999.0.0"]) == 1
    assert "FAILED" in capsys.readouterr().err


@pytest.mark.phase_3
def test_main_accepts_the_tag_for_the_declared_version() -> None:
    (declared,) = set(tag_check.package_versions().values())
    assert tag_check.main([f"v{declared}"]) == 0


@pytest.mark.phase_3
def test_the_workflow_runs_the_check_on_tag_pushes_before_building() -> None:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["gate"]["steps"]
    names = [step.get("name") for step in steps]
    guard = next(step for step in steps if "check_release_tag.py" in step.get("run", ""))
    assert guard["if"] == "github.event_name == 'push'"
    assert '"$GITHUB_REF_NAME"' in guard["run"]
    assert names.index(guard["name"]) < names.index("Release gate")
