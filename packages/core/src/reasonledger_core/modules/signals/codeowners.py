"""CODEOWNERS: files grouped by their first owner, where that owner is discriminating."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from reasonledger_core.modules.config import MAX_COMPONENT_SHARE, MIN_MODULE_FILES
from reasonledger_core.modules.models import Candidate, SignalKind

CODEOWNERS_LOCATIONS: tuple[str, ...] = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")


def _pattern_regex(pattern: str) -> re.Pattern[str]:
    """gitignore-style: a leading slash anchors; a trailing slash means a directory."""
    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    body = pattern.strip("/")
    out: list[str] = []
    i = 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif body[i] == "*":
            out.append("[^/]*")
            i += 1
        elif body[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(body[i]))
            i += 1
    prefix = "" if anchored else "(?:.*/)?"
    return re.compile(f"{prefix}{''.join(out)}(?:/.*)?\\Z")


def _rules(text: str) -> list[tuple[re.Pattern[str], str]]:
    rules: list[tuple[re.Pattern[str], str]] = []
    for raw in text.splitlines():
        parts = raw.split("#")[0].split()
        if len(parts) >= 2:
            rules.append((_pattern_regex(parts[0]), parts[1]))
    return rules


def codeowners_candidates(root: Path, files: Sequence[str]) -> list[Candidate]:
    text = next(
        (
            (root / name).read_text(encoding="utf-8", errors="replace")
            for name in CODEOWNERS_LOCATIONS
            if (root / name).is_file()
        ),
        None,
    )
    if text is None:
        return []
    rules = _rules(text)
    owned: dict[str, set[str]] = defaultdict(set)
    for path in files:
        owner = next((o for regex, o in reversed(rules) if regex.match(path)), None)
        if owner:
            owned[owner].add(path)
    return [
        Candidate(
            name=owner.lstrip("@").rsplit("/", 1)[-1],
            signal=SignalKind.CODEOWNERS,
            files=frozenset(members),
        )
        for owner, members in sorted(owned.items())
        if MIN_MODULE_FILES <= len(members) <= MAX_COMPONENT_SHARE * len(files)
    ]
