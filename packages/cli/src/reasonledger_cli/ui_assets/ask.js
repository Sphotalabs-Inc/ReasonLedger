/* ReasonLedger Ask — look a decision up, and browse the whole ledger through one filter.
 *
 * Live mode only. The search and the Why box are browse.js's; this file decides which
 * records they see. One select replaces a row of count chips and six stacked sections:
 * the decision filters narrow what the search covers, and the side lists (orphaned, stale)
 * take the search's place while they are chosen.
 */
(function (global) {
  const esc = global.RLRender.escapeHtml;

  const DECISION_FILTERS = [
    {
      key: "all",
      label: "Active decisions",
      // What it replaced rides on its card; replaced and retired ones are under History.
      keep: global.RLLedger.isInForce,
    },
    { key: "pending", label: "Needs review", keep: global.RLNeeds.isPending },
    {
      key: "judged",
      label: "Judged by a person",
      keep: function (d) {
        return d.oversight !== "pending" && global.RLLedger.isInForce(d);
      },
    },
    {
      key: "history",
      label: "History (retired or superseded)",
      keep: function (d) {
        return d.status === "retired" || d.status === "superseded";
      },
    },
  ];

  /** What the page was last drawn from, so a filter change can redraw without a reload. */
  const state = { pane: null, view: null, ctx: null, filter: "all" };

  function decisionFilter(key) {
    return DECISION_FILTERS.filter(function (f) {
      return f.key === key;
    })[0];
  }

  /** "All decisions" always; every other choice only while it holds something. */
  function options(view) {
    const decisions = view.decisions || [];
    const counted = DECISION_FILTERS.map(function (f) {
      return { key: f.key, label: f.label, count: decisions.filter(f.keep).length };
    });
    return counted
      .filter(function (o) {
        return o.key === "all" || o.count > 0;
      })
      .concat(global.RLLedger.sideLists(view));
  }

  function filterHtml(choices) {
    return (
      '<p class="ask-filter"><label for="ask-filter">Show</label> <select id="ask-filter">' +
      choices
        .map(function (o) {
          return (
            '<option value="' +
            esc(o.key) +
            '"' +
            (o.key === state.filter ? " selected" : "") +
            ">" +
            esc(o.label + " (" + o.count + ")") +
            "</option>"
          );
        })
        .join("") +
      "</select></p>"
    );
  }

  function draw() {
    const view = state.view;
    if (!state.pane || !view) return;
    if (global.RLLedger.isEmpty(view)) {
      state.pane.innerHTML =
        '<div class="layout"><p class="hint">No decisions to look up yet. The Overview tab ' +
        "shows how to record the first one.</p></div>";
      return;
    }
    const choices = options(view);
    if (!choices.some(function (o) { return o.key === state.filter; })) state.filter = "all";
    const chosen = decisionFilter(state.filter);
    state.pane.innerHTML =
      '<div class="layout">' +
      filterHtml(choices) +
      (chosen ? '<div id="browse-root"></div>' : global.RLLedger.sideListHtml(view, state.filter)) +
      "</div>";
    document.getElementById("ask-filter").addEventListener("change", function (ev) {
      state.filter = ev.currentTarget.value;
      draw();
    });
    if (chosen) {
      const shown = { decisions: (view.decisions || []).filter(chosen.keep) };
      global.RLBrowse.mount(shown, state.ctx.request, state.ctx.verdict, view.decisions || []);
    }
  }

  /** `ctx` is {request(path), verdict(id, kind)} from app.js. */
  function render(pane, view, ctx) {
    state.pane = pane;
    state.view = view;
    state.ctx = ctx;
    draw();
  }

  function show(filter) {
    state.filter = filter;
    draw();
  }

  /** Search every decision for this text; an id leads with that decision. */
  function find(text) {
    global.RLBrowse.setQuery(text);
    // An id may name a replaced or retired decision, which only History lists.
    const named = ((state.view && state.view.decisions) || []).filter(function (d) {
      return d.id === text;
    })[0];
    show(named && !global.RLLedger.isInForce(named) ? "history" : "all");
  }

  /** Ask why about a file, line or symbol, from anywhere in the app. */
  async function why(target) {
    if (!decisionFilter(state.filter)) show("all");
    await global.RLBrowse.ask(target);
    draw();
  }

  global.RLAsk = { render: render, show: show, find: find, why: why };
})(window);
