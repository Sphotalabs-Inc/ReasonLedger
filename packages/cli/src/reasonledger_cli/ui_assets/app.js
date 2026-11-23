/* ReasonLedger local UI — the live app: the tabs, what each is drawn from, and the actions.
 *
 * The static export has its own runner in ui_html.py and never loads this file.
 */
(function () {
  const root = document.getElementById("app");
  const bootEl = document.getElementById("rl-bootstrap");
  if (!root || !bootEl) return;

  let boot;
  try {
    boot = JSON.parse(bootEl.textContent || "{}");
  } catch (err) {
    root.textContent = "Failed to parse bootstrap.";
    return;
  }

  const isLive = boot.mode === "live";

  /** Build /api/... without embedding the contiguous "/api/" marker (static export). */
  function apiPath(parts) {
    return ["", "api"].concat(parts).join("/");
  }

  const R = window.RLRender;
  const escapeHtml = R.escapeHtml;

  const apiFetch = window.RLApi.request;

  /** Who the server will record actions as: its git identity, fetched with each view. */
  let identity = { name: null, hint: "" };
  let decisionsById = {};

  /** Who the server will record the action as, or nothing after saying how to set it. */
  function actingName() {
    if (!identity.name) window.alert(identity.hint);
    return identity.name;
  }

  /** Say what just happened and who it was recorded as; the card itself keeps the same line. */
  function announce(message) {
    let note = byId("action-notice");
    if (!note) {
      note = document.createElement("p");
      note.id = "action-notice";
      note.className = "action-notice";
      note.setAttribute("role", "status");
      root.before(note);
    }
    note.textContent = message;
  }

  function promptDismissReason() {
    const reason = window.prompt(
      "Why is this not a real conflict? (required — committed to .reasonledger/dismissed.yml)"
    );
    if (reason == null) return null;
    const trimmed = reason.trim();
    return trimmed || null;
  }

  /** Tab name → the element that holds it. Map has two: the tiles, and Edit map. */
  const PANES = {
    overview: "overview-pane",
    review: "app",
    conflicts: "conflicts-pane",
    ask: "ask-pane",
    map: "map-pane",
    settings: "settings-pane",
  };

  /** True while the ledger is empty: Overview then shows setup alone, and no legend. */
  let firstRun = false;
  /** Which half of the Map tab is showing: "map" (the tiles) or "organize" (Edit map). */
  let mapMode = "map";

  function byId(id) {
    return document.getElementById(id);
  }

  /** Approve, retire or supersede through the review dialog, then redraw; `map` is reloaded if given. */
  function openVerdict(id, kind, map, successor) {
    const decision = decisionsById[id];
    if (!decision) return;
    window.RLReview.open(decision, kind || "approve", {
      identity: identity,
      request: apiFetch,
      successor: successor,
      done: async function () {
        await refresh();
        if (map) await map.reload("Approved " + id);
      },
    });
  }

  function showTab(name) {
    byId("top-tabs")
      .querySelectorAll(".top-tab")
      .forEach(function (btn) {
        btn.classList.toggle("is-active", btn.getAttribute("data-tab") === name);
      });
    Object.keys(PANES).forEach(function (tab) {
      byId(PANES[tab]).hidden = tab !== name;
    });
    const onMap = name === "map";
    const organizing = mapMode === "organize";
    byId("map-mode").hidden = !onMap;
    byId("map-pane").hidden = !onMap || organizing;
    byId("organize-pane").hidden = !onMap || !organizing;
    byId("map-mode")
      .querySelectorAll("[data-map-mode]")
      .forEach(function (btn) {
        btn.setAttribute("aria-pressed", String(btn.getAttribute("data-map-mode") === mapMode));
      });
    if (onMap && organizing) window.RLOrganize.show(byId("organize-pane"), apiFetch);
    if (onMap && !organizing) {
      window.RLMap.show(byId("map-pane"), apiFetch, {
        review: function (id, map) {
          openVerdict(id, "approve", map);
        },
        // The Overview strip counts decisions per module, which an edit made here moves.
        changed: function () {
          refresh().catch(function () {});
        },
      });
    }
    // The state names are used on the charts and wherever records are listed.
    const legend = document.querySelector(".legend");
    if (legend) legend.hidden = firstRun || name === "map" || name === "settings";
  }

  function activeTab() {
    const active = byId("top-tabs").querySelector(".top-tab.is-active");
    return active ? active.getAttribute("data-tab") : "overview";
  }

  /** Links that cross tabs: a tab link, the Map's mode switch, and a link to one record. */
  function onNavigate(ev) {
    const go = ev.target.closest("[data-open-tab]");
    if (go) {
      ev.preventDefault();
      if (go.getAttribute("data-ask-filter")) window.RLAsk.show(go.getAttribute("data-ask-filter"));
      showTab(go.getAttribute("data-open-tab"));
      window.scrollTo(0, 0);
      return;
    }
    const mode = ev.target.closest("[data-map-mode]");
    if (mode) {
      mapMode = mode.getAttribute("data-map-mode");
      showTab("map");
      return;
    }
    const link = ev.target.closest("a.item-link");
    const href = link ? link.getAttribute("href") || "" : "";
    if (href.indexOf("#item-") !== 0) return;
    const target = byId(href.slice(1));
    if (target && root.contains(target)) {
      // Waiting on a person, so its card is in the queue: open the row and let the jump land.
      showTab("review");
      for (let el = target; el && el !== root; el = el.parentElement) {
        if (el.tagName === "DETAILS") el.open = true;
      }
      return;
    }
    // Anything settled is found by its id in Ask, which leads with that decision.
    ev.preventDefault();
    window.RLAsk.find(href.slice("#item-".length));
    showTab("ask");
    window.scrollTo(0, 0);
  }

  function initTabs() {
    const tabs = byId("top-tabs");
    tabs.hidden = false;
    tabs.querySelectorAll(".top-tab").forEach(function (btn) {
      btn.addEventListener("click", function () {
        showTab(btn.getAttribute("data-tab"));
      });
    });
    showTab("overview");
  }

  /** A tab that has something for a person to do says how much. */
  function tabCount(tab, label, count) {
    byId("top-tabs").querySelector('[data-tab="' + tab + '"]').innerHTML =
      label + (count ? ' <span class="tab-count">' + escapeHtml(count) + "</span>" : "");
  }

  function render(view) {
    firstRun = window.RLLedger.isEmpty(view);
    tabCount("review", "Review", window.RLLedger.waitingCount(view));
    tabCount("conflicts", "Conflicts", window.RLConflicts.count(view));
    const actingHtml = identity.name
      ? '<span class="acting-as">Acting as <strong>' + escapeHtml(identity.name) + "</strong> (git)</span>"
      : '<span class="acting-as error">' + escapeHtml(identity.hint) + "</span>";
    window.RLOverview.render(byId("overview-pane"), view, {
      toolbarHtml:
        actingHtml + '<button type="button" class="refresh-btn secondary" id="refresh-btn">↻ Refresh</button>',
      request: apiFetch,
      why: function (target) {
        window.RLAsk.why(target);
        showTab("ask");
      },
    });
    root.innerHTML = '<div class="layout">' + window.RLLedger.queueHtml(view) + "</div>";
    window.RLSetup.bindCopy(root);
    window.RLAsk.render(byId("ask-pane"), view, { request: apiFetch, verdict: openVerdict });
    const conflictsPane = byId("conflicts-pane");
    conflictsPane.innerHTML = '<div class="layout">' + window.RLConflicts.html(view) + "</div>";
    window.RLSetup.bindCopy(conflictsPane);
    if (byId("judge-root")) {
      window.RLJudge.mount(byId("judge-root"), view, {
        request: apiFetch,
        // A check that finds a conflict, or ends, changes the lists and the tab's count.
        changed: function () {
          refresh().catch(function () {});
        },
      });
    }
    showTab(activeTab());
    byId("refresh-btn").addEventListener("click", function () {
      refresh().catch(function (err) {
        window.alert(err.message || String(err));
      });
    });
  }

  async function refresh() {
    const loaded = await Promise.all([apiFetch(apiPath(["view"])), apiFetch(apiPath(["identity"]))]);
    identity = loaded[1];
    decisionsById = {};
    (loaded[0].decisions || []).forEach(function (d) {
      decisionsById[d.id] = d;
    });
    render(loaded[0]);
  }

  /** One handler for every data-action button, wherever a list draws it. */
  async function onAction(ev) {
    const btn = ev.target.closest("[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    try {
      if (action === "confirm") {
        const id = btn.getAttribute("data-id");
        if (!id) return;
        const who = actingName();
        if (!who) return;
        await apiFetch(apiPath(["proposals", id, "confirm"]), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
        announce("Confirmed " + id + " as " + who + ".");
      } else if (action === "reject") {
        const id = btn.getAttribute("data-id");
        if (!id) return;
        if (!window.confirm("Reject " + id + "?")) return;
        await apiFetch(apiPath(["proposals", id, "reject"]), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        });
      } else if (action === "approve" || action === "retire" || action === "supersede") {
        // The dialog refreshes on success itself; nothing has changed until then.
        openVerdict(btn.getAttribute("data-id"), action, null, btn.getAttribute("data-successor"));
        return;
      } else if (action === "judge-pair") {
        // Stay on the pair: its list says how the check went, and nothing scrolls away.
        btn.textContent = "Checking this pair…";
        const cards = Array.from(document.querySelectorAll("#conflicts-pane .item.related"));
        const at = Math.max(cards.indexOf(btn.closest(".item.related")), 0);
        await window.RLJudge.checkPair(btn.getAttribute("data-a"), btn.getAttribute("data-b"), at);
        return;
      } else if (action === "dismiss") {
        const a = btn.getAttribute("data-a");
        const b = btn.getAttribute("data-b");
        if (!a || !b) return;
        const reason = promptDismissReason();
        if (!reason) return;
        await apiFetch(apiPath(["dismiss"]), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision_a: a, decision_b: b, reason: reason }),
        });
      }
      await refresh();
    } catch (err) {
      window.alert(err.message || String(err));
    }
  }

  if (isLive) {
    document.addEventListener("click", onNavigate);
    document.addEventListener("click", onAction);
    initTabs();
    refresh().catch(function (err) {
      root.innerHTML = '<p class="error">' + escapeHtml(err.message || err) + "</p>";
    });
  } else {
    root.textContent = "This page needs the reasonledger ui server.";
  }
})();
