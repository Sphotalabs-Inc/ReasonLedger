"""The files a scan models: tracked paths minus dependencies, lockfiles and assets."""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path, PurePosixPath

from reasonledger_core.importer.scan import DEFAULT_EXCLUDE_PARTS
from reasonledger_core.modules.config import (
    ASSET_SUFFIXES,
    CONFIG_NAME_PATTERN,
    CONFIG_SUFFIXES,
    GENERATED_DIR_SUFFIXES,
    NOISE_FILE_PATTERNS,
    SUPPORT_DIRS,
    TOOLING_DIR_PATTERN,
)
from reasonledger_core.sync.repo import tracked_files

# test_pdfs, tests-build, tokio-test: named for testing, so support code like tests/
_TOOLING = re.compile(TOOLING_DIR_PATTERN)
_TESTISH = re.compile(r"^tests?[-_]|[-_]tests?$")
_CONFIG_NAME = re.compile(CONFIG_NAME_PATTERN, re.IGNORECASE)


def _modelled(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if any(part in DEFAULT_EXCLUDE_PARTS or "venv" in part for part in parts):
        return False
    if any(part.endswith(GENERATED_DIR_SUFFIXES) for part in parts[:-1]):
        return False
    name = parts[-1]
    if PurePosixPath(name).suffix.lower() in ASSET_SUFFIXES:
        return False
    return not any(fnmatch.fnmatch(name, pattern) for pattern in NOISE_FILE_PATTERNS)


def is_support_name(part: str) -> bool:
    """A directory name that marks tests, docs, examples, fixtures or a dot-directory."""
    name = part.lower()
    return name in SUPPORT_DIRS or name.startswith(".") or bool(_TESTISH.search(name))


def is_support(path: str) -> bool:
    """Tests, docs, examples, fixtures and dot-directories: part of a repo, not of a module."""
    return any(is_support_name(part) for part in PurePosixPath(path).parts[:-1])


def is_tooling_name(part: str) -> bool:
    """A directory name for build, deploy or maintenance code: deploy, scripts, cleanup_scripts."""
    return bool(_TOOLING.match(part.lower()))


def is_tooling(path: str) -> bool:
    """Files under tooling directories belong to the platform, not to any feature."""
    return any(is_tooling_name(part) for part in PurePosixPath(path).parts[:-1])


def is_config_file(path: str) -> bool:
    """A dotfile, Dockerfile, ``*.config.*`` or a file of a configuration format."""
    name = PurePosixPath(path).name
    return bool(_CONFIG_NAME.match(name)) or PurePosixPath(name).suffix.lower() in CONFIG_SUFFIXES


def _walk(root: Path) -> list[str]:
    found: list[str] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDE_PARTS and "venv" not in d]
        base = Path(current).relative_to(root)
        found.extend((base / name).as_posix() for name in names)
    return found


def modelled_files(root: Path) -> tuple[list[str], bool]:
    """Sorted repo-relative paths to model, and whether they came from git.

    Outside a git repo the working tree is walked instead; ``.gitignore`` is then
    not honoured, which the caller reports as a limitation.
    """
    tracked = tracked_files(root)
    paths = tracked if tracked is not None else _walk(root)
    return sorted(p for p in paths if _modelled(p)), tracked is not None
