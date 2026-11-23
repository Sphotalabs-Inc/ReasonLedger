/* ReasonLedger Conflicts — pairs of decisions that may clash: settle the ones a model found,
 * check the ones nobody has read, and see the rest.
 *
 * Live mode only. A conflict is something a person must settle, so it has a tab and a count
 * of its own instead of sitting under a queue of approvals. Each side of a pair shows who
 * recorded and judged it and when, and the later-recorded one says so: which came second is
 * usually the first thing a person asks. The buttons carry data-action, handled in app.js.
 */
(function (global) {
  const R = global.RLRender;
  const esc = R.escapeHtml;

  function conflictsOf(view) {
    return view.conflicts_with_details || view.conflicts || [];
  }

  function relatedOf(view) {
    return view.related_with_details || view.related || [];
  }

  /** Conflict pairs render two shapes: enriched detail_a/detail_b, or plain decision_a/b. */
  function pairOf(c) {
    if (c.detail_a && c.detail_b) return [c.detail_a.decision_id, c.detail_b.decision_id];
    return [c.decision_a, c.decision_b];
  }

  /** Map each decision id → peer ids it is in a judged conflict with. */
  function peerMap(view) {
    const map = {};
    conflictsOf(view).forEach(function (c) {
      const pair = pairOf(c);
      if (!pair[0] || !pair[1]) return;
      pair.forEach(function (id, i) {
        if (!map[id]) map[id] = [];
        if (map[id].indexOf(pair[1 - i]) < 0) map[id].push(pair[1 - i]);
      });
    });
    return map;
  }

  function indexById(view) {
    const byId = {};
    (view.proposals || []).concat(view.decisions || []).forEach(function (d) {
      byId[d.id] = d;
    });
    return byId;
  }

  /** [htmlA, htmlB]: who and when under each side; the one recorded later is marked. */
  function sideMeta(c, byId) {
    const sides = pairOf(c).map(function (id) {
      return byId[id];
    });
    // An undated side parses to NaN, which loses both comparisons: then neither is marked.
    const at = sides.map(function (d) {
      return d && d.recorded_at ? Date.parse(d.recorded_at) : NaN;
    });
    const newer = at[0] > at[1] ? 0 : at[1] > at[0] ? 1 : -1;
    return sides.map(function (d, i) {
      if (!d) return "";
      const mark = i === newer ? '<p><span class="badge recent-badge">more recent</span></p>' : "";
      const lines = global.RLProvenance.lines(d).map(function (line) {
        return '<p class="conflict-who">' + line + "</p>";
      });
      return mark + lines.join("");
    });
  }

  function pairButton(look, action, id, successor, label) {
    return (
      '<button type="button" class="' + look + '" data-action="' + action + '" data-id="' + esc(id) +
      (successor ? '" data-successor="' + esc(successor) : "") + '">' + esc(label) + "</button>"
    );
  }

  /** What an agent needs to hear to write the decision that replaces a clashing pair. */
  function replacePrompt(pair) {
    return (
      pair[0] + " and " + pair[1] + " conflict. Read both with the reasonledger MCP tool " +
      "query_decisions, then record the decision that settles the question with " +
      "record_decision, setting supersedes to " + pair[0] + "."
    );
  }

  /** Check and Dismiss for a pair no model has read; both wait while a check is running. */
  function uncheckedActions(pair) {
    const off = global.RLJudge.busy() ? " disabled" : "";
    const ids = '" data-a="' + esc(pair[0]) + '" data-b="' + esc(pair[1]) + '"' + off;
    return (
      '<div class="actions"><button type="button" class="secondary" data-action="judge-pair' + ids +
      '>Check this pair</button><button type="button" class="dismiss" data-action="dismiss' + ids +
      ">Dismiss — not a conflict</button></div>" +
      '<p class="hint">Or ask your coding agent to judge just these two with its own model:</p>' +
      global.RLSetup.cmd(global.RLSetup.judgePairPrompt(pair[0], pair[1]))
    );
  }

  /**
   * The ways out of a judged conflict: keep one (the other becomes superseded by it), dismiss
   * it as not a conflict, retire one, or have an agent write a replacement. `settle` is false
   * when a side is a proposal, which is confirmed or rejected instead.
   */
  function settleActions(pair, settle) {
    const dismiss =
      '<button type="button" class="dismiss" data-action="dismiss" data-a="' + esc(pair[0]) +
      '" data-b="' + esc(pair[1]) + '">Dismiss — not a conflict</button>';
    if (!settle) return '<div class="actions">' + dismiss + "</div>";
    return (
      '<div class="actions">' +
      pairButton("primary", "supersede", pair[1], pair[0], "Keep " + pair[0]) +
      pairButton("primary", "supersede", pair[0], pair[1], "Keep " + pair[1]) +
      dismiss +
      '</div><details class="setup-more"><summary>Other ways to settle it</summary>' +
      '<ul class="setup-options"><li>One no longer applies at all: ' +
      pairButton("secondary", "retire", pair[0], "", "Retire " + pair[0]) + " " +
      pairButton("secondary", "retire", pair[1], "", "Retire " + pair[1]) +
      "</li><li>Neither is right: ask your coding agent to record the decision that replaces them. " +
      global.RLSetup.cmd(replacePrompt(pair)) +
      " It supersedes the first; supersede the second with <code>reasonledger supersede " +
      esc(pair[1]) + " --successor</code> and the new id.</li></ul></details>"
    );
  }

  function settleHtml(view, byId) {
    const conflicts = conflictsOf(view);
    const inForce = (view.decisions || []).filter(global.RLLedger.isInForce).map(function (d) {
      return d.id;
    });
    const unjudged = (view.counts || {}).unverified || 0;
    const none = unjudged
      ? "None found so far. A conflict only shows once a pair has been checked, and " +
        unjudged + (unjudged === 1 ? " related pair has" : " related pairs have") + " not been."
      : "None. Every related pair has been checked.";
    const cards = conflicts.map(function (c) {
      const pair = pairOf(c);
      const settle = pair.every(function (id) {
        return inForce.indexOf(id) >= 0;
      });
      return R.conflictItem(c, settleActions(pair, settle), sideMeta(c, byId));
    });
    return (
      '<section class="setup-card needs-card"><h2>Conflicts to settle' +
      (conflicts.length ? " (" + conflicts.length + ")" : "") +
      '</h2><p class="hint">' +
      esc(conflicts.length ? "A model judged that both answer the same question and the answers clash." : none) +
      "</p>" +
      cards.join("") +
      "</section>"
    );
  }

  /** Pairs that share a topic: not checked yet, or checked and found compatible. */
  function relatedHtml(view, byId) {
    const related = relatedOf(view);
    if (!related.length) return "";
    const cards = related.map(function (c) {
      const actions = c.relation === "unverified" ? uncheckedActions(pairOf(c)) : "";
      return R.conflictItem(c, actions, sideMeta(c, byId));
    });
    // The outcome of a single-pair check goes where that pair's card was.
    const note = global.RLJudge.pairNote();
    if (note.html) cards.splice(Math.min(note.at, cards.length), 0, note.html);
    return (
      '<h2 class="pairs-title">Related pairs (' + related.length + ")</h2>" +
      '<p class="hint">Decisions on similar topics: not checked yet, or checked and found compatible.</p>' +
      cards.join("")
    );
  }

  /** The Conflicts tab: what to settle, the check that finds more, then every related pair. */
  function html(view) {
    if (global.RLLedger.isEmpty(view)) {
      return '<p class="hint">No decisions to compare yet. The Overview tab shows how to record the first one.</p>';
    }
    const byId = indexById(view);
    return settleHtml(view, byId) + '<div id="judge-root"></div>' + relatedHtml(view, byId);
  }

  function count(view) {
    return conflictsOf(view).length;
  }

  global.RLConflicts = { html: html, count: count, peerMap: peerMap };
})(window);
