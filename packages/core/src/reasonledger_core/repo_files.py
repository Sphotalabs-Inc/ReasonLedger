"""The repository boundary: files read because they sit in a checkout, and files written there.

A repository can commit a symlink, and a symlink resolves wherever it points: ``docs/notes.md``
may be a link to a file in the user's home directory, and ``.reasonledger/decisions`` may be a
link to a directory outside the checkout. Whether a path belongs to the repo is therefore
decided by where it resolves, never by how it is spelled. A link that stays inside the repo is
ordinary and allowed.
"""

from __future__ import annotations

from pathlib import Path


class RepoBoundaryError(ValueError):
    """A path that is spelled inside the repository but resolves outside it."""


def resolves_inside(resolved_root: Path, path: Path) -> bool:
    """Whether ``path`` resolves under ``resolved_root``, which the caller resolved once."""
    return path.resolve().is_relative_to(resolved_root)


def contained_dir(root: Path, relative: Path) -> Path:
    """``root / relative``, refused when it resolves outside ``root`` (a committed symlink)."""
    path = root / relative
    if not resolves_inside(root.resolve(), path):
        raise RepoBoundaryError(
            f"{relative.as_posix()} resolves outside the repository; refusing to write there"
        )
    return path


def read_repo_text(root: Path, relative: str) -> str | None:
    """The text of ``relative``, or None when it resolves outside ``root``, is missing or binary."""
    path = root / relative
    if not resolves_inside(root.resolve(), path):
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
