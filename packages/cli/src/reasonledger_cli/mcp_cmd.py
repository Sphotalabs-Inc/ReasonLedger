"""`reasonledger mcp`: the MCP server, under the one package name a user installs."""

from __future__ import annotations

from pathlib import Path

from reasonledger_mcp.server import main as serve

EXIT_PASS = 0


def run_mcp_cmd(*, repo_root: Path | None) -> int:
    """Serve over stdio through the same entry point as `reasonledger-mcp`.

    Nothing may be printed here: stdout carries only protocol messages.
    """
    serve(["--repo-root", str(repo_root)] if repo_root is not None else [])
    return EXIT_PASS
