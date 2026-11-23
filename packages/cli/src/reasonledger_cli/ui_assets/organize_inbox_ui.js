/* ReasonLedger Organize inbox — markup builders. Data in, HTML out; no state, no requests.
 *
 * Live mode only. A card says what is suggested, why (the evidence), and what a person can do.
 */
(function (global) {
  const esc = global.RLRender.escapeHtml;
  const U = global.RLMapUi;
  const FILES_LISTED = 12;

  function badge(confidence) {
    const extra = confidence === "high" ? " is-shared" : confidence === "low" ? " is-warn" : "";
    return '<span class="map-badge' + extra + '">' + esc(confidence) + "</span>";
  }

  function evidenceHtml(list) {
    return (
      '<p class="org-ev">' +
      list
        .map(function (e) {
          return '<span class="org-chip">' + esc(e.text) + "</span>";
        })
        .join(" ") +
      "</p>"
    );
  }

  function filesHtml(item) {
    if (!item.files.length) return "";
    const rows = item.files.slice(0, FILES_LISTED).map(function (path) {
      return "<li><code>" + esc(path) + "</code></li>";
    });
    const more = item.file_count > rows.length ? "<li>and " + (item.file_count - rows.length) + " more</li>" : "";
    return (
      "<details><summary>" + U.plural(item.file_count, "file") + '</summary><ul class="org-files">' +
      rows.join("") + more + "</ul></details>"
    );
  }

  function button(key, action, label, extra) {
    return (
      '<button type="button" class="' + (extra || "secondary") + '" data-inbox="' + action +
      '" data-key="' + esc(key) + '">' + esc(label) + "</button>"
    );
  }

  function placeButtons(item) {
    const out = [button(item.key, "accept", "Accept", "")];
    if (item.rule) out.push(button(item.key, "rule", "Accept as folder rule"));
    out.push(button(item.key, "choose", "Choose another…"));
    out.push(button(item.key, "decline", "Not " + (item.target_name || item.target)));
    return out;
  }

  function buttons(item) {
    let out = [];
    if (item.kind === "place") out = placeButtons(item);
    if (item.kind === "new-module") out = [button(item.key, "new", "Create module…", ""), button(item.key, "choose", "Choose a home…")];
    if (item.kind === "rule") out = [button(item.key, "accept", "Make it a rule", "")];
    if (item.kind === "proposal") {
      out = [button(item.key, "confirm", "Confirm", ""), button(item.key, "reject", "Reject"), button(item.key, "open", "Open")];
    }
    out.push(button(item.key, "skip", "Skip for now"));
    return out.join("");
  }

  function why(item) {
    if (item.kind === "place") {
      const alt = item.alternative_name ? " or " + esc(item.alternative_name) : "";
      return "<p>Suggested home: <strong>" + esc(item.target_name || item.target) + "</strong>" + alt + "</p>";
    }
    if (item.kind === "new-module") return "<p>Suggested name: <strong>" + esc(item.name) + "</strong></p>";
    return "";
  }

  function chooser(item) {
    return (
      '<form class="org-choose" data-key="' + esc(item.key) + '" hidden><label>Move these files to ' +
      '<input type="text" list="org-targets" autocomplete="off" /></label>' +
      '<button type="submit" class="secondary">Move</button></form>'
    );
  }

  function card(item) {
    return (
      '<article class="org-card" data-kind="' + esc(item.kind) + '"><header><strong>' + esc(item.title) + "</strong> " +
      badge(item.confidence) + "</header>" + why(item) + evidenceHtml(item.evidence) + filesHtml(item) +
      '<div class="org-card-actions">' + buttons(item) + "</div>" + chooser(item) + "</article>"
    );
  }

  function notes(inbox) {
    const out = [];
    if (!inbox.history) out.push("No git history could be read, so changes made together are not used as evidence.");
    if (inbox.unsuggested) out.push(U.plural(inbox.unsuggested, "new file") + " fit nothing yet: see Unplaced.");
    if (inbox.proposals_waiting) out.push(U.plural(inbox.proposals_waiting, "more proposed module") + " wait behind these.");
    return out.length ? '<p class="map-note">' + esc(out.join(" ")) + "</p>" : "";
  }

  /** The inbox page: `visible` items are the first few not skipped; `waiting` is how many follow. */
  function inboxHtml(inbox, visible, waiting, high) {
    if (!visible.length) {
      return '<h2 id="org-title">Inbox</h2><p class="map-note">Nothing needs a decision.</p>' + notes(inbox);
    }
    const bulk = high
      ? '<button type="button" data-inbox="all">Accept ' + U.plural(high, "high-confidence suggestion") + "</button>"
      : "";
    const more = waiting
      ? '<button type="button" class="secondary" data-inbox="more">Show more (' + waiting + " waiting)</button>"
      : "";
    return (
      '<div class="org-head"><h2 id="org-title">Inbox</h2><span class="org-actions">' + bulk + "</span></div>" +
      '<p class="map-note">Most trusted first, a few at a time. Nothing moves until you accept.</p>' + notes(inbox) +
      visible.map(card).join("") + more
    );
  }

  global.RLOrganizeInboxUi = { inboxHtml: inboxHtml };
})(window);
