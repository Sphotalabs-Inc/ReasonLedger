"""Phase 2 CI gate integration — sandbox PR workflow scenarios."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SANDBOX = REPO_ROOT / "fixtures" / "sandbox" / "pr-workflows"
ACTION = REPO_ROOT / ".github" / "actions" / "reasonledger-check" / "action.yml"
WORKFLOW = SANDBOX / "example-workflow.yml"


def _run_check(change_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "reasonledger_cli",
            "check",
            "--policy",
            str(SANDBOX / "policy.yml"),
            "--change",
            str(SANDBOX / change_name),
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.phase_2
def test_action_and_workflow_yaml_are_valid() -> None:
    action = yaml.safe_load(ACTION.read_text("utf-8"))
    workflow = yaml.safe_load(WORKFLOW.read_text("utf-8"))
    assert action["name"] == "ReasonLedger Check"
    assert "reasonledger check" in ACTION.read_text("utf-8")
    assert "pull_request" in workflow["on"]
    assert "reasonledger-check" in workflow["jobs"]


@pytest.mark.phase_2
def test_sandbox_pr_violating_blocks_merge() -> None:
    result = _run_check("pr-violating.json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["overall"] == "fail"


@pytest.mark.phase_2
def test_sandbox_pr_compliant_passes() -> None:
    result = _run_check("pr-compliant.json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["overall"] == "pass"


@pytest.mark.phase_2
def test_sandbox_pr_warn_annotates_without_blocking() -> None:
    result = _run_check("pr-warn.json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["overall"] == "warn"
    warn_rules = [r for r in payload["rules"] if r["result"] == "warn"]
    assert warn_rules
