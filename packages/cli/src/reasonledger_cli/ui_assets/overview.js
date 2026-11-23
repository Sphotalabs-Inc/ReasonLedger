/* ReasonLedger Overview — the landing page: where the ledger stands, then what to do next.
 *
 * Live mode only. The charts lead because they answer "where does this ledger stand" at a
 * glance; under them sit what may be waiting on a person (approvals, conflicts) and the one
 * question the product exists to answer. An empty ledger has nothing to chart, so it gets the
 * Getting started checklist alone.
 */
(function (global) {
  const R = global.RLRender;
  const esc = R.escapeHtml;

  function waitingHtml(count) {
    if (!count) {
      return '<section class="overview-cta"><span>Nothing is waiting on you.</span></section>';
    }
    return (
      '<section class="overview-cta is-waiting"><span><strong>' +
      esc(count) +
      "</strong> " +
      (count === 1 ? "item is" : "items are") +
      ' waiting on your review</span><button type="button" class="primary" ' +
      'data-open-tab="review">Start reviewing</button></section>'
    );
  }

  function whyHtml() {
    return (
      '<section class="why-card"><h2 class="why-card-title">Why does this code look like this?</h2>' +
      '<form class="why-form" id="overview-why"><input name="target" autocomplete="off" ' +
      'placeholder="A file, optionally with :line or ::function" ' +
      'aria-label="File, line or symbol" />' +
      '<button type="submit" class="primary">Ask</button></form></section>'
    );
  }

  /** Conflicts found, or pairs nobody has checked: either is a reason to open Conflicts. */
  function conflictsHtml(view) {
    const found = global.RLConflicts.count(view);
    const unjudged = (view.counts || {}).unverified || 0;
    if (found) {
      return (
        '<section class="overview-cta is-waiting"><span><strong>' + esc(found) + "</strong> " +
        (found === 1 ? "conflict" : "conflicts") + " between decisions to settle</span>" +
        '<button type="button" class="primary" data-open-tab="conflicts">Settle conflicts</button></section>'
      );
    }
    if (!unjudged) return "";
    return (
      '<section class="overview-cta"><span><strong>' + esc(unjudged) + "</strong> related " +
      (unjudged === 1 ? "pair has" : "pairs have") + " not been checked for conflicts</span>" +
      '<button type="button" class="secondary" data-open-tab="conflicts">Check them</button></section>'
    );
  }

  /** The lists that are not decisions waiting on anyone, as links into the Ask tab. */
  function alsoHtml(view) {
    const lists = global.RLLedger.sideLists(view);
    if (!lists.length) return "";
    return (
      '<p class="hint">Also in the ledger: ' +
      lists
        .map(function (list) {
          return (
            '<a href="#" data-open-tab="ask" data-ask-filter="' +
            esc(list.key) +
            '">' +
            esc(list.count + " " + list.label.toLowerCase()) +
            "</a>"
          );
        })
        .join(" · ") +
      "</p>"
    );
  }

  /** `ctx` is {toolbarHtml, request(path), why(target)} from app.js. */
  function render(pane, view, ctx) {
    const firstRun = global.RLLedger.isEmpty(view);
    // Hash-matched hints are far noisier than the configured model's; say so rather
    // than let a degraded run pass for the real thing.
    pane.innerHTML =
      '<div class="layout">' +
      R.embedderNotice(view) +
      (firstRun
        ? '<div id="setup-root"></div><div class="toolbar">' +
          '<span class="muted">This page fills in once your agent records a decision.</span>'
        : '<div id="stats-root"></div>' +
          waitingHtml(global.RLLedger.waitingCount(view)) +
          conflictsHtml(view) +
          whyHtml() +
          alsoHtml(view) +
          '<div id="setup-root"></div><div class="toolbar">') +
      ctx.toolbarHtml +
      "</div></div>";
    global.RLSetup.mountChecklist(document.getElementById("setup-root"));
    if (firstRun) return;
    global.RLStats.mount(document.getElementById("stats-root"), ctx.request);
    document.getElementById("overview-why").addEventListener("submit", function (ev) {
      ev.preventDefault();
      ctx.why((ev.currentTarget.elements.target.value || "").trim());
    });
  }

  global.RLOverview = { render: render };
})(window);
