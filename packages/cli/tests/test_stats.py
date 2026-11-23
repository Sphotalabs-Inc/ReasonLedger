"""`status --stats` and the UI summary strip: one count, two surfaces."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_cli.ui_html import assets_dir
from reasonledger_core.views import LedgerStats
from test_ui_map import ui as ui  # noqa: F401  (the two-module repo with one shared decision)
from test_ui_server import _UiServer


def _root(server: _UiServer) -> Path:
    return Path(json.loads(server.request("GET", "/api/view")[1])["root"])


@pytest.mark.phase_5
def test_the_stats_endpoint_and_the_cli_report_the_same_count(
    ui: _UiServer,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    status, raw = ui.request("GET", "/api/stats")
    assert status == 200
    served = LedgerStats.model_validate_json(raw)
    assert (served.in_force, served.judged, served.pending) == (1, 1, 0)
    assert [(m.id, m.decisions) for m in served.modules] == [("billing", 1), ("orders", 1)]

    assert main(["status", "--root", str(_root(ui)), "--stats", "--json"]) == EXIT_PASS
    assert LedgerStats.model_validate_json(capsys.readouterr().out) == served
    assert ui.request("GET", "/api/stats", token=None)[0] == 403


@pytest.mark.phase_5
def test_stats_text_names_the_backlog_and_each_module(
    ui: _UiServer,  # noqa: F811
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["status", "--root", str(_root(ui)), "--stats"]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "decisions in force: 1" in out
    assert "1 judged by a person  0 pending" in out
    assert "Billing" in out and "Orders" in out


@pytest.mark.phase_5
def test_stats_without_a_ledger_or_a_map_say_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["status", "--root", str(tmp_path), "--stats"]) == EXIT_PASS
    out = capsys.readouterr().out
    assert "decisions in force: 0" in out and "no module map yet" in out


@pytest.mark.phase_5
def test_the_strip_is_live_only_and_draws_no_count_of_its_own(tmp_path: Path) -> None:
    out = tmp_path / "ledger.html"
    assert main(["status", "--root", str(tmp_path), "--html", str(out)]) == EXIT_PASS
    exported = out.read_text(encoding="utf-8")
    assert "stats.js" not in exported and "stats.css" not in exported
    # The script reads the served numbers; a second tally in the browser could drift from the CLI.
    script = (assets_dir() / "stats.js").read_text(encoding="utf-8")
    assert "/api/stats" in script and ".filter(function (d)" not in script
