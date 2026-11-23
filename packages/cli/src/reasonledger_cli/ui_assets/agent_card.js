/* ReasonLedger Settings — "Use your coding agent": what an agent can do with no model configured.
 *
 * Live mode only, and static on purpose: it asks the server nothing. The prompts and the copy
 * button are the ones the first-run checklist uses (setup.js), so the wording lives once.
 */
(function (global) {
  const S = global.RLSetup;
  const host = document.getElementById("settings-pane");
  const after = document.getElementById("rl-settings");
  if (!S || !host || !after) return;

  const ABILITIES = [
    ["Build the module map", S.prompts.map],
    ["Check related decisions for conflicts", S.prompts.judge],
    ["Record decisions as it works", S.prompts.record],
    ["Import decisions from docs and commit messages", S.prompts.import],
  ];

  const panel = document.createElement("section");
  panel.className = "settings";
  panel.id = "rl-agent-settings";
  panel.innerHTML =
    "<h2>Use your coding agent</h2>" +
    '<p class="hint">Claude Code and Cursor can do part of this with their own model, so there is no key ' +
    "to set and ReasonLedger sends nothing off your machine. Paste a prompt into your agent.</p>" +
    '<ul class="setup-options">' +
    ABILITIES.map(function (ability) {
      return "<li><strong>" + ability[0] + "</strong>: " + S.cmd(ability[1]) + "</li>";
    }).join("") +
    "</ul>" +
    '<p class="settings-note">Your agent reaches ReasonLedger through its MCP server. ' +
    "<code>reasonledger init</code> writes <code>.mcp.json</code> (Claude Code) and " +
    "<code>.cursor/mcp.json</code> (Cursor); restart the agent after it.</p>" +
    '<p class="hint">A model above is optional. <code>reasonledger import</code> and ' +
    "<code>catchup</code> use it when you would rather not ask the agent. The agent can do the " +
    "same backfill: it reads the files itself, and ReasonLedger does not send them anywhere.</p>";
  after.after(panel);
  S.bindCopy(panel);
})(window);
