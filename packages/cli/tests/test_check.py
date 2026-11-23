"""Phase 2 CLI check tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_FAIL, EXIT_PASS, main

SANDBOX = Path(__file__).resolve().parents[3] / "fixtures" / "sandbox" / "pr-workflows"


@pytest.mark.phase_2
def test_cli_check_fail_on_violating_pr(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "check",
            "--policy",
            str(SANDBOX / "policy.yml"),
            "--change",
            str(SANDBOX / "pr-violating.json"),
            "--json",
        ]
    )
    assert code == EXIT_FAIL
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall"] == "fail"


@pytest.mark.phase_2
def test_cli_check_pass_on_compliant_pr(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "check",
            "--policy",
            str(SANDBOX / "policy.yml"),
            "--change",
            str(SANDBOX / "pr-compliant.json"),
            "--json",
        ]
    )
    assert code == EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall"] == "pass"


@pytest.mark.phase_2
def test_cli_check_warn_does_not_block(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "check",
            "--policy",
            str(SANDBOX / "policy.yml"),
            "--change",
            str(SANDBOX / "pr-warn.json"),
            "--json",
        ]
    )
    assert code == EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall"] == "warn"


@pytest.mark.phase_2
def test_check_invalid_policy_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    policy = tmp_path / "policy.yml"
    policy.write_text("rules:\n  - id: r1\n    when:\n      ai_assisted: true\n", encoding="utf-8")
    change = tmp_path / "change.json"
    change.write_text("{}", encoding="utf-8")
    code = main(["check", "--policy", str(policy), "--change", str(change)])
    assert code == 2
    assert "ai_assisted" in capsys.readouterr().err
