"""Shared SPA HTML rendering for `reasonledger ui` and `status --html`."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

_BOOTSTRAP_MARKER = "__RL_BOOTSTRAP_JSON__"
_LOGO_MARKER = "__RL_LOGO_SRC__"
_ASSETS_DIR = Path(__file__).resolve().parent / "ui_assets"
_LOGO_PATH = _ASSETS_DIR / "logo.svg"
# Static export must stay one self-contained file — no separate
# asset request the exported HTML could outlive or be moved away from.
_LOGO_STATIC_MIME = "image/svg+xml"

# Static-export-only runner. It renders through the same `render.js` the live app
# uses — only the orchestration differs — so item markup cannot drift between the
# two surfaces. It exists separately from `app.js` because `app.js` carries the
# CSRF header name and the API path builder, neither of which may appear in an
# export (see `test_status_html_export`).
_STATIC_APP_JS = """
(function () {
  var root = document.getElementById("app");
  var bootEl = document.getElementById("rl-bootstrap");
  if (!root || !bootEl) return;
  var boot = JSON.parse(bootEl.textContent || "{}");
  var view = boot.view;
  if (!view) {
    root.textContent = "No view data in export.";
    return;
  }
  var R = window.RLRender;
  // Forwards the row alone: Array.map also passes the index, which a renderer with a
  // second parameter (decisionItem's actionsHtml) would take as markup.
  function join(rows, fn) {
    return (rows || [])
      .map(function (row) {
        return fn(row);
      })
      .join("");
  }
  function size(rows) {
    return (rows || []).length;
  }
  // The detailed pairs carry both sides' text; the bare lists only have ids.
  var conflicts = view.conflicts_with_details || view.conflicts;
  var related = view.related_with_details || view.related;
  function pair(c) {
    return R.conflictItem(c, "");
  }
  root.innerHTML =
    '<p class="static-banner">Read-only export — mutations and why are disabled.</p>' +
    R.relatedNotices(view) +
    R.countsList(view.counts || {}) +
    R.section(
      "Proposals",
      null,
      join(view.proposals, function (p) {
        return R.proposalItem(p, "");
      }),
      "no proposals — run `reasonledger import`",
      size(view.proposals),
      false,
      "section-proposals"
    ) +
    R.section(
      "Decisions",
      null,
      join(view.decisions, R.decisionItem),
      "no confirmed decisions yet",
      size(view.decisions),
      false,
      "section-decisions"
    ) +
    R.section(
      "Stale & Watchers",
      null,
      join(view.stale, R.decisionItem) + join(view.watchers, R.watcherItem),
      "no stale decisions or watchers",
      size(view.stale) + size(view.watchers),
      false,
      "section-stale"
    ) +
    R.section(
      "Orphaned",
      "the code these decisions point at is gone — re-target or retire them",
      join(view.orphaned, R.orphanItem),
      "no orphaned decisions",
      size(view.orphaned),
      false,
      "section-orphaned"
    ) +
    R.section(
      "Conflicts",
      R.CONFLICTS_HINT,
      join(conflicts, pair),
      "no conflicts found among judged pairs",
      size(conflicts),
      size(conflicts) > 0,
      "section-conflicts"
    ) +
    R.section(
      "Related decisions",
      R.RELATED_HINT,
      join(related, pair),
      "no related decisions",
      size(related),
      false,
      "section-related"
    );
})();
"""


# The files the server may serve from the assets folder; anything else is a 404.
STATIC_NAMES = frozenset(
    {
        "api.js",
        "app.js",
        "ask.js",
        "browse.js",
        "browse_refs.js",
        "config.js",
        "consent.js",
        "conflict_config.js",
        "conflicts.js",
        "agent_card.js",
        "ledger_list.js",
        "map.css",
        "map.js",
        "map_actions.js",
        "map_page.js",
        "needs.js",
        "organize.css",
        "organize.js",
        "organize_actions.js",
        "organize_decisions.js",
        "organize_inbox.js",
        "organize_inbox_ui.js",
        "organize_ui.js",
        "overview.js",
        "provenance.js",
        "render.js",
        "review.css",
        "review.js",
        "setup.js",
        "stats.css",
        "stats.js",
        "style.css",
        "judge.js",
        "logo.svg",
    }
)


def assets_dir() -> Path:
    return _ASSETS_DIR


def _logo_data_uri() -> str:
    encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:{_LOGO_STATIC_MIME};base64,{encoded}"


def render_spa_html(*, token: str | None = None, view: dict[str, Any] | None = None) -> str:
    """Build index.html with a JSON bootstrap (live token or static inlined view).

    The live server serves the logo as a same-origin static asset (``/logo.svg``);
    the static export inlines it as a data URI so the exported file has no
    dependency on anything outside itself.
    """
    if token is not None:
        bootstrap: dict[str, Any] = {"mode": "live", "token": token}
        logo_src = "/logo.svg"
    elif view is not None:
        bootstrap = {"mode": "static", "view": view}
        logo_src = _logo_data_uri()
    else:
        msg = "render_spa_html requires token or view"
        raise ValueError(msg)
    template = (_ASSETS_DIR / "index.html").read_text(encoding="utf-8")
    payload = json.dumps(bootstrap, separators=(",", ":")).replace("<", "\\u003c")
    html = template.replace(_BOOTSTRAP_MARKER, payload)
    return html.replace(_LOGO_MARKER, logo_src)


def write_status_html(path: Path, view_dump: dict[str, Any]) -> None:
    """Write a read-only self-contained HTML export (no token, no API endpoints)."""
    html = render_spa_html(view=view_dump)
    css = (_ASSETS_DIR / "style.css").read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="/style.css" />',
        f"<style>\n{css}\n</style>",
    )
    for pure in ("provenance.js", "render.js"):
        source = (_ASSETS_DIR / pure).read_text(encoding="utf-8")
        html = html.replace(f'<script src="/{pure}"></script>', f"<script>\n{source}\n</script>")
    html = html.replace(
        '<script src="/app.js"></script>',
        f"<script>\n{_STATIC_APP_JS}\n</script>",
    )
    # Both settings panels are dropped rather than inlined: an export has no server to
    # save to, so either form would be a dead control — the same reason Refresh is
    # live-only. Top tabs / settings host are live chrome too (would be dead buttons).
    html = html.replace('\n    <script src="/api.js"></script>', "")
    html = html.replace('\n    <script src="/browse_refs.js"></script>', "")
    html = html.replace('\n    <script src="/browse.js"></script>', "")
    html = html.replace('\n    <script src="/config.js"></script>', "")
    html = html.replace('\n    <script src="/conflict_config.js"></script>', "")
    html = html.replace('\n    <script src="/setup.js"></script>', "")
    html = html.replace('\n    <script src="/consent.js"></script>', "")
    html = html.replace('\n    <script src="/needs.js"></script>', "")
    html = html.replace('\n    <script src="/review.js"></script>', "")
    for name in ("ledger_list", "conflicts", "ask", "overview", "judge"):
        html = html.replace(f'\n    <script src="/{name}.js"></script>', "")
    html = html.replace('\n    <link rel="stylesheet" href="/review.css" />', "")
    # The summary strip reads /api/stats, which an export does not have.
    html = html.replace('\n    <script src="/stats.js"></script>', "")
    html = html.replace('\n    <link rel="stylesheet" href="/stats.css" />', "")
    html = html.replace('\n    <script src="/agent_card.js"></script>', "")
    # The module map is live-only too: it reads two endpoints an export does not have.
    html = html.replace('\n    <link rel="stylesheet" href="/map.css" />', "")
    html = html.replace('\n    <link rel="stylesheet" href="/organize.css" />', "")
    html = html.replace('\n    <script src="/organize_ui.js"></script>', "")
    for name in ("organize_actions", "organize_inbox_ui", "organize_inbox", "organize_decisions"):
        html = html.replace(f'\n    <script src="/{name}.js"></script>', "")
    html = html.replace('\n    <script src="/organize.js"></script>', "")
    html = html.replace('\n    <div id="organize-pane" class="map-pane" hidden></div>', "")
    html = html.replace('\n    <script src="/map.js"></script>', "")
    html = html.replace('\n    <script src="/map_actions.js"></script>', "")
    html = html.replace('\n    <script src="/map_page.js"></script>', "")
    html = html.replace('\n    <div id="map-pane" class="map-pane" hidden></div>', "")
    html = html.replace('\n    <div id="overview-pane" hidden></div>', "")
    html = html.replace('\n    <div id="ask-pane" hidden></div>', "")
    html = html.replace('\n    <div id="conflicts-pane" hidden></div>', "")
    html = re.sub(r'\n\s*<div id="map-mode"[\s\S]*?</div>', "", html, count=1)
    html = re.sub(
        r"\n\s*<nav class=\"top-tabs\"[\s\S]*?</nav>",
        "",
        html,
        count=1,
    )
    html = html.replace(
        '\n    <div id="settings-pane" class="settings-pane" hidden></div>',
        "",
    )
    path.write_text(html, encoding="utf-8")
