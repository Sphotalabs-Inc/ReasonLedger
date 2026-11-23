"""`reasonledger ui` — stdlib-only localhost review UI over LedgerView."""

from __future__ import annotations

import json
import re
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.reasoning import parse_target, resolve_why, why_payload
from reasonledger_core.reasoning.why import WhyQueryError
from reasonledger_core.views import build_ledger_view_cached

from reasonledger_cli.conflict_config_ui import (
    handle_get_conflict_config,
    handle_post_conflict_config,
)
from reasonledger_cli.ui_approve import handle_decision_action
from reasonledger_cli.ui_config import (
    handle_get_config,
    handle_post_config,
    handle_test_config,
)
from reasonledger_cli.ui_html import STATIC_NAMES, assets_dir, render_spa_html
from reasonledger_cli.ui_identity import handle_get_identity
from reasonledger_cli.ui_judge import JudgeSession
from reasonledger_cli.ui_map import handle_get_map, handle_get_module
from reasonledger_cli.ui_organize import OrganizeSession
from reasonledger_cli.ui_proposals import handle_confirm, handle_dismiss, handle_reject
from reasonledger_cli.ui_setup import (
    handle_get_consent,
    handle_get_setup,
    handle_post_consent,
    handle_post_map_scan,
)
from reasonledger_cli.ui_stats import handle_get_stats

EXIT_PASS = 0
EXIT_USAGE = 2

_DECISION_ID_RE = re.compile(r"^dec_[a-z0-9]+$")
_TOKEN_HEADER = "X-RL-Token"
_ORGANIZE = "/api/organize/"
_JUDGE = "/api/judge/"
_PROPOSALS = "/api/proposals/"
_DECISIONS = "/api/decisions/"
_CONTENT_TYPES = {
    "html": "text/html; charset=utf-8",
    "js": "application/javascript; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "svg": "image/svg+xml",
}


def _json_error(message: str) -> bytes:
    return json.dumps({"error": message}).encode("utf-8")


