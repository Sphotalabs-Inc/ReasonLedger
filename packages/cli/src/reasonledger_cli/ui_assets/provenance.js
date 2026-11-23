/* ReasonLedger UI — who did what to a decision, and when.
 *
 * Pure, like render.js, so the static export inlines it. One line per event a reviewer may
 * be asked to trust: recorded, confirmed or approved, retired, superseded. A date the record
 * does not carry is said to be missing rather than left blank, and one read from git history
 * says so.
 */
(function (global) {
  const NO_DATE = "date not recorded";
  const VERDICTS = { reviewed: "Approved", modified: "Approved with changes", rejected: "Rejected" };

  function esc(value) {
    return global.RLRender.escapeHtml(value);
  }

  /** ISO timestamp → "2026-11-09 14:03 UTC", or null when absent or unreadable. */
  function stamp(value) {
    const date = value ? new Date(value) : null;
    if (!date || isNaN(date.getTime())) return null;
    return date.toISOString().slice(0, 16).replace("T", " ") + " UTC";
  }

  function event(verb, who, at, note) {
    const date = stamp(at);
    return esc(verb + " by " + who) + (date ? " on " + esc(date) : ", " + NO_DATE) + (note || "");
  }

  function recorder(d) {
    if (d.ai_tool === "none") return "a person";
    return d.ai_tool + (d.model ? " (" + d.model + ")" : "");
  }

  function lines(d) {
    const out = [];
    if (d.ai_tool) {
      out.push(event("Recorded", recorder(d), d.recorded_at, d.recorded_at_from_git ? " (date from git history)" : ""));
    }
    if (d.confirmed_by) {
      out.push(event("Confirmed", d.confirmed_by, d.confirmed_at));
    } else if (d.approved_by && VERDICTS[d.oversight]) {
      out.push(event(VERDICTS[d.oversight], d.approved_by, d.approved_at));
    }
    if (d.retired_by) {
      out.push(event("Retired", d.retired_by, d.retired_at, d.retired_reason ? " — " + esc(d.retired_reason) : ""));
    }
    const successor = d.superseded_by ? global.RLRender.decisionLink(d.superseded_by) : "";
    if (d.superseded_decided_by) {
      const why = d.superseded_reason ? " — " + esc(d.superseded_reason) : "";
      out.push(event("Superseded", d.superseded_decided_by, d.superseded_at, ", in favour of " + successor + why));
    } else if (successor) {
      out.push("Superseded by " + successor);
    }
    return out;
  }

  function html(d) {
    return lines(d)
      .map(function (line) {
        return '<p class="item-meta">' + line + "</p>";
      })
      .join("");
  }

  global.RLProvenance = { html: html, lines: lines, stamp: stamp };
})(window);
