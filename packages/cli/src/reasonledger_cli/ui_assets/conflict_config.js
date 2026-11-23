/* ReasonLedger local UI — related-decision settings panel (shortlist, judge, embedder).
 *
 * Same shape as config.js: live mode only, panel built here rather than in
 * index.html so a static export (no server to save to) never ships a dead
 * form. Mirrors config.js's GET-on-load / POST-on-submit / status-line pattern
 * so the two settings panels behave identically even though they tune
 * different things.
 */
(function () {
  const bootEl = document.getElementById("rl-bootstrap");
  if (!bootEl) return;

  let boot;
  try {
    boot = JSON.parse(bootEl.textContent || "{}");
  } catch (err) {
    return;
  }
  if (boot.mode !== "live") return;

  const R = window.RLRender;
  const escapeHtml = R.escapeHtml;

  const host = document.getElementById("settings-pane");
  if (!host) return;

  // Tuning most people never touch, so it is one click away and not a third of the page.
  const fold = document.createElement("details");
  fold.className = "settings";
  fold.innerHTML = '<summary class="settings-fold">Advanced: related-decision tuning</summary>';
  const panel = document.createElement("section");
  panel.id = "rl-conflict-settings";
  fold.appendChild(panel);
  host.appendChild(fold);

  const api = window.RLApi.request;

  function field(id, label, value, attrs) {
    return (
      '<p class="settings-field"><label for="' +
      id +
      '">' +
      escapeHtml(label) +
      '</label><input id="' +
      id +
      '" ' +
      attrs +
      ' value="' +
      escapeHtml(value == null ? "" : value) +
      '" /></p>'
    );
  }

  function providerOptions(cfg) {
    const unsetLabel = "(default — follows RL_EMBEDDING_PROVIDER)";
    let options =
      '<option value=""' +
      (cfg.embedding_provider ? "" : " selected") +
      ">" +
      escapeHtml(unsetLabel) +
      "</option>";
    (cfg.embedding_providers || []).forEach(function (name) {
      options +=
        '<option value="' +
        escapeHtml(name) +
        '"' +
        (name === cfg.embedding_provider ? " selected" : "") +
        ">" +
        escapeHtml(name) +
        "</option>";
    });
    return options;
  }

  function render(cfg) {
    panel.innerHTML =
      "<h2>Related-decision settings</h2>" +
      '<p class="hint">Which decisions get compared, and which model judges them. ' +
      "<code>reasonledger conflict-config</code> sets the same values from a terminal; " +
      "<code>reasonledger judge</code> runs the judge.</p>" +
      '<form id="conflict-settings-form">' +
      field(
        "cc-shortlist-k",
        "Neighbours per decision",
        cfg.shortlist_k,
        'type="number" step="1" min="1" max="50"'
      ) +
      '<p class="hint">How many of its most similar decisions each decision is compared with.</p>' +
      field(
        "cc-context-gate",
        "Minimum context similarity",
        cfg.context_similarity_gate,
        'type="number" step="0.01" min="0" max="1" placeholder="per embedder"'
      ) +
      '<p class="hint">Leave empty to use the embedder&#39;s own floor.</p>' +
      field(
        "cc-judge-model",
        "Judge model",
        cfg.judge_model,
        'type="text" placeholder="same as import"'
      ) +
      '<p class="hint">Leave empty to judge with the model import uses.</p>' +
      '<p class="settings-field"><label for="cc-embedding-provider">Embedder</label>' +
      '<select id="cc-embedding-provider">' +
      providerOptions(cfg) +
      "</select></p>" +
      '<div class="actions"><button type="submit" class="primary">Save</button></div>' +
      "</form>" +
      '<p class="settings-status" id="cc-status" role="status"></p>';

    document
      .getElementById("conflict-settings-form")
      .addEventListener("submit", onSave);
  }

  function status(message, kind) {
    const el = document.getElementById("cc-status");
    if (!el) return;
    el.className = "settings-status" + (kind ? " " + kind : "");
    el.textContent = message;
  }

  function formValues() {
    const providerRaw = document.getElementById("cc-embedding-provider").value;
    const gateRaw = document.getElementById("cc-context-gate").value.trim();
    const judgeRaw = document.getElementById("cc-judge-model").value.trim();
    return {
      context_similarity_gate: gateRaw === "" ? null : Number(gateRaw),
      shortlist_k: Number(document.getElementById("cc-shortlist-k").value),
      judge_model: judgeRaw || null,
      embedding_provider: providerRaw || null,
    };
  }

  async function onSave(ev) {
    ev.preventDefault();
    try {
      const saved = await api("/api/conflict-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formValues()),
      });
      render(saved);
      status("Saved to " + saved.path, "ok");
    } catch (err) {
      status(err.message || String(err), "warn");
    }
  }

  api("/api/conflict-config")
    .then(render)
    .catch(function (err) {
      panel.innerHTML =
        "<h2>Related-decision settings</h2><p class=\"error\">" +
        escapeHtml(err.message || err) +
        "</p>";
    });
})();
