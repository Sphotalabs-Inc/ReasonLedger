"""The package READMEs are the PyPI pages: what they tell a stranger to run must work as written."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
from reasonledger_cli.agent_targets import CLI_EXECUTABLE, MCP_SUBCOMMAND

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_READMES = sorted((REPO_ROOT / "packages").glob("*/README.md"))
PRE_RELEASE = re.compile(r"\d(?:a|b|rc)\d+$")
PIP_INSTALL = re.compile(r"^\s*pip install\b(?P<rest>.*)$", re.MULTILINE)
JSON_FENCE = re.compile(r"```json\n(?P<body>.*?)\n```", re.DOTALL)


def _release_version() -> str:
    pyproject = REPO_ROOT / "packages" / "cli" / "pyproject.toml"
    version: str = tomllib.loads(pyproject.read_text("utf-8"))["project"]["version"]
    return version


@pytest.mark.phase_3
@pytest.mark.parametrize("readme", PACKAGE_READMES, ids=lambda path: path.parent.name)
def test_pip_install_lines_select_a_pre_release(readme: Path) -> None:
    """pip skips pre-releases by default, so a plain line fails while every release is one."""
    if not PRE_RELEASE.search(_release_version()):
        pytest.skip("a stable release exists, so a plain `pip install` finds it")
    for match in PIP_INSTALL.finditer(readme.read_text("utf-8")):
        assert "--pre" in match["rest"], f"{readme.parent.name}: {match[0].strip()}"


@pytest.mark.phase_3
def test_mcp_readme_config_is_what_init_writes() -> None:
    """`uv tool install reasonledger` has no `reasonledger-mcp` on PATH; `init` writes `mcp`."""
    text = (REPO_ROOT / "packages" / "mcp" / "README.md").read_text("utf-8")
    fence = JSON_FENCE.search(text)
    assert fence is not None, "the MCP README shows no config"
    entry = json.loads(fence["body"])["mcpServers"]["reasonledger"]
    assert entry["command"] == CLI_EXECUTABLE
    assert entry["args"][0] == MCP_SUBCOMMAND
