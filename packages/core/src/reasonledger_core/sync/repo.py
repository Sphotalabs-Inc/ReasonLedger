"""Git queries behind the catch-up delta — read-only, and never fatal.

Shells out to the `git` binary rather than adding a dependency (AGENTS.md §7).
Every helper degrades to "I don't know" instead of raising: a repo may not be a
git checkout, `git` may not be installed, and a recorded commit may have been
rebased or squashed away. In each case catch-up must still work — it falls back
to a full scan, which is correct, just less economical.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# A catch-up scan shells out at most a handful of times; a slow or hung git must
# not wedge the command.
_GIT_TIMEOUT_SECONDS = 30
_DATE_MARK = "date:"  # prefixes the date line so it cannot be read as a file name
_GITLINK_MODE = "160000"  # the index mode git gives a submodule entry


def _git(root: Path, *args: str) -> str | None:
    """Run a read-only git command, or return None if it cannot be answered."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def is_git_repo(root: Path) -> bool:
    return _git(root, "rev-parse", "--git-dir") is not None


def head_commit(root: Path) -> str | None:
    """Full SHA of HEAD, or None outside a git repo (or in one with no commits)."""
    out = _git(root, "rev-parse", "HEAD")
    return out.strip() if out and out.strip() else None


def commit_exists(root: Path, commit: str) -> bool:
    """False when a recorded watermark has been rebased or squashed out of history."""
    return _git(root, "cat-file", "-e", f"{commit}^{{commit}}") is not None


def changed_paths_since(root: Path, commit: str) -> list[str] | None:
    """Repo-relative paths touched since ``commit``, including uncommitted work.

    None means the delta is unknowable (not a repo, or the commit is gone) and
    the caller should fall back to a full scan rather than silently scanning
    nothing — reporting "no changes" when we simply cannot tell would be the
    worst possible answer for a catch-up.
    """
    if not commit_exists(root, commit):
        return None
    committed = _git(root, "diff", "--name-only", f"{commit}..HEAD")
    if committed is None:
        return None
    # Working-tree edits count: a decision written but not yet committed is still
    # a decision the ledger has not seen.
    pending = _git(root, "status", "--porcelain", "--untracked-files=all") or ""
    paths = {line for line in committed.splitlines() if line}
    for line in pending.splitlines():
        if len(line) > 3:
            paths.add(line[3:].strip().strip('"'))
    return sorted(paths)


def commit_messages_since(
    root: Path,
    commit: str,
    *,
    limit: int,
) -> list[tuple[str, str]] | None:
    """(sha, full message) for commits after ``commit``, newest first, capped at ``limit``.

    Commit messages are the other place a decision lands when nobody wrote a doc:
    a PR body explaining *why* is prose about a choice, which is exactly what the
    extractor reads. Returns None when the range cannot be resolved.
    """
    if not commit_exists(root, commit):
        return None
    # %x00 separates sha from body, %x1e separates records — neither can appear in
    # a commit message, unlike a newline.
    out = _git(
        root,
        "log",
        f"--max-count={limit}",
        "--no-merges",
        "--format=%H%x00%B%x1e",
        f"{commit}..HEAD",
    )
    if out is None:
        return None
    return _parse_commit_log(out)


def recent_commit_messages(root: Path, *, limit: int) -> list[tuple[str, str]]:
    """Newest ``limit`` commit messages. Empty when the history is unknowable."""
    if not is_git_repo(root):
        return []
    out = _git(
        root,
        "log",
        f"--max-count={limit}",
        "--no-merges",
        "--format=%H%x00%B%x1e",
        "HEAD",
    )
    if out is None:
        return []
    return _parse_commit_log(out)


def _parse_commit_log(out: str) -> list[tuple[str, str]]:
    commits: list[tuple[str, str]] = []
    for record in out.split("\x1e"):
        entry = record.strip("\n")
        if not entry:
            continue
        sha, _, message = entry.partition("\x00")
        if sha and message.strip():
            commits.append((sha, message.strip()))
    return commits


def decision_files_added_since(root: Path, ref: str, decisions_dir: Path) -> list[str] | None:
    """Basenames of decision files added since ``ref``. None when unknowable.

    None means "cannot tell" and callers MUST treat every decision as new.
    """
    if not is_git_repo(root):
        return None
    out = _git(
        root,
        "diff",
        "--name-only",
        "--diff-filter=A",
        ref,
        "--",
        str(decisions_dir),
    )
    if out is None:
        return None
    names: list[str] = []
    for line in out.splitlines():
        if line.strip():
            names.append(Path(line.strip()).name)
    return names


