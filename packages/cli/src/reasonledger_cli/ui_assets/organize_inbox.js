/* ReasonLedger Organize inbox — state and events. Live mode only.
 *
 * Skipping a card only hides it in this window; accepting or declining writes modules.yml through
 * the same edits as the rest of the workbench, so an accepted placement is a label like any other
 * and undo covers it.
 */
(function (global) {
  const PAGE = 5;
  const state = { shown: PAGE, skipped: {} };

  function open(inbox) {
    return inbox.items.filter(function (item) {
      return !state.skipped[item.key];
    });
  }

  function isHigh(item) {
    return item.kind === "place" && item.confidence === "high";
  }

  function skippedKeys(inbox) {
    return inbox.items.filter(function (item) {
      return state.skipped[item.key];
    }).map(function (item) {
      return item.key;
    });
  }

  /** High-confidence homes still open: all of them on the server, less the ones skipped here. */
  function highCount(inbox) {
    return inbox.high_places - inbox.items.filter(function (item) {
      return state.skipped[item.key] && isHigh(item);
    }).length;
  }

  /** Items still needing a decision in this window: what the list entry counts. */
  function count(inbox) {
    if (!inbox) return 0;
    return inbox.total - (inbox.items.length - open(inbox).length);
  }

  function html(inbox) {
    const items = open(inbox);
    return global.RLOrganizeInboxUi.inboxHtml(inbox, items.slice(0, state.shown), Math.max(0, items.length - state.shown), highCount(inbox));
  }

  function find(ctx, key) {
    return ctx.state.inbox.items.filter(function (item) {
      return item.key === key;
    })[0];
  }

  async function newModule(ctx, item) {
    const name = window.prompt("Name the new module:", item.name || "");
    if (!name || !name.trim()) return;
    await ctx.act("inbox-accept", { key: item.key, name: name.trim() });
  }

  async function confirmProposal(ctx, item) {
    await ctx.act("confirm", { ids: [item.target] });
  }

  async function rejectProposal(ctx, item) {
    if (!window.confirm("Reject " + item.target + "? It stays down while a map covers about its files.")) return;
    await ctx.act("reject", { id: item.target, reason: window.prompt("Why? (optional)") || "" });
  }

  /** One button on a card; returns a promise when it writes, or nothing when it only shows. */
  function onClick(button, ctx) {
    const action = button.getAttribute("data-inbox");
    const item = find(ctx, button.getAttribute("data-key"));
    const actions = {
      accept: function () { return ctx.act("inbox-accept", { key: item.key }); },
      rule: function () { return ctx.act("inbox-accept", { key: item.key, rule: true }); },
      decline: function () { return ctx.act("inbox-decline", { key: item.key }); },
      new: function () { return newModule(ctx, item); },
      confirm: function () { return confirmProposal(ctx, item); },
      reject: function () { return rejectProposal(ctx, item); },
      open: function () { return ctx.open(item.target); },
      all: function () { return ctx.act("inbox-accept-all", { skipped: skippedKeys(ctx.state.inbox) }); },
      more: function () { state.shown += PAGE; ctx.paint(); },
      skip: function () { state.skipped[item.key] = true; ctx.paint(); },
      choose: function () {
        const form = button.closest(".org-card").querySelector(".org-choose");
        form.hidden = !form.hidden;
        if (!form.hidden) form.querySelector("input").focus();
      },
    };
    return actions[action] ? actions[action]() : null;
  }

  function onSubmit(form, ctx) {
    const target = form.querySelector("input").value.trim();
    if (!target) return null;
    return ctx.act("inbox-accept", { key: form.getAttribute("data-key"), target: target });
  }

  global.RLOrganizeInbox = { html: html, count: count, onClick: onClick, onSubmit: onSubmit, reset: function () { state.shown = PAGE; } };
})(window);
