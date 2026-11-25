"""CLI test setup: the machine's installed agents must not change what `init` does."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

LaunchAs = Callable[[Path, Path | None], None]


@pytest.fixture(autouse=True)
def _no_agent_cli_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend neither `claude` nor `cursor` is on PATH; a test that needs one re-patches this."""
    monkeypatch.setattr("reasonledger_cli.agent_targets.agent_cli_found", lambda _name: False)


@pytest.fixture
def launch_as(monkeypatch: pytest.MonkeyPatch) -> LaunchAs:
    """Pin how this process was started: the script that ran, and what PATH finds for the CLI.

    Both are real files, so the comparison `init` makes between them is the real one.
    """

    def pin(script: Path, on_path: Path | None) -> None:
        for path in (script, on_path):
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
        monkeypatch.setattr(sys, "argv", [str(script)])
        found = None if on_path is None else str(on_path)
        monkeypatch.setattr("shutil.which", lambda _name: found)

    return pin
