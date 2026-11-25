"""S48 — `--version` reports the installed package metadata, never a second hard-coded copy."""

from __future__ import annotations

from importlib.metadata import version

import pytest
from reasonledger_cli.main import main
from reasonledger_mcp.server import main as mcp_main


@pytest.mark.phase_3
def test_version_flag_matches_metadata(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as cli:
        main(["--version"])
    assert cli.value.code == 0
    assert capsys.readouterr().out.strip() == f"reasonledger {version('reasonledger')}"
    with pytest.raises(SystemExit) as mcp:
        mcp_main(["--version"])
    assert mcp.value.code == 0
    assert capsys.readouterr().out.strip() == f"reasonledger-mcp {version('reasonledger-mcp')}"


@pytest.mark.phase_3
def test_workspace_packages_share_one_version() -> None:
    assert {version(n) for n in ("reasonledger", "reasonledger-core", "reasonledger-mcp")} == {
        "0.3.0a8"
    }
