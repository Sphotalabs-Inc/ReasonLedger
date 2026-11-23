/* ReasonLedger UI — "Check for conflicts": start the model judge, watch it, stop it.
 *
 * Live mode only. Nothing here runs on page load: a person presses the button, and the
 * server refuses (saying what is needed) when no model is configured or when a model off
 * this machine has no consent for decision text. A run saves each verdict as it arrives,
 * so stopping one loses nothing and the next continues where it ended.
 */
(function (global) {
  const esc = global.RLRender.escapeHtml;
  const POLL_MS = 2000;

  /** Where the card is drawn, what it needs from app.js, and what the last look showed. */
  const state = {
    host: null,
    ctx: null,
    unjudged: 0,
    conflictsSeen: 0,
    problem: "",
    timer: null,
    running: false,
    // id → the question that decision answered, to say what a pair is about.
    titles: {},
    // Set while one pair is checked from its card in Ask; `note` is what came of it.
    pair: null,
    note: "",
    // Where in the related list that pair's card sat, so the note appears where it was.
    noteAt: 0,
  };

  function post(action, body) {
    return state.ctx.request("/api/judge/" + action, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function plural(n, word) {
    return n + " " + word + (n === 1 ? "" : "s");
  }

  function summary(job) {
    const failed = job.failed ? ", " + job.failed + " the model could not answer" : "";
    return (
      plural(job.checked, "pair") + " checked: " + plural(job.conflicts, "conflict") + ", " +
      job.compatible + " compatible" + failed + "."
    );
  }

  /** What to do when the server refuses to start: fix it in Settings, or use the agent. */
  function problemHtml() {
    if (!state.problem) return "";
    return (
      '<p class="error" role="alert">' + esc(state.problem) + "</p>" +
      '<p class="hint"><button type="button" class="secondary" data-open-tab="settings">Open Settings</button> ' +
      "or ask your coding agent: " + global.RLSetup.cmd(global.RLSetup.prompts.judge) + "</p>"
    );
  }

  /** The agent route, spelled out: every pair, a few, or one. Needs no model and no key. */
  function agentHintHtml() {
    const S = global.RLSetup;
    return (
      '<details class="setup-more"><summary>Use your coding agent instead</summary>' +
      '<p class="hint">Your agent judges with its own model, so nothing needs configuring. ' +
      "Paste one of these into it.</p>" +
      '<ul class="setup-options">' +
      "<li><strong>Every pair</strong>, batch after batch until none are left: " + S.cmd(S.prompts.judge) + "</li>" +
      "<li><strong>A few</strong>, then it stops: " + S.cmd(S.prompts.judgeFew) + "</li>" +
      "<li><strong>One pair</strong>: copy the prompt shown under that pair below, or run <code>reasonledger judge --pair A B</code> with a model.</li>" +
      "</ul></details>"
    );
  }

  function isBusy(job) {
    return job.state === "running" || job.state === "stopping";
  }

  /** The two decisions the model is reading right now, each with the question it answered. */
  function comparingHtml(job) {
    if (!job.current) return "";
    return (
      '<p class="hint">Comparing now:</p><ul class="judge-pair">' +
      job.current
        .map(function (id) {
          return "<li><code>" + esc(id) + "</code> " + esc(state.titles[id] || "") + "</li>";
        })
        .join("") +
      "</ul>"
    );
  }

  function html(job) {
    if (isBusy(job)) {
      // A model call cannot be cancelled, so Stop takes effect when the pair in flight returns.
      const control =
        job.state === "stopping"
          ? '<p class="hint" role="status">Stopping once this pair is done. Verdicts already saved are kept.</p>'
          : '<button type="button" class="secondary" data-judge="stop">Stop</button>';
      return (
        '<p role="status">Checking with <code>' + esc(job.model || "your model") + "</code>: " +
        esc(job.checked) + " of " + esc(job.total || "…") + " pairs done, " +
        esc(plural(job.conflicts, "conflict")) + " found so far.</p>" +
        comparingHtml(job) +
        control
      );
    }
    const last =
      job.state === "idle" ? "" : '<p class="hint">' + esc(job.state === "failed" ? job.error : summary(job)) + "</p>";
    const left = state.unjudged
      ? "<p><strong>" + esc(state.unjudged) + "</strong> related " +
        (state.unjudged === 1 ? "pair has" : "pairs have") +
        " not been checked for conflicts.</p>" +
        '<button type="button" class="primary" data-judge="start">Check for conflicts</button>' +
        agentHintHtml()
      : '<p class="hint">Every related pair has been checked.</p>';
    return last + left + problemHtml();
  }

  function draw(job) {
    if (!state.host || !state.host.isConnected) return;
    // Nothing to check and nothing to report: no card at all.
    const quiet = job.state === "idle" && !state.unjudged && !state.problem;
    state.host.innerHTML = quiet
      ? ""
      : '<section class="setup-card"><h2>Check for conflicts</h2>' +
        '<p class="hint">A model, or your coding agent, reads each pair of related decisions and says whether they ' +
        "clash. Conflicts it finds appear at the top of this page, for you to settle.</p>" +
        html(job) +
        "</section>";
    global.RLSetup.bindCopy(state.host);
  }

  /**
   * While a check runs, a pair can be neither checked nor dismissed: one run at a time, and
   * a dismissal made under a pair the model is reading would race its verdict.
   */
  function lockPairs() {
    document.querySelectorAll('[data-action="judge-pair"], .item.related [data-action="dismiss"]').forEach(function (btn) {
      btn.disabled = true;
    });
  }

  /** Look again while a run is going; redraw the lists when it ends or finds a conflict. */
  async function watch() {
    global.clearTimeout(state.timer);
    let job;
    try {
      job = await state.ctx.request("/api/judge");
    } catch (err) {
      return;
    }
    const found = job.conflicts > state.conflictsSeen;
    state.conflictsSeen = job.conflicts;
    if (isBusy(job)) {
      // Also true for a run this page did not start: one begun before a reload.
      state.running = true;
      lockPairs();
      draw(job);
      state.timer = global.setTimeout(watch, POLL_MS);
      if (found) state.ctx.changed();
      return;
    }
    if (state.running) {
      // The run just ended: the view holds new verdicts, and redrawing it mounts this again.
      state.running = false;
      if (state.pair) state.note = pairOutcome(job);
      state.pair = null;
      state.ctx.changed();
      return;
    }
    draw(job);
  }

  /** What one pair's check came to, said where the person pressed the button. */
  function pairOutcome(job) {
    const names = state.pair.join(" and ");
    if (job.state === "failed" || job.failed) return "The model could not answer for " + names + ". Try again.";
    if (job.conflicts) return names + " conflict. The pair is now at the top of this page, for you to settle.";
    if (!job.checked) return names + " was not checked: the run was stopped.";
    return names + " do not conflict. The pair is now marked judged compatible in this list.";
  }

  async function start(body) {
    state.problem = "";
    state.note = "";
    state.pair = body.pair || null;
    try {
      await post("start", body);
      state.running = true;
      state.conflictsSeen = 0;
      lockPairs();
    } catch (err) {
      state.problem = err.message || String(err);
      // A refused pair check is explained on its own list, which needs a redraw to say so.
      if (state.pair) state.ctx.changed();
      state.pair = null;
    }
    await watch();
  }

  function onClick(ev) {
    const btn = ev.target.closest("[data-judge]");
    if (!btn) return;
    if (btn.getAttribute("data-judge") === "start") start({});
    else post("stop").then(watch, watch);
  }

  /**
   * For the related-pairs list: how the last single-pair check went, or why it could not
   * start, and the position of the card it was pressed on (a pair found to conflict leaves
   * the list, so the note takes its place).
   */
  function pairNote() {
    const note = state.note ? '<p class="judge-note" role="status">' + esc(state.note) + "</p>" : "";
    return { html: note + problemHtml(), at: state.noteAt };
  }

  /** `ctx` is {request(path, options), changed()} from app.js; `view` gives the unjudged count. */
  function mount(host, view, ctx) {
    state.host = host;
    state.ctx = ctx;
    state.unjudged = (view.counts || {}).unverified || 0;
    state.titles = {};
    (view.proposals || []).concat(view.decisions || []).forEach(function (d) {
      state.titles[d.id] = global.RLNeeds.clip(d.context);
    });
    host.addEventListener("click", onClick);
    watch();
  }

  /** Check one pair from its card in the related list; the list is redrawn, in place, when it is done. */
  function checkPair(a, b, at) {
    state.noteAt = at;
    return start({ pair: [a, b] });
  }

  /** True from the moment a run is accepted until it ends; lists drawn meanwhile lock their pairs. */
  function busy() {
    return state.running;
  }

  global.RLJudge = { mount: mount, checkPair: checkPair, pairNote: pairNote, busy: busy };
})(window);
