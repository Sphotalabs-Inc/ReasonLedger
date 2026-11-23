"""Serialize and parse `.reasonledger/decisions/*.md` records."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from reasonledger_core.models.decision import (
    DECISION_ID_PATTERN,
    DecisionFrontmatter,
    DecisionRecord,
)
from reasonledger_core.repo_files import RepoBoundaryError

DECISIONS_DIR = Path(".reasonledger/decisions")
# libyaml parses a decision several times faster than the pure-Python loader, which is
# what keeps a view of hundreds of records inside its time budget.
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<yaml>.*?)\n---\s*\n?(?P<body>.*)\Z",
    re.DOTALL,
)


class DecisionFormatError(ValueError):
    """Raised when a decision markdown document is invalid."""


def render_decision_markdown(record: DecisionRecord) -> str:
    payload = record.frontmatter.model_dump(mode="json", exclude_none=True)
    dumped = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).strip()
    body = record.body.strip()
    if body:
        return f"---\n{dumped}\n---\n\n{body}\n"
    return f"---\n{dumped}\n---\n"


def parse_decision_markdown(raw: str) -> DecisionRecord:
    match = _FRONTMATTER_RE.match(raw)
    if match is None:
        raise DecisionFormatError("decision markdown must start with YAML frontmatter")
    try:
        data = yaml.load(match.group("yaml"), Loader=_YAML_LOADER)
    except yaml.YAMLError as exc:
        raise DecisionFormatError(f"invalid frontmatter YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise DecisionFormatError("frontmatter must be a mapping")
    try:
        frontmatter = DecisionFrontmatter.model_validate(data)
    except Exception as exc:
        raise DecisionFormatError(f"invalid decision frontmatter: {exc}") from exc
    body = match.group("body").strip()
    return DecisionRecord(frontmatter=frontmatter, body=body)


# O_NOFOLLOW makes the open itself refuse a symlink, closing the gap after the check below;
# where the platform has none (Windows), the check alone stands.
_NO_FOLLOW = getattr(os, "O_NOFOLLOW", 0)
_NEW_FILE_MODE = 0o666  # narrowed by the umask, as Path.write_text would


def write_decision_file(path: Path, record: DecisionRecord) -> Path:
    """Write ``record`` to ``path``, never through a symlink: a committed link points anywhere.

    The directory is the caller's to contain (``repo_files.contained_dir``); this refuses the
    file itself being a link, including a broken one, which ``Path.exists`` reports as absent.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RepoBoundaryError(
            f"{path.name} is a symlink; refusing to write a decision through it"
        )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _NO_FOLLOW, _NEW_FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(render_decision_markdown(record))
    return path


def read_decision_file(path: Path) -> DecisionRecord:
    return parse_decision_markdown(path.read_text(encoding="utf-8"))


_DECISION_ID_RE = re.compile(DECISION_ID_PATTERN)


class DecisionIdError(ValueError):
    """A decision id that cannot be used as a file name, or one already taken."""


def decision_filename(decision_id: str) -> str:
    """The file name for an id; refuses anything that is not a plain ``dec_`` id."""
    if not _DECISION_ID_RE.fullmatch(decision_id):
        raise DecisionIdError(
            f"invalid decision id {decision_id!r}: expected dec_ then a-z, 0-9 or _"
        )
    return f"{decision_id}.md"
