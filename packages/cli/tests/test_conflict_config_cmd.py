"""`reasonledger conflict-config` — per-repo conflict-detection tuning."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, main
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.reasoning.conflict_config import CONFLICT_CONFIG_PATH
from verdict_helpers import commit_verdict

_LOCAL_AVAILABLE = "reasonledger_core.reasoning.conflict_config.local_embedder_available"


@pytest.mark.phase_4
def test_show_prints_defaults_with_no_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["conflict-config", "--root", str(tmp_path), "--show"])
    assert code == EXIT_PASS
    out = capsys.readouterr().out
    assert "context_similarity_gate: (unset — per embedder)" in out
    assert "shortlist_k: 5" in out
    assert "judge_model: (unset" in out
    assert "RL_EMBEDDING_PROVIDER" in out
    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()


@pytest.mark.phase_4
def test_single_flag_write_preserves_other_fields(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_LOCAL_AVAILABLE, lambda: True)
    root = str(tmp_path)
    assert main(["conflict-config", "--root", root, "--context-similarity-gate", "0.4"]) == (
        EXIT_PASS
    )
    capsys.readouterr()

    assert main(["conflict-config", "--root", root, "--embedding-provider", "local"]) == EXIT_PASS
    capsys.readouterr()

    code = main(["conflict-config", "--root", root, "--show"])
    assert code == EXIT_PASS
    out = capsys.readouterr().out
    assert "context_similarity_gate: 0.4" in out
    assert "embedding_provider: local" in out


@pytest.mark.phase_4
def test_out_of_range_gate_rejected(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["conflict-config", "--root", str(tmp_path), "--context-similarity-gate", "1.5"])
    assert code == EXIT_USAGE
    assert "error" in capsys.readouterr().err.lower()
    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()


@pytest.mark.phase_4
def test_bad_embedding_provider_rejected_by_argparse(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["conflict-config", "--root", str(tmp_path), "--embedding-provider", "bogus"])
    assert exc.value.code == EXIT_USAGE


@pytest.mark.phase_4
def test_no_flags_is_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["conflict-config", "--root", str(tmp_path)])
    assert code == EXIT_USAGE
    assert "nothing to set" in capsys.readouterr().err


@pytest.mark.phase_4
def test_show_surfaces_malformed_file_instead_of_hiding_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--show` is the diagnostic entry point for a broken override — it must not
    quietly report defaults while status/ui silently do the same underneath it."""
    path = tmp_path / CONFLICT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("context_similarity_gate: [not, a, float]\n", encoding="utf-8")

    code = main(["conflict-config", "--root", str(tmp_path), "--show"])
    assert code == EXIT_USAGE
    assert "error" in capsys.readouterr().err.lower()


@pytest.mark.phase_4
def test_write_over_malformed_file_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / CONFLICT_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("shortlist_k: not-a-number\n", encoding="utf-8")
    before = path.read_text("utf-8")

    code = main(["conflict-config", "--root", str(tmp_path), "--context-similarity-gate", "0.5"])
    assert code == EXIT_USAGE
    assert path.read_text("utf-8") == before


def _write_confirmed(root: Path, decision_id: str, *, context: str, choice: str) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            status=DecisionStatus.CONFIRMED,
            context=context,
            choice=choice,
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


@pytest.mark.phase_4
def test_widened_gate_suppresses_conflict_in_the_ci_gate(tmp_path: Path) -> None:
    """`reasonledger check --decisions` must respect a per-repo conflict.yml too —
    not just `status`/`ui`: a pair the floor drops from the shortlist cannot fail
    the gate, even with a committed conflict verdict."""
    root = str(tmp_path)
    # DeterministicEmbedder rates this pair's context similarity at ~0.8 — chosen so
    # a real, in-range gate (0.9) can flip the verdict, unlike a pair with identical
    # context text (similarity pinned at exactly 1.0, which no gate <= 1.0 excludes).
    _write_confirmed(
        tmp_path,
        "dec_retry_pay",
        context="Retry policy for flaky network calls to the payments API",
        choice="Exponential backoff with jitter",
    )
    _write_confirmed(
        tmp_path,
        "dec_retry_bill",
        context="Retry strategy for flaky network calls to the billing API",
        choice="Fixed delay retry, three attempts",
    )

    commit_verdict(tmp_path, "dec_retry_pay", "dec_retry_bill")
    assert main(["check", "--decisions", "--root", root]) == EXIT_FAIL

    assert (
        main(["conflict-config", "--root", root, "--context-similarity-gate", "0.9"]) == EXIT_PASS
    )

    assert main(["check", "--decisions", "--root", root]) == EXIT_PASS


@pytest.mark.phase_4
def test_local_refused_when_extra_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_LOCAL_AVAILABLE, lambda: False)
    code = main(["conflict-config", "--root", str(tmp_path), "--embedding-provider", "local"])
    assert code == EXIT_USAGE
    assert "--extra embeddings" in capsys.readouterr().err
    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()


@pytest.mark.phase_4
def test_missing_root_is_a_usage_error_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "no-such-repo"
    code = main(["conflict-config", "--root", str(missing), "--context-similarity-gate", "0.4"])
    assert code == EXIT_USAGE
    assert "does not exist" in capsys.readouterr().err
    assert not missing.exists()


@pytest.mark.phase_4
def test_shortlist_k_and_judge_model_round_trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = str(tmp_path)
    assert (
        main(["conflict-config", "--root", root, "--shortlist-k", "8", "--judge-model", "m-1"])
        == EXIT_PASS
    )
    capsys.readouterr()
    assert main(["conflict-config", "--root", root, "--show"]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "shortlist_k: 8" in out
    assert "judge_model: m-1" in out


@pytest.mark.phase_4
def test_shortlist_k_out_of_range_rejected(tmp_path: Path) -> None:
    assert main(["conflict-config", "--root", str(tmp_path), "--shortlist-k", "0"]) == EXIT_USAGE
    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()
