"""Phase 4 — `reasonledger judge`: configuration errors, dry run, and a judged run."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, EXIT_USAGE, main
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.importer.config import (
    ExtractorConfig,
    ExtractorProvider,
    write_extractor_config,
)
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.reasoning.dismissals import add_dismissal
from reasonledger_core.reasoning.judge import ModelJudge, build_model_judge
from reasonledger_core.reasoning.verdicts import VERDICTS_PATH, load_verdicts
from reasonledger_core.views import build_ledger_view

CONFLICT = {
    "same_question": True,
    "compatible": False,
    "question": "Which timezone are timestamps stored in?",
    "reason": "One stores UTC, the other server-local time.",
    "severity": "high",
}


def _seed(root: Path) -> None:
    for decision_id, choice in (("dec_utc", "UTC"), ("dec_local", "server-local")):
        record = DecisionRecord(
            frontmatter=DecisionFrontmatter(
                id=decision_id,
                ai_tool=AiTool.NONE,
                oversight=DecisionOversight.REVIEWED,
                context="Timestamp storage timezone policy",
                choice=choice,
            ),
            body="",
        )
        write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


def _configure(root: Path) -> None:
    write_extractor_config(
        root,
        ExtractorConfig(
            provider=ExtractorProvider.OPENAI_COMPATIBLE,
            base_url="https://judge.test/v1",
            model="m",
        ),
    )


@pytest.mark.phase_4
def test_judge_without_a_model_says_how_to_configure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    assert main(["judge", "--root", str(tmp_path)]) == EXIT_USAGE
    assert "reasonledger config" in capsys.readouterr().err


@pytest.mark.phase_4
def test_dry_run_lists_pending_without_a_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    assert main(["judge", "--root", str(tmp_path), "--dry-run"]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "pending: 1" in out
    assert "dec_local <-> dec_utc" in out
    assert not (tmp_path / VERDICTS_PATH).exists()


@pytest.mark.phase_4
def test_dry_run_leaves_out_pairs_a_person_already_dismissed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    add_dismissal(tmp_path, decision_a="dec_local", decision_b="dec_utc", reason="different apps")
    assert main(["judge", "--root", str(tmp_path), "--dry-run"]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "shortlisted: 1  judged: 0  dismissed: 1  pending: 0" in out
    assert "dec_local <-> dec_utc" not in out


@pytest.mark.phase_4
def test_judged_conflict_reaches_status_and_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path)
    _configure(tmp_path)

    def post(
        url: str, payload: dict[str, object], headers: Mapping[str, str], timeout: float
    ) -> dict[str, object]:
        return {"choices": [{"message": {"content": json.dumps(CONFLICT)}}]}

    def fake_build(config: ExtractorConfig, *, model: str | None = None) -> ModelJudge:
        return build_model_judge(config, model=model, http_post=post)

    monkeypatch.setattr("reasonledger_cli.judge_cmd.build_model_judge", fake_build)
    # The configured model is off this machine, so nothing is sent until it is allowed.
    assert main(["judge", "--root", str(tmp_path)]) == EXIT_USAGE
    assert main(["consent", "grant", "decision_text", "--root", str(tmp_path)]) == EXIT_PASS
    capsys.readouterr()
    assert main(["judge", "--root", str(tmp_path)]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "dec_local <-> dec_utc: conflict" in out
    assert f"commit {VERDICTS_PATH}" in out
    assert len(load_verdicts(tmp_path)) == 1

    view = build_ledger_view(tmp_path)
    assert view.counts["conflicts"] == 1
    assert main(["check", "--decisions", "--root", str(tmp_path)]) == 1

    # Nothing left to judge on a second run.
    assert main(["judge", "--root", str(tmp_path), "--dry-run"]) == EXIT_PASS
    assert "pending: 0" in capsys.readouterr().out


@pytest.mark.phase_4
def test_limit_must_be_positive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["judge", "--root", str(tmp_path), "--limit", "0"]) == EXIT_USAGE
    assert "--limit" in capsys.readouterr().err


@pytest.mark.phase_4
def test_pair_narrows_a_dry_run_to_those_two_decisions_in_either_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    args = ["judge", "--root", str(tmp_path), "--dry-run", "--pair", "dec_utc", "dec_local"]
    assert main(args) == EXIT_PASS
    out = capsys.readouterr().out
    assert "dec_local <-> dec_utc" in out


@pytest.mark.phase_4
def test_pair_that_is_not_waiting_is_refused_with_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    assert main(["judge", "--root", str(tmp_path), "--pair", "dec_utc", "dec_nope"]) == EXIT_USAGE
    assert "not waiting for a verdict" in capsys.readouterr().err


@pytest.mark.phase_4
def test_pair_cannot_be_combined_with_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path)
    args = ["judge", "--root", str(tmp_path), "--pair", "dec_utc", "dec_local", "--limit", "2"]
    assert main(args) == EXIT_USAGE
    assert "--pair" in capsys.readouterr().err
