/* ReasonLedger module map — one module's page and the decision card both views share.
 *
 * Live mode only (loaded after map.js). A decision in two or more modules is drawn apart: a
 * split edge, a Shared badge and a named chip per module, so colour is never the only channel.
 */
(function (global) {
  const U = global.RLMapUi;
  const esc = U.esc;
  const plural = U.plural;

  /** Hover text: where a shared decision anchors, module by module. */
  function evidence(d) {
    return d.modules
      .map(function (m) {
        return (d.anchors[m.id] || []).join(", ") + " (" + m.name + ")";
      })
      .join("; ");
  }

  function badge(text, extra) {
    return '<span class="map-badge ' + (extra || "") + '">' + esc(text) + "</span>";
  }

  function badges(d) {
    const pending = d.oversight === "pending";
    const out = [badge(d.status), pending ? badge("pending review", "is-warn") : badge(d.oversight)];
    if (d.proposed_by) out.push(badge(d.proposed_by === "human" ? "agreed" : "recommended"));
    if (d.shared) out.push(badge("Shared", "is-shared"));
    if (d.cross_cutting) out.push(badge("Cross-cutting", "is-shared"));
    if (d.superseded) out.push(badge(d.status === "retired" ? "retired" : "superseded", "is-warn"));
    if (d.placed_by) out.push(badge("placed by hand: " + d.placed_by));
    return out.join("");
  }

  function lociHtml(loci) {
    return loci
      .map(function (locus) {
        return "<code>" + esc(locus) + "</code>";
      })
      .join(" ");
  }

  /** One decision. `currentId` is the module whose page this is ("" in the overview). */
  function decisionCard(d, currentId) {
    const here = d.anchors[currentId] || [];
    const others = d.modules.filter(function (m) {
      return m.id !== currentId;
    });
    const classes = "map-decision" + (d.shared || d.cross_cutting ? " is-shared" : "") + (d.superseded ? " is-superseded" : "");
    const sharedWith = others.length
      ? '<p class="map-chips" title="' + esc(evidence(d)) + '">' +
        (currentId ? "Shared with " : "Anchored in ") + others.map(U.chip).join(" ") + "</p>"
      : "";
    const outside = d.outside.length ? "<p>Outside every module: " + lociHtml(d.outside) + "</p>" : "";
    const anchors = here.length ? "<p>Anchors here: " + lociHtml(here) + "</p>" : "";
    return (
      '<article class="' + classes + '" id="decision-' + esc(d.id) + '"><header><code>' + esc(d.id) + "</code>" +
      badges(d) + "</header>" +
      "<p>" + esc(d.context || "") + "</p><p><strong>Chose:</strong> " + esc(d.choice || "") + "</p>" +
      anchors + sharedWith + outside + global.RLMapActions.html(d) + "</article>"
    );
  }

  function factsHtml(tile) {
    const rows = [
      ["Files", tile.files],
      ["Decisions", tile.decisions],
      ["Shared", tile.shared],
      ["Files with a decision", U.percent(tile.coverage) + "%"],
      ["Status", tile.status],
    ];
    return (
      '<dl class="map-facts">' +
      rows
        .map(function (row) {
          return "<div><dt>" + esc(row[0]) + "</dt><dd>" + esc(String(row[1])) + "</dd></div>";
        })
        .join("") +
      "</dl>"
    );
  }

  function filesHtml(page) {
    const anchored = {};
    page.anchored_files.forEach(function (f) {
      anchored[f] = true;
    });
    const items = page.files
      .map(function (f) {
        return '<li class="' + (anchored[f] ? "is-anchored" : "") + '"><code>' + esc(f) + "</code></li>";
      })
      .join("");
    return (
      "<details><summary>" + plural(page.files.length, "file") + " (" + page.anchored_files.length +
      " with a decision, marked ✓; paths only, no source)</summary><ul class=\"map-files\">" + items + "</ul></details>"
    );
  }

  function neighboursHtml(page) {
    if (!page.neighbours.length) return "<p class=\"map-note\">No other module shares a decision with this one.</p>";
    return (
      '<p class="map-chips">' +
      page.neighbours
        .map(function (n) {
          return U.chip(n) + " (" + plural(n.shared, "shared decision") + ")";
        })
        .join(" ") +
      "</p>"
    );
  }

  function problemsHtml(page) {
    const orphans = page.orphaned
      .map(function (o) {
        return "<li><code>" + esc(o.decision_id) + "</code> anchors <code>" + esc(o.locus) + "</code>, which is gone</li>";
      })
      .join("");
    const conflicts = page.conflicts
      .map(function (c) {
        return "<li><code>" + esc(c.decision_a) + "</code> and <code>" + esc(c.decision_b) + "</code> (" + esc(c.severity) + "): " + esc(c.explanation) + "</li>";
      })
      .join("");
    return (
      (orphans ? "<h4>Orphaned anchors</h4><ul>" + orphans + "</ul>" : "") +
      (conflicts ? "<h4>Conflicts judged inside this module</h4><ul>" + conflicts + "</ul>" : "")
    );
  }

  function pageHtml(page) {
    const tile = page.tile;
    const cross = tile.cross_cutting
      ? '<p class="map-note">' + plural(tile.cross_cutting, "cross-cutting decision") + " touch this module; they are listed once, on the overview.</p>"
      : "";
    const decisions = page.decisions
      .map(function (d) {
        return decisionCard(d, tile.id);
      })
      .join("");
    return (
      '<button type="button" class="secondary map-back" data-map-back="1">← All modules</button>' +
      "<h2>" + esc(tile.name) + " " + U.tierChip(tile.tier) + " " + badge(tile.kind) + "</h2>" +
      '<p class="map-note">' + esc(tile.description || "No description.") + "</p>" +
      factsHtml(tile) +
      "<details><summary>Paths (" + page.paths.length + ")</summary><p>" + lociHtml(page.paths) + "</p></details>" +
      filesHtml(page) +
      '<h3>Decisions <label class="map-note"><input type="checkbox" id="map-page-shared" /> Shared only</label></h3>' +
      cross +
      (decisions || '<p class="map-note">No decision anchors in this module yet.</p>') +
      problemsHtml(page) +
      "<h3>Neighbouring modules</h3>" + neighboursHtml(page)
    );
  }

  function filterShared(pane, on) {
    pane.querySelectorAll(".map-decision").forEach(function (card) {
      card.hidden = on && !card.classList.contains("is-shared");
    });
  }

  global.RLMapPage = { pageHtml: pageHtml, decisionCard: decisionCard, filterShared: filterShared };
})(window);