def decision_files_changed_since(
    root: Path, ref: str, decisions_dir: Path
) -> dict[str, str] | None:
    """Map decision filename -> git status letter (A/M/D). None when unknowable."""
    if not is_git_repo(root):
        return None
    out = _git(root, "diff", "--name-status", ref, "--", str(decisions_dir))
    if out is None:
        return None
    result: dict[str, str] = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        status, _, path = line.partition("\t")
        if not path:
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            status, path = parts
        letter = status.strip()[:1].upper()
        if letter:
            result[Path(path.strip()).name] = letter
    return result


def commit_author_for_path(root: Path, path: str) -> str | None:
    """Author of the most recent commit touching ``path``, or None."""
    out = _git(root, "log", "-1", "--format=%an", "--", path)
    if out is None:
        return None
    author = out.strip()
    return author or None


def file_at_ref(root: Path, ref: str, path: str) -> str | None:
    """``path`` as it was at ``ref``, or None when it did not exist there (or git cannot say)."""
    return _git(root, "show", f"{ref}:{path}")


def last_author_since(root: Path, ref: str, path: str) -> str | None:
    """Author name of the newest commit after ``ref`` that touched ``path``, or None."""
    out = _git(root, "log", "-1", "--format=%an", f"{ref}..HEAD", "--", path)
    return (out or "").strip() or None


def git_user_name(root: Path) -> str | None:
    """``user.name`` as git would sign a commit from this checkout, or None when unset."""
    out = _git(root, "config", "user.name")
    return (out or "").strip() or None


def first_commit_dates(root: Path, directory: Path) -> dict[str, datetime]:
    """File name -> author date of the commit that added it, for files under ``directory``.

    One ``git log`` for the whole directory. Empty when the files are untracked or
    gitignored, or outside a git checkout.
    """
    out = _git(
        root,
        "log",
        "--diff-filter=A",
        f"--format={_DATE_MARK}%aI",
        "--name-only",
        "--",
        str(directory),
    )
    dates: dict[str, datetime] = {}
    when: datetime | None = None
    for line in (out or "").splitlines():
        if line.startswith(_DATE_MARK):
            when = datetime.fromisoformat(line[len(_DATE_MARK) :])
        elif line.strip() and when is not None:
            # Newest first, so the last write per file is its earliest add.
            dates[Path(line.strip()).name] = when
    return dates


def commits_since(root: Path, commit: str) -> int | None:
    """How many commits have landed since the watermark — gap size, for the report."""
    if not commit_exists(root, commit):
        return None
    out = _git(root, "rev-list", "--count", f"{commit}..HEAD")
    if out is None or not out.strip().isdigit():
        return None
    return int(out.strip())


@dataclass(frozen=True)
class CommitChange:
    """One commit's subject and the repo-relative paths it touched."""

    sha: str
    subject: str
    files: tuple[str, ...]


def tracked_files(root: Path) -> list[str] | None:
    """Tracked plus untracked-but-not-ignored paths (what a working tree holds), or None.

    A submodule is one index entry (a gitlink), not a file, so it is left out.
    """
    out = _git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    if out is None:
        return None
    staged = _git(root, "ls-files", "--stage", "-z") or ""
    submodules = {
        entry.split("\t", 1)[1] for entry in staged.split("\0") if entry.startswith(_GITLINK_MODE)
    }
    return sorted({path for path in out.split("\0") if path} - submodules)


def is_shallow(root: Path) -> bool:
    """A shallow clone has cut its history, so co-change sees only what is left."""
    out = _git(root, "rev-parse", "--is-shallow-repository")
    return out is not None and out.strip() == "true"


def recent_commit_changes(root: Path, *, limit: int) -> list[CommitChange] | None:
    """The newest ``limit`` non-merge commits with the paths each touched, or None.

    Reads names only (never contents). A blobless or treeless clone answers this
    from commit and tree objects, so a scan works on a partial clone.
    """
    out = _git(
        root,
        "-c",
        "core.quotepath=off",
        "log",
        "--no-merges",
        "--no-renames",  # rename detection reads file contents, which a partial clone lacks
        f"--max-count={limit}",
        "--name-only",
        "--format=%x1e%H%x1f%s",
    )
    if out is None:
        return None
    changes: list[CommitChange] = []
    for record in out.split("\x1e"):
        header, _, names = record.partition("\n")
        sha, _, subject = header.partition("\x1f")
        if sha.strip():
            files = tuple(line for line in names.splitlines() if line)
            changes.append(CommitChange(sha=sha.strip(), subject=subject, files=files))
    return changes
