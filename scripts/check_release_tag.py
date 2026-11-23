"""Refuse a release whose tag does not name the version the packages declare.

Run by the `gate` job of `.github/workflows/release.yml` on a `v*` tag push, before anything is
built. Publishing uploads whatever version `pyproject.toml` says, so a tag that disagrees with it
(`v0.3.0a7` on a tree still at `0.3.0a6`) would put the wrong number on PyPI, where a version can
never be reused.

    python scripts/check_release_tag.py v0.3.0a6

The three packages move in lockstep, so all three must carry the tag's version.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRS = ("core", "cli", "mcp")
TAG_PREFIX = "v"


class TagError(Exception):
    """The tag cannot be released from this tree; the message is what the job log shows."""


def package_versions(root: Path = REPO_ROOT) -> dict[str, str]:
    """Each package's name mapped to the version its pyproject.toml declares."""
    versions: dict[str, str] = {}
    for directory in PACKAGE_DIRS:
        pyproject = root / "packages" / directory / "pyproject.toml"
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
        versions[str(project["name"])] = str(project["version"])
    return versions


def check_tag(tag: str, versions: Mapping[str, str]) -> None:
    """Raise TagError unless `tag` is exactly the prefix plus the one version all packages share."""
    if not tag.startswith(TAG_PREFIX):
        raise TagError(f"tag {tag!r} does not start with {TAG_PREFIX!r}")
    wanted = tag.removeprefix(TAG_PREFIX)
    stale = {name: version for name, version in versions.items() if version != wanted}
    if stale:
        declared = ", ".join(f"{name} {version}" for name, version in sorted(versions.items()))
        raise TagError(
            f"tag {tag!r} names version {wanted}, but the packages declare: {declared}. "
            "Bump every pyproject.toml to the tag's version, or tag the version they declare."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tag", help="the pushed tag, e.g. v0.3.0a6")
    args = parser.parse_args(argv)
    try:
        check_tag(args.tag, package_versions())
    except TagError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"tag {args.tag} matches every package version", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
