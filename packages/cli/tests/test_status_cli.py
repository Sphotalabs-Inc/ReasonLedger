"""S13: `reasonledger status` and `reject` CLI."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, EXIT_USAGE, main
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.extractor import DecisionCandidate
from reasonledger_core.importer.propose import PROPOSED_DIR, confirm_proposed, propose_decisions
from reasonledger_core.views import LedgerView

EXTRACTED_AT = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)


def _stage(root: Path, ref: str, context: str, choice: str) -> str:
    result = propose_decisions(
        [DecisionCandidate(context=context, choice=choice, source_ref=ref)],
        root=root,
        extracted_by="test/extractor",
        extracted_at=EXTRACTED_AT,
    )
    return result.proposed_ids[0]


@pytest.mark.phase_3
def test_cli_status_human_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proposal_id = _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    confirmed_id = _stage(tmp_path, "docs/b.md#queue", "Queue technology selection", "sqs")
    confirm_proposed(confirmed_id, root=tmp_path, confirmed_by="alice", confirmed_at=EXTRACTED_AT)

    code = main(["status", "--root", str(tmp_path)])
    assert code == EXIT_PASS
    out = capsys.readouterr().out
    assert "proposed: 1" in out
    assert "confirmed: 1" in out
    assert proposal_id in out
    assert "hint:" in out


@pytest.mark.phase_3
def test_cli_status_json_round_trips_and_is_deterministic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    _stage(tmp_path, "docs/b.md#pagination", "API pagination style", "cursor pagination")

    assert main(["status", "--root", str(tmp_path), "--json"]) == EXIT_PASS
    first = LedgerView.model_validate_json(capsys.readouterr().out)
    assert main(["status", "--root", str(tmp_path), "--json"]) == EXIT_PASS
    second = LedgerView.model_validate_json(capsys.readouterr().out)

    first_ids = [p.id for p in first.proposals]
    assert first_ids == sorted(first_ids)
    assert first_ids == [p.id for p in second.proposals]
    assert first.counts == second.counts


@pytest.mark.phase_3
def test_cli_status_rejects_bad_watch_values(tmp_path: Path) -> None:
    bad = tmp_path / "values.json"
    bad.write_text('{"queue_depth": "many"}', encoding="utf-8")
    assert main(["status", "--root", str(tmp_path), "--watch-values", str(bad)]) == EXIT_USAGE


@pytest.mark.phase_3
def test_cli_reject_deletes_only_proposal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    proposal_id = _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")

    assert main(["reject", proposal_id, "--root", str(tmp_path)]) == EXIT_PASS
    assert "rejected" in capsys.readouterr().out
    assert list((tmp_path / PROPOSED_DIR).glob("dec_*.md")) == []
    assert not (tmp_path / DECISIONS_DIR).exists()

    # Unknown id and malformed id are usage errors.
    assert main(["reject", "dec_missing1", "--root", str(tmp_path)]) == EXIT_USAGE
    assert main(["reject", "../evil", "--root", str(tmp_path)]) == EXIT_USAGE


@pytest.mark.phase_4
def test_cli_status_warns_when_embedder_falls_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from reasonledger_core.reasoning.conflict_config import ConflictConfig, write_conflict_config

    _stage(tmp_path, "docs/a.md#tz", "Timestamp storage timezone policy", "UTC")
    _stage(tmp_path, "docs/b.md#tz", "Timestamp storage timezone policy", "server-local")
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))

    def _missing(**_: object) -> object:
        raise ImportError("No module named 'fastembed'")

    monkeypatch.setattr("reasonledger_core.reasoning.conflict_config.get_embedder", _missing)
    assert main(["status", "--root", str(tmp_path)]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "warning: related-decision hints use basic word matching" in out
    assert "--extra embeddings" in out
    assert "related: 1" in out
