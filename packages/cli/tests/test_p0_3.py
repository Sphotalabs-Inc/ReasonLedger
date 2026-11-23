"""P0-3 — `reasonledger init` onboarding and `rl why` hero path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_cli.init_cmd import POLICY_STUB, scaffold_repo
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.decisions import record_decision_to_path
from reasonledger_core.models.decision import AiTool, DecisionOversight, RecordDecisionInput

REASONLEDGER_ROOT = Path(__file__).resolve().parents[3]


def _seed(root: Path) -> None:
    record_decision_to_path(
        RecordDecisionInput(
            context="Retry policy",
            choice="Exponential backoff",
            ai_tool=AiTool.CURSOR,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            justifies=["payments/retry.py:40-72"],
            decision_id="dec_why001",
        ),
        root=root,
    )


@pytest.mark.phase_3
def test_cli_init_scaffold(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "init",
            "--policy",
            "--root",
            str(tmp_path),
            "--reasonledger-root",
            str(REASONLEDGER_ROOT),
        ]
    )
    assert code == EXIT_PASS
    out = capsys.readouterr().out
    assert (tmp_path / ".reasonledger" / "decisions" / ".gitkeep").is_file()
    assert (tmp_path / ".reasonledger" / "policy.yml").read_text("utf-8") == POLICY_STUB
    assert "Decision records" in out
    assert (tmp_path / ".mcp.json").is_file() and "Restart" in out

    policy_path = tmp_path / ".reasonledger" / "policy.yml"
    policy_path.write_text('version: "1"\ncustomized: true\n', encoding="utf-8")

    code = main(
        [
            "init",
            "--root",
            str(tmp_path),
            "--reasonledger-root",
            str(REASONLEDGER_ROOT),
        ]
    )
    assert code == EXIT_PASS
    assert policy_path.read_text("utf-8") == 'version: "1"\ncustomized: true\n'

    _seed(tmp_path)
    decision_path = tmp_path / ".reasonledger" / "decisions" / "dec_why001.md"
    assert decision_path.is_file()
    decision_path.write_text(
        decision_path.read_text("utf-8") + "\n<!-- preserved -->\n",
        encoding="utf-8",
    )

    code = main(
        [
            "init",
            "--root",
            str(tmp_path),
            "--reasonledger-root",
            str(REASONLEDGER_ROOT),
        ]
    )
    assert code == EXIT_PASS
    assert "<!-- preserved -->" in decision_path.read_text("utf-8")


@pytest.mark.phase_3
def test_cli_init_scaffold_unit(tmp_path: Path) -> None:
    actions = scaffold_repo(root=tmp_path, policy=True)
    assert actions
    assert (tmp_path / ".reasonledger" / "policy.yml").is_file()
    assert scaffold_repo(root=tmp_path, policy=True) == []


@pytest.mark.phase_3
def test_cli_why_hit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path)

    code = main(["why", "payments/retry.py:55", "--root", str(tmp_path)])
    assert code == EXIT_PASS
    text = capsys.readouterr().out
    assert "dec_why001" in text
    assert "Exponential backoff" in text
    assert "reviewed" in text

    code = main(["why", "payments/retry.py:55", "--root", str(tmp_path), "--json"])
    assert code == EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    decision = payload["decisions"][0]
    assert decision["id"] == "dec_why001"
    assert decision["choice"] == "Exponential backoff"
    assert decision["oversight"] == "reviewed"


@pytest.mark.phase_3
def test_cli_why_miss(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed(tmp_path)
    (tmp_path / "unrelated").mkdir()
    (tmp_path / "unrelated" / "file.py").write_text("x = 1\n", encoding="utf-8")
    code = main(["why", "unrelated/file.py:1", "--root", str(tmp_path)])
    assert code == EXIT_PASS
    assert "No decision names this file" in capsys.readouterr().out
