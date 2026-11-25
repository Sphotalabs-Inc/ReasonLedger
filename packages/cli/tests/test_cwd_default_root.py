"""Install-anywhere contract: cwd is the ledger root, and `init` emits a runnable MCP command.

These guard the tool-install path (`uv tool install … reasonledger`), where the CLI is
invoked from an application repo with no `--root` and no ReasonLedger checkout in sight.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from reasonledger_cli.init_cmd import run_init
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_cli.parser import build_parser

REASONLEDGER_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REASONLEDGER_ROOT / "fixtures" / "golden" / "import" / "extractor_replay.json"

# The replay fixture is keyed by source document, so the app repo has to hold the doc
# the recorded extraction came from — otherwise the scan finds nothing to replay against.
FIXTURE_DOC = "claude.md"
FIXTURE_DOC_BODY = "# Notes\n\nWe store all timestamps in UTC.\n"


def _app_repo(tmp_path: Path) -> Path:
    (tmp_path / FIXTURE_DOC).write_text(FIXTURE_DOC_BODY, encoding="utf-8")
    return tmp_path


@pytest.mark.phase_3
def test_every_root_option_defaults_to_cwd() -> None:
    """A tool-installed CLI is only usable if `--root` is optional everywhere."""
    parser = build_parser()
    # argparse exposes no public accessor for registered subparsers.
    groups = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    assert groups, "expected a subcommand parser"

    checked = 0
    for name, sub in groups[0].choices.items():
        for option in sub._actions:
            if "--root" not in option.option_strings:
                continue
            assert option.default == Path.cwd(), f"{name} --root does not default to cwd"
            assert option.required is False, f"{name} --root is required"
            checked += 1
    assert checked >= 10, f"only {checked} subcommands expose --root"


@pytest.mark.phase_3
def test_full_loop_from_cwd_without_root_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """init → import → status → why, run from inside the app repo with no `--root`."""
    app = _app_repo(tmp_path)
    monkeypatch.chdir(app)

    assert main(["init"]) == EXIT_PASS
    capsys.readouterr()
    assert (app / ".reasonledger" / "decisions").is_dir()

    assert (
        main(["import", "--extracted-by", "fixture/test", "--fixture", str(FIXTURE)]) == EXIT_PASS
    )
    capsys.readouterr()

    assert main(["status", "--json"]) == EXIT_PASS
    counts = json.loads(capsys.readouterr().out)["counts"]
    assert counts["proposed"] == 1, counts

    assert main(["confirm", "--all", "--confirmed-by", "tester@example.com"]) == EXIT_PASS
    capsys.readouterr()

    assert main(["why", "backend/app/date_utils.py"]) == EXIT_PASS
    assert "UTC" in capsys.readouterr().out


@pytest.mark.phase_3
def test_cwd_root_never_reads_a_sibling_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `--directory` footgun, as a test: a populated neighbour must not leak in."""
    other = tmp_path / "other"
    app = tmp_path / "app"
    other.mkdir()
    app.mkdir()
    _app_repo(other)

    monkeypatch.chdir(other)
    assert main(["init"]) == EXIT_PASS
    assert (
        main(["import", "--extracted-by", "fixture/test", "--fixture", str(FIXTURE)]) == EXIT_PASS
    )
    capsys.readouterr()

    monkeypatch.chdir(app)
    assert main(["init"]) == EXIT_PASS
    capsys.readouterr()
    assert main(["status", "--json"]) == EXIT_PASS
    assert json.loads(capsys.readouterr().out)["counts"]["proposed"] == 0


@pytest.mark.phase_3
def test_init_mcp_snippet_runs_the_installed_executable(
    tmp_path: Path, launch_as: Callable[[Path, Path | None], None]
) -> None:
    installed = tmp_path / "bin" / "reasonledger"
    launch_as(installed, installed)
    app = tmp_path / "app"
    run_init(root=app, scan=False)
    entry = json.loads((app / ".mcp.json").read_text("utf-8"))["mcpServers"]["reasonledger"]
    assert entry["command"] == "reasonledger"
    assert entry["args"] == ["mcp", "--repo-root", str(app.resolve())]


@pytest.mark.phase_3
def test_init_mcp_snippet_uses_project_not_directory(tmp_path: Path) -> None:
    """`--directory` moves cwd to the checkout; `--project` leaves it where the user is."""
    run_init(root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=False)
    entry = json.loads((tmp_path / ".mcp.json").read_text("utf-8"))["mcpServers"]["reasonledger"]
    assert entry["command"] == "uv"
    assert "--directory" not in entry["args"]
    assert entry["args"][:3] == ["run", "--project", str(REASONLEDGER_ROOT.resolve())]
    assert entry["args"][-2:] == ["--repo-root", str(tmp_path.resolve())]
