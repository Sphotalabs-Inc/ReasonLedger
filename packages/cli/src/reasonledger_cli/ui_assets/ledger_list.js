/* ReasonLedger UI — the lists a person works through: the Review queue, and the ledger's
 * side lists (orphaned, stale) that the Ask tab shows on request. Pairs are in conflicts.js.
 *
 * Live mode only. A decision in the queue is one line until someone opens it: with every
 * card open the page ran to twenty screens. The buttons here carry data-action, which
 * app.js handles wherever they are drawn.
 */
(function (global) {
  const R = global.RLRender;
  const esc = R.escapeHtml;

  function proposalActions(p) {
    const confirmLabel = p.supersedes ? "Confirm &amp; retire" : "Confirm";
    return (
      '<div class="actions">' +
      '<button type="button" class="primary" data-action="confirm" data-id="' +
      esc(p.id) +
      '">' +
      confirmLabel +
      "</button>" +
      '<button type="button" class="danger" data-action="reject" data-id="' +
      esc(p.id) +
      '">Reject</button></div>'
    );
  }

  function waitingBadge(d) {
    const label = global.RLNeeds.waitingLabel(d);
    return label ? ' <span class="badge waiting">' + esc(label) + "</span>" : "";
  }

  /** One line per pending decision, its Review button on the line; opening it shows the card. */
  function decisionRow(d) {
    return (
      '<details class="item-row"><summary><code>' +
      esc(d.id) +
      "</code>" +
      R.proposerBadge(d) +
      waitingBadge(d) +
      ' <span class="item-row-what">' +
      esc(global.RLNeeds.clip(d.context)) +
      "</span>" +
      global.RLReview.button(d) +
      '<span class="item-row-meta">' +
      (global.RLProvenance.lines(d)[0] || "") +
      "</span></summary>" +
      R.decisionItem(d, global.RLReview.actions(d)) +
      "</details>"
    );
  }

  /** Nothing recorded and nothing proposed: the app has only setup to offer. */
  function isEmpty(view) {
    return !(view.decisions || []).length && !(view.proposals || []).length;
  }

  /** How many approvals wait on a person: the number on the Review tab. */
  function waitingCount(view) {
    return (view.decisions || []).filter(global.RLNeeds.isPending).length + (view.proposals || []).length;
  }

  function isInForce(d) {
    return d.status !== "retired" && d.status !== "superseded";
  }

  function group(title, count, bodyHtml) {
    if (!count) return "";
    return "<h3>" + esc(title) + " (" + count + ")</h3>" + bodyHtml;
  }

  /** The Review tab: every pending decision and proposal, and nothing else. */
  function queueHtml(view) {
    const waiting = global.RLNeeds.oldestFirst((view.decisions || []).filter(global.RLNeeds.isPending));
    const proposals = view.proposals || [];
    const peersById = global.RLConflicts.peerMap(view);
    if (isEmpty(view)) {
      return (
        '<section class="setup-card needs-card"><h2>Nothing to review yet</h2>' +
        '<p class="hint">Decisions your agent records show up here for you to approve. ' +
        "The Overview tab shows how to record the first one.</p></section>"
      );
    }
    if (!waitingCount(view)) {
      return (
        '<section class="setup-card needs-card"><h2>Nothing is waiting on you</h2>' +
        '<p class="hint">Every decision has been judged by a person, and there is no ' +
        "proposal to confirm.</p></section>"
      );
    }
    return (
      '<section class="setup-card needs-card"><h2>Waiting on you</h2>' +
      '<p class="hint">Longest-waiting first. Review opens the whole decision; approving there says you read it ' +
      "and agree it should stand.</p>" +
      group("Decisions to approve", waiting.length, waiting.map(decisionRow).join("")) +
      group(
        "Proposals to confirm",
        proposals.length,
        proposals
          .map(function (p) {
            return R.proposalItem(p, proposalActions(p), peersById[p.id] || []);
          })
          .join("")
      ) +
      "</section>"
    );
  }

  function decisionsById(view) {
    const byId = {};
    (view.decisions || []).forEach(function (d) {
      byId[d.id] = d;
    });
    return byId;
  }

  /** Retire sits on the card: the decision's code is gone, and a person says whether it still stands. */
  function orphanHtml(view) {
    const byId = decisionsById(view);
    return (view.orphaned || [])
      .map(function (o) {
        const d = byId[o.decision_id];
        return R.orphanItem(o, byId, d ? global.RLReview.actions(d) : "");
      })
      .join("");
  }

  /** The side lists, by the Ask tab's filter value. Each: what it holds and how to draw it. */
  const SIDE_LISTS = {
    orphaned: {
      label: "Orphaned",
      hint: "The code these decisions point at is gone or moved. Retire any that no longer hold; decisions on nearby code are listed as possible replacements.",
      count: function (view) {
        return (view.orphaned || []).length;
      },
      html: function (view) {
        return orphanHtml(view);
      },
    },
    stale: {
      label: "Stale and watchers",
      hint: "An assumption these depended on no longer holds. Worth re-deciding.",
      count: function (view) {
        return (view.stale || []).length + (view.watchers || []).length;
      },
      html: function (view) {
        // Wrapped, not passed bare: map would hand decisionItem its index as actionsHtml.
        const stale = (view.stale || []).map(function (d) {
          return R.decisionItem(d);
        });
        return stale.join("") + (view.watchers || []).map(R.watcherItem).join("");
      },
    },
  };

  /** [{key, label, count}] for the side lists that hold something. */
  function sideLists(view) {
    return Object.keys(SIDE_LISTS)
      .map(function (key) {
        return { key: key, label: SIDE_LISTS[key].label, count: SIDE_LISTS[key].count(view) };
      })
      .filter(function (list) {
        return list.count > 0;
      });
  }

  function sideListHtml(view, key) {
    const list = SIDE_LISTS[key];
    return '<p class="hint">' + esc(list.hint) + "</p>" + list.html(view);
  }

  global.RLLedger = {
    isEmpty: isEmpty,
    isInForce: isInForce,
    waitingCount: waitingCount,
    queueHtml: queueHtml,
    sideLists: sideLists,
    sideListHtml: sideListHtml,
  };
})(window);
