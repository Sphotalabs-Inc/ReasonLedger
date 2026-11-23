"""The sync watermark: where the ledger last caught up to.

Without this there is no way to answer "what was decided while I wasn't using
ReasonLedger" — every import is a full re-scan with no notion of *since when*,
so genuinely new decisions arrive indistinguishable from ones already reviewed.

The watermark records only what is needed to compute a delta. It is committable
and holds no secret, mirroring ``config.yml``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

STATE_PATH = Path(".reasonledger/state.yml")


class SyncState(BaseModel):
    """Where the last completed catch-up left off."""

    last_synced_commit: str | None = None
    last_synced_at: datetime | None = None


class SyncStateError(ValueError):
    """Raised when the sync state file is malformed."""


def load_sync_state(root: Path, *, state_path: Path | None = None) -> SyncState:
    """Load the watermark. A repo that has never synced returns an empty state."""
    path = root / (state_path or STATE_PATH)
    if not path.is_file():
        return SyncState()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SyncStateError(f"invalid state YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise SyncStateError("state.yml must be a mapping")
    section = data.get("sync", {})
    if not isinstance(section, dict):
        raise SyncStateError("state.yml 'sync' must be a mapping")
    try:
        return SyncState.model_validate(section)
    except ValueError as exc:
        raise SyncStateError(f"invalid sync state: {exc}") from exc


def write_sync_state(root: Path, state: SyncState, *, state_path: Path | None = None) -> Path:
    """Persist the watermark. Only ever called after a scan actually completed."""
    path = root / (state_path or STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sync": state.model_dump(mode="json", exclude_none=True)}
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path
