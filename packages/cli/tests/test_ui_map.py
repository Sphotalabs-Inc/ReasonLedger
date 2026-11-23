"""Phase 5 — the module map in `reasonledger ui`: endpoints, tab and export."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.modules import Manifest, Module, write_manifest
from test_ui_server import _UiServer


def _decision(root: Path, decision_id: str, *loci: str) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            justifies=list(loci),
            context="Which timezone do timestamps use?",
            choice="UTC everywhere",
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


@pytest.fixture
def ui(tmp_path: Path) -> Iterator[_UiServer]:
    for folder in ("orders", "billing"):
        for index in range(3):
            path = tmp_path / "app" / folder / f"f{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x = 1\n", encoding="utf-8")
    write_manifest(
        tmp_path,
        Manifest(
            modules=[
                Module(id="orders", name="Orders", paths=["app/orders/**"]),
                Module(id="billing", name="Billing", paths=["app/billing/**"]),
            ]
        ),
    )
    _decision(tmp_path, "dec_both", "app/orders/f0.py:1-5", "app/billing/f0.py::charge")
    server = _UiServer(tmp_path)
    yield server
    server.close()


@pytest.mark.phase_5
def test_the_map_endpoint_serves_tiles_and_needs_the_session_token(ui: _UiServer) -> None:
    status, raw = ui.request("GET", "/api/map")
    assert status == 200
    view = json.loads(raw)
    tiles = {t["id"]: t for t in view["features"]}
    assert set(tiles) == {"orders", "billing"} and view["decisions"] == 1
    assert tiles["orders"]["shared"] == 1 and tiles["orders"]["coverage"] == pytest.approx(
        0.333, abs=0.001
    )
    assert ui.request("GET", "/api/map", token=None)[0] == 403
    assert ui.request("GET", "/api/map/module?id=orders", token="wrong")[0] == 403


@pytest.mark.phase_5
def test_a_module_page_shows_the_shared_decision_and_refuses_a_bad_id(ui: _UiServer) -> None:
    status, raw = ui.request("GET", "/api/map/module?id=orders")
    page = json.loads(raw)
    assert status == 200 and [d["id"] for d in page["decisions"]] == ["dec_both"]
    assert [m["id"] for m in page["decisions"][0]["modules"]] == ["billing", "orders"]
    assert [n["id"] for n in page["neighbours"]] == ["billing"]
    assert ui.request("GET", "/api/map/module?id=nowhere")[0] == 404
    assert ui.request("GET", "/api/map/module?id=../secrets")[0] == 404
    assert ui.request("GET", "/api/map/module")[0] == 404


@pytest.mark.phase_5
def test_without_a_manifest_the_map_endpoint_answers_empty(tmp_path: Path) -> None:
    server = _UiServer(tmp_path)
    try:
        status, raw = server.request("GET", "/api/map")
        assert status == 200 and json.loads(raw)["empty"] is True
    finally:
        server.close()


@pytest.mark.phase_5
def test_the_page_offers_a_map_tab_and_serves_its_assets(ui: _UiServer) -> None:
    status, raw = ui.request("GET", "/", token=None)
    html = raw.decode("utf-8")
    assert status == 200 and 'data-tab="map"' in html and 'id="map-pane"' in html
    for name in ("map.js", "map_page.js", "map.css"):
        assert f"/{name}" in html
        code, body = ui.request("GET", f"/{name}", token=None)
        assert code == 200 and body


@pytest.mark.phase_5
def test_the_static_export_leaves_the_live_map_out(tmp_path: Path) -> None:
    out = tmp_path / "ledger.html"
    assert main(["status", "--root", str(tmp_path), "--html", str(out)]) == EXIT_PASS
    html = out.read_text("utf-8")
    for live_only in (
        "map-pane",
        "map.js",
        "map_page.js",
        "map.css",
        "RLMap",
        'data-tab="map"',
        "organize",
        "Organize",
    ):
        assert live_only not in html
