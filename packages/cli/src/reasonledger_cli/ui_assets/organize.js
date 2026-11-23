/* ReasonLedger Organize workbench — state, requests and events.
 *
 * Live mode only. Every edit is one request that writes modules.yml through the same core
 * functions the CLI uses, and the last edits can be undone. Nothing here decides where a file
 * belongs: a person selects, previews what a move would change, and moves.
 */
(function (global) {
  const UI = global.RLOrganizeUi;
  const U = global.RLMapUi;
  const esc = U.esc;
  const UNPLACED = UI.UNPLACED;
  const INBOX = UI.INBOX;
  const DECISIONS = UI.DECISIONS;
  const A = global.RLOrganizeActions;
  const Inbox = global.RLOrganizeInbox;
  const Decisions = global.RLOrganizeDecisions;
  const PREVIEW_DELAY_MS = 250;
  const state = {
    pane: null,
    request: null,
    map: null,
    module: null,
    query: "",
    page: null,
    selected: {},
    matching: false,
    target: "",
    impact: null,
    inbox: null,
    decisions: null,
    lastIndex: -1,
    status: { message: "", error: "", canUndo: false, last: "" },
  };
  let timer = null;
  let loadSeq = 0;

  function tiles() {
    return state.map.features.concat(state.map.foundations, state.map.buckets);
  }

  function tileOf(id) {
    return tiles().filter(function (t) {
      return t.id === id;
    })[0] || null;
  }

  function isVirtual(id) {
    return id === UNPLACED || id === INBOX || id === DECISIONS;
  }

  function firstModule() {
    if (Inbox.count(state.inbox)) return INBOX;
    if (state.map.unplaced_files) return UNPLACED;
    const all = tiles();
    return all.length ? all[0].id : null;
  }

  function post(action, body) {
    return state.request("/api/organize/" + action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  function selectedPaths() {
    return Object.keys(state.selected).filter(function (p) {
      return state.selected[p];
    });
  }

  function selectedCount() {
    return state.matching ? state.page.total : selectedPaths().length;
  }

  function spec() {
    return state.matching ? { module: state.module, query: state.query } : { paths: selectedPaths() };
  }

  function part(id, html) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  }

  function paintBar() {
    part("org-bar", UI.barHtml(selectedCount(), state.page ? state.page.total : 0, state.matching, state.target));
  }

  function paintStatus() {
    part("org-status", UI.statusHtml(state.status));
  }

  function paintAll() {
    part("org-mods", UI.listHtml(state.map, state.module, Inbox.count(state.inbox), Decisions.count(state.decisions)));
    const inbox = state.module === INBOX;
    const decisions = state.module === DECISIONS;
    document.getElementById("org-inbox").hidden = !inbox;
    document.getElementById("org-decisions").hidden = !decisions;
    document.getElementById("org-files").hidden = inbox || decisions;
    if (inbox || decisions) {
      part(inbox ? "org-inbox" : "org-decisions", inbox ? Inbox.html(state.inbox) : Decisions.html(state.decisions));
      paintStatus();
      return;
    }
    part("org-head", UI.headHtml(tileOf(state.module)));
    part("org-rows", UI.rowsHtml(state.page, state.selected, state.matching));
    part("org-impact", UI.impactHtml(state.impact));
    const total = document.getElementById("org-total");
    if (total) total.textContent = U.plural(state.page.total, "file");
    paintBar();
    paintStatus();
  }

  function shell() {
    state.pane.innerHTML =
      '<div class="org"><aside class="org-mods" id="org-mods"></aside><section class="org-main">' +
      '<div id="org-inbox" hidden></div><div id="org-decisions" hidden></div><div id="org-files"><div id="org-head"></div><div class="org-tools">' +
      '<input type="search" id="org-filter" placeholder="Filter files: text, or a glob like app/*/f0.py" ' +
      'aria-label="Filter files" /><span class="map-note" id="org-total"></span></div><div id="org-bar"></div>' +
      '<div id="org-impact"></div><div class="org-rows" id="org-rows"></div></div><div id="org-status"></div>' +
      "</section></div>" + UI.targetsHtml(state.map);
  }

  async function loadFiles(append) {
    const offset = append ? state.page.offset + state.page.files.length : 0;
    const seq = ++loadSeq;
    const url =
      "/api/organize/files?module=" + encodeURIComponent(state.module) + "&q=" + encodeURIComponent(state.query) +
      "&offset=" + offset;
    const page = await state.request(url);
    if (seq !== loadSeq) return false;
    if (append) {
      page.files = state.page.files.concat(page.files);
      page.offset = state.page.offset;
    }
    state.page = page;
    return true;
  }

  function fail(err) {
    state.status = { message: "", error: err.message || String(err), canUndo: state.status.canUndo, last: state.status.last };
    paintStatus();
  }

  function resetSelection() {
    state.selected = {};
    state.matching = false;
    state.target = "";
    state.impact = null;
    state.lastIndex = -1;
  }

  async function refreshInbox() {
    state.inbox = await state.request("/api/organize/inbox");
    state.decisions = await state.request("/api/organize/decisions");
  }

  async function selectModule(id) {
    state.module = id;
    state.query = "";
    resetSelection();
    const filter = document.getElementById("org-filter");
    if (filter) filter.value = "";
    try {
      if (id === INBOX || id === DECISIONS) {
        Inbox.reset();
        await refreshInbox();
        paintAll();
      } else if (await loadFiles(false)) {
        paintAll();
      }
    } catch (err) {
      fail(err);
    }
  }

  /** After an edit: show what happened, reload the map and inbox, and follow the module if it moved. */
  async function afterEdit(reply) {
    state.status = { message: reply.message, error: "", canUndo: reply.can_undo, last: reply.last || "" };
    state.map = await state.request("/api/map");
    await refreshInbox();
    if (reply.module && state.module !== INBOX && state.module !== DECISIONS) state.module = reply.module;
    if (!isVirtual(state.module) && !tileOf(state.module)) state.module = firstModule();
    if (state.module === UNPLACED && !state.map.unplaced_files) state.module = firstModule();
    await selectModule(state.module);
  }

  async function act(action, body) {
    try {
      await afterEdit(await post(action, body));
    } catch (err) {
      fail(err);
    }
  }

  function knownTarget() {
    return tileOf(state.target) ? state.target : "";
  }

  async function runPreview() {
    if (!selectedCount() || !knownTarget()) {
      state.impact = null;
    } else {
      try {
        state.impact = await post("preview", { selection: spec(), target: state.target });
      } catch (err) {
        state.impact = null;
      }
    }
    part("org-impact", UI.impactHtml(state.impact));
  }

  function schedulePreview() {
    clearTimeout(timer);
    timer = setTimeout(runPreview, PREVIEW_DELAY_MS);
  }

  function changeSelection() {
    paintBar();
    schedulePreview();
  }

  function onCheckbox(box, shift) {
    const index = Number(box.getAttribute("data-index"));
    const boxes = state.pane.querySelectorAll(".org-row input[type=checkbox]");
    const from = shift && state.lastIndex >= 0 ? Math.min(state.lastIndex, index) : index;
    const to = shift && state.lastIndex >= 0 ? Math.max(state.lastIndex, index) : index;
    for (let i = from; i <= to; i++) {
      boxes[i].checked = box.checked;
      state.selected[boxes[i].getAttribute("data-path")] = box.checked;
    }
    state.matching = false;
    state.lastIndex = index;
    changeSelection();
  }

  function useHint(button) {
    const box = button.closest(".org-row").querySelector("input[type=checkbox]");
    box.checked = true;
    state.selected[box.getAttribute("data-path")] = true;
    state.target = button.getAttribute("data-hint");
    paintBar();
    schedulePreview();
  }

  async function move(asRule) {
    if (!knownTarget()) {
      fail(new Error("Type a module or bucket to move to, and pick it from the list."));
      return;
    }
    await act("move", { selection: spec(), target: state.target, rule: asRule });
  }

  function onAction(name, button) {
    const handlers = {
      move: function () { return move(false); },
      rule: function () { return move(true); },
      "new-module": function () { return A.newModule(ctx); },
      confirm: function () { return A.confirmModule(ctx); },
      reject: function () { return A.rejectModule(ctx); },
      rename: function () { A.startRename(ctx); },
      merge: function () {
        const form = document.getElementById("org-merge");
        form.hidden = !form.hidden;
        if (!form.hidden) document.getElementById("org-merge-into").focus();
      },
      undo: function () { return act("undo", {}); },
      more: function () { return reload(true); },
      all: function () { state.matching = true; paintAll(); schedulePreview(); },
      clear: function () { resetSelection(); paintAll(); },
    };
    if (handlers[name]) handlers[name](button);
  }

  function onClick(ev) {
    const card = ev.target.closest("[data-inbox]");
    if (card) {
      Inbox.onClick(card, ctx);
      return;
    }
    const module = ev.target.closest("[data-module]");
    const action = ev.target.closest("[data-action]");
    const hint = ev.target.closest("[data-hint]");
    if (module) {
      selectModule(module.getAttribute("data-module"));
    } else if (hint) {
      ev.preventDefault();
      useHint(hint);
    } else if (action) {
      onAction(action.getAttribute("data-action"), action);
    } else if (ev.target.matches(".org-row input[type=checkbox]")) {
      onCheckbox(ev.target, ev.shiftKey);
    }
  }

  /** Load the list again and paint it, unless a newer request has already replaced this one. */
  function reload(append) {
    return loadFiles(append).then(function (fresh) {
      if (fresh) paintAll();
    }).catch(fail);
  }

  function onInput(ev) {
    if (ev.target.id === "org-target") {
      state.target = ev.target.value.trim();
      schedulePreview();
    } else if (ev.target.id === "org-filter") {
      clearTimeout(timer);
      state.query = ev.target.value;
      resetSelection();
      part("org-impact", "");
      paintBar();
      timer = setTimeout(function () {
        reload(false);
      }, PREVIEW_DELAY_MS);
    }
  }

  function onSubmit(ev) {
    if (ev.target.classList.contains("org-choose")) {
      ev.preventDefault();
      Inbox.onSubmit(ev.target, ctx);
      return;
    }
    if (ev.target.id !== "org-merge") return;
    ev.preventDefault();
    const into = document.getElementById("org-merge-into").value.trim();
    if (into) act("merge", { keep: into, absorb: state.module });
  }

  function onKey(ev) {
    if (ev.target.id === "org-rename") {
      if (ev.key === "Enter") A.finishRename(ctx, ev.target);
      if (ev.key === "Escape") paintAll();
      return;
    }
    const typing = ev.target.matches("input, textarea");
    if (ev.key === "Escape" && !typing) {
      resetSelection();
      paintAll();
    } else if (ev.key === "/" && !typing) {
      ev.preventDefault();
      document.getElementById("org-filter").focus();
    } else if (ev.key === "m" && !typing && selectedCount()) {
      ev.preventDefault();
      document.getElementById("org-target").focus();
    }
  }

  const ctx = { state: state, act: act, open: selectModule, paint: paintAll, spec: spec, tileOf: tileOf };

  function bindOnce(pane) {
    if (pane.getAttribute("data-bound")) return;
    pane.setAttribute("data-bound", "1");
    pane.addEventListener("click", onClick);
    pane.addEventListener("input", onInput);
    pane.addEventListener("submit", onSubmit);
    document.addEventListener("keydown", function (ev) {
      if (!pane.hidden) onKey(ev);
    });
  }

  /** Load the workbench into the pane; called each time Edit map opens. */
  async function show(pane, request) {
    state.pane = pane;
    state.request = request;
    bindOnce(pane);
    try {
      const loaded = await Promise.all([state.request("/api/map"), state.request("/api/organize/state")]);
      state.map = loaded[0];
      state.status = { message: "", error: "", canUndo: loaded[1].can_undo, last: loaded[1].last || "" };
      if (state.map.empty) {
        if (global.RLSetup) {
          global.RLSetup.mountMapEmpty(pane, { onDone: function () { show(pane, request); } });
        } else {
          pane.innerHTML = '<p class="map-note">No module map yet. Run <code>reasonledger map</code> first.</p>';
        }
        return;
      }
      await refreshInbox();
      if (!state.module || !(isVirtual(state.module) || tileOf(state.module))) state.module = firstModule();
      shell();
      Decisions.mount(document.getElementById("org-decisions"), ctx);
      await selectModule(state.module);
    } catch (err) {
      pane.innerHTML = '<p class="error">' + esc(err.message || String(err)) + "</p>";
    }
  }

  global.RLOrganize = { show: show };
})(window);
