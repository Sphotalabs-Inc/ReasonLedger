"""P0-4 S10/S11: `reasonledger config`, `import`, and `confirm` CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.config import ExtractorProvider, load_extractor_config
from reasonledger_core.importer.propose import PROPOSED_DIR

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "import"
CONFLICT_FIXTURE = FIXTURES / "extractor_replay_conflict.json"


def _seed_conflicting_docs(root: Path) -> None:
    (root / "claude.md").write_text("timestamps are UTC", encoding="utf-8")
    docs = root / "backend" / "docs"
    docs.mkdir(parents=True)
    (docs / "date-semantics.md").write_text("timestamps are server-local", encoding="utf-8")


def _import_fixture(root: Path) -> None:
    _seed_conflicting_docs(root)
    main(
        [
            "import",
            "--root",
            str(root),
            "--extracted-by",
            "replay/fixture",
            "--fixture",
            str(CONFLICT_FIXTURE),
        ]
    )


@pytest.mark.phase_3
def test_cli_config_writes_no_secret(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "config",
            "--provider",
            "anthropic",
            "--model",
            "claude-sonnet-5",
            "--api-key-env",
            "ANTHROPIC_API_KEY",
            "--root",
            str(tmp_path),
        ]
    )
    assert code == EXIT_PASS
    out = capsys.readouterr().out
    assert "wrote" in out

    config_path = tmp_path / ".reasonledger" / "config.yml"
    text = config_path.read_text("utf-8")
    assert "ANTHROPIC_API_KEY" in text
    assert "sk-" not in text

    loaded = load_extractor_config(tmp_path)
    assert loaded.provider is ExtractorProvider.ANTHROPIC
    assert loaded.model == "claude-sonnet-5"
    assert loaded.api_key_env == "ANTHROPIC_API_KEY"


@pytest.mark.phase_3
def test_cli_import_fixture_reports_conflict(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _import_fixture(tmp_path)

    out = capsys.readouterr().out
    # Fresh proposals have no verdicts yet: the pair is reported as related and
    # unjudged, with the command that would judge it.
    assert "related decisions: 1 — 1 not judged yet" in out
    assert "reasonledger judge" in out
    assert "proposals:" in out
    assert "created: 2" in out
    assert str(PROPOSED_DIR) in out
    assert "confirm" in out.lower()

    assert len(list((tmp_path / PROPOSED_DIR).glob("dec_*.md"))) == 2
    assert not (tmp_path / DECISIONS_DIR).exists()


@pytest.mark.phase_3
def test_cli_confirm_all_promotes_into_ledger(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _import_fixture(tmp_path)
    capsys.readouterr()  # drop import output

    code = main(["confirm", "--root", str(tmp_path), "--confirmed-by", "alice", "--all"])
    assert code == EXIT_PASS
    assert "confirmed 2" in capsys.readouterr().out

    ledger = load_decisions_from_dir(tmp_path / DECISIONS_DIR)
    assert len(ledger) == 2
    assert all(r.frontmatter.status.value == "confirmed" for r in ledger)
    assert all(r.frontmatter.confirmed_by == "alice" for r in ledger)
    # Proposals cleared from staging once promoted.
    assert len(list((tmp_path / PROPOSED_DIR).glob("dec_*.md"))) == 0


@pytest.mark.phase_3
def test_cli_confirm_unknown_id_is_usage_error(tmp_path: Path) -> None:
    code = main(["confirm", "dec_missing", "--root", str(tmp_path), "--confirmed-by", "alice"])
    assert code == 2
