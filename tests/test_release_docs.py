"""S56.6 and S56.8 — the release docs name the six environments."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENTS = (
    "pypi-core",
    "pypi",
    "pypi-mcp",
    "testpypi-core",
    "testpypi",
    "testpypi-mcp",
)


@pytest.mark.phase_3
@pytest.mark.parametrize(
    "path",
    ["docs/releasing.md", ".github/workflows/release.yml"],
)
def test_release_docs_list_all_six_environments(path: str) -> None:
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    for environment in ENVIRONMENTS:
        assert re.search(rf"(?<![\w-]){environment}(?![\w-])", text), f"{path}: {environment}"

