/* ReasonLedger module map — the overview: one tile per module, bands, and what is left out.
 *
 * Live mode only. It reads /api/map and /api/map/module through the shared authenticated
 * request, so the static export leaves this file out.
 */
(function (global) {
  const R = global.RLRender;
  const esc = R.escapeHtml;
  const HUES = 8;
  const SIZE_STEPS = 5;
  // Coverage bands: below LOW is "low", below HIGH is "mid", else "high"; zero is "none".
  const COVERAGE_LOW = 0.34;
  const COVERAGE_HIGH = 0.67;
  // `hooks` come from app.js; `moduleId` is the open module page ("" on the overview).
  const state = { pane: null, request: null, hooks: null, view: null, moduleId: "", notice: "" };

  function plural(n, word) {
    return n + " " + word + (n === 1 ? "" : "s");
  }

  function percent(share) {
    return Math.round(share * 100);
  }

  function hueOf(id) {
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % HUES;
    return h + 1;
  }

  function sizeOf(files, maxFiles) {
    if (!maxFiles) return 1;
    return Math.max(1, Math.ceil(Math.sqrt(files / maxFiles) * SIZE_STEPS));
  }

  function coverageBand(share) {
    if (share <= 0) return "none";
    return share < COVERAGE_LOW ? "low" : share < COVERAGE_HIGH ? "mid" : "high";
  }

  function tierChip(tier) {
    return tier ? '<span class="map-tier" data-tier="' + esc(tier) + '">' + esc(tier) + "</span>" : "";
  }

  /** A named chip that jumps to the module: the module is in the words, not only the colour. */
  function chip(ref) {
    return (
      '<a class="map-chip" href="#module-' + esc(ref.id) + '" data-hue="' + hueOf(ref.id) +
      '" data-module-link="' + esc(ref.id) + '">' + esc(ref.name) + "</a>"
    );
  }

  function tileHtml(tile, maxFiles) {
    const share = percent(tile.coverage);
    const pending = tile.pending ? " · " + tile.pending + " pending review" : "";
    const cross = tile.cross_cutting ? " · " + tile.cross_cutting + " cross-cutting" : "";
    return (
      '<button type="button" class="map-tile" data-module-link="' + esc(tile.id) +
      '" data-size="' + sizeOf(tile.files, maxFiles) + '" data-coverage="' + coverageBand(tile.coverage) +
      '" data-shared="' + tile.shared + '" data-search="' + esc(tile.search) + '">' +
      '<span class="map-tile-name">' + esc(tile.name) + "</span>" +
      '<span class="map-tile-meta">' + tierChip(tile.tier) +
      (tile.kind === "bucket" ? "" : " " + tile.status) + "</span>" +
      '<span class="map-tile-counts">' + plural(tile.decisions, "decision") + " · " +
      tile.shared + " shared" + pending + cross + "</span>" +
      '<span class="map-tile-files">' + plural(tile.files, "file") + "</span>" +
      '<progress class="map-coverage" max="100" value="' + share + '"></progress>' +
      '<span class="map-tile-files">' + share + "% of files have a decision</span></button>"
    );
  }

  function bandHtml(title, hint, tiles, maxFiles) {
    if (!tiles.length) return "";
    return (
      '<section class="map-band"><h3>' + esc(title) + " (" + tiles.length + ")</h3>" +
      '<p class="map-note">' + esc(hint) + "</p>" +
      '<div class="map-tiles">' +
      tiles.map(function (t) { return tileHtml(t, maxFiles); }).join("") +
      "</div></section>"
    );
  }

  function factsLine(view) {
    const parts = [];
    if (view.mapped_by) {
      const commit = view.mapped_at_commit ? " at " + view.mapped_at_commit.slice(0, 7) : "";
      parts.push("mapped by " + view.mapped_by + commit);
    }
    parts.push(plural(view.unplaced_files, "source file") + " in no module or bucket");
    if (view.pending_proposals) parts.push(plural(view.pending_proposals, "module") + " proposed, not confirmed");
    if (view.dangling_labels.length) parts.push("labels pointing at a missing module: " + view.dangling_labels.join(", "));
    return parts.join(" · ");
  }

  /** Both loose ends are fixed in Edit map, so point there: the inbox places files and confirms modules. */
  function editMapHint(view) {
    const todo = [];
    if (view.unplaced_files) todo.push("place those files");
    if (view.pending_proposals) todo.push("confirm the proposed modules");
    if (!todo.length) return "";
    return (
      ' <button type="button" class="secondary map-edit-link" data-map-mode="organize">' +
      "Open Edit map</button> to " + todo.join(" and ") + "."
    );
  }

  function groupHtml(title, hint, decisions, id) {
    const body = decisions.map(function (d) { return global.RLMapPage.decisionCard(d, ""); }).join("");
    return R.section(title, hint, body, "none", decisions.length, decisions.length > 0, id);
  }

  /** What the last edit made from a card did, and where to take it back. */
  function noticeHtml() {
    if (!state.notice) return "";
    return '<p class="map-notice" role="status">' + esc(state.notice) + ". Undo is under Edit map.</p>";
  }

  function emptyHtml() {
    return (
      '<p class="map-note">No module map yet. Run <code>reasonledger map</code>, or ask your coding ' +
      "agent to call <code>get_mapping_task</code> and <code>submit_module_map</code>.</p>"
    );
  }

  function render() {
    const view = state.view;
    if (view.empty) {
      if (global.RLSetup) {
        global.RLSetup.mountMapEmpty(state.pane, {
          onDone: function () { show(state.pane, state.request); },
        });
      } else {
        state.pane.innerHTML = emptyHtml();
      }
      return;
    }
    const all = view.features.concat(view.foundations, view.buckets);
    global.RLMapActions.setTargets(all);
    const maxFiles = Math.max.apply(null, all.map(function (t) { return t.files; }));
    const capabilities = view.features.length + view.foundations.length;
    state.pane.innerHTML =
      "<h2>Module map</h2>" + noticeHtml() + global.RLMapActions.datalist() +
      '<p class="map-headline"><strong>' + plural(capabilities, "module") + "</strong> · <strong>" +
      plural(view.files, "file") + "</strong> · <strong>" + plural(view.decisions, "decision") + "</strong></p>" +
      '<p class="map-note">Tiles do not add up to the decision total: a decision anchored in several ' +
      "modules shows in each of them and counts once here.</p>" +
      '<p class="map-facts-line">' + esc(factsLine(view)) + editMapHint(view) + "</p>" +
      '<div class="map-toolbar"><input type="search" id="map-search" placeholder="Search modules, decisions, anchors" aria-label="Search the map" />' +
      '<label><input type="checkbox" id="map-shared" /> Shared decisions only</label></div>' +
      bandHtml("Features", "Capabilities users see. Size follows file count; the bar shows how many files have a decision.", view.features, maxFiles) +
      bandHtml("Foundations", "Capabilities the features build on. A foundation's decisions stay here.", view.foundations, maxFiles) +
      bandHtml("Buckets", "Files no capability owns, placed by the architecture. Not modules; move a file with reasonledger modules label.", view.buckets, maxFiles) +
      groupHtml("Cross-cutting decisions", "Anchored in more than four modules, listed once here.", view.cross_cutting, "map-cross") +
      groupHtml("Decisions with no module", "No anchor lands in a module, or there is no anchor at all. Each card says how to give it one.", view.unplaced_decisions, "map-unplaced");
  }

  function applyFilters() {
    const query = (document.getElementById("map-search") || { value: "" }).value.trim().toLowerCase();
    const sharedOnly = !!(document.getElementById("map-shared") || {}).checked;
    state.pane.querySelectorAll(".map-tile").forEach(function (tile) {
      const text = tile.getAttribute("data-search") || "";
      const hide = (query && text.indexOf(query) < 0) || (sharedOnly && tile.getAttribute("data-shared") === "0");
      tile.hidden = !!hide;
    });
    state.pane.querySelectorAll(".map-band").forEach(function (band) {
      band.hidden = !band.querySelector(".map-tile:not([hidden])");
    });
  }

  async function openModule(id) {
    state.moduleId = id;
    state.pane.innerHTML = '<p class="muted">Loading…</p>';
    try {
      const page = await state.request("/api/map/module?id=" + encodeURIComponent(id));
      state.pane.innerHTML = global.RLMapPage.pageHtml(page);
    } catch (err) {
      state.pane.innerHTML = '<p class="error">' + esc(err.message || String(err)) + "</p>";
    }
  }

  function onClick(ev) {
    const link = ev.target.closest("[data-module-link]");
    if (link) {
      ev.preventDefault();
      openModule(link.getAttribute("data-module-link"));
    } else if (ev.target.closest("[data-map-back]")) {
      state.moduleId = "";
      render();
      applyFilters();
    }
  }

  function bindOnce(pane) {
    if (pane.getAttribute("data-bound")) return;
    pane.setAttribute("data-bound", "1");
    pane.addEventListener("click", onClick);
    global.RLMapActions.bind(pane, {
      request: function (path, options) { return state.request(path, options); },
      review: function (id) { state.hooks.review(id, { reload: reload }); },
      // A placement moves decisions between modules, which the Overview strip counts too.
      done: function (message) {
        state.hooks.changed();
        return reload(message);
      },
    });
    pane.addEventListener("input", function (ev) {
      if (ev.target.id === "map-search") applyFilters();
      if (ev.target.id === "map-page-shared") global.RLMapPage.filterShared(pane, ev.target.checked);
    });
    pane.addEventListener("change", function (ev) {
      if (ev.target.id === "map-shared") applyFilters();
    });
  }

  async function load() {
    state.pane.innerHTML = '<p class="muted">Loading…</p>';
    try {
      state.view = await state.request("/api/map");
      render();
    } catch (err) {
      state.pane.innerHTML = '<p class="error">' + esc(err.message || String(err)) + "</p>";
    }
  }

  /** After an action on a card: fetch again and stay where the person was. */
  async function reload(message) {
    state.notice = message || "";
    await load();
    if (state.moduleId) await openModule(state.moduleId);
  }

  /** Load the overview into the pane; called each time the Map tab opens. `hooks.review(id, map)` opens the review dialog and calls `map.reload` after; `hooks.changed()` says the map was edited. */
  async function show(pane, request, hooks) {
    state.pane = pane;
    state.request = request;
    state.hooks = hooks;
    state.moduleId = "";
    state.notice = "";
    bindOnce(pane);
    await load();
  }

  global.RLMap = { show: show };
  global.RLMapUi = { esc: esc, plural: plural, percent: percent, hueOf: hueOf, tierChip: tierChip, chip: chip };
})(window);
