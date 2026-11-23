"""`reasonledger catchup` — the reconnect flow, end to end and offline."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_cli import catchup_cmd
from reasonledger_cli.main import EXIT_PASS, EXIT_USAGE, main
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.extractor import ReplayExtractor
from reasonledger_core.importer.propose import PROPOSED_DIR, confirm_proposed
from reasonledger_core.sync import STATE_PATH, load_sync_state
from reasonledger_core.views import build_ledger_view

CONFIRMED_AT = datetime(2026, 7, 20, 9, 0, 0, tzinfo=UTC)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _fixture(tmp_path: Path, candidates: dict[str, list[dict[str, object]]]) -> Path:
    path = tmp_path / "fx.json"
    path.write_text(json.dumps(candidates), encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    app = tmp_path / "app"
    (app / "docs").mkdir(parents=True)
    (app / "docs" / "arch.md").write_text("# Arch\nUTC everywhere.\n", encoding="utf-8")
    _git(app, "init", "-q")
    _git(app, "config", "user.email", "test@example.com")
    _git(app, "config", "user.name", "Test")
    _git(app, "add", "-A")
    _git(app, "commit", "-qm", "first")
    return app


@pytest.mark.phase_3
def test_catchup_records_a_watermark(repo: Path, tmp_path: Path) -> None:
    fixture = _fixture(
        tmp_path,
        {"docs/arch.md": [{"context": "Timestamps", "choice": "UTC", "source_ref": "a.md#ts"}]},
    )
    assert not (repo / STATE_PATH).exists()

    assert main(["catchup", "--root", str(repo), "--fixture", str(fixture)]) == EXIT_PASS

    state = load_sync_state(repo)
    assert state.last_synced_commit is not None
    assert state.last_synced_at is not None


@pytest.mark.phase_3
def test_second_catchup_scans_only_what_changed(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole point: after a gap, report what is new — not everything again."""
    fixture = _fixture(
        tmp_path,
        {
            "docs/arch.md": [
                {"context": "Timestamps", "choice": "UTC", "source_ref": "docs/arch.md#ts"}
            ],
            "docs/cache.md": [
                {"context": "Cache", "choice": "redis", "source_ref": "docs/cache.md#cache"}
            ],
        },
    )
    assert main(["catchup", "--root", str(repo), "--fixture", str(fixture)]) == EXIT_PASS
    capsys.readouterr()

    # A new doc lands during the "disconnected" stretch.
    (repo / "docs" / "cache.md").write_text("# Cache\nRedis.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "second")

    assert main(["catchup", "--root", str(repo), "--fixture", str(fixture)]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "1 changed document to scan" in out
    assert "new proposals: 1" in out


@pytest.mark.phase_3
def test_catchup_reports_a_supersede_after_the_gap(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The payoff: a doc rewritten while disconnected contradicts a confirmed decision."""
    before = _fixture(
        tmp_path,
        {"docs/arch.md": [{"context": "Ts", "choice": "UTC", "source_ref": "docs/arch.md#ts"}]},
    )
    assert main(["catchup", "--root", str(repo), "--fixture", str(before)]) == EXIT_PASS
    staged = next((repo / PROPOSED_DIR).glob("dec_*.md"))
    confirm_proposed(staged.stem, root=repo, confirmed_by="alice", confirmed_at=CONFIRMED_AT)
    capsys.readouterr()

    (repo / "docs" / "arch.md").write_text("# Arch\nServer-local.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "rewrote arch")
    after = _fixture(
        tmp_path,
        {
            "docs/arch.md": [
                {"context": "Ts", "choice": "server-local", "source_ref": "docs/arch.md#ts"}
            ]
        },
    )

    assert main(["catchup", "--root", str(repo), "--fixture", str(after)]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "superseded (source changed since confirmation)" in out
    assert "replaces" in out


@pytest.mark.phase_3
def test_catchup_reports_orphaned_loci(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file deleted during the gap leaves its decision pointing at nothing."""
    fixture = _fixture(
        tmp_path,
        {
            "docs/arch.md": [
                {
                    "context": "Retry",
                    "choice": "backoff",
                    "source_ref": "docs/arch.md#retry",
                    "justifies": ["payments/retry.py:40-72"],
                }
            ]
        },
    )
    assert main(["catchup", "--root", str(repo), "--fixture", str(fixture)]) == EXIT_PASS
    staged = next((repo / PROPOSED_DIR).glob("dec_*.md"))
    confirm_proposed(staged.stem, root=repo, confirmed_by="alice", confirmed_at=CONFIRMED_AT)
    capsys.readouterr()

    assert main(["catchup", "--root", str(repo), "--dry-run"]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "orphaned (justifies a file that no longer exists)" in out
    assert "payments/retry.py:40-72" in out

    # And it is gone once the file exists.
    (repo / "payments").mkdir()
    (repo / "payments" / "retry.py").write_text("# retry\n", encoding="utf-8")
    assert build_ledger_view(repo).orphaned == []


@pytest.mark.phase_3
def test_dry_run_spends_nothing_and_leaves_the_watermark(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--dry-run must work with no model configured, since that is when you reach for it."""
    assert main(["catchup", "--root", str(repo), "--dry-run"]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "dry run" in out
    assert not (repo / STATE_PATH).exists()
    assert not (repo / PROPOSED_DIR).exists()


@pytest.mark.phase_3
def test_catchup_states_its_own_scope(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Never imply the scan is exhaustive — undocumented decisions are unrecoverable."""
    assert main(["catchup", "--root", str(repo), "--dry-run"]) == EXIT_PASS
    assert "cannot be recovered by a scan" in capsys.readouterr().out


@pytest.mark.phase_3
def test_catchup_without_a_model_or_fixture_fails_cleanly(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["catchup", "--root", str(repo)]) == EXIT_USAGE
    assert "error:" in capsys.readouterr().err
    assert not (repo / DECISIONS_DIR).exists()


_EXPLAINED_COMMIT = (
    "Adopt Redis for the session cache\n\n"
    "Memcached was the incumbent but loses everything on restart, which stampedes "
    "the database on every deploy. Redis persists, and we already run it for queues."
)


@pytest.mark.phase_3
def test_catchup_mines_commit_messages_from_the_gap(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A decision that never reached a doc can still be recoverable from history."""
    empty = _fixture(tmp_path, {})
    assert main(["catchup", "--root", str(repo), "--fixture", str(empty)]) == EXIT_PASS
    capsys.readouterr()

    # Only the commit carries this decision — no document mentions Redis anywhere.
    (repo / "cache.py").write_text("# cache\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", _EXPLAINED_COMMIT)
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # ReplayExtractor is keyed by source path, so a hit here proves the commit was
    # handed to the extractor as `git:<sha>`.
    fixture = _fixture(
        tmp_path,
        {
            f"git:{sha[:12]}": [
                {
                    "context": "Session cache backend",
                    "choice": "Redis",
                    "source_ref": f"git:{sha[:12]}#session-cache",
                }
            ]
        },
    )
    assert main(["catchup", "--root", str(repo), "--fixture", str(fixture)]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "1 commit message explain a change" in out
    assert "new proposals: 1" in out

    staged = list((repo / PROPOSED_DIR).glob("dec_*.md"))
    assert len(staged) == 1
    assert "Redis" in staged[0].read_text("utf-8")


@pytest.mark.phase_3
def test_no_commits_flag_reads_documents_only(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = _fixture(tmp_path, {})
    assert main(["catchup", "--root", str(repo), "--fixture", str(empty)]) == EXIT_PASS
    capsys.readouterr()

    (repo / "cache.py").write_text("# cache\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", _EXPLAINED_COMMIT)

    assert (
        main(["catchup", "--root", str(repo), "--fixture", str(empty), "--no-commits"]) == EXIT_PASS
    )
    assert "commit message" not in capsys.readouterr().out


@pytest.mark.phase_3
def test_first_catchup_does_not_mine_all_of_history(
    repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no watermark there is no gap, just everything — that needs asking for."""
    _git(repo, "commit", "-q", "--allow-empty", "-m", _EXPLAINED_COMMIT)
    empty = _fixture(tmp_path, {})

    assert main(["catchup", "--root", str(repo), "--fixture", str(empty)]) == EXIT_PASS
    assert "commit message" not in capsys.readouterr().out


@pytest.mark.phase_5
def test_a_held_source_keeps_the_watermark_so_the_next_run_reads_it_again(
    repo: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(tmp_path, {})
    assert main(["catchup", "--root", str(repo), "--fixture", str(fixture)]) == EXIT_PASS
    before = load_sync_state(repo).last_synced_commit
    (repo / "docs" / "owners.md").write_text("Ask lead@example.com first.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "owners")
    capsys.readouterr()
    # Stands in for a configured model off this machine, which is what turns screening on.
    monkeypatch.setattr(
        catchup_cmd, "_build_extractor", lambda root, fixture: (ReplayExtractor({}), True)
    )

    assert main(["catchup", "--root", str(repo)]) == EXIT_PASS

    out = capsys.readouterr().out
    assert "held back, not sent (1)" in out and "docs/owners.md: email" in out
    assert "watermark unchanged" in out
    assert load_sync_state(repo).last_synced_commit == before
