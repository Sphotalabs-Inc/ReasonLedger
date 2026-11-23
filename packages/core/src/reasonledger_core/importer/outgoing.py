"""The ``repo_text`` a model may be sent, and the check it passes first.

``repo_text`` is the text of the repo's docs and of its commit messages, subject and body: the
sources ``import`` and ``catchup`` extract decisions from. Before any of it goes to a model off
this machine, each source passes the PII linter's patterns (emails, phone numbers, card-like
numbers, API keys, private keys). A source that matches is held back whole, never partly
masked, and reported by path and rule so a person can fix it; it is not marked seen, so it is
read again once it changes. The preview builds its sample with the same prompt builder the
extractor sends, so what a person is shown is what goes.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from reasonledger_core.importer.prompt import build_user_prompt
from reasonledger_core.importer.scan import (
    COMMIT_PATH_PREFIX,
    ImportSource,
    commit_sources,
    scan_docs,
)
from reasonledger_core.privacy.pii_linter import lint_text
from reasonledger_core.sync.repo import recent_commit_messages

COMMIT_SCAN_LIMIT = 200


@dataclass(frozen=True)
class HeldSource:
    """A source kept on this machine: its path and the rules it matched, never the match."""

    path: str
    rules: tuple[str, ...]


@dataclass(frozen=True)
class ScreenedSources:
    sendable: list[ImportSource]
    held: list[HeldSource]


@dataclass(frozen=True)
class RepoTextPreview:
    """What ``repo_text`` would send: counts, what is held, and one message exactly as sent."""

    docs: int
    commits: int
    held: list[HeldSource]
    sample_path: str | None
    sample_message: str | None


def repo_text_sources(root: Path) -> list[ImportSource]:
    """Every doc a full scan reads, then the recent commit messages worth extracting from."""
    commits = commit_sources(recent_commit_messages(root, limit=COMMIT_SCAN_LIMIT))
    return [*scan_docs(root), *commits]


def screen_sources(sources: Iterable[ImportSource]) -> ScreenedSources:
    """Split ``sources`` into those that may be sent and those the patterns hold back."""
    sendable: list[ImportSource] = []
    held: list[HeldSource] = []
    for source in sources:
        rules = sorted({finding.rule_id for finding in lint_text(source.text)})
        if rules:
            held.append(HeldSource(path=source.path, rules=tuple(rules)))
        else:
            sendable.append(source)
    return ScreenedSources(sendable=sendable, held=held)


def preview_repo_text(root: Path) -> RepoTextPreview:
    """The ``repo_text`` payload for ``root``, screened as it would be before sending."""
    screened = screen_sources(repo_text_sources(root))
    commits = sum(1 for s in screened.sendable if s.path.startswith(COMMIT_PATH_PREFIX))
    first = screened.sendable[0] if screened.sendable else None
    return RepoTextPreview(
        docs=len(screened.sendable) - commits,
        commits=commits,
        held=screened.held,
        sample_path=first.path if first else None,
        sample_message=build_user_prompt(first) if first else None,
    )
