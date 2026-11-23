"""Static guards on the shipped UI assets.

These check the asset files themselves rather than the server, because the local plane's
two hardest-to-notice failures are invisible from the HTTP layer: an asset that reaches
off-box, and an asset that no longer runs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from reasonledger_cli.ui_html import _STATIC_APP_JS, STATIC_NAMES, assets_dir, write_status_html

_SCRIPTS = [
    "agent_card.js",
    "api.js",
    "app.js",
    "ask.js",
    "browse.js",
    "browse_refs.js",
    "config.js",
    "conflict_config.js",
    "conflicts.js",
    "consent.js",
    "judge.js",
    "ledger_list.js",
    "map.js",
    "map_actions.js",
    "map_page.js",
    "needs.js",
    "organize.js",
    "organize_actions.js",
    "organize_decisions.js",
    "organize_inbox.js",
    "organize_inbox_ui.js",
    "organize_ui.js",
    "overview.js",
    "provenance.js",
    "render.js",
    "review.js",
    "setup.js",
    "stats.js",
]
_ALL_ASSETS = [
    "index.html",
    "style.css",
    "map.css",
    "organize.css",
    "review.css",
    "stats.css",
    *_SCRIPTS,
]


@pytest.mark.phase_3
def test_renderers_are_never_handed_to_map_bare() -> None:
    """Array.map passes the index as a second argument, and a renderer may take one.

    decisionItem(d, actionsHtml) read that index as markup, so the static export printed a
    stray digit after every decision card but the first. No server test runs the JS, so the
    shape that causes it is checked in the source.
    """
    live = (assets_dir() / "ledger_list.js").read_text("utf-8")
    renderers = (assets_dir() / "render.js").read_text("utf-8")
    # Derived, not listed: a renderer is at risk exactly when it takes a second parameter.
    risky = re.findall(r"function (\w+)\([^)]*,[^)]*\)", renderers)
    assert "decisionItem" in risky, "the guard no longer sees the renderer it exists for"
    bare_map = re.compile(rf"\.map\(\s*R\.(?:{'|'.join(risky)})\b")
    assert bare_map.search(live) is None, "ledger_list.js hands a renderer straight to map"
    assert bare_map.search(_STATIC_APP_JS) is None, "static runner hands a renderer to map"
    assert "fn(row)" in _STATIC_APP_JS, "static join must forward the row alone"


@pytest.mark.phase_3
def test_ui_assets_no_external_refs() -> None:
    """The UI binds loopback and stays there — no CDN, no font host, no beacon."""
    pattern = re.compile(r"https?://")
    for name in _ALL_ASSETS:
        text = (assets_dir() / name).read_text("utf-8")
        assert pattern.search(text) is None, f"{name} has external URL"


# Everything the asset scripts may call without defining it themselves: browser globals
# plus JS keywords that look like calls. Anything else must be defined in the same file
# or reached through a member expression (`window.x()`, `R.x()`).
_JS_AMBIENT = frozenset(
    {
        "Array",
        "Boolean",
        "Date",
        "Error",
        "JSON",
        "Number",
        "Object",
        "Promise",
        "String",
        "await",
        "catch",
        "clearTimeout",
        "decodeURIComponent",
        "encodeURIComponent",
        "fetch",
        "for",
        "function",
        "if",
        "isNaN",
        "new",
        "parseFloat",
        "parseInt",
        "return",
        "setTimeout",
        "switch",
        "throw",
        "typeof",
        "while",
    }
)
_JS_CALL = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(")
_JS_DEFINE = re.compile(r"(?:function|const|let|var)\s+([A-Za-z_$][\w$]*)")
# Prose in comments and markup in string literals both read as calls to the regex above
# ("Base URL (optional)"), so they come out before the scan.
_JS_NOISE = re.compile(r"//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", re.S)


@pytest.mark.phase_3
@pytest.mark.parametrize("name", _SCRIPTS)
def test_ui_asset_defines_every_helper_it_calls(name: str) -> None:
    """Splitting a UI asset must not leave a call site behind its definition.

    The app.js split did exactly that: `apiFetch` and `promptConfirmedBy` were called but
    defined nowhere, so the live page threw on load and rendered a bare ReferenceError
    instead of the ledger. Every server-side test still passed — none of them run the JS.
    """
    source = _JS_NOISE.sub(" ", (assets_dir() / name).read_text("utf-8"))
    defined = set(_JS_DEFINE.findall(source)) | _JS_AMBIENT
    missing = sorted({call for call in _JS_CALL.findall(source) if call not in defined})
    assert missing == [], f"{name} calls undefined: {missing}"


@pytest.mark.phase_3
@pytest.mark.parametrize("name", [n for n in _SCRIPTS if n != "api.js"])
def test_only_api_js_sends_the_session_token(name: str) -> None:
    """One authenticated request, shared: three private copies had drifted into the tree."""
    source = (assets_dir() / name).read_text("utf-8")
    assert "X-RL-Token" not in source, f"{name} builds its own authenticated request"


@pytest.mark.phase_3
def test_every_shipped_asset_is_served_and_every_served_name_ships() -> None:
    """The server's allowlist and the assets folder cannot drift: a missed name is a 404."""
    shipped = {p.name for p in assets_dir().iterdir() if p.is_file()} - {"index.html"}
    assert shipped == set(STATIC_NAMES)


