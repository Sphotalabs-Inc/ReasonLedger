"""Phase 5 — the consent gate in front of every command that sends data to a model."""

from __future__ import annotations

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
    DecisionStatus,
)

CLOUD = ExtractorConfig(provider=ExtractorProvider.ANTHROPIC, model="claude-sonnet-5")
LOCAL = ExtractorConfig(
    provider=ExtractorProvider.LOCAL, base_url="http://localhost:11434", model="llama3.1"
)


def _seed(root: Path, config: ExtractorConfig) -> None:
    for decision_id in ("dec_one", "dec_two"):
        record = DecisionRecord(
            frontmatter=DecisionFrontmatter(
                id=decision_id,
                ai_tool=AiTool.NONE,
                oversight=DecisionOversight.REVIEWED,
                status=DecisionStatus.ACTIVE,
                context="Timestamp storage timezone policy",
                choice=decision_id,
            ),
            body="",
        )
        write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)
    write_extractor_config(root, config)


@pytest.mark.phase_5
def test_judge_refuses_to_send_to_a_cloud_model_until_allowed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path, CLOUD)

    assert main(["judge", "--root", str(tmp_path)]) == EXIT_USAGE

    captured = capsys.readouterr()
    assert "decision_text" in captured.err and "api.anthropic.com" in captured.err
    assert "reasonledger consent grant decision_text" in captured.err


@pytest.mark.phase_5
def test_a_model_on_this_machine_passes_the_gate_without_consent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path, LOCAL)

    main(["judge", "--root", str(tmp_path)])  # fails later (no server); the gate let it through

    assert "no consent" not in capsys.readouterr().err


@pytest.mark.phase_5
def test_consent_status_grant_and_revoke_round_trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path, CLOUD)
    root = str(tmp_path)

    assert main(["consent", "--root", root]) == EXIT_PASS
    assert "not allowed" in capsys.readouterr().out

    assert main(["consent", "grant", "paths", "--root", root]) == EXIT_PASS
    assert main(["consent", "--root", root]) == EXIT_PASS
    status = capsys.readouterr().out
    assert "paths" in status and "allowed " in status

    assert main(["consent", "revoke", "--root", root]) == EXIT_PASS
    assert main(["consent", "grant", "nonsense", "--root", root]) == EXIT_USAGE


@pytest.mark.phase_5
def test_consent_says_so_when_the_model_is_local_or_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["consent", "--root", str(tmp_path)]) == EXIT_PASS
    assert "nothing is sent" in capsys.readouterr().out
    write_extractor_config(tmp_path, LOCAL)
    assert main(["consent", "--root", str(tmp_path)]) == EXIT_PASS
    assert "no consent is needed" in capsys.readouterr().out
    assert main(["consent", "grant", "paths", "--root", str(tmp_path)]) == EXIT_USAGE


@pytest.mark.phase_5
def test_map_with_allow_cloud_still_works_for_one_run_without_a_grant(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed(tmp_path, CLOUD)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "a.py").write_text("x = 1\n", encoding="utf-8")

    assert main(["map", "--root", str(tmp_path), "--dry-run"]) == EXIT_USAGE
    assert "--allow-cloud" in capsys.readouterr().err
    assert main(["map", "--root", str(tmp_path), "--allow-cloud", "--dry-run"]) == EXIT_PASS


@pytest.mark.phase_5
def test_map_scan_needs_no_model_and_no_consent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for folder in ("orders", "payments"):
        for index in range(4):
            path = tmp_path / "app" / folder / f"f{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x = 1\n", encoding="utf-8")

    assert main(["map", "--scan", "--root", str(tmp_path)]) == EXIT_PASS

    out = capsys.readouterr().out
    assert "No model was used; nothing was sent" in out
    assert (tmp_path / ".reasonledger" / "modules.yml").is_file()


@pytest.mark.phase_5
def test_preview_shows_what_repo_text_sends_and_what_it_holds_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_extractor_config(tmp_path, CLOUD)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "queue.md").write_text("We chose Postgres for jobs.", encoding="utf-8")
    (tmp_path / "docs" / "owners.md").write_text("Ask lead@example.com.", encoding="utf-8")

    assert main(["consent", "--root", str(tmp_path), "--preview", "repo_text"]) == EXIT_PASS

    out = capsys.readouterr().out
    assert "up to 1 document(s) and 0 commit message(s) to https://api.anthropic.com" in out
    assert "docs/owners.md: email" in out
    assert "exactly as sent for docs/queue.md:" in out
    assert "  | Document path: docs/queue.md" in out
    assert "  | We chose Postgres for jobs." in out
    assert "lead@example.com" not in out
