"""Sync watermark + git delta: the primitive behind `reasonledger catchup`."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.sync import (
    STATE_PATH,
    SyncState,
    SyncStateError,
    changed_paths_since,
    commit_messages_since,
    commits_since,
    head_commit,
    is_git_repo,
    load_sync_state,
    write_sync_state,
)

SYNCED_AT = datetime(2026, 7, 20, 9, 0, 0, tzinfo=UTC)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "claude.md").write_text("# Decisions\nUTC everywhere.\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "first")
    return tmp_path


@pytest.mark.phase_3
def test_missing_state_is_empty_not_an_error(tmp_path: Path) -> None:
    """A repo that never synced is the normal starting point, not a failure."""
    state = load_sync_state(tmp_path)
    assert state.last_synced_commit is None
    assert state.last_synced_at is None


@pytest.mark.phase_3
def test_state_round_trips(tmp_path: Path) -> None:
    written = write_sync_state(
        tmp_path, SyncState(last_synced_commit="a" * 40, last_synced_at=SYNCED_AT)
    )
    assert written == tmp_path / STATE_PATH
    reloaded = load_sync_state(tmp_path)
    assert reloaded.last_synced_commit == "a" * 40
    assert reloaded.last_synced_at == SYNCED_AT


@pytest.mark.phase_3
def test_malformed_state_raises_rather_than_silently_resetting(tmp_path: Path) -> None:
    """Treating a corrupt watermark as 'never synced' would silently re-scan everything."""
    path = tmp_path / STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("sync: [not, a, mapping]\n", encoding="utf-8")
    with pytest.raises(SyncStateError):
        load_sync_state(tmp_path)


@pytest.mark.phase_3
def test_git_helpers_degrade_outside_a_repo(tmp_path: Path) -> None:
    """No git, no crash — catch-up falls back to a full scan."""
    assert is_git_repo(tmp_path) is False
    assert head_commit(tmp_path) is None
    assert changed_paths_since(tmp_path, "a" * 40) is None
    assert commits_since(tmp_path, "a" * 40) is None


@pytest.mark.phase_3
def test_changed_paths_since_lists_committed_and_pending_work(repo: Path) -> None:
    base = head_commit(repo)
    assert base is not None

    (repo / "docs").mkdir()
    (repo / "docs" / "arch.md").write_text("# Arch\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "second")
    # Uncommitted: still a decision the ledger has not seen.
    (repo / "notes.md").write_text("# Notes\n", encoding="utf-8")

    changed = changed_paths_since(repo, base)
    assert changed is not None
    assert "docs/arch.md" in changed
    assert "notes.md" in changed
    assert "claude.md" not in changed
    assert commits_since(repo, base) == 1


@pytest.mark.phase_3
def test_unknown_commit_is_unknowable_not_empty(repo: Path) -> None:
    """A rebased-away watermark must not read as 'nothing changed'."""
    assert changed_paths_since(repo, "b" * 40) is None
    assert commits_since(repo, "b" * 40) is None


@pytest.mark.phase_3
def test_commit_messages_since_returns_shas_and_bodies(repo: Path) -> None:
    base = head_commit(repo)
    assert base is not None
    (repo / "cache.md").write_text("# Cache\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "Adopt Redis\n\nMemcached lacks the persistence we need.")

    commits = commit_messages_since(repo, base, limit=10)
    assert commits is not None
    assert len(commits) == 1
    sha, message = commits[0]
    assert len(sha) == 40
    assert message.startswith("Adopt Redis")
    assert "Memcached lacks the persistence" in message


@pytest.mark.phase_3
def test_commit_messages_since_respects_the_limit(repo: Path) -> None:
    """An unbounded gap would be a surprise model bill, so the window is capped."""
    base = head_commit(repo)
    assert base is not None
    for n in range(5):
        (repo / f"f{n}.md").write_text("x", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", f"change {n}\n\nbody {n}")

    commits = commit_messages_since(repo, base, limit=2)
    assert commits is not None
    assert len(commits) == 2
    # Newest first, so a capped window keeps the most recent work.
    assert commits[0][1].startswith("change 4")
