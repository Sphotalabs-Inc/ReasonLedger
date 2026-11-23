"""CLI test setup: the machine's installed agents must not change what `init` does."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_agent_cli_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend neither `claude` nor `cursor` is on PATH; a test that needs one re-patches this."""
    monkeypatch.setattr("reasonledger_cli.agent_targets.agent_cli_found", lambda _name: False)
