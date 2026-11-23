/* ReasonLedger Organize workbench — markup builders. Data in, HTML out; no state, no requests.
 *
 * Live mode only (loaded after map.js, before organize.js).
 */
(function (global) {
  const esc = global.RLRender.escapeHtml;
  const U = global.RLMapUi;
  const UNPLACED = "_unplaced";
  const INBOX = "_inbox";
  const DECISIONS = "_decisions";

  function entry(tile, current) {
    const short = tile.tier === "frontend" ? "fe" : "be";
    const tier = tile.tier ? '<span class="map-tier" data-tier="' + esc(tile.tier) + '">' + short + "</span>" : "";
    const proposed = tile.status === "proposed" && tile.kind !== "bucket";
    const mark = proposed ? '<span class="org-dot" title="proposed, not confirmed"></span>' : "";
    return (
      '<button type="button" class="org-mod' + (tile.id === current ? " is-current" : "") +
      '" data-module="' + esc(tile.id) + '">' + mark + "<span>" + esc(tile.name) + "</span>" + tier +
      '<span class="org-n">' + tile.files + "</span></button>"
    );
  }

  function group(title, tiles, current) {
    if (!tiles.length) return "";
    const items = tiles.map(function (tile) {
      return entry(tile, current);
    });
    return '<div class="org-group">' + esc(title) + "</div>" + items.join("");
  }

  function inboxEntry(count, current) {
    return (
      '<button type="button" class="org-mod' + (current === INBOX ? " is-current" : "") + '" data-module="' + INBOX +
      '"><span>Inbox</span><span class="org-n">' + count + "</span></button>"
    );
  }

  /** Decisions that have no working anchor; shown only while there are some (null count: none). */
  function decisionsEntry(count, current) {
    if (count === null) return "";
    return (
      '<button type="button" class="org-mod' + (current === DECISIONS ? " is-current" : "") + '" data-module="' + DECISIONS +
      '"><span>Unplaced decisions</span><span class="org-n">' + count + "</span></button>"
    );
  }

  function listHtml(map, current, inboxCount, decisionsCount) {
    const unplaced = map.unplaced_files
      ? '<button type="button" class="org-mod' + (current === UNPLACED ? " is-current" : "") +
        '" data-module="' + UNPLACED + '"><span>Unplaced</span><span class="org-n">' + map.unplaced_files + "</span></button>"
      : "";
    return (
      inboxEntry(inboxCount, current) + decisionsEntry(decisionsCount, current) + unplaced + group("Features", map.features, current) + group("Foundations", map.foundations, current) +
      group("Buckets", map.buckets, current)
    );
  }

  function targetsHtml(map) {
    const tiles = map.features.concat(map.foundations, map.buckets);
    const options = tiles.map(function (tile) {
      return '<option value="' + esc(tile.id) + '">' + esc(tile.name) + "</option>";
    });
    return '<datalist id="org-targets">' + options.join("") + "</datalist>";
  }

  function button(action, label) {
    return '<button type="button" class="secondary" data-action="' + action + '">' + esc(label) + "</button>";
  }

  function headHtml(tile) {
    if (!tile) {
      return (
        '<h2 id="org-title">Unplaced files</h2><p class="map-note">In no module, bucket or label yet. ' +
        "Select some and move them to a module.</p>"
      );
    }
    const editable = tile.kind !== "bucket";
    const proposed = tile.status === "proposed";
    const actions = [];
    if (editable && proposed) actions.push(button("confirm", "Confirm"));
    if (editable) actions.push(button("rename", "Rename"), button("merge", "Merge into…"));
    if (editable && proposed) actions.push(button("reject", "Reject"));
    const state = editable ? tile.status : "bucket";
    return (
      '<div class="org-head"><h2 id="org-title">' + esc(tile.name) + "</h2>" + U.tierChip(tile.tier) +
      '<span class="map-badge">' + esc(state) + '</span><span class="org-actions">' + actions.join("") + "</span></div>" +
      '<form class="org-merge" id="org-merge" hidden><label>Merge ' + esc(tile.name) + ' into ' +
      '<input type="text" id="org-merge-into" list="org-targets" autocomplete="off" /></label>' +
      '<button type="submit" class="secondary">Merge</button></form>' +
      '<p class="map-note">' + esc(tile.description || "No description.") + " " + U.plural(tile.files, "file") +
      ", " + U.plural(tile.decisions, "decision") + ".</p>"
    );
  }

  function hintHtml(hint) {
    if (!hint) return "";
    return (
      '<button type="button" class="org-hint" data-hint="' + esc(hint.module) + '" title="Select this file and move it there">' +
      hint.agree + " of " + hint.total + " beside it are in " + esc(hint.name) + "</button>"
    );
  }

  function rowHtml(row, index, checked) {
    const pinned = row.pinned_by ? '<span class="map-badge">placed by you</span>' : "";
    const decisions = row.decisions
      ? '<span class="map-badge is-shared">' + U.plural(row.decisions, "decision") + "</span>"
      : "";
    return (
      '<label class="org-row"><input type="checkbox" data-index="' + index + '" data-path="' + esc(row.path) + '"' +
      (checked ? " checked" : "") + " /><code>" + esc(row.path) + "</code>" + pinned + decisions + hintHtml(row.hint) + "</label>"
    );
  }

  function rowsHtml(page, selected, matching) {
    if (!page.files.length) return '<p class="map-note">No files here' + (page.total ? "" : " match") + ".</p>";
    const rows = page.files.map(function (row, index) {
      return rowHtml(row, index, matching || !!selected[row.path]);
    });
    const shown = page.offset + page.files.length;
    const more = shown < page.total
      ? '<button type="button" class="secondary" data-action="more">Show more (' + (page.total - shown) + " left)</button>"
      : "";
    return rows.join("") + more;
  }

  function barHtml(count, total, matching, target) {
    if (!count) return "";
    const all = !matching && total > count
      ? ' <button type="button" class="org-link" data-action="all">Select all ' + total + " matching</button>"
      : "";
    return (
      '<div class="org-bar"><span id="org-count">' + U.plural(count, "file") + " selected</span>" + all +
      '<input type="text" id="org-target" list="org-targets" autocomplete="off" placeholder="Move to… (module or bucket)" value="' + esc(target) + '" />' +
      '<button type="button" data-action="move">Move</button>' +
      '<button type="button" class="secondary" data-action="new-module">New module from selection</button>' +
      '<button type="button" class="org-link" data-action="clear">Clear</button></div>'
    );
  }

  function shiftHtml(shift) {
    return (
      "<li><code>" + esc(shift.decision_id) + "</code> " + esc(shift.before.join(", ") || "no module") +
      " → " + esc(shift.after.join(", ") || "no module") + "</li>"
    );
  }

  function impactHtml(impact) {
    if (!impact) return "";
    const from = Object.keys(impact.from_modules).map(function (id) {
      return impact.from_modules[id] + " from " + (id === UNPLACED ? "unplaced" : id);
    });
    const already = impact.already_there ? " " + impact.already_there + " already there." : "";
    const moving = impact.moving ? "Moves " + U.plural(impact.moving, "file") + " (" + from.join(", ") + ")." : "Nothing to move.";
    const shifts = impact.decisions.map(shiftHtml).join("");
    const decisions = impact.decisions_total
      ? "<p>" + U.plural(impact.decisions_total, "decision") + (impact.decisions_total === 1 ? " changes" : " change") + " module:</p><ul>" + shifts + "</ul>"
      : "<p>No decision changes module.</p>";
    const rule = impact.rule
      ? '<p>The files share a folder. <button type="button" class="org-link" data-action="rule">Make <code>' + esc(impact.rule.pattern) +
        "</code> a rule</button> (" + U.plural(impact.rule.extra_files, "more file") + (impact.rule.from_other_owner
          ? ", " + impact.rule.from_other_owner + " of them now in other modules"
          : "") + "), so later files in it follow.</p>"
      : "";
    return '<div class="org-impact"><p>' + esc(moving + already) + "</p>" + decisions + rule + "</div>";
  }

  function statusHtml(status) {
    if (!status.message && !status.error) return "";
    const text = status.error ? '<span class="error">' + esc(status.error) + "</span>" : esc(status.message);
    const undo = status.canUndo ? ' <button type="button" class="org-link" data-action="undo">Undo' + (status.last ? ": " + esc(status.last) : "") + "</button>" : "";
    return '<div class="org-status" role="status">' + text + undo + "</div>";
  }

  global.RLOrganizeUi = {
    UNPLACED: UNPLACED,
    INBOX: INBOX,
    DECISIONS: DECISIONS,
    listHtml: listHtml,
    targetsHtml: targetsHtml,
    headHtml: headHtml,
    rowsHtml: rowsHtml,
    barHtml: barHtml,
    impactHtml: impactHtml,
    statusHtml: statusHtml,
  };
})(window);
