"""S59.4 in the local UI: the API carries `nearby` and `whyResultsHtml` renders it."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

import pytest
from reasonledger_cli.ui_html import assets_dir
from reasonledger_core.models.decision import DecisionStatus
from test_ui_server import _UiServer
from why_helpers import HUNTER, HUNTER_LOCUS, decide, write_source

NODE = shutil.which("node")
HARNESS = """
const fs = require("fs");
global.window = global;
global.RLRender = { escapeHtml: (s) => String(s).replace(/[&<>"']/g,
  (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])) };
global.RLRefs = {};
eval(fs.readFileSync(process.argv[1], "utf8"));
const payload = JSON.parse(process.argv[2]);
process.stdout.write(window.RLBrowse.whyResultsHtml(payload, Number(process.argv[3])));
"""


@pytest.fixture
def server(tmp_path: Path) -> Iterator[_UiServer]:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_hunt01", [HUNTER_LOCUS])
    decide(tmp_path, "dec_gone01", [f"{HUNTER}:25-27"], status=DecisionStatus.RETIRED)
    ui = _UiServer(tmp_path)
    yield ui
    ui.close()


def _ask(server: _UiServer, target: str) -> dict[str, object]:
    status, raw = server.request("GET", "/api/why?target=" + quote(target))
    assert status == 200
    payload: dict[str, object] = json.loads(raw)
    return payload


def _render(payload: dict[str, object], ledger_size: int) -> str:
    assert NODE is not None
    script = (assets_dir() / "browse.js").as_posix()
    done = subprocess.run(
        [NODE, "-e", HARNESS, script, json.dumps(payload), str(ledger_size)],
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


@pytest.mark.phase_4
def test_ui_why_api_carries_nearby_on_a_miss(server: _UiServer) -> None:
    miss = _ask(server, f"{HUNTER}:1")
    assert miss["count"] == 0
    ids = [entry["id"] for entry in miss["nearby"]]  # type: ignore[attr-defined,union-attr]
    assert ids == ["dec_hunt01", "dec_gone01"]
    assert _ask(server, f"{HUNTER}:16")["nearby"] == []


@pytest.mark.phase_4
@pytest.mark.skipif(NODE is None, reason="node is needed to run the UI script")
def test_ui_why_near_miss_lists_anchors(server: _UiServer) -> None:
    html = _render(_ask(server, f"{HUNTER}:1"), ledger_size=2)
    assert "No decision covers" in html and "line 1" in html
    assert "dec_hunt01" in html and "15-19" in html
    assert f"reasonledger why {HUNTER}:15" in html
    assert "dec_gone01" not in html and "1 retired" in html
    assert "No decision is recorded for this file" not in html


@pytest.mark.phase_4
@pytest.mark.skipif(NODE is None, reason="node is needed to run the UI script")
def test_ui_why_uncovered_file_counts_the_ledger(tmp_path: Path) -> None:
    write_source(tmp_path, HUNTER)
    ui = _UiServer(tmp_path)
    try:
        payload = _ask(ui, f"{HUNTER}:1")
    finally:
        ui.close()
    assert "ledger is empty" in _render(payload, ledger_size=0)
    html = _render(payload, ledger_size=7)
    assert "No decision names this file" in html and "7 decisions" in html


@pytest.mark.phase_4
@pytest.mark.skipif(NODE is None, reason="node is needed to run the UI script")
def test_ui_why_missing_file_keeps_its_error(tmp_path: Path) -> None:
    ui = _UiServer(tmp_path)
    try:
        payload = _ask(ui, "nope/file.ts:1")
    finally:
        ui.close()
    assert "There is no file at" in _render(payload, ledger_size=3)
