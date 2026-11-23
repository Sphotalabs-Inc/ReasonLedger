/* ReasonLedger local UI — model settings panel.
 *
 * Live mode only, and the whole panel is built here rather than in index.html: the
 * static export inlines that markup, and a settings form with no server behind it is
 * a dead control at best and a secret-entry prompt at worst.
 *
 * The panel never handles an API key. The key field is a *variable name*; presence of
 * the value is a boolean the server derives, and no request or response here can carry
 * the secret itself.
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

  const panel = document.createElement("section");
  panel.className = "settings";
  panel.id = "rl-settings";
  host.appendChild(panel);

  const api = window.RLApi.request;

  function providerOptions(cfg) {
    const disabled = cfg.provider === "disabled";
    const placeholder = disabled
      ? '<option value="" selected>Choose a provider…</option>'
      : "";
    return (
      placeholder +
      (cfg.providers || [])
        .map(function (name) {
          return (
            '<option value="' +
            escapeHtml(name) +
            '"' +
            (name === cfg.provider ? " selected" : "") +
            ">" +
            escapeHtml(name) +
            "</option>"
          );
        })
        .join("")
    );
  }

  function field(id, label, value, placeholder) {
    return (
      '<p class="settings-field"><label for="' +
      id +
      '">' +
      escapeHtml(label) +
      '</label><input id="' +
      id +
      '" type="text" spellcheck="false" value="' +
      escapeHtml(value || "") +
      '" placeholder="' +
      escapeHtml(placeholder) +
      '" /></p>'
    );
  }

  /** The panel's highest-value line: turns a confusing import failure into an obvious one. */
  function keyState(cfg) {
    if (!cfg.api_key_env) return "";
    if (cfg.api_key_present) {
      return (
        '<p class="settings-note ok"><code>' +
        escapeHtml(cfg.api_key_env) +
        "</code> is set in this server's environment.</p>"
      );
    }
    return (
      '<p class="settings-note warn"><code>' +
      escapeHtml(cfg.api_key_env) +
      "</code> isn't set in the environment this server was started from. " +
      "Export it and restart <code>reasonledger ui</code> before importing.</p>"
    );
  }

  function intro(cfg) {
    if (cfg.provider !== "disabled") {
      return (
        '<p class="hint">Optional. ReasonLedger calls this model for <code>reasonledger import</code>, ' +
        "<code>judge</code> and <code>map</code>. Without one, your coding agent's own model does the same work;" +
        "to turn this off, delete the <code>extractor</code> section of <code>.reasonledger/config.yml</code>. " +
        "The <code>reasonledger config</code> command is the same setting from a terminal.</p>"
      );
    }
    return (
      '<p class="hint"><strong>Optional. Default: your coding agent\'s own model.</strong> ' +
      "Claude Code or Cursor does the work with whatever model it is already running, so there is " +
      "no key to set and nothing leaves your machine (see below). Pick a provider only if you want " +
      "ReasonLedger itself to call a different model when you run <code>reasonledger import</code>, " +
      "<code>judge</code> or <code>map</code> from a terminal. " +
      "(Importing from a recorded fixture needs no model at all.)</p>"
    );
  }

  /* Discoverability, not capability: `reasonledger ui` is a foreground process, so a
     user reading this always has a terminal — they just may not know the command. */
  function importHint(cfg) {
    if (cfg.provider === "disabled") return "";
    return (
      '<p class="settings-note">Ready to import:<br /><code>' +
      escapeHtml(cfg.import_command) +
      "</code></p>"
    );
  }

  function render(cfg) {
    panel.innerHTML =
      "<h2>Model settings (optional)</h2>" +
      intro(cfg) +
      '<form id="settings-form">' +
      '<p class="settings-field"><label for="cfg-provider">Provider</label>' +
      '<select id="cfg-provider">' +
      providerOptions(cfg) +
      "</select></p>" +
      field("cfg-model", "Model", cfg.model, "claude-sonnet-5") +
      field("cfg-base-url", "Base URL (optional)", cfg.base_url, "") +
      field(
        "cfg-api-key-env",
        "API key environment variable",
        cfg.api_key_env,
        "ANTHROPIC_API_KEY"
      ) +
      '<p class="hint">The name of an environment variable — not the key itself. ' +
      "The key is never saved to disk.</p>" +
      keyState(cfg) +
      '<div class="actions">' +
      '<button type="submit" class="primary">Save</button>' +
      '<button type="button" class="secondary" id="cfg-test">Test connection</button>' +
      "</div></form>" +
      '<p class="settings-status" id="cfg-status" role="status"></p>' +
      importHint(cfg);

    document.getElementById("settings-form").addEventListener("submit", onSave);
    document.getElementById("cfg-test").addEventListener("click", onTest);
  }

  function status(message, kind) {
    const el = document.getElementById("cfg-status");
    if (!el) return;
    el.className = "settings-status" + (kind ? " " + kind : "");
    el.textContent = message;
  }

  function formValues() {
    return {
      provider: document.getElementById("cfg-provider").value,
      model: document.getElementById("cfg-model").value,
      base_url: document.getElementById("cfg-base-url").value,
      api_key_env: document.getElementById("cfg-api-key-env").value,
    };
  }

  async function onSave(ev) {
    ev.preventDefault();
    const values = formValues();
    if (!values.provider) {
      status("Choose a provider first.", "warn");
      return;
    }
    try {
      const saved = await api("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      render(saved);
      status("Saved to " + saved.path, "ok");
    } catch (err) {
      status(err.message || String(err), "warn");
    }
  }

  /* The only outbound call this page can make, and only from this click. */
  async function onTest(ev) {
    const btn = ev.currentTarget;
    btn.disabled = true;
    status("Testing connection…", "");
    try {
      const result = await api("/api/config/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      status(result.message, result.ok ? "ok" : "warn");
    } catch (err) {
      status(err.message || String(err), "warn");
    } finally {
      btn.disabled = false;
    }
  }

  api("/api/config")
    .then(render)
    .catch(function (err) {
      panel.innerHTML =
        '<h2>Model settings</h2><p class="error">' +
        escapeHtml(err.message || err) +
        "</p>";
    });
})();
