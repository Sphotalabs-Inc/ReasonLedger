/* ReasonLedger UI — pure item renderers, shared by the live app and the static export.
 *
 * Nothing here touches the network or the session token, which is what lets the
 * static export inline this file verbatim instead of keeping a second copy of the
 * same markup in sync.
 */
(function (global) {
  const COUNT_KEYS = [
    "proposed",
    "confirmed",
    "active",
    "pending_approval",
    "agreed",
    "recommended",
    "superseded",
    "retired",
    "stale",
    "orphaned",
    "conflicts",
    "related",
  ];

  /** Count keys whose raw name is not what a reader should see. */
  const COUNT_LABELS = { pending_approval: "pending review" };

  /** Who originated a choice: a person stated or accepted it, or an agent made it. */
  const PROPOSER_LABELS = {
    human: { text: "agreed", hint: "A person stated or explicitly accepted this choice" },
    ai: { text: "recommended", hint: "An agent chose this; a person may not have asked for it" },
  };

  /** Count chip → section id (status chips land on Decisions). */
  const COUNT_SECTIONS = {
    proposed: "section-proposals",
    confirmed: "section-decisions",
    active: "section-decisions",
    pending_approval: "section-decisions",
    agreed: "section-decisions",
    recommended: "section-decisions",
    superseded: "section-decisions",
    retired: "section-decisions",
    stale: "section-stale",
    orphaned: "section-orphaned",
    conflicts: "section-conflicts",
    related: "section-related",
  };

  /** What a related pair's badge says in place of a severity. */
  const RELATION_LABELS = {
    unverified: "not judged yet",
    compatible: "judged compatible",
  };

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      // Escaped, not literal: test_ui_assets.py strips string literals with a regex, and
      // a bare double-quote inside a regex literal desyncs it for the rest of the file.
      .replace(/\u0022/g, "&quot;");
  }

  function itemAnchorId(id) {
    return "item-" + String(id || "");
  }

  function decisionLink(id) {
    if (!id) return "";
    return (
      '<a class="item-link" href="#' +
      escapeHtml(itemAnchorId(id)) +
      '">' +
      escapeHtml(id) +
      "</a>"
    );
  }

  function countsList(counts) {
    return (
      '<ul class="counts">' +
      COUNT_KEYS.map(function (k) {
        var sectionId = COUNT_SECTIONS[k];
        var label =
          "<strong>" +
          escapeHtml(counts[k] || 0) +
          "</strong> " +
          escapeHtml(COUNT_LABELS[k] || k);
        if (!sectionId) return "<li>" + label + "</li>";
        return (
          '<li><a class="count-chip" href="#' +
          escapeHtml(sectionId) +
          '">' +
          label +
          "</a></li>"
        );
      }).join("") +
      "</ul>"
    );
  }

  /** A proposal that replaces a confirmed decision needs that stated before any action. */
  function supersedeNote(p) {
    if (!p.supersedes) return "";
    return (
      '<p class="item-supersede">Replaces ' +
      decisionLink(p.supersedes) +
      " — confirming this retires that decision.</p>"
    );
  }

  function conflictPeersNote(peers) {
    if (!peers || !peers.length) return "";
    return (
      '<p class="item-conflict-peers">Conflicts with ' +
      peers.map(decisionLink).join(", ") +
      "</p>"
    );
  }

  function proposalItem(p, actionsHtml, conflictPeers) {
    return (
      '<article class="item' +
      (p.supersedes ? " supersede" : "") +
      (p.has_conflict ? " has-conflict" : "") +
      '" id="' +
      escapeHtml(itemAnchorId(p.id)) +
      '" data-proposal="' +
      escapeHtml(p.id) +
      '"><p class="item-title">' +
      escapeHtml(p.id) +
      (p.has_conflict ? ' <span class="badge conflict-badge">conflict</span>' : "") +
      '</p><p class="item-body"><strong>' +
      escapeHtml(p.context || "") +
      '</strong></p><p class="item-body">' +
      escapeHtml(p.choice || "") +
      "</p>" +
      conflictPeersNote(conflictPeers) +
      supersedeNote(p) +
      '<p class="item-meta">' +
      (p.source_ref ? escapeHtml(p.source_ref) : "") +
      "</p>" +
      (actionsHtml || "") +
      "</article>"
    );
  }

  /** A decision in force no person has judged yet; one out of force is waiting on nobody. */
  function pendingBadge(d) {
    if (d.oversight !== "pending" || d.status === "retired" || d.status === "superseded") return "";
    return ' <span class="badge pending-badge">pending review</span>';
  }

  /** Whose idea the choice was; absent on records that predate the field. */
  function proposerBadge(d) {
    var label = PROPOSER_LABELS[d.proposed_by];
    if (!label) return "";
    return (
      ' <span class="badge proposer-badge ' +
      escapeHtml(d.proposed_by) +
      '" title="' +
      escapeHtml(label.hint) +
      '">' +
      escapeHtml(label.text) +
      "</span>"
    );
  }

  function reasoningList(title, items) {
    return (
      '<p class="item-notes-title">' +
      escapeHtml(title) +
      '</p><ul class="item-notes">' +
      items
        .map(function (text) {
          return "<li>" + escapeHtml(text) + "</li>";
        })
        .join("") +
      "</ul>"
    );
  }

  /** What a reviewer vouches for beyond the choice, collapsed so the card stays scannable. */
  function reasoningDetails(d) {
    var assumptions = d.assumptions || [];
    var rejected = d.alternatives_rejected || [];
    var labels = [];
    var inner = "";
    if (assumptions.length) {
      labels.push("Assumptions (" + assumptions.length + ")");
      inner += reasoningList("Assumptions", assumptions);
    }
    if (rejected.length) {
      labels.push("Alternatives rejected (" + rejected.length + ")");
      inner += reasoningList("Alternatives rejected", rejected);
    }
    if (!inner) return "";
    return (
      '<details class="item-details"><summary>' +
      escapeHtml(labels.join(" · ")) +
      "</summary>" +
      inner +
      "</details>"
    );
  }

  function decisionItem(d, actionsHtml) {
    return (
      '<article class="item status-' +
      escapeHtml(d.status) +
      '" id="' +
      escapeHtml(itemAnchorId(d.id)) +
      '"><p class="item-title">' +
      escapeHtml(d.id) +
      ' <span class="badge">' +
      escapeHtml(d.status) +
      "</span>" +
      proposerBadge(d) +
      pendingBadge(d) +
      '</p><p class="item-body"><strong>' +
      escapeHtml(d.context || "") +
      '</strong></p><p class="item-body">' +
      escapeHtml(d.choice || "") +
      "</p>" +
      reasoningDetails(d) +
      global.RLProvenance.html(d) +
      (actionsHtml || "") +
      "</article>"
    );
  }

  function watcherItem(w) {
    return (
      '<article class="item"><p class="item-title">' +
      decisionLink(w.decision_id) +
      ' <span class="badge">' +
      escapeHtml(w.status) +
      '</span></p><p class="item-meta">' +
      escapeHtml(w.condition) +
      (w.last_value != null ? " · last " + escapeHtml(w.last_value) : "") +
      "</p></article>"
    );
  }

  var ORPHAN_NOTES = {
    anchor_moved: ", which moved: the code is still in the file at other lines",
    anchor_lost: ", whose code can no longer be found; it matches the whole file",
  };

  /** One line of a decision's answer, for places that must not send the reader elsewhere. */
  function brief(d) {
    const text = (d && (d.choice || d.context)) || "";
    return text.length > 160 ? text.slice(0, 157) + "…" : text;
  }

  /** Decisions in force that explain code beside the lost locus: where its replacement likely lives. */
  function candidatesHtml(o, byId) {
    const found = (o.candidates || []).filter(function (id) {
      return byId && byId[id];
    });
    if (!found.length) return "";
    return (
      '<p class="item-notes-title">Possibly replaced by</p><ul class="item-notes">' +
      found
        .map(function (id) {
          return "<li><code>" + escapeHtml(id) + "</code> " + escapeHtml(brief(byId[id])) + "</li>";
        })
        .join("") +
      "</ul>"
    );
  }

  /**
   * `byId` (decisions by id) and `actionsHtml` are given in the live app, where the card can
   * say what the decision decided and offer Retire without leaving the list.
   */
  function orphanItem(o, byId, actionsHtml) {
    const d = byId && byId[o.decision_id];
    return (
      '<article class="item orphan"><p class="item-title">' +
      (d ? "<code>" + escapeHtml(o.decision_id) + "</code>" : decisionLink(o.decision_id)) +
      '</p><p class="item-meta">justifies <code>' +
      escapeHtml(o.locus) +
      "</code>" +
      (ORPHAN_NOTES[o.reason] || ", which is no longer in the repo") +
      "</p>" +
      (d ? "<p>" + escapeHtml(brief(d)) + "</p>" : "") +
      candidatesHtml(o, byId) +
      (actionsHtml || "") +
      "</article>"
    );
  }

  function conflictSide(detail, fallbackId, metaHtml) {
    var id = (detail && detail.decision_id) || fallbackId;
    var choice = detail ? detail.choice : null;
    var sourceRef = detail ? detail.source_ref : null;
    return (
      '<div class="conflict-side"><strong>' +
      decisionLink(id) +
      "</strong><p><em>" +
      escapeHtml(choice || "(no choice)") +
      "</em></p>" +
      (sourceRef ? '<p class="source">from ' + escapeHtml(sourceRef) + "</p>" : "") +
      (metaHtml || "") +
      "</div>"
    );
  }

  /** `sideMeta` is [htmlA, htmlB], shown under each side's choice; the export passes none. */
  function conflictItem(c, actionsHtml, sideMeta) {
    var meta = sideMeta || [];
    var idA = (c.detail_a && c.detail_a.decision_id) || c.decision_a;
    var idB = (c.detail_b && c.detail_b.decision_id) || c.decision_b;
    var title =
      c.context ||
      (c.detail_a && c.detail_a.context) ||
      (c.detail_b && c.detail_b.context) ||
      "Related decisions";
    // Only a judged conflict gets the alarm styling and a severity; a related pair
    // says what is known about it instead.
    var isConflict = !c.relation || c.relation === "conflict";
    var badge = isConflict ? c.severity : RELATION_LABELS[c.relation] || c.relation;
    // A re-opened pair was dismissed once, on text that has since changed. Without
    // saying so it reads as the detector ignoring a verdict the reviewer already gave.
    var reopened = c.status === "reopened";
    return (
      '<article class="item ' +
      (isConflict ? "conflict" : "related") +
      (reopened ? " reopened" : "") +
      '" id="' +
      escapeHtml(itemAnchorId("conflict-" + idA + "-" + idB)) +
      '"><p class="item-title">' +
      escapeHtml(title) +
      ' <span class="badge">' +
      escapeHtml(badge) +
      "</span>" +
      (reopened ? ' <span class="badge reopened-badge">re-opened</span>' : "") +
      "</p>" +
      (reopened
        ? '<p class="item-reopened">You dismissed this pair before. A decision has ' +
          "changed since, so the earlier verdict no longer covers it.</p>"
        : "") +
      '<div class="conflict-details">' +
      conflictSide(c.detail_a, c.decision_a, meta[0]) +
      '<div class="conflict-vs">vs</div>' +
      conflictSide(c.detail_b, c.decision_b, meta[1]) +
      "</div>" +
      verdictHtml(c) +
      (actionsHtml || "") +
      "</article>"
    );
  }

  /**
   * What the pair's check found, led by the word Verdict, then who gave it and when. A pair
   * nobody has judged only says why it is shown, so it gets no verdict line.
   */
  function verdictHtml(c) {
    var judged = c.relation === "conflict" || c.relation === "compatible" || !c.relation;
    if (!judged) return '<p class="item-meta">' + escapeHtml(c.explanation || "") + "</p>";
    var word = c.relation === "compatible" ? "Compatible" : "Conflict";
    var when = global.RLProvenance ? global.RLProvenance.stamp(c.judged_at) : null;
    var by = c.judged_by
      ? "Judged by " + escapeHtml(c.judged_by) + (when ? " on " + escapeHtml(when) : ", date not recorded")
      : "Who judged this, and when, was not recorded.";
    return (
      '<p class="item-verdict"><strong>Verdict: ' + word + ".</strong> " +
      escapeHtml(c.explanation || "") + "</p>" +
      '<p class="item-meta">' + by + "</p>"
    );
  }

  var CONFLICTS_HINT = "a model judged that both answer the same question and the answers clash";
  var RELATED_HINT = "similar topics that are not conflicts, or not judged yet";

  /** A degraded embedder changes what every related pair means, so it leads the page. */
  function embedderNotice(view) {
    var fallback = view.embedder && view.embedder.fallback_reason;
    if (!fallback) return "";
    return (
      '<p class="embedder-warning" role="status">Related decisions use basic word ' +
      "matching because " +
      escapeHtml(fallback) +
      ".</p>"
    );
  }

  function unjudgedNotice(view) {
    var unjudged = (view.counts && view.counts.unverified) || 0;
    if (!unjudged) return "";
    return (
      '<p class="embedder-warning" role="status">' +
      escapeHtml(unjudged) +
      " related pair(s) are not judged yet. Optional: run <code>reasonledger judge</code>, " +
      "or ask your coding agent to call <code>get_judging_task</code>, to check them for " +
      "conflicts.</p>"
    );
  }

  /** The export's warnings above the counts: it has no sections to fold either into. */
  function relatedNotices(view) {
    return embedderNotice(view) + unjudgedNotice(view);
  }

  function section(title, hint, bodyHtml, emptyHint, count, open, sectionId) {
    var n = count == null ? 0 : count;
    return (
      '<details class="section"' +
      (sectionId ? ' id="' + escapeHtml(sectionId) + '"' : "") +
      (open ? " open" : "") +
      "><summary>" +
      '<span class="section-title">' +
      escapeHtml(title) +
      '</span> <span class="section-count">(' +
      escapeHtml(n) +
      ")</span></summary>" +
      (hint ? '<p class="hint">' + escapeHtml(hint) + "</p>" : "") +
      (bodyHtml || '<p class="hint">' + escapeHtml(emptyHint) + "</p>") +
      "</details>"
    );
  }

  global.RLRender = {
    escapeHtml: escapeHtml,
    embedderNotice: embedderNotice,
    relatedNotices: relatedNotices,
    CONFLICTS_HINT: CONFLICTS_HINT,
    RELATED_HINT: RELATED_HINT,
    itemAnchorId: itemAnchorId,
    decisionLink: decisionLink,
    reasoningDetails: reasoningDetails,
    proposerBadge: proposerBadge,
    pendingBadge: pendingBadge,
    countsList: countsList,
    proposalItem: proposalItem,
    decisionItem: decisionItem,
    watcherItem: watcherItem,
    orphanItem: orphanItem,
    conflictItem: conflictItem,
    section: section,
  };
})(window);
