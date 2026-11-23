/* ReasonLedger Review — the dialog a person approves or retires a decision from.
 *
 * Live mode only. A verdict (approve, retire, supersede) is given with the whole record in view: context, choice,
 * assumptions, rejected alternatives, the code it explains, and who recorded it when. The
 * name it will be recorded under is shown beside the button and comes from the server
 * (the checkout's git identity); nothing typed here can change it. The buttons that open it
 * are built here too, and bound by app.js through their data-action.
 */
(function (global) {
  const R = global.RLRender;
  const esc = R.escapeHtml;
  const MODES = {
    approve: {
      title: "Review decision",
      verb: "Approve",
      acting: "Approving as",
      buttonClass: "primary",
      note: "Approving says you read this and agree it should stand.",
    },
    retire: {
      title: "Retire decision",
      verb: "Retire",
      acting: "Retiring as",
      buttonClass: "danger",
      note: "Retiring keeps the record and its approval as history, and stops it counting as guidance.",
      reason: "Why does it no longer apply? (recorded with the decision)",
    },
    supersede: {
      title: "Supersede decision",
      verb: "Supersede",
      acting: "Superseding as",
      buttonClass: "danger",
      note: "Superseding keeps this record and its approval as history, and points readers to the decision that stands.",
      reason: "Why does the other decision stand? (recorded with this one)",
    },
  };

  function decisionButton(d, action, label, kind) {
    return (
      '<button type="button" class="' +
      kind +
      '" data-action="' +
      action +
      '" data-id="' +
      esc(d.id) +
      '">' +
      label +
      "</button>"
    );
  }

  /** Only a pending record is waiting on a person; any other verdict is already evidence. */
  function reviewAction(d) {
    if (!global.RLNeeds.isPending(d)) return "";
    return decisionButton(d, "approve", "Review", "primary");
  }

  /** A decision still in force can be retired whatever its verdict: approval is not forever. */
  function actions(d) {
    if (d.status === "retired" || d.status === "superseded") return "";
    const retire = decisionButton(d, "retire", "Retire", "secondary");
    return '<div class="actions">' + reviewAction(d) + retire + "</div>";
  }

  function findButton(d, kind, label, look) {
    return (
      '<button type="button" class="' + look + '" data-review-id="' + esc(d.id) +
      '" data-review-kind="' + kind + '">' + label + "</button>"
    );
  }

  /** Review or retire from a search hit; browse.js handles the click, as its results are redrawn per key. */
  function findAction(d) {
    if (d.status === "retired" || d.status === "superseded") return "";
    const review = global.RLNeeds.isPending(d) ? findButton(d, "approve", "Review", "primary") : "";
    return '<div class="actions">' + review + findButton(d, "retire", "Retire", "secondary") + "</div>";
  }

  function lociHtml(d) {
    const loci = d.justifies || [];
    if (!loci.length) return '<p class="item-meta">Explains no code location.</p>';
    return (
      '<p class="item-notes-title">Code it explains</p><ul class="item-notes">' +
      loci
        .map(function (locus) {
          return "<li><code>" + esc(locus) + "</code></li>";
        })
        .join("") +
      "</ul>"
    );
  }

  function actingHtml(mode, identity) {
    if (!identity.name) return '<p class="review-acting error">' + esc(identity.hint) + "</p>";
    return (
      '<p class="review-acting">' +
      esc(mode.acting) +
      " <strong>" +
      esc(identity.name) +
      "</strong> — your git identity for this checkout.</p>"
    );
  }

  /** A mode that takes a decision out of force asks why; the answer is stored with it. */
  function reasonHtml(mode, successor) {
    if (!mode.reason) return "";
    const stands = successor
      ? '<p class="review-acting">Stands in its place: <code>' + esc(successor) + "</code></p>"
      : "";
    return (
      stands +
      '<label class="review-reason" for="review-reason">' +
      esc(mode.reason) +
      "</label>" +
      '<textarea id="review-reason" rows="3" required></textarea>'
    );
  }

  function bodyHtml(d, mode, successor, identity) {
    return (
      '<h2 id="review-title">' +
      esc(mode.title) +
      '</h2><div class="review-record">' +
      R.decisionItem(d, "") +
      lociHtml(d) +
      "</div>" +
      '<p class="hint">' +
      esc(mode.note) +
      "</p>" +
      reasonHtml(mode, successor) +
      actingHtml(mode, identity) +
      '<p class="error" id="review-error" role="alert" hidden></p>' +
      '<div class="actions"><button type="button" class="' +
      mode.buttonClass +
      '" id="review-go"' +
      (identity.name ? "" : " disabled") +
      ">" +
      esc(mode.verb) +
      '</button><button type="button" class="secondary" id="review-cancel">Cancel</button></div>'
    );
  }

  /** `ctx` is {identity, request(path, options), done(), successor?} from app.js. */
  function open(d, kind, ctx) {
    const mode = MODES[kind];
    const stale = document.querySelector("dialog.review-dialog");
    if (stale) stale.remove();
    const dialog = document.createElement("dialog");
    dialog.className = "review-dialog";
    dialog.setAttribute("aria-labelledby", "review-title");
    dialog.innerHTML = bodyHtml(d, mode, ctx.successor, ctx.identity);
    // The card is a copy: the page already owns this record's anchor, and here every
    // part of the reasoning is open rather than one click away.
    dialog.querySelector(".item").removeAttribute("id");
    dialog.querySelectorAll("details").forEach(function (details) {
      details.open = true;
    });
    const failed = dialog.querySelector("#review-error");
    const reason = dialog.querySelector("#review-reason");
    dialog.addEventListener("close", function () {
      dialog.remove();
    });
    dialog.querySelector("#review-cancel").addEventListener("click", function () {
      dialog.close();
    });
    dialog.querySelector("#review-go").addEventListener("click", async function () {
      if (reason && !reason.value.trim()) {
        reason.focus();
        return;
      }
      try {
        await ctx.request("/api/decisions/" + encodeURIComponent(d.id) + "/" + kind, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(reason ? { reason: reason.value.trim(), successor: ctx.successor } : {}),
        });
        dialog.close();
        await ctx.done();
      } catch (err) {
        failed.textContent = err.message || String(err);
        failed.hidden = false;
      }
    });
    document.body.appendChild(dialog);
    dialog.showModal();
  }

  global.RLReview = { open: open, actions: actions, button: reviewAction, findAction: findAction };
})(window);
