/* ReasonLedger Organize workbench — the edits that ask a person something first.
 *
 * Live mode only. Each takes the workbench context: its state, `act` (send an edit and refresh),
 * `spec` (the current selection) and `tileOf` (a module's summary).
 */
(function (global) {
  const esc = global.RLMapUi.esc;

  function startRename(ctx) {
    const title = document.getElementById("org-title");
    const tile = ctx.tileOf(ctx.state.module);
    if (!title || !tile) return;
    title.innerHTML = '<input type="text" id="org-rename" aria-label="New name" value="' + esc(tile.name) + '" />';
    const input = document.getElementById("org-rename");
    input.focus();
    input.select();
  }

  async function finishRename(ctx, input) {
    const name = input.value.trim();
    if (!name) return;
    await ctx.act("rename", { id: ctx.state.module, name: name });
  }

  async function newModule(ctx) {
    const name = window.prompt("Name the new module:");
    if (!name || !name.trim()) return;
    await ctx.act("new-module", { selection: ctx.spec(), name: name.trim() });
  }

  async function confirmModule(ctx) {
    await ctx.act("confirm", { ids: [ctx.state.module] });
  }

  async function rejectModule(ctx) {
    const id = ctx.state.module;
    if (!window.confirm("Reject " + id + "? It stays down while a map covers about its files.")) return;
    const reason = window.prompt("Why? (optional)") || "";
    await ctx.act("reject", { id: id, reason: reason });
  }

  global.RLOrganizeActions = {
    startRename: startRename,
    finishRename: finishRename,
    newModule: newModule,
    confirmModule: confirmModule,
    rejectModule: rejectModule,
  };
})(window);
