/* ReasonLedger Organize — "Unplaced decisions": decisions with no working anchor, placed by hand.
 *
 * Live mode only. A decision belongs where its code anchors are; these have no anchor, or only
 * anchors that point at files that are gone. A card says why, offers the homes the repo's own
 * history points at (with the evidence), and lets a person pick another. Nothing is placed
 * without a click, and no model is involved. It binds its own events on its panel.
 */
(function (global) {
  const esc = global.RLRender.escapeHtml;
  const U = global.RLMapUi;
  const DEAD_SHOWN = 3;
  const LABELS = { waiting: "no module", guessed: "module guessed from a dead anchor", hand: "placed by hand" };

  function badge(text, extra) {
    return '<span class="map-badge' + (extra ? " " + extra : "") + '">' + esc(text) + "</span>";
  }

  /** Items still listed: null when there are none, else how many have no module yet. */
  function count(data) {
    return data && data.items.length ? data.waiting : null;
  }

  function chips(list) {
    return (
      '<p class="org-ev">' +
      list
        .map(function (text) {
          return '<span class="org-chip">' + esc(text) + "</span>";
        })
        .join(" ") +
      "</p>"
    );
  }

  function idea(item, home) {
    return (
      '<li class="org-idea"><button type="button" class="secondary" data-decision-act="home" data-decision="' +
      esc(item.id) + '" data-home="' + esc(home.module) + '">Place in ' + esc(home.name) + "</button> " +
      badge(home.confidence, home.confidence === "high" ? "is-shared" : home.confidence === "low" ? "is-warn" : "") +
      chips(home.evidence) + "</li>"
    );
  }

  function deadHtml(item) {
    if (!item.dead_anchors.length) return "";
    const shown = item.dead_anchors.slice(0, DEAD_SHOWN).map(function (locus) {
      return "<code>" + esc(locus) + "</code>";
    });
    const more = item.dead_anchors.length > DEAD_SHOWN ? " and " + (item.dead_anchors.length - DEAD_SHOWN) + " more" : "";
    return " (" + shown.join(", ") + more + ")";
  }

  function placedHtml(item) {
    if (item.state === "guessed") {
      return "<p>Now in <strong>" + esc(item.modules.join(", ")) + "</strong> only because the path of a dead anchor still matches it.</p>";
    }
    if (!item.placed_by) return "";
    return (
      "<p>Placed in <strong>" + esc(item.modules.join(", ")) + "</strong> by " + esc(item.placed_by) +
      ' <button type="button" class="org-link" data-decision-act="take-back" data-decision="' + esc(item.id) +
      '">Take back</button></p>'
    );
  }

  function formHtml(item) {
    return (
      '<form class="org-place" data-decision="' + esc(item.id) + '"><label>' + (item.state === "hand" ? "Change to " : "Place in ") +
      '<input type="text" list="org-targets" autocomplete="off" placeholder="a module id, or up to four with commas" /></label>' +
      '<button type="submit" class="secondary">Place</button></form>'
    );
  }

  function card(item) {
    const ideas = item.state === "hand" || !item.ideas.length
      ? ""
      : '<ul class="org-ideas">' + item.ideas.map(function (home) {
          return idea(item, home);
        }).join("") + "</ul>";
    return (
      '<article class="org-card"><header><strong>' + esc(item.context || "(no context recorded)") + "</strong> " +
      badge(LABELS[item.state], item.state === "waiting" ? "is-warn" : "") + "</header>" +
      "<p>" + esc(item.choice || "") + '</p><p class="map-note"><code>' + esc(item.id) + "</code>: " + esc(item.why) +
      deadHtml(item) + ".</p>" + placedHtml(item) + ideas + formHtml(item) + "</article>"
    );
  }

  function staleHtml(stale) {
    const ids = Object.keys(stale);
    if (!ids.length) return "";
    return (
      '<p class="map-note">A hand placement no longer applies: ' +
      ids.map(function (id) {
        return "<code>" + esc(id) + "</code> (" + esc(stale[id]) + ")";
      }).join("; ") + ".</p>"
    );
  }

  function html(data) {
    const intro =
      '<div class="org-head"><h2 id="org-title">Unplaced decisions</h2></div><p class="map-note">A decision belongs ' +
      "where its code anchors are. These have no anchor, or only anchors that point at files that are gone, so you " +
      "can say where they belong; a few sit in a module only because a dead anchor's path still matches it. One with an anchor that still works is placed by it and is not listed. Nothing is " +
      "placed until you click.</p>";
    if (!data || !data.items.length) return intro + '<p class="map-note">Every decision has an anchor that works.</p>';
    return intro + staleHtml(data.stale) + data.items.map(card).join("") + '<p class="map-note">' + U.plural(data.waiting, "decision") + " still without a module.</p>";
  }

  function place(ctx, id, modules) {
    ctx.act("place-decision", { decision: id, modules: modules });
  }

  /** Bind the panel once; `ctx.act` writes through the workbench and reloads it. */
  function mount(host, ctx) {
    host.addEventListener("click", function (ev) {
      const button = ev.target.closest("[data-decision-act]");
      if (!button) return;
      const id = button.getAttribute("data-decision");
      if (button.getAttribute("data-decision-act") === "take-back") {
        ctx.act("unplace-decision", { decision: id });
      } else {
        place(ctx, id, [button.getAttribute("data-home")]);
      }
    });
    host.addEventListener("submit", function (ev) {
      ev.preventDefault();
      const modules = ev.target.querySelector("input").value.split(",").map(function (name) {
        return name.trim();
      }).filter(Boolean);
      if (modules.length) place(ctx, ev.target.getAttribute("data-decision"), modules);
    });
  }

  global.RLOrganizeDecisions = { html: html, count: count, mount: mount };
})(window);