def make_ui_handler(*, root: Path, token: str, origin: str) -> type[BaseHTTPRequestHandler]:
    """Build a request handler closed over repo root, CSRF token, and origin."""
    asset_root = assets_dir()
    organize = OrganizeSession(root)
    judge = JudgeSession(root)
    expected_host = urlparse(origin).netloc

    class UiHandler(BaseHTTPRequestHandler):
        server_version = "ReasonLedgerUI/0.1"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def parse_request(self) -> bool:
            """Refuse any Host other than the one this server was bound under.

            A page on another site can make a browser resolve its own name to 127.0.0.1 (DNS
            rebinding); the browser then treats this server as that site's origin and a plain GET
            carries no Origin header. The Host header still names the attacker's domain, and it is
            the one thing such a page cannot rewrite.
            """
            if not super().parse_request():
                return False
            if self.headers.get("Host") == expected_host:
                return True
            self._send_error_json(403, f"forbidden: open this UI at {origin}")
            return False

        def _send(
            self,
            status: int,
            body: bytes,
            content_type: str,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, payload: dict[str, Any] | list[Any] | str) -> None:
            if isinstance(payload, str):
                body = payload.encode("utf-8")
            else:
                body = json.dumps(payload).encode("utf-8")
            self._send(status, body, _CONTENT_TYPES["json"])

        def _send_error_json(self, status: int, message: str) -> None:
            self._send(status, _json_error(message), _CONTENT_TYPES["json"])

        def _check_api_guards(self) -> bool:
            got = self.headers.get(_TOKEN_HEADER)
            if got != token:
                self._send_error_json(403, "forbidden")
                return False
            req_origin = self.headers.get("Origin")
            if req_origin is not None and req_origin != origin:
                self._send_error_json(403, "forbidden")
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path in {"/", "/index.html"}:
                body = render_spa_html(token=token).encode("utf-8")
                self._send(200, body, _CONTENT_TYPES["html"])
                return
            if path.lstrip("/") in STATIC_NAMES:
                name = path.lstrip("/")
                data = (asset_root / name).read_bytes()
                ext = name.rsplit(".", 1)[-1]
                ctype = _CONTENT_TYPES.get(ext, "application/octet-stream")
                self._send(200, data, ctype)
                return
            if path.startswith("/api/"):
                if not self._check_api_guards():
                    return
                if path == "/api/view":
                    view = build_ledger_view_cached(root)
                    self._send_json(200, view.model_dump_json())
                    return
                if path.startswith(_ORGANIZE):
                    self._send_json(*organize.get(path[len(_ORGANIZE) :], parse_qs(parsed.query)))
                    return
                if path == "/api/stats":
                    self._send_json(*handle_get_stats(root))
                    return
                if path == "/api/judge":
                    self._send_json(*judge.get())
                    return
                if path == "/api/map":
                    self._send_json(*handle_get_map(root))
                    return
                if path == "/api/map/module":
                    module_ids = parse_qs(parsed.query).get("id", [""])
                    self._send_json(*handle_get_module(root, module_ids[0]))
                    return
                if path == "/api/config":
                    self._send_json(*handle_get_config(root))
                    return
                if path == "/api/identity":
                    self._send_json(*handle_get_identity(root))
                    return
                if path == "/api/setup":
                    self._send_json(*handle_get_setup(root))
                    return
                if path == "/api/consent":
                    self._send_json(*handle_get_consent(root))
                    return
                if path == "/api/conflict-config":
                    self._send_json(*handle_get_conflict_config(root))
                    return
                if path == "/api/why":
                    targets = parse_qs(parsed.query).get("target", [])
                    if not targets or not targets[0].strip():
                        self._send_error_json(400, "missing target")
                        return
                    target_raw = targets[0]
                    try:
                        why_target = parse_target(target_raw)
                    except WhyQueryError as exc:
                        self._send_error_json(400, str(exc))
                        return
                    records = load_decisions_from_dir(root / DECISIONS_DIR)
                    hits = resolve_why(records, why_target, root=root)
                    self._send_json(
                        200, why_payload(target_raw, why_target, hits, root=root, records=records)
                    )
                    return
                self._send_error_json(404, "not found")
                return
            self._send_error_json(404, "not found")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if not path.startswith("/api/"):
                self._send_error_json(405, "method not allowed")
                return
            if not self._check_api_guards():
                return
            if path.startswith(_ORGANIZE):
                body = self._read_json_body()
                if body is None:
                    return
                self._send_json(*organize.post(path[len(_ORGANIZE) :], body))
                return
            if path.startswith(_JUDGE):
                body = self._read_json_body()
                if body is not None:
                    self._send_json(*judge.post(path[len(_JUDGE) :], body))
                return
            if path == "/api/config/test":
                self._send_json(*handle_test_config(root))
                return
            if path == "/api/map/scan":
                self._send_json(*handle_post_map_scan(root))
                return
            if path == "/api/consent":
                body = self._read_json_body()
                if body is None:
                    return
                self._send_json(*handle_post_consent(root, body))
                return
            if path == "/api/config":
                body = self._read_json_body()
                if body is None:
                    return
                self._send_json(*handle_post_config(root, body))
                return
            if path == "/api/conflict-config":
                body = self._read_json_body()
                if body is None:
                    return
                self._send_json(*handle_post_conflict_config(root, body))
                return
            if path.startswith(_PROPOSALS):
                self._post_proposal(path[len(_PROPOSALS) :])
                return
            if path.startswith(_DECISIONS):
                self._post_decision(path[len(_DECISIONS) :])
                return
            if path == "/api/dismiss":
                self._post_dismiss()
                return
            self._send_error_json(404, "not found")

        def do_PUT(self) -> None:  # noqa: N802
            if urlparse(self.path).path.startswith("/api/") and not self._check_api_guards():
                return
            self._send_error_json(405, "method not allowed")

        def do_DELETE(self) -> None:  # noqa: N802
            if urlparse(self.path).path.startswith("/api/") and not self._check_api_guards():
                return
            self._send_error_json(405, "method not allowed")

        def _read_json_body(self) -> dict[str, Any] | None:
            length_raw = self.headers.get("Content-Length", "0")
            try:
                length = int(length_raw)
            except ValueError:
                self._send_error_json(400, "invalid content length")
                return None
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_error_json(400, "invalid json")
                return None
            if not isinstance(data, dict):
                self._send_error_json(400, "body must be an object")
                return None
            return data

        def _decision_id(self, raw: object) -> str | None:
            """The id if it is well formed; otherwise answers 404 and returns None."""
            if isinstance(raw, str) and _DECISION_ID_RE.match(raw):
                return raw
            self._send_error_json(404, "unknown id")
            return None

        def _post_proposal(self, rest: str) -> None:
            decision_id, _, action = rest.partition("/")
            if self._decision_id(decision_id) is None:
                return
            if action == "confirm":
                self._send_json(*handle_confirm(root, decision_id))
            elif action == "reject":
                self._send_json(*handle_reject(root, decision_id))
            else:
                self._send_error_json(404, "not found")

        def _post_decision(self, rest: str) -> None:
            decision_id, _, action = rest.partition("/")
            if self._decision_id(decision_id) is None:
                return
            body = self._read_json_body()
            if body is not None:
                self._send_json(*handle_decision_action(root, decision_id, action, body))

        def _post_dismiss(self) -> None:
            body = self._read_json_body()
            if body is None:
                return
            pair = [body.get("decision_a"), body.get("decision_b")]
            if not all(isinstance(i, str) and _DECISION_ID_RE.match(i) for i in pair):
                self._send_error_json(400, "decision_a and decision_b must be decision ids")
                return
            self._send_json(*handle_dismiss(root, body, str(pair[0]), str(pair[1])))

    return UiHandler


class _BindProbeHandler(BaseHTTPRequestHandler):
    """Placeholder so ThreadingHTTPServer can bind before the real handler is set."""

    def do_GET(self) -> None:  # noqa: N802
        self.send_error(503)


def create_ui_server(*, root: Path, port: int = 0) -> tuple[ThreadingHTTPServer, str, str]:
    """Bind loopback-only UI server. Returns (server, token, origin_url)."""
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(("127.0.0.1", port), _BindProbeHandler)
    host_raw, bound_port = server.server_address[:2]
    host = host_raw.decode("ascii") if isinstance(host_raw, bytes) else str(host_raw)
    origin = f"http://{host}:{bound_port}"
    server.RequestHandlerClass = make_ui_handler(root=root, token=token, origin=origin)
    return server, token, origin


def run_ui_cmd(*, root: Path, port: int = 0, no_open: bool = False) -> int:
    """Serve the interactive ledger UI until interrupted."""
    if not root.is_dir():
        print(f"error: root is not a directory: {root}", file=sys.stderr)
        return EXIT_USAGE
    server, _token, origin = create_ui_server(root=root, port=port)
    # Flushed explicitly: serve_forever() blocks indefinitely, so a buffered stdout
    # (any redirect or pipe) would withhold the URL for the whole life of the server.
    print(f"ReasonLedger UI: {origin}")
    print("Press Ctrl+C to stop.", flush=True)
    if not no_open:
        webbrowser.open(origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return EXIT_PASS
