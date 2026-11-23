/* ReasonLedger Overview — the summary strip: review backlog, whose idea, decisions by module.
 *
 * Live mode only. It draws what /api/stats counted and counts nothing itself, so the numbers
 * are the ones `reasonledger status --stats` prints. Every chart sits beside its figures in words:
 * the colour is never the only carrier.
 */
(function (global) {
  const R = global.RLRender;
  const esc = R.escapeHtml;
  // Module bars are drawn in a 0-100 box stretched to the row; pies in a box of this radius.
  const BAR_UNITS = 100;
  const BAR_HEIGHT = 12;
  const PIE_RADIUS = 50;
  const MODULES_SHOWN = 6;

  function plural(n, word) {
    return n + " " + word + (n === 1 ? "" : "s");
  }

  function point(share) {
    const angle = 2 * Math.PI * share - Math.PI / 2;
    return (PIE_RADIUS * Math.cos(angle)).toFixed(3) + " " + (PIE_RADIUS * Math.sin(angle)).toFixed(3);
  }

  /** One pie. parts: [{key, label, value}]; an empty part gets no slice, a lone part the whole disc. */
  function pie(parts, total) {
    const shown = parts.filter(function (p) { return p.value > 0; });
    let done = 0;
    const slices = shown.map(function (p) {
      const from = done / total;
      done += p.value;
      const to = done / total;
      const title = "<title>" + esc(p.value + " " + p.label) + "</title>";
      const attrs = 'class="stats-seg" data-series="' + esc(p.key) + '"';
      if (shown.length === 1) return "<circle " + attrs + ' r="' + PIE_RADIUS + '">' + title + "</circle>";
      const large = to - from > 0.5 ? 1 : 0;
      return (
        "<path " + attrs + ' d="M0 0 L' + point(from) + " A" + PIE_RADIUS + " " + PIE_RADIUS +
        " 0 " + large + " 1 " + point(to) + ' Z">' + title + "</path>"
      );
    });
    const summary = parts.map(function (p) { return p.value + " " + p.label; }).join(", ");
    const box = -PIE_RADIUS + " " + -PIE_RADIUS + " " + 2 * PIE_RADIUS + " " + 2 * PIE_RADIUS;
    return (
      '<svg class="stats-pie" viewBox="' + box + '" role="img" aria-label="' + esc(summary) + '">' +
      slices.join("") + "</svg>"
    );
  }

  function legend(parts) {
    return (
      '<ul class="stats-legend">' +
      parts.map(function (p) {
        const text = "<strong>" + esc(p.value) + "</strong> " + esc(p.label);
        const list = p.filter ? '" data-ask-filter="' + esc(p.filter) : "";
        const body = p.tab ? '<a href="#" data-open-tab="' + esc(p.tab) + list + '">' + text + "</a>" : text;
        return '<li><span class="stats-swatch" data-series="' + esc(p.key) + '"></span>' + body + "</li>";
      }).join("") +
      "</ul>"
    );
  }

  function panel(title, note, parts, total) {
    return (
      '<section class="stats-panel"><h3>' + esc(title) + "</h3>" +
      '<p class="stats-note">' + esc(note) + "</p>" +
      '<div class="stats-pie-row">' + pie(parts, total) + legend(parts) + "</div></section>"
    );
  }

  function moduleRow(m, top) {
    const width = top ? (BAR_UNITS * m.decisions) / top : 0;
    const pending = m.pending ? " · " + m.pending + " pending" : "";
    return (
      '<li class="stats-module"><span class="stats-module-name">' + esc(m.name) + "</span>" +
      '<svg class="stats-bar" viewBox="0 0 ' + BAR_UNITS + " " + BAR_HEIGHT +
      '" preserveAspectRatio="none" aria-hidden="true"><rect class="stats-seg" data-series="module" ' +
      'x="0" y="0" width="' + width.toFixed(2) + '" height="' + BAR_HEIGHT + '"></rect></svg>' +
      '<span class="stats-module-count"><strong>' + esc(m.decisions) + "</strong>" + esc(pending) + "</span></li>"
    );
  }

  function modulesPanel(stats) {
    const head = '<section class="stats-panel stats-panel-wide"><h3>Decisions by module</h3>';
    if (!stats.mapped) {
      return head + '<p class="stats-note">No module map yet — the Map tab builds one.</p></section>';
    }
    const top = stats.modules.length ? stats.modules[0].decisions : 0;
    const rest = stats.modules.length - MODULES_SHOWN;
    const none = stats.modules_without_decisions
      ? plural(stats.modules_without_decisions, "module") + " with no decision yet. "
      : "";
    return (
      head +
      '<p class="stats-note">A decision anchored in two modules counts in both.</p>' +
      '<ul class="stats-modules">' +
      stats.modules.slice(0, MODULES_SHOWN).map(function (m) { return moduleRow(m, top); }).join("") +
      "</ul>" +
      '<p class="stats-note">' + esc(none) + (rest > 0 ? esc(rest + " more not shown. ") : "") +
      '<button type="button" class="secondary" data-open-tab="map">Open the map</button></p></section>'
    );
  }

  function html(stats) {
    const review = [
      { key: "judged", label: "judged by a person", value: stats.judged, tab: "ask", filter: "judged" },
      { key: "pending", label: "pending review", value: stats.pending, tab: "review" },
    ];
    const proposer = [
      { key: "human", label: "agreed: a person's choice", value: stats.proposed_human },
      { key: "agent", label: "recommended: an agent's choice", value: stats.proposed_ai },
      { key: "unset", label: "not stated", value: stats.proposed_unset },
    ];
    return (
      '<div class="stats-card" aria-label="Ledger summary">' +
      panel("Review backlog", plural(stats.in_force, "decision") + " in force", review, stats.in_force) +
      panel("Whose idea", "who proposed each choice", proposer, stats.in_force) +
      modulesPanel(stats) +
      "</div>"
    );
  }

  /** Fill the strip; an empty ledger or a failed count leaves it out instead of showing zeros. */
  async function mount(host, request) {
    if (!host) return;
    try {
      const load = request;
      const stats = await load("/api/stats");
      if (!stats.in_force) return;
      host.innerHTML = html(stats);
    } catch (err) {
      host.innerHTML = "";
    }
  }

  global.RLStats = { mount: mount };
})(window);
