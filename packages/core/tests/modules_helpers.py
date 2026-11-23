"""Build small throwaway git repos for module-detection tests."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
        capture_output=True,
        text=True,
        check=True,
        env=_ENV,
    )
    return done.stdout


def write_files(root: Path, files: Mapping[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def make_repo(root: Path, commits: Sequence[tuple[str, Mapping[str, str]]]) -> Path:
    """``git init`` then one commit per ``(subject, {path: text})``, oldest first."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q")
    for subject, files in commits:
        write_files(root, files)
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", subject)
    return root


def tree(prefix: str, count: int, suffix: str = ".py") -> dict[str, str]:
    """``count`` placeholder files under ``prefix``: ``a/f0.py``, ``a/f1.py``, ..."""
    return {f"{prefix}/f{i}{suffix}": f"# {prefix} {i}\n" for i in range(count)}
