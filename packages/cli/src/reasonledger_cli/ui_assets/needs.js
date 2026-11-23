/* ReasonLedger UI — what counts as waiting on a person, and how a record's title is clipped.
 *
 * Live mode only; shared by the Review queue, the review dialog's buttons and the Ask tab.
 */
(function (global) {
  const TITLE_MAX = 110;

  /** A retired or superseded record is history: nobody is asked to vouch for it. */
  function isPending(d) {
    return d.oversight === "pending" && d.status !== "retired" && d.status !== "superseded";
  }

  function clip(text) {
    const flat = String(text || "").replace(/\s+/g, " ").trim();
    return flat.length > TITLE_MAX ? flat.slice(0, TITLE_MAX - 1) + "…" : flat;
  }

  const DAY_MS = 24 * 60 * 60 * 1000;

  /** Whole days since the record was written, or null when it carries no date at all. */
  function waitingDays(d, now) {
    const at = d.recorded_at ? Date.parse(d.recorded_at) : NaN;
    return isNaN(at) ? null : Math.max(0, Math.floor(((now || Date.now()) - at) / DAY_MS));
  }

  /** "waiting 12 days", so a decision left for weeks does not look like one from this morning. */
  function waitingLabel(d, now) {
    const days = waitingDays(d, now);
    if (days === null) return "";
    if (days === 0) return "waiting since today";
    return "waiting " + days + (days === 1 ? " day" : " days");
  }

  /** Oldest first, so the longest wait is at the top; undated records go last, in id order. */
  function oldestFirst(decisions) {
    return decisions.slice().sort(function (a, b) {
      const x = a.recorded_at ? Date.parse(a.recorded_at) : Infinity;
      const y = b.recorded_at ? Date.parse(b.recorded_at) : Infinity;
      return x === y ? (a.id < b.id ? -1 : 1) : x - y;
    });
  }

  global.RLNeeds = {
    isPending: isPending,
    clip: clip,
    waitingDays: waitingDays,
    waitingLabel: waitingLabel,
    oldestFirst: oldestFirst,
  };
})(window);
