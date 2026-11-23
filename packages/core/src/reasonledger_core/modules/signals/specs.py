"""Spec documents: one file per module whose "Key files" section names its code."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Collection, Sequence
from pathlib import Path, PurePosixPath

from reasonledger_core.modules.config import MIN_MODULE_FILES
from reasonledger_core.modules.models import Candidate, SignalKind

SPEC_MODULE_DIRS: tuple[str, ...] = ("specs/modules", "docs/modules")
MAX_DESCRIPTION_LENGTH = 240

_KEY_FILES = re.compile(r"^##\s+(?:\d+\.\s*)?key files\b", re.IGNORECASE)
_PURPOSE = re.compile(r"^##\s+(?:\d+\.\s*)?purpose\b", re.IGNORECASE)
_SPAN = re.compile(r"`([^`\n]+)`")
_TITLE_SUFFIX = re.compile(r"\s*[—–-]+\s*behaviou?r spec\s*$", re.IGNORECASE)


def _section(lines: list[str], start: re.Pattern[str]) -> list[str]:
    for index, line in enumerate(lines):
        if start.match(line):
            body: list[str] = []
            for follow in lines[index + 1 :]:
                if follow.startswith("## "):
                    break
                body.append(follow)
            return body
    return []


def _description(lines: list[str]) -> str:
    title = next((_TITLE_SUFFIX.sub("", ln[2:]).strip() for ln in lines if ln.startswith("# ")), "")
    paragraph: list[str] = []
    for line in (ln.strip() for ln in _section(lines, _PURPOSE)):
        if not line and paragraph:
            break
        if line:
            paragraph.append(line)
    purpose = " ".join(paragraph).replace("**", "").replace("`", "")
    return f"{title}. {purpose}".strip(" .")[:MAX_DESCRIPTION_LENGTH]


def _title(lines: list[str], fallback: str) -> str:
    found = next((_TITLE_SUFFIX.sub("", ln[2:]).strip() for ln in lines if ln.startswith("# ")), "")
    return found or fallback


def resolve_reference(span: str, files: Collection[str], by_name: dict[str, list[str]]) -> set[str]:
    """Files a backticked span names: a path, a directory, or a unique bare filename."""
    path = span.split("::")[0].split("(")[0].strip().removeprefix("./")
    if not path or " " in path:
        return set()
    if path in files:
        return {path}
    prefix = path.rstrip("/") + "/"
    under = {f for f in files if f.startswith(prefix)}
    if under:
        return under
    named = by_name.get(PurePosixPath(path).name, []) if "/" not in path else []
    return {named[0]} if len(named) == 1 else set()


def spec_candidates(root: Path, files: Sequence[str]) -> list[Candidate]:
    known = set(files)
    by_name: dict[str, list[str]] = defaultdict(list)
    for path in files:
        by_name[PurePosixPath(path).name].append(path)
    found: list[Candidate] = []
    for spec_dir in SPEC_MODULE_DIRS:
        for spec in sorted(f for f in files if f.startswith(spec_dir + "/") and f.endswith(".md")):
            stem = PurePosixPath(spec).stem
            if stem.startswith("_"):
                continue
            try:
                lines = (root / spec).read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            named: set[str] = set()
            for line in _section(lines, _KEY_FILES):
                for span in _SPAN.findall(line):
                    named |= resolve_reference(span, known, by_name)
            named.discard(spec)
            if len(named) >= MIN_MODULE_FILES:
                found.append(
                    Candidate(
                        name=_title(lines, stem),
                        id_hint=stem,
                        signal=SignalKind.SPECS,
                        files=frozenset(named),
                        description=_description(lines),
                    )
                )
    return found
