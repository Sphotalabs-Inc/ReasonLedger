"""release.yml and release_gate.sh — who can reach PyPI, in what order, and what is pinned.

The workflow only runs on GitHub, so its safety properties are read from the parsed YAML; the
gate script's one new refusal is run for real against a throwaway repository.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GATE_SCRIPT = REPO_ROOT / "scripts" / "release_gate.sh"
PUSH_ONLY = "github.event_name == 'push'"
PINNED = re.compile(r"@[0-9a-f]{40}$")
# release_gate.sh runs on Linux (the release workflow) and macOS (the maintainer), never on Windows.
# There, `bash` on PATH is the WSL launcher in System32, which is not Git Bash and fails at once.
RUNS_BASH = pytest.mark.skipif(
    sys.platform == "win32", reason="`bash` on a Windows runner is the WSL launcher, not Git Bash"
)
PUBLISH_ENVIRONMENTS = {
    "publish-core": ("pypi-core", "testpypi-core"),
    "publish-mcp": ("pypi-mcp", "testpypi-mcp"),
    "publish-app": ("pypi", "testpypi"),
}


def _load(path: Path) -> dict[Any, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _needs(job: dict[str, Any]) -> set[str]:
    needs = job.get("needs", [])
    return {needs} if isinstance(needs, str) else set(needs)


def _steps(job_name: str) -> list[dict[str, Any]]:
    return _load(WORKFLOW)["jobs"][job_name]["steps"]  # type: ignore[no-any-return]


@pytest.mark.phase_3
def test_a_manual_run_cannot_choose_pypi() -> None:
    workflow = _load(WORKFLOW)
    # YAML 1.1 reads the bare key `on` as the boolean True.
    triggers: dict[str, Any] = workflow.get("on") or workflow[True]
    assert not (triggers["workflow_dispatch"] or {}).get("inputs")
    assert workflow["env"]["INDEX"] == "${{ github.event_name == 'push' && 'pypi' || 'testpypi' }}"


@pytest.mark.phase_3
@pytest.mark.parametrize("job_name", sorted(PUBLISH_ENVIRONMENTS))
def test_only_a_tag_push_reaches_a_pypi_environment(job_name: str) -> None:
    expression = _load(WORKFLOW)["jobs"][job_name]["environment"]
    pypi, testpypi = PUBLISH_ENVIRONMENTS[job_name]
    assert expression == f"${{{{ {PUSH_ONLY} && '{pypi}' || '{testpypi}' }}}}"


@pytest.mark.phase_3
def test_a_tag_must_be_on_main_before_anything_is_tested_or_built() -> None:
    steps = _steps("gate")
    names = [step.get("name") for step in steps]
    check = steps[names.index("Tag is on main")]
    assert check["if"] == PUSH_ONLY
    assert "git merge-base --is-ancestor" in check["run"]
    assert "origin/main" in check["run"]
    assert names.index("Tag is on main") < names.index("Release gate")
    checkout = next(step for step in steps if "actions/checkout" in step.get("uses", ""))
    assert checkout["with"]["fetch-depth"] == 0


@pytest.mark.phase_3
def test_publishing_runs_core_then_the_mcp_server_then_the_cli() -> None:
    jobs = _load(WORKFLOW)["jobs"]
    assert _needs(jobs["publish-core"]) == {"gate"}
    assert _needs(jobs["publish-mcp"]) == {"publish-core"}
    assert {"publish-core", "publish-mcp"} <= _needs(jobs["publish-app"])


@pytest.mark.phase_3
def test_every_action_is_pinned_to_a_commit() -> None:
    unpinned = [
        step["uses"]
        for job in _load(WORKFLOW)["jobs"].values()
        for step in job["steps"]
        if "uses" in step and not PINNED.search(step["uses"])
    ]
    assert unpinned == []


@pytest.mark.phase_3
def test_the_release_runs_on_the_python_ci_runs_on() -> None:
    assert _load(WORKFLOW)["env"]["UV_PYTHON"] == _load(CI_WORKFLOW)["env"]["UV_PYTHON"]


@pytest.mark.phase_3
def test_token_permissions_are_read_only_except_where_a_job_publishes() -> None:
    workflow = _load(WORKFLOW)
    assert workflow["permissions"] == {"contents": "read"}
    for job_name in PUBLISH_ENVIRONMENTS:
        assert workflow["jobs"][job_name]["permissions"] == {"id-token": "write"}


@pytest.mark.phase_3
def test_the_gate_uploads_the_files_it_tested_rather_than_building_again() -> None:
    steps = _steps("gate")
    gate = next(step for step in steps if step.get("name") == "Release gate")
    assert "DIST_DIR=" in gate["run"]
    assert not [step for step in steps if "uv build" in step.get("run", "")]


def _gate_in(root: Path, untracked: str) -> subprocess.CompletedProcess[str]:
    """Run release_gate.sh in a throwaway repository whose `uv` just says it was reached."""
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "release_gate.sh").write_text(GATE_SCRIPT.read_text(encoding="utf-8"))
    (root / "packages" / "core").mkdir(parents=True)
    (root / "packages" / "core" / "module.py").write_text("x = 1\n", encoding="utf-8")
    fake_bin = root / "bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text("#!/bin/sh\necho reached-uv\nexit 99\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    env = {**os.environ, "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"}
    git = ["git", "-c", "user.name=gate-test", "-c", "user.email=gate@example.com"]
    for argv in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "tracked"]):
        subprocess.run([*git, *argv], cwd=root, check=True, capture_output=True)
    target = root / untracked
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("stray\n", encoding="utf-8")
    return subprocess.run(
        ["bash", "scripts/release_gate.sh"], cwd=root, env=env, capture_output=True, text=True
    )


@RUNS_BASH
@pytest.mark.phase_3
def test_the_gate_refuses_an_untracked_file_under_packages(tmp_path: Path) -> None:
    result = _gate_in(tmp_path, "packages/core/stray.py")
    assert result.returncode == 1
    assert "untracked files under packages/" in result.stderr
    assert "reached-uv" not in result.stdout


@RUNS_BASH
@pytest.mark.phase_3
def test_the_gate_ignores_an_untracked_file_elsewhere(tmp_path: Path) -> None:
    result = _gate_in(tmp_path, "notes.txt")
    assert "reached-uv" in result.stdout
    assert "untracked files under packages/" not in result.stderr
