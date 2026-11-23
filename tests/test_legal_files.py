"""S54 — the licence terms are one consistent statement and the README links to every legal file."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("core", "cli", "mcp")
COPYRIGHT_HOLDER = "SphotaLabs Inc."
LICENCE_EXPRESSION = "Apache-2.0"
# Duplicated at the root and in each package so every sdist and wheel carries them.
SHIPPED_LEGAL_FILES = ("LICENSE", "NOTICE")
README_LEGAL_LINKS = ("LICENSE", "NOTICE", "TRADEMARKS.md", "CONTRIBUTING.md", "SECURITY.md")
COPYRIGHT_LINE = re.compile(r"^\s*Copyright (?:\(c\) )?\d{4} (?P<holder>.+?)\s*$", re.MULTILINE)
MARKDOWN_LINK = re.compile(r"\]\((?P<target>[^)\s]+)\)")
EMAIL_ADDRESS = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")


def _project(package: str) -> dict[str, object]:
    path = REPO_ROOT / "packages" / package / "pyproject.toml"
    project: dict[str, object] = tomllib.loads(path.read_text("utf-8"))["project"]
    return project


@pytest.mark.phase_3
@pytest.mark.parametrize("name", SHIPPED_LEGAL_FILES)
@pytest.mark.parametrize("package", PACKAGES)
def test_license_copies_are_identical(package: str, name: str) -> None:
    root_copy = REPO_ROOT / name
    package_copy = REPO_ROOT / "packages" / package / name
    assert root_copy.is_file() and not root_copy.is_symlink(), name
    # A symlink escapes the sdist archive, so each copy must be a real file.
    assert package_copy.is_file() and not package_copy.is_symlink(), f"{package}/{name}"
    assert package_copy.read_bytes() == root_copy.read_bytes(), f"{package}/{name} differs"


@pytest.mark.phase_3
def test_copyright_holder_is_one_string() -> None:
    for name in SHIPPED_LEGAL_FILES:
        holders = {m["holder"] for m in COPYRIGHT_LINE.finditer((REPO_ROOT / name).read_text())}
        assert holders == {COPYRIGHT_HOLDER}, f"{name}: {holders}"
    for package in PACKAGES:
        assert _project(package)["authors"] == [{"name": COPYRIGHT_HOLDER}], package


@pytest.mark.phase_3
@pytest.mark.parametrize("package", PACKAGES)
def test_package_declares_licence_once_and_ships_both_files(package: str) -> None:
    project = _project(package)
    assert project["license"] == LICENCE_EXPRESSION
    assert project["license-files"] == list(SHIPPED_LEGAL_FILES)
    # The SPDX expression is the single statement; a classifier would be a second one.
    classifiers = project["classifiers"]
    assert isinstance(classifiers, list)
    assert not [c for c in classifiers if str(c).startswith("License ::")]


@pytest.mark.phase_3
def test_readme_links_resolve_and_cover_the_legal_files() -> None:
    text = (REPO_ROOT / "README.md").read_text("utf-8")
    targets = {
        m["target"].split("#", 1)[0]
        for m in MARKDOWN_LINK.finditer(text)
        if not re.match(r"[a-z][a-z0-9+.-]*:", m["target"])
    }
    missing = {t for t in targets if t and not (REPO_ROOT / t).exists()}
    assert not missing, f"README links to files that do not exist: {sorted(missing)}"
    assert set(README_LEGAL_LINKS) <= targets


@pytest.mark.phase_3
def test_security_policy_names_a_reporting_address() -> None:
    """Reporters need somewhere private to go; a policy without an address is a dead end."""
    text = (REPO_ROOT / "SECURITY.md").read_text("utf-8")
    assert EMAIL_ADDRESS.search(text), "SECURITY.md names no reporting address"