@pytest.mark.phase_3
def test_live_only_scripts_load_after_what_they_need_and_the_export_keeps_none() -> None:
    page = (assets_dir() / "index.html").read_text("utf-8")
    order = re.findall(r'<script src="/([a-z_]+\.js)"', page)
    assert order.index("needs.js") < order.index("app.js")  # app.js renders it on first load
    assert order.index("needs.js") < order.index("review.js") < order.index("app.js")
    assert order.index("review.js") < order.index("ledger_list.js") < order.index("app.js")
    # Ask and Overview are drawn by app.js from the lists and the search they sit on.
    assert order.index("ledger_list.js") < order.index("ask.js") < order.index("app.js")
    assert order.index("browse.js") < order.index("ask.js")
    assert order.index("stats.js") < order.index("overview.js") < order.index("app.js")
    assert order.index("judge.js") < order.index("app.js")  # app.js mounts it on the Conflicts tab
    # The queue names a proposal's conflict peers; conflicts.js asks the queue what is in force.
    assert order.index("review.js") < order.index("conflicts.js") < order.index("app.js")
    assert order.index("consent.js") > order.index("conflict_config.js")  # last Settings panel
    assert order.index("agent_card.js") > order.index("setup.js")  # reuses its prompts
    assert order.index("agent_card.js") > order.index("config.js")  # sits after the model panel


@pytest.mark.phase_3
def test_the_static_export_has_no_script_that_needs_a_server(tmp_path: Path) -> None:
    target = tmp_path / "status.html"
    write_status_html(target, {})
    assert re.findall(r'<script src="/', target.read_text("utf-8")) == []


@pytest.mark.phase_3
def test_the_export_keeps_no_live_tab_chrome(tmp_path: Path) -> None:
    target = tmp_path / "status.html"
    write_status_html(target, {})
    page = target.read_text("utf-8")
    for live_only in (
        'id="overview-pane"',
        'id="ask-pane"',
        'id="conflicts-pane"',
        'id="map-mode"',
        "data-map-mode=",
        'id="top-tabs"',
    ):
        assert live_only not in page, f"export still carries {live_only}"


@pytest.mark.phase_3
def test_every_tab_has_a_pane_and_organize_is_a_map_mode_not_a_tab() -> None:
    page = (assets_dir() / "index.html").read_text("utf-8")
    assert re.findall(r'data-tab="([a-z]+)"', page) == [
        "overview",
        "review",
        "conflicts",
        "ask",
        "map",
        "settings",
    ]
    assert re.findall(r'data-map-mode="([a-z]+)"', page) == ["map", "organize"]
    app = (assets_dir() / "app.js").read_text("utf-8")
    for pane in ("overview-pane", "conflicts-pane", "ask-pane", "map-pane", "settings-pane"):
        assert f'id="{pane}"' in page
        assert f'"{pane}"' in app


@pytest.mark.phase_3
def test_review_groups_decisions_by_folder_and_points_at_the_map_tab() -> None:
    source = (assets_dir() / "browse.js").read_text("utf-8")
    assert 'data-open-tab="map"' in source
    assert "topic" not in source.lower()
