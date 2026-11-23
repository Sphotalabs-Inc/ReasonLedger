"""S14: `reasonledger ui` localhost server + `status --html` export."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from http.client import HTTPConnection
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_cli.ui_cmd import create_ui_server
from reasonledger_cli.ui_html import assets_dir
from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    decision_filename,
    write_decision_file,
)
from reasonledger_core.importer.extractor import DecisionCandidate
from reasonledger_core.importer.propose import (
    PROPOSED_DIR,
    confirm_proposed,
    propose_decisions,
)
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.views import LedgerView

EXTRACTED_AT = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)
_TOKEN_HEADER = "X-RL-Token"


def _stage(root: Path, ref: str, context: str, choice: str) -> str:
    result = propose_decisions(
        [DecisionCandidate(context=context, choice=choice, source_ref=ref)],
        root=root,
        extracted_by="test/extractor",
        extracted_at=EXTRACTED_AT,
    )
    return result.proposed_ids[0]


def _write_confirmed(root: Path, decision_id: str, *, context: str, choice: str) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=DecisionOversight.REVIEWED,
            status=DecisionStatus.CONFIRMED,
            context=context,
            choice=choice,
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


def _stage_conflicting_pair(root: Path) -> None:
    _write_confirmed(root, "dec_tzutc", context="Timestamp storage timezone policy", choice="UTC")
    _write_confirmed(
        root, "dec_tzlocal", context="Timestamp storage timezone policy", choice="server-local"
    )


_MISSING = object()


class _UiServer:
    def __init__(self, root: Path) -> None:
        self.server, self.token, self.origin = create_ui_server(root=root, port=0)
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        # server_address widens the host to str | bytes; HTTPConnection wants str.
        raw_host, self.port = self.server.server_address[:2]
        self.host = raw_host.decode("ascii") if isinstance(raw_host, bytes) else str(raw_host)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=5)

    def request(
        self,
        method: str,
        path: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        token: str | None | object = _MISSING,
        origin: str | None = None,
    ) -> tuple[int, bytes]:
        hdrs: dict[str, str] = dict(headers or {})
        if token is _MISSING:
            hdrs[_TOKEN_HEADER] = self.token
        elif isinstance(token, str):
            hdrs[_TOKEN_HEADER] = token
        if origin is not None:
            hdrs["Origin"] = origin
        if body is not None and "Content-Type" not in hdrs:
            hdrs["Content-Type"] = "application/json"
        conn = HTTPConnection(self.host, self.port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=hdrs)
            resp = conn.getresponse()
            return resp.status, resp.read()
        finally:
            conn.close()


@pytest.fixture
def ui(tmp_path: Path, git_identity: str) -> Iterator[_UiServer]:
    server = _UiServer(tmp_path)
    yield server
    server.close()


@pytest.mark.phase_3
def test_ui_binds_loopback_only(ui: _UiServer) -> None:
    assert ui.host == "127.0.0.1"
    assert ui.origin.startswith("http://127.0.0.1:")


@pytest.mark.phase_3
def test_ui_view_endpoint(tmp_path: Path, ui: _UiServer) -> None:
    proposal_id = _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    status, raw = ui.request("GET", "/api/view")
    assert status == 200
    view = LedgerView.model_validate_json(raw)
    assert view.counts["proposed"] == 1
    assert view.proposals[0].id == proposal_id


@pytest.mark.phase_3
def test_ui_confirm_moves_file(tmp_path: Path, ui: _UiServer) -> None:
    proposal_id = _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    status, raw = ui.request(
        "POST",
        f"/api/proposals/{proposal_id}/confirm",
        body=json.dumps({"confirmed_by": "alice@example.com"}).encode(),
    )
    assert status == 200
    payload = json.loads(raw)
    assert payload["id"] == proposal_id
    assert payload["status"] == "confirmed"
    assert list((tmp_path / PROPOSED_DIR).glob("dec_*.md")) == []
    assert (tmp_path / DECISIONS_DIR / f"{proposal_id}.md").is_file()

    status, raw = ui.request("GET", "/api/view")
    assert status == 200
    view = LedgerView.model_validate_json(raw)
    assert view.counts["proposed"] == 0
    assert view.counts["confirmed"] == 1
    assert view.decisions[0].id == proposal_id


@pytest.mark.phase_3
def test_ui_reject_deletes(tmp_path: Path, ui: _UiServer) -> None:
    proposal_id = _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    status, raw = ui.request(
        "POST",
        f"/api/proposals/{proposal_id}/reject",
        body=b"{}",
    )
    assert status == 200
    assert json.loads(raw)["rejected"] is True
    assert list((tmp_path / PROPOSED_DIR).glob("dec_*.md")) == []
    assert not (tmp_path / DECISIONS_DIR).exists()


@pytest.mark.phase_3
def test_ui_dismiss_removes_conflict_from_next_view(tmp_path: Path, ui: _UiServer) -> None:
    """The whole path: a flagged pair disappears from /api/view after dismissal.

    This also exercises the view cache — build_ledger_view_cached must notice
    dismissed.yml changed even though no decision file did.
    """
    _stage_conflicting_pair(tmp_path)
    status, raw = ui.request("GET", "/api/view")
    assert status == 200
    view = LedgerView.model_validate_json(raw)
    assert view.counts["related"] == 1

    status, raw = ui.request(
        "POST",
        "/api/dismiss",
        body=json.dumps(
            {
                "decision_a": "dec_tzutc",
                "decision_b": "dec_tzlocal",
                "reason": "different subsystems; storage policy is scoped per service",
                "dismissed_by": "alice@example.com",
            }
        ).encode(),
    )
    assert status == 200
    payload = json.loads(raw)
    assert payload["pair"] == "dec_tzlocal::dec_tzutc"

    status, raw = ui.request("GET", "/api/view")
    assert status == 200
    view = LedgerView.model_validate_json(raw)
    assert view.counts["related"] == 0
    assert view.counts["dismissed"] == 1
    assert view.conflicts_with_details == []


@pytest.mark.phase_3
def test_ui_dismiss_requires_reason(tmp_path: Path, ui: _UiServer) -> None:
    _stage_conflicting_pair(tmp_path)
    status, raw = ui.request(
        "POST",
        "/api/dismiss",
        body=json.dumps({"decision_a": "dec_tzutc", "decision_b": "dec_tzlocal"}).encode(),
    )
    assert status == 400
    assert "reason" in json.loads(raw)["error"]

    status, raw = ui.request("GET", "/api/view")
    assert LedgerView.model_validate_json(raw).counts["related"] == 1


@pytest.mark.phase_3
def test_ui_dismiss_rejects_malformed_ids(tmp_path: Path, ui: _UiServer) -> None:
    _stage_conflicting_pair(tmp_path)
    status, raw = ui.request(
        "POST",
        "/api/dismiss",
        body=json.dumps(
            {"decision_a": "dec_tzutc", "decision_b": "not-an-id", "reason": "x"}
        ).encode(),
    )
    assert status == 400
    assert "decision" in json.loads(raw)["error"]

    status, raw = ui.request(
        "POST",
        "/api/dismiss",
        body=json.dumps(
            {"decision_a": "dec_tzutc", "decision_b": "dec_tzutc", "reason": "x"}
        ).encode(),
    )
    assert status == 400
    assert "itself" in json.loads(raw)["error"]


@pytest.mark.phase_3
def test_ui_dismiss_requires_token(tmp_path: Path, ui: _UiServer) -> None:
    _stage_conflicting_pair(tmp_path)
    status, _ = ui.request(
        "POST",
        "/api/dismiss",
        body=json.dumps(
            {"decision_a": "dec_tzutc", "decision_b": "dec_tzlocal", "reason": "x"}
        ).encode(),
        token=None,
    )
    assert status == 403
    assert not (tmp_path / ".reasonledger" / "dismissed.yml").exists()


@pytest.mark.phase_3
def test_ui_token_required(tmp_path: Path, ui: _UiServer) -> None:
    proposal_id = _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    staged = tmp_path / PROPOSED_DIR / f"{proposal_id}.md"
    before = staged.read_text("utf-8")

    status, _ = ui.request("GET", "/api/view", token=None)
    assert status == 403
    status, _ = ui.request("GET", "/api/view", token="wrong-token")
    assert status == 403
    status, _ = ui.request(
        "POST",
        f"/api/proposals/{proposal_id}/confirm",
        body=json.dumps({"confirmed_by": "alice"}).encode(),
        token=None,
    )
    assert status == 403
    assert staged.read_text("utf-8") == before

    status, _ = ui.request(
        "POST",
        "/api/proposals/not-an-id/confirm",
        body=json.dumps({"confirmed_by": "alice"}).encode(),
    )
    assert status == 404

    status, _ = ui.request("GET", "/api/view", origin="http://evil.example")
    assert status == 403


@pytest.mark.phase_3
def test_ui_refuses_a_foreign_host_header(tmp_path: Path, ui: _UiServer) -> None:
    """DNS rebinding: the page and the token must not be served under another site's name."""
    rebound = {"Host": f"evil.example:{ui.port}"}
    for path in ("/", "/app.js", "/api/view"):
        status, body = ui.request("GET", path, headers=rebound)
        assert status == 403, path
        assert ui.token.encode() not in body
    status, _ = ui.request("POST", "/api/consent", body=b"{}", headers=rebound)
    assert status == 403
    status, _ = ui.request("GET", "/api/view", headers={"Host": f"localhost:{ui.port}"})
    assert status == 403
    status, _ = ui.request("GET", "/api/view")
    assert status == 200


