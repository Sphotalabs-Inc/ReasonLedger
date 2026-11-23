"""Repo-wide test setup: no test may read or write the developer's real consent file,
and a test that acts as a person says which git identity it acts as."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_consent_dir(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    directory = tmp_path_factory.mktemp("consent")
    monkeypatch.setenv("RL_CONSENT_DIR", str(directory))
    return directory


TEST_REVIEWER = "Test Reviewer"


@pytest.fixture
def git_identity(monkeypatch: pytest.MonkeyPatch) -> str:
    """Give git a ``user.name`` whatever the machine's own config says; returns the name."""
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.name")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", TEST_REVIEWER)
    return TEST_REVIEWER


@pytest.fixture
def no_git_identity(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hide every ``user.name``: no env override, and a home with no git config in it.

    An empty HOME rather than GIT_CONFIG_GLOBAL, which older gits ignore.
    """
    home = tmp_path_factory.mktemp("home")
    monkeypatch.delenv("GIT_CONFIG_COUNT", raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
