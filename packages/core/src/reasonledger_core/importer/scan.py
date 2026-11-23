"""Scan an application repo for documents that may contain decisions (P0-4).

Deterministic, offline, framework-free. Real decisions in a mature repo tend to
live in prose (``claude.md``, ``docs/``, ``.cursorrules``) rather than formal
ADRs; this collects those candidate documents for the extractor.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from reasonledger_core.repo_files import resolves_inside

# Non-markdown decision-bearing files worth scanning, plus all markdown.
DEFAULT_DOC_GLOBS: tuple[str, ...] = (".cursorrules", "**/*.md")

# The block `init` writes into an agent's shared rule file (CLAUDE.md, AGENTS.md, ...). It is
# tooling text, not the repo's own prose, so a scan must neither read it nor count a file for it.
RULE_BEGIN = "<!-- reasonledger:begin -->"
RULE_END = "<!-- reasonledger:end -->"
_RULE_BLOCK = re.compile(re.escape(RULE_BEGIN) + r".*?" + re.escape(RULE_END), re.DOTALL)
# A file bigger than the rule block plus markers cannot hold only the rule, so counting
# need not open it; a test pins the rule under this size.
RULE_ONLY_MAX_BYTES = 4096

# Commit sources are addressed `git:<sha>` — deliberately not a valid file path,
# so a decision's source_ref makes plain it came from history, not a document.
COMMIT_PATH_PREFIX = "git:"
COMMIT_SHA_LEN = 12
# Below this a commit message is a changelog line, not an explanation. Tuned to
# admit a short paragraph while rejecting "fix flaky test\n\nretry twice".
MIN_COMMIT_MESSAGE_CHARS = 120
# Git trailers that name a person (Co-authored-by, Signed-off-by, Reviewed-by, ...). A name and
# email there are author identity, which repo_text never carries, so the lines are dropped before
# a message is measured or sent; left in, every co-authored commit would also trip the email check.
_PERSON_TRAILER = re.compile(
    r"^[ \t]*[A-Za-z]+(?:-[A-Za-z]+)*-by:.*\n?", re.IGNORECASE | re.MULTILINE
)

# Any path segment matching one of these (or containing "venv") is skipped:
# dependencies, vendored code, and build output never hold our decisions.
#
# ``.reasonledger`` is excluded because decision records are themselves markdown:
# without it the extractor re-reads the ledger's own output as though it were
# source prose, spending model tokens to propose decisions from decisions.
DEFAULT_EXCLUDE_PARTS: frozenset[str] = frozenset(
    {
        ".reasonledger",
        "node_modules",
        "site-packages",
        ".git",
        "__pycache__",
        ".next",
        "dist",
        "build",
    }
)


@dataclass(frozen=True)
class ImportSource:
    """A repo document that may contain decisions."""

    path: str  # repo-relative POSIX path
    text: str


def strip_rule_blocks(text: str) -> str:
    """``text`` without any ReasonLedger rule block (markers included)."""
    return _RULE_BLOCK.sub("", text)


def _has_prose(path: Path) -> bool:
    """False for a file that holds nothing but the ReasonLedger rule (or nothing at all)."""
    try:
        if path.stat().st_size > RULE_ONLY_MAX_BYTES:
            return True
        return bool(strip_rule_blocks(path.read_text(encoding="utf-8")).strip())
    except (UnicodeDecodeError, OSError):
        return True


def _is_excluded(parts: tuple[str, ...], exclude_parts: frozenset[str]) -> bool:
    return any(part in exclude_parts or "venv" in part for part in parts)


def commit_sources(commits: Iterable[tuple[str, str]]) -> list[ImportSource]:
    """Turn (sha, message) pairs into extractable sources, dropping the noise.

    Most commits are "fix typo" and contain no reasoning; sending them to a model
    costs money and yields junk proposals. Two filters keep the signal: a message
    must have a **body** beyond its subject line, and must clear a length floor.
    Someone who wrote a paragraph explaining a change was explaining a decision.
    Person trailers are removed first, so they neither count towards the floor nor leave.
    """
    sources: list[ImportSource] = []
    for sha, raw in commits:
        message = _PERSON_TRAILER.sub("", raw).strip()
        subject, _, body = message.partition("\n")
        if not body.strip() or len(message) < MIN_COMMIT_MESSAGE_CHARS:
            continue
        sources.append(
            ImportSource(
                path=f"{COMMIT_PATH_PREFIX}{sha[:COMMIT_SHA_LEN]}",
                # The subject is repeated so the model sees the headline it summarises.
                text=f"Commit {sha[:COMMIT_SHA_LEN]}: {subject.strip()}\n\n{body.strip()}",
            )
        )
    return sources


def scannable_paths(
    paths: Iterable[str],
    *,
    globs: tuple[str, ...] = DEFAULT_DOC_GLOBS,
    exclude_parts: frozenset[str] = DEFAULT_EXCLUDE_PARTS,
) -> list[str]:
    """Narrow repo-relative paths to the ones a scan would actually read.

    Lets a caller report a *meaningful* changed-file count: a git delta is full of
    source files and ReasonLedger's own bookkeeping, none of which is scanned.
    """
    suffixes = tuple(glob.rsplit(".", 1)[-1] for glob in globs if glob.startswith("**/*."))
    names = frozenset(glob for glob in globs if not glob.startswith("**/"))
    kept = []
    for raw in paths:
        rel = PurePosixPath(raw)
        if _is_excluded(rel.parts, exclude_parts):
            continue
        if rel.name in names or rel.suffix.lstrip(".") in suffixes:
            kept.append(raw)
    return sorted(set(kept))


def count_scannable_docs(
    root: Path,
    *,
    globs: tuple[str, ...] = DEFAULT_DOC_GLOBS,
    exclude_parts: frozenset[str] = DEFAULT_EXCLUDE_PARTS,
) -> int:
    """Count the documents a scan would read, without reading any of them.

    ``init`` reports this to show a new user how much is already recoverable.
    Reading every markdown file in a large repo to produce a single integer is
    work the user waits on for no benefit, so this walks names only. It mirrors
    ``scan_docs``' filtering exactly — the two must not disagree about what
    counts as scannable. The one file it opens is a small one, to tell a rule-only file
    from a document.
    """
    base = root.resolve()
    seen: set[str] = set()
    for glob in globs:
        for path in root.glob(glob):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if _is_excluded(rel.parts, exclude_parts) or not resolves_inside(base, path):
                continue
            if not _has_prose(path):
                continue
            seen.add(rel.as_posix())
    return len(seen)


def scan_docs(
    root: Path,
    *,
    globs: tuple[str, ...] = DEFAULT_DOC_GLOBS,
    exclude_parts: frozenset[str] = DEFAULT_EXCLUDE_PARTS,
    only_paths: Collection[str] | None = None,
) -> list[ImportSource]:
    """Return decision-bearing documents under ``root`` in deterministic order.

    ``only_paths`` narrows the scan to a set of repo-relative POSIX paths — the
    catch-up delta. Passing an empty collection scans nothing, which is the
    correct answer when nothing changed; pass ``None`` for a full scan.

    A document is read only when it resolves inside ``root``: a committed symlink to a file
    elsewhere on this machine would otherwise be read and sent to a model as repo prose.
    """
    base = root.resolve()
    seen: dict[str, ImportSource] = {}
    for glob in globs:
        for path in root.glob(glob):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if _is_excluded(rel.parts, exclude_parts) or not resolves_inside(base, path):
                continue
            rel_posix = rel.as_posix()
            if only_paths is not None and rel_posix not in only_paths:
                continue
            if rel_posix in seen:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            text = strip_rule_blocks(text)
            if not text.strip():
                continue
            seen[rel_posix] = ImportSource(path=rel_posix, text=text)
    return [seen[key] for key in sorted(seen)]
