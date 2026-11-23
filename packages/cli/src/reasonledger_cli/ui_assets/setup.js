/* ReasonLedger UI — first-run checklist and "build your map" card.
 *
 * Live mode only: both read or write through the authenticated API, so the static export
 * drops this file. Nothing here calls a model, and the quick map is local: a click sends
 * nothing anywhere.
 */
(function (global) {
  const bootEl = document.getElementById("rl-bootstrap");
  if (!bootEl) return;
  let boot;
  try {
    boot = JSON.parse(bootEl.textContent || "{}");
  } catch (err) {
    return;
  }
  if (boot.mode !== "live") return;

  const R = global.RLRender;
  const esc = R.escapeHtml;
  const api = global.RLApi.request;

  const PROMPT_RECORD =
    "When you make a design choice, record it with the reasonledger MCP tool record_decision.";
  const PROMPT_MAP =
    "Use the reasonledger MCP tools: call get_mapping_task, then submit_module_map.";
  const PROMPT_JUDGE =
    "Use the reasonledger MCP tools: call get_judging_task, then submit_verdicts.";
  const PROMPT_JUDGE_FEW =
    "Use the reasonledger MCP tools: call get_judging_task with limit 5, then submit_verdicts. " +
    "Stop after that one batch.";
  const PROMPT_IMPORT =
    "Use the reasonledger MCP tools: call get_import_task, read those files, then submit_candidates.";

  /** Ask the agent to judge exactly these two decisions and stop. */
  function judgePairPrompt(a, b) {
    return (
      "Use the reasonledger MCP tools: call get_judging_task with decision_a " + a +
      " and decision_b " + b + ", then submit_verdicts."
    );
  }

  /** A command or prompt with a copy button. */
  function cmd(text) {
    return (
      '<span class="setup-cmd"><code>' +
      esc(text) +
      '</code><button type="button" class="setup-copy secondary" data-copy="' +
      esc(text) +
      '">Copy</button></span>'
    );
  }

  function bindCopy(container) {
    container.querySelectorAll(".setup-copy").forEach(function (btn) {
      btn.addEventListener("click", function () {
        const text = btn.getAttribute("data-copy") || "";
        const done = function () {
          btn.textContent = "Copied";
          setTimeout(function () {
            btn.textContent = "Copy";
          }, 1500);
        };
        if (global.navigator.clipboard && global.navigator.clipboard.writeText) {
          global.navigator.clipboard.writeText(text).then(done, function () {});
        }
      });
    });
  }

  function openSettings() {
    const tab = document.querySelector('.top-tab[data-tab="settings"]');
    if (tab) tab.click();
  }

  /* ---------------------------------------------------------------- quick map */

  async function runScan(note) {
    note.textContent = "Scanning folders, names and git history on this machine…";
    try {
      return await api("/api/map/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
    } catch (err) {
      note.textContent = err.message || String(err);
      return null;
    }
  }

  function scanOutcomeText(outcome) {
    return outcome.proposed > 0
      ? outcome.proposed + " modules proposed from " + outcome.files_total + " files."
      : "Not enough structure to propose modules yet (" +
        outcome.files_total +
        " source file" +
        (outcome.files_total === 1 ? "" : "s") +
        " found). The map fills in as the code grows into folders; or ask your agent below.";
  }

  function mapOptionsHtml() {
    return (
      "<p><strong>Quick map</strong>, from folders, names and git history. No model; nothing is " +
      'sent. <button type="button" class="primary" data-setup="scan">Build quick map</button></p>' +
      '<p class="setup-note" data-setup="note" role="status"></p>' +
      '<details class="setup-more"><summary>Other ways to build it</summary>' +
      '<ul class="setup-options">' +
      "<li><strong>Ask your coding agent</strong> (uses its own model): " +
      cmd(PROMPT_MAP) +
      "</li>" +
      "<li><strong>Use your configured model</strong>: " +
      cmd("reasonledger map") +
      " It asks before sending file paths anywhere off your machine.</li></ul></details>"
    );
  }

  /** The Map tab's empty state, in either mode: a card that does something, not a dead end. */
  function mountMapEmpty(container, opts) {
    container.innerHTML =
      '<section class="setup-card"><h2>Build your module map</h2>' +
      "<p>The map shows your app's modules and which decisions cover each. " +
      "A new repo with little code has nothing to map yet.</p>" +
      mapOptionsHtml() +
      "</section>";
    bindCopy(container);
    const note = container.querySelector('[data-setup="note"]');
    container.querySelector('[data-setup="scan"]').addEventListener("click", async function () {
      const outcome = await runScan(note);
      if (!outcome) return;
      if (outcome.proposed > 0 && opts && opts.onDone) {
        opts.onDone();
      } else {
        note.textContent = scanOutcomeText(outcome);
      }
    });
  }

  /* ---------------------------------------------------------------- checklist */

  function consentLine(model) {
    if (!model.configured) {
      return (
        "<strong>Model:</strong> none configured. Everything above works without one; a model " +
        "is only needed to import from your docs or to check conflicts without your agent."
      );
    }
    const name = esc(model.provider + ":" + (model.model || "?"));
    if (!model.off_machine) {
      return "<strong>Model:</strong> " + name + " runs on this machine. Nothing leaves it.";
    }
    return (
      "<strong>Model:</strong> " +
      name +
      " → " +
      esc(model.destination) +
      ", off your machine. Nothing is sent until you allow it."
    );
  }

  function buildSteps(s) {
    const steps = [];
    const connect =
      "Run " +
      cmd("reasonledger init") +
      " (it writes the MCP config for Cursor and Claude Code), then restart your agent.";
    if (!s.ledger && !s.mcp_files.length) {
      // Both are the same command, and two steps saying so read as two things to do.
      steps.push({ done: false, title: "Set up this repo and connect your coding agent", body: connect });
    } else {
      steps.push({
        done: s.ledger,
        title: "ReasonLedger is set up in this repo",
        body: s.ledger ? "" : "Run " + cmd("reasonledger init") + " in your app repo.",
      });
      steps.push({
        done: s.mcp_files.length > 0,
        title: "Connect your coding agent",
        body: s.mcp_files.length
          ? "Wrote " + s.mcp_files.map(esc).join(" and ") + ". Restart your agent if you haven't since."
          : connect,
      });
    }
    let record =
      "Your agent records decisions as it works. Ask it to make a choice, or paste: " +
      cmd(PROMPT_RECORD);
    if (s.candidates > 0) {
      record +=
        "<br>To import the <strong>" +
        s.candidates +
        "</strong> " +
        (s.candidates === 1 ? "candidate" : "candidates") +
        " already in your docs and commit messages, paste: " +
        cmd(PROMPT_IMPORT);
      if (s.model.configured && s.model.import_command) {
        record +=
          " Or run " +
          cmd(s.model.import_command) +
          (s.model.off_machine
            ? " It asks before sending that text to " + esc(s.model.destination) + "."
            : "");
      }
    }
    steps.push({
      done: s.decisions + s.proposals > 0,
      title: "Record your first decision",
      body: record,
    });
    steps.push({
      done: s.map.modules > 0,
      optional: true,
      title: "Map your app's modules",
      body: s.map.modules > 0 ? s.map.modules + " modules in your map. See the Map tab." : mapOptionsHtml(),
    });
    if (s.unjudged > 0 && s.decisions + s.proposals > 1) {
      steps.push({
        done: false,
        optional: true,
        title: "Check related decisions for conflicts",
        body:
          s.unjudged +
          " related pair(s) are not judged yet. Ask your agent: " +
          cmd(PROMPT_JUDGE) +
          " or run " +
          cmd("reasonledger judge") +
          " with your own model.",
      });
    }
    return steps;
  }

  function checklistHtml(s) {
    const steps = buildSteps(s);
    const doneCount = steps.filter(function (x) {
      return x.done;
    }).length;
    if (steps.every(function (x) {
      return x.done;
    })) {
      return "";
    }
    // Open until the first record exists; after that it is a one-line reminder, so it
    // never stands between a person and the decisions waiting on them.
    const open = s.decisions + s.proposals === 0;
    const items = steps
      .map(function (step) {
        return (
          '<li class="setup-step' +
          (step.done ? " is-done" : "") +
          '"><span class="setup-mark" aria-hidden="true">' +
          (step.done ? "✓" : "○") +
          '</span><div><div class="setup-title">' +
          esc(step.title) +
          (step.optional ? ' <span class="setup-tag">optional</span>' : "") +
          "</div>" +
          (step.body ? '<div class="setup-body">' + step.body + "</div>" : "") +
          "</div></li>"
        );
      })
      .join("");
    return (
      '<details class="setup-card"' +
      (open ? " open" : "") +
      "><summary><strong>Getting started</strong> " +
      '<span class="muted">' +
      doneCount +
      " of " +
      steps.length +
      " done</span></summary>" +
      '<ol class="setup-steps">' +
      items +
      "</ol>" +
      '<p class="setup-model">' +
      consentLine(s.model) +
      ' <button type="button" class="secondary" data-setup="settings">Settings</button></p></details>'
    );
  }

  async function mountChecklist(container) {
    if (!container) return;
    let facts;
    try {
      facts = await api("/api/setup");
    } catch (err) {
      container.innerHTML = "";
      return;
    }
    container.innerHTML = checklistHtml(facts);
    bindCopy(container);
    const settings = container.querySelector('[data-setup="settings"]');
    if (settings) settings.addEventListener("click", openSettings);
    const scan = container.querySelector('[data-setup="scan"]');
    if (scan) {
      const note = container.querySelector('[data-setup="note"]');
      scan.addEventListener("click", async function () {
        const outcome = await runScan(note);
        if (!outcome) return;
        if (outcome.proposed > 0) {
          mountChecklist(container);
        } else {
          note.textContent = scanOutcomeText(outcome);
        }
      });
    }
  }

  // Other tabs change what the checklist shows (a map built, a model chosen), so look again
  // whenever Overview comes back into view.
  const overviewTab = document.querySelector('.top-tab[data-tab="overview"]');
  if (overviewTab) {
    overviewTab.addEventListener("click", function () {
      mountChecklist(document.getElementById("setup-root"));
    });
  }

  global.RLSetup = {
    mountChecklist: mountChecklist,
    mountMapEmpty: mountMapEmpty,
    cmd: cmd,
    bindCopy: bindCopy,
    prompts: {
      record: PROMPT_RECORD,
      map: PROMPT_MAP,
      judge: PROMPT_JUDGE,
      judgeFew: PROMPT_JUDGE_FEW,
      import: PROMPT_IMPORT,
    },
    judgePairPrompt: judgePairPrompt,
  };
})(window);
