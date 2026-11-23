/* ReasonLedger UI — which decisions name which, for the Ask tab's search.
 *
 * Live mode only. A decision's text often names another by id ("This revises dec_…"), so a
 * search for an id finds both the decision itself and every one that mentions it. This tells
 * the two apart: the decision asked for comes first, and the others say that they only mention
 * it. Every card also lists what it refers to and what refers to it, each a link to that search.
 */
(function (global) {
  const esc = global.RLRender.escapeHtml;
  const ID = /\bdec_[a-z0-9]+\b/g;
  let refersTo = {};
  let referredBy = {};

  function prose(d) {
    return [d.context, d.choice].concat(d.assumptions || [], d.alternatives_rejected || []).join(" ");
  }

  /** Read every decision's text once; ids that are not in the ledger are ignored. */
  function index(decisions) {
    const known = {};
    decisions.forEach(function (d) {
      known[d.id] = true;
    });
    refersTo = {};
    referredBy = {};
    decisions.forEach(function (d) {
      const named = (prose(d).match(ID) || []).filter(function (id, at, all) {
        return known[id] && id !== d.id && all.indexOf(id) === at;
      });
      refersTo[d.id] = named;
      named.forEach(function (id) {
        (referredBy[id] = referredBy[id] || []).push(d.id);
      });
    });
  }

  /** Ids typed in the search box that are decisions in `shown`. */
  function asked(shown, text) {
    const words = text.toLowerCase().split(/\s+/);
    return shown
      .map(function (d) {
        return d.id;
      })
      .filter(function (id) {
        return words.indexOf(id) >= 0;
      });
  }

  function links(ids) {
    return ids
      .map(function (id) {
        return '<button type="button" class="locus-link" data-find="' + esc(id) + '">' + esc(id) + "</button>";
      })
      .join(", ");
  }

  /** A card's line of references; empty when it names no decision and none names it. */
  function html(d) {
    const to = refersTo[d.id] || [];
    const by = referredBy[d.id] || [];
    if (!to.length && !by.length) return "";
    const parts = [];
    if (to.length) parts.push("Refers to " + links(to));
    if (by.length) parts.push("Referred to by " + links(by));
    return '<p class="item-refs">' + parts.join(" · ") + "</p>";
  }

  function badge(text, kind) {
    return ' <span class="badge ref-badge ref-' + kind + '">' + esc(text) + "</span>";
  }

  /** The badge for a search hit: the decision asked for by id, or one that only mentions it. */
  function hitBadge(d, askedIds) {
    if (!askedIds.length) return "";
    if (askedIds.indexOf(d.id) >= 0) return badge("the decision you searched for", "asked");
    return badge("mentions " + askedIds.join(", "), "mention");
  }

  global.RLRefs = { index: index, asked: asked, html: html, hitBadge: hitBadge };
})(window);
