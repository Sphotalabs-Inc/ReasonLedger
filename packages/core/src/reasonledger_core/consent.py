"""Consent to send repo data to a model that is not on this machine.

Nothing leaves the machine until a person says so, per repo, per kind of data, and for the
destination they saw. A model on this machine (a loopback address) needs no consent. The
record lives in the user's own config directory, never in the repo and never committed, so a
clone or a CI run starts with nothing granted and fails closed.

Three kinds of data can be sent, and each is its own grant:

* ``decision_text``: each decision's context and choice (``judge``).
* ``paths``: file paths and route paths, never file contents (``map``).
* ``repo_text``: text of your docs and your commit messages, subject and body (``import``,
  ``catchup``). Before it is sent, a doc or commit that matches the PII/secret patterns is held
  back whole and reported (``importer.outgoing``).

A grant is bound to the destination origin (scheme, host and port) it was given for. Point the
repo at a different provider, or the same host over another scheme or port, and it asks again;
so does a new kind of data. Grants recorded before origins were used named a bare host, match
no origin, and so are asked for again.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.endpoint import is_loopback, origin
from reasonledger_core.importer.llm import ANTHROPIC_DEFAULT_BASE_URL

CONSENT_DIR_ENV = "RL_CONSENT_DIR"
CONSENT_FILE = "consent.yml"
CONSENT_VERSION = "1"


class DataClass(StrEnum):
    DECISION_TEXT = "decision_text"
    PATHS = "paths"
    REPO_TEXT = "repo_text"


LABELS: dict[DataClass, str] = {
    DataClass.DECISION_TEXT: "Decision text",
    DataClass.PATHS: "File and route paths",
    DataClass.REPO_TEXT: "Docs and commit messages",
}

DESCRIPTIONS: dict[DataClass, str] = {
    DataClass.DECISION_TEXT: (
        "the context and choice of your recorded decisions, to judge which related ones conflict"
    ),
    DataClass.PATHS: (
        "file paths and HTTP route paths, to propose your module map; never file contents"
    ),
    DataClass.REPO_TEXT: (
        "the text of your docs and of your commit messages (subject and body), to extract "
        "decisions from them; a doc or commit matching the PII/secret check is held back; "
        "never diffs or author names"
    ),
}


class ConsentError(ValueError):
    """Raised for a request that cannot be a grant (an unknown class, a local model)."""


def parse_classes(names: list[str]) -> list[DataClass]:
    """Class names as typed on the command line or sent by the UI."""
    parsed: list[DataClass] = []
    for name in names:
        try:
            parsed.append(DataClass(name))
        except ValueError as exc:
            valid = ", ".join(item.value for item in DataClass)
            raise ConsentError(f"unknown data class {name!r} (choose from {valid})") from exc
    return parsed


def destination(config: ExtractorConfig) -> str | None:
    """The origin a prompt goes to, or ``None`` when it never leaves this machine.

    A disabled provider sends nothing. Anthropic is always off the machine; any other
    provider is local only when its base URL is a loopback address.
    """
    if config.provider is ExtractorProvider.DISABLED:
        return None
    if config.provider is ExtractorProvider.ANTHROPIC:
        return origin(config.base_url or ANTHROPIC_DEFAULT_BASE_URL)
    if is_loopback(config.base_url):
        return None
    return origin(config.base_url) if config.base_url else "(no base_url set)"


def consent_dir() -> Path:
    """User-scope config directory: outside every repo, so it can never be committed."""
    override = os.environ.get(CONSENT_DIR_ENV)
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "reasonledger"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "reasonledger"


def repo_key(root: Path) -> str:
    """The repo's first commit hash (stable across clones), else its resolved path."""
    resolved = root.resolve()
    try:
        out = subprocess.run(  # noqa: S603
            ["git", "-C", str(resolved), "rev-list", "--max-parents=0", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return str(resolved)
    first = out.stdout.split()
    return first[0] if out.returncode == 0 and first else str(resolved)


def _load() -> dict[str, Any]:
    path = consent_dir() / CONSENT_FILE
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}  # unreadable means nothing is granted: fail closed
    repos = raw.get("repos") if isinstance(raw, dict) else None
    return {"repos": repos} if isinstance(repos, dict) else {}


def _save(repos: dict[str, Any]) -> None:
    directory = consent_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CONSENT_FILE
    payload = {"version": CONSENT_VERSION, "repos": repos}
    path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    with contextlib.suppress(OSError):  # best effort on filesystems without POSIX modes
        path.chmod(0o600)


def granted_classes(root: Path, config: ExtractorConfig) -> set[DataClass]:
    """Classes granted for this repo to the destination the config points at now."""
    host = destination(config)
    if host is None:
        return set()
    entry = _load().get("repos", {}).get(repo_key(root), {})
    granted = entry.get("granted", {}) if isinstance(entry, dict) else {}
    found: set[DataClass] = set()
    for name, record in granted.items() if isinstance(granted, dict) else []:
        if isinstance(record, dict) and record.get("destination") == host:
            try:
                found.add(DataClass(name))
            except ValueError:
                continue
    return found


def missing_classes(
    root: Path, config: ExtractorConfig, classes: list[DataClass]
) -> list[DataClass]:
    """Classes this call needs that nobody has allowed yet. Empty for a model on this machine."""
    if destination(config) is None:
        return []
    have = granted_classes(root, config)
    return [item for item in classes if item not in have]


def grant(
    root: Path,
    config: ExtractorConfig,
    classes: list[DataClass],
    *,
    now: datetime | None = None,
) -> None:
    """Record that these classes may go to the configured destination for this repo."""
    host = destination(config)
    if host is None:
        raise ConsentError("the configured model runs on this machine; nothing to allow")
    repos = _load().get("repos", {})
    entry = repos.setdefault(repo_key(root), {})
    entry["path"] = str(root.resolve())
    granted = entry.setdefault("granted", {})
    stamp = (now or datetime.now(UTC)).isoformat()
    for item in classes:
        granted[item.value] = {"destination": host, "granted_at": stamp}
    _save(repos)


def revoke(root: Path, classes: list[DataClass] | None = None) -> None:
    """Withdraw consent for these classes, or for everything when none are named."""
    repos = _load().get("repos", {})
    key = repo_key(root)
    entry = repos.get(key)
    if not isinstance(entry, dict):
        return
    granted = entry.get("granted", {})
    if classes is None:
        granted = {}
    else:
        for item in classes:
            granted.pop(item.value, None)
    if granted:
        entry["granted"] = granted
    else:
        repos.pop(key, None)
    _save(repos)
