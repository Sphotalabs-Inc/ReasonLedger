"""Refuse a release whose tag does not name the version the packages declare.

Run by the `gate` job of `.github/workflows/release.yml` on a `v*` tag push, before anything is
built. Publishing uploads whatever version `pyproject.toml` says, so a tag that disagrees with it
(`v0.3.0a9` on a tree still at `0.3.0a8`) would put the wrong number on PyPI, where a version can
never be reused.

    python scripts/check_release_tag.py v0.3.0a8

The three packages move in lockstep, so all three must carry the tag's version and require each
other at exactly that version.
"""

from __future__ import annotations

import argparse
import itertools
import re
import sys
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRS = ("core", "cli", "mcp")
TAG_PREFIX = "v"
# A PEP 508 requirement up to its marker: name, optional extras, then the version specifier.
REQUIREMENT = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)\s*(?:\[[^\]]*\])?\s*(?P<spec>[^;]*)")


class TagError(Exception):
    """The tag cannot be released from this tree; the message is what the job log shows."""


class SiblingPin(NamedTuple):
    """One package's requirement on another package of this release."""

    owner: str
    name: str
    spec: str


def _projects(root: Path) -> list[dict[str, Any]]:
    return [
        tomllib.loads((root / "packages" / d / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]
        for d in PACKAGE_DIRS
    ]


def sibling_pins(root: Path = REPO_ROOT) -> list[SiblingPin]:
    """Every requirement, extras included, that one package declares on another of the three."""
    projects = _projects(root)
    names = {str(project["name"]) for project in projects}
    pins: list[SiblingPin] = []
    for project in projects:
        groups: Iterable[list[str]] = [
            project.get("dependencies", []),
            *project.get("optional-dependencies", {}).values(),
        ]
        for requirement in itertools.chain.from_iterable(groups):
            match = REQUIREMENT.match(requirement)
            if match and match["name"] in names:
                pins.append(SiblingPin(str(project["name"]), match["name"], match["spec"].strip()))
    return pins


def check_pins(version: str, pins: Iterable[SiblingPin]) -> None:
    """Raise TagError unless every sibling requirement is exactly ``==version``.

    A range lets `pip install -U reasonledger` keep an older core or MCP release beside the new
    CLI, a pairing no release was tested as.
    """
    wanted = f"=={version}"
    loose = [f"{pin.owner} needs {pin.name}{pin.spec}" for pin in pins if pin.spec != wanted]
    if loose:
        raise TagError(
            f"the packages must pin each other to {wanted}, but {'; '.join(loose)}. "
            "Set every sibling requirement in pyproject.toml to the release version."
        )


def package_versions(root: Path = REPO_ROOT) -> dict[str, str]:
    """Each package's name mapped to the version its pyproject.toml declares."""
    versions: dict[str, str] = {}
    for project in _projects(root):
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
    parser.add_argument("tag", help="the pushed tag, e.g. v0.3.0a8")
    args = parser.parse_args(argv)
    try:
        check_tag(args.tag, package_versions())
        check_pins(args.tag.removeprefix(TAG_PREFIX), sibling_pins())
    except TagError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"tag {args.tag} matches every package version and sibling pin", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
