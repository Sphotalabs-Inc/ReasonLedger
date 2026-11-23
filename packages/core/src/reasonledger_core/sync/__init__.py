"""Catch-up support: the sync watermark and the git delta behind it."""

from reasonledger_core.sync.repo import (
    changed_paths_since,
    commit_author_for_path,
    commit_exists,
    commit_messages_since,
    commits_since,
    decision_files_added_since,
    decision_files_changed_since,
    head_commit,
    is_git_repo,
    recent_commit_messages,
)
from reasonledger_core.sync.state import (
    STATE_PATH,
    SyncState,
    SyncStateError,
    load_sync_state,
    write_sync_state,
)

__all__ = [
    "STATE_PATH",
    "SyncState",
    "SyncStateError",
    "changed_paths_since",
    "commit_author_for_path",
    "commit_exists",
    "commit_messages_since",
    "commits_since",
    "decision_files_added_since",
    "decision_files_changed_since",
    "head_commit",
    "is_git_repo",
    "load_sync_state",
    "recent_commit_messages",
    "write_sync_state",
]