@pytest.mark.phase_3
def test_status_html_export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    proposal_id = _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    out = tmp_path / "ledger.html"
    assert main(["status", "--root", str(tmp_path), "--html", str(out)]) == EXIT_PASS
    assert f"wrote {out}" in capsys.readouterr().out
    html = out.read_text("utf-8")
    assert proposal_id in html
    assert '"mode":"static"' in html
    assert '"token"' not in html
    assert "X-RL-Token" not in html
    assert "api.js" not in html
    assert "/api/" not in html
    assert "__RL_BOOTSTRAP_JSON__" not in html
    assert "__RL_TOKEN__" not in html


@pytest.mark.phase_3
def test_static_export_renders_through_shared_renderers(tmp_path: Path) -> None:
    """The export inlines render.js, so item markup cannot drift from the live UI."""
    _stage(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    out = tmp_path / "ledger.html"
    assert main(["status", "--root", str(tmp_path), "--html", str(out)]) == EXIT_PASS
    html = out.read_text("utf-8")
    assert "RLRender" in html
    assert '<script src="/render.js">' not in html


@pytest.mark.phase_3
def test_state_legend_is_present_on_both_surfaces(tmp_path: Path, ui: _UiServer) -> None:
    """Every state the UI can show has to be explained where it is shown."""
    states = (
        "proposed",
        "confirmed",
        "active",
        "pending review",
        "superseded",
        "stale",
        "orphaned",
        "conflicts",
    )

    _, raw = ui.request("GET", "/", token=None)
    live = raw.decode("utf-8")

    out = tmp_path / "ledger.html"
    assert main(["status", "--root", str(tmp_path), "--html", str(out)]) == EXIT_PASS
    export = out.read_text("utf-8")

    for surface, html in (("live", live), ("export", export)):
        assert "What do these states mean?" in html, surface
        for state in states:
            assert f"<dt>{state}</dt>" in html, f"{state} unexplained in {surface}"


@pytest.mark.phase_3
def test_ui_shows_what_a_supersede_would_retire(tmp_path: Path, ui: _UiServer) -> None:
    """Confirming a supersede retires another decision — the UI must say so first."""
    original_id = _stage(tmp_path, "docs/a.md#ts", "Timestamp policy", "UTC")
    confirm_proposed(original_id, root=tmp_path, confirmed_by="alice", confirmed_at=EXTRACTED_AT)
    staged = propose_decisions(
        [
            DecisionCandidate(
                context="Timestamp policy", choice="server-local", source_ref="docs/a.md#ts"
            )
        ],
        root=tmp_path,
        extracted_by="test/extractor",
        extracted_at=EXTRACTED_AT,
    )
    supersede_id = staged.superseded[0].proposal_id

    status, raw = ui.request("GET", "/api/view")
    assert status == 200
    proposals = {p["id"]: p for p in json.loads(raw)["proposals"]}
    assert proposals[supersede_id]["supersedes"] == original_id

    # The renderer turns that field into a warning the reviewer reads before the buttons.
    render_js = (assets_dir() / "render.js").read_text("utf-8")
    assert "retires that decision" in render_js


@pytest.mark.phase_3
def test_ui_prints_url_before_blocking(tmp_path: Path) -> None:
    """A redirected stdout is block-buffered, and serve_forever() never returns.

    Without an explicit flush the URL stays in the buffer for the entire life of the
    server, so anything that pipes or redirects `reasonledger ui` sees nothing at all.
    Only a real subprocess reproduces that — an in-process capture is never buffered
    the same way.
    """
    log = tmp_path / "ui.log"
    with log.open("wb") as sink:
        process = subprocess.Popen(
            [sys.executable, "-m", "reasonledger_cli", "ui", "--root", str(tmp_path), "--no-open"],
            stdout=sink,
            stderr=subprocess.STDOUT,
        )
    try:
        # Generous: a cold interpreter on a loaded CI runner can take well over 15s to import.
        deadline = time.monotonic() + 90
        match = None
        while time.monotonic() < deadline and match is None:
            match = re.search(r"ReasonLedger UI: (http://127\.0\.0\.1:\d+)", log.read_text("utf-8"))
            if match is None:
                time.sleep(0.05)
        assert match is not None, (
            f"url never reached the redirected stdout: {log.read_text(encoding='utf-8')!r}"
        )
        assert process.poll() is None, "server exited instead of serving"
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.phase_3
def test_ui_serves_spa_shell(ui: _UiServer) -> None:
    status, raw = ui.request("GET", "/", token=None)
    assert status == 200
    html = raw.decode("utf-8")
    assert "ReasonLedger" in html
    assert ui.token in html
    assert "__RL_BOOTSTRAP_JSON__" not in html
    assert '<script src="/api.js"></script>' in html
    status, raw = ui.request("GET", "/api.js", token=None)
    assert status == 200
    assert "RLApi" in raw.decode("utf-8")
