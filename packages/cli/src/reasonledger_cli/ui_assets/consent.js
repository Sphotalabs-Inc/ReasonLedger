/* ReasonLedger Settings — "Data sent to your model": what a person allows off the machine.
 *
 * Live mode only: it reads and writes through the authenticated API, so the static export
 * drops this file. A button here only records what a person allows; it sends nothing.
 */
(function (global) {
  const host = document.getElementById("settings-pane");
  const bootEl = document.getElementById("rl-bootstrap");
  if (!host || !bootEl) return;
  let boot;
  try {
    boot = JSON.parse(bootEl.textContent || "{}");
  } catch (err) {
    return;
  }
  if (boot.mode !== "live") return;

  const esc = global.RLRender.escapeHtml;
  const api = global.RLApi.request;

  const consentPanel = document.createElement("section");
  consentPanel.className = "settings";
  consentPanel.id = "rl-consent";
  host.appendChild(consentPanel);

  function consentHtml(c) {
    if (!c.configured) {
      return (
        "<h2>Data sent to your model</h2><p>No model is configured, so nothing is sent " +
        "anywhere. Pick one above if you want to import from your docs or check conflicts " +
        "with your own model.</p>"
      );
    }
    if (!c.off_machine) {
      return (
        "<h2>Data sent to your model</h2><p>Your model (" +
        esc(c.model) +
        ") runs on this machine. Nothing leaves it, so there is nothing to allow.</p>"
      );
    }
    const rows = c.classes
      .map(function (item) {
        return (
          '<li class="consent-row"><div><strong>' +
          esc(item.label) +
          "</strong> " +
          (item.allowed
            ? '<span class="setup-tag is-on">allowed</span>'
            : '<span class="setup-tag">not allowed</span>') +
          '<div class="muted">' +
          esc(item.description) +
          (item.count ? " (" + esc(item.count) + ")" : "") +
          '</div></div><button type="button" class="' +
          (item.allowed ? "secondary" : "primary") +
          '" data-consent="' +
          (item.allowed ? "revoke" : "grant") +
          '" data-class="' +
          esc(item.id) +
          '">' +
          (item.allowed ? "Withdraw" : "Allow") +
          "</button></li>"
        );
      })
      .join("");
    return (
      "<h2>Data sent to your model</h2><p>" +
      esc(c.model) +
      " is at <strong>" +
      esc(c.destination) +
      "</strong>, off your machine. Nothing is sent until you allow it, one kind of data at a " +
      "time. Your choice is stored in your user config, not in the repo, and applies to this " +
      'repo and this destination only.</p><ul class="consent-list">' +
      rows +
      "</ul>"
    );
  }

  async function mountConsent() {
    try {
      consentPanel.innerHTML = consentHtml(await api("/api/consent"));
    } catch (err) {
      consentPanel.innerHTML = '<p class="error">' + esc(err.message || String(err)) + "</p>";
      return;
    }
    consentPanel.querySelectorAll("[data-consent]").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        try {
          const payload = await api("/api/consent", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action: btn.getAttribute("data-consent"),
              classes: [btn.getAttribute("data-class")],
            }),
          });
          consentPanel.innerHTML = consentHtml(payload);
          mountConsent();
        } catch (err) {
          global.alert(err.message || String(err));
        }
      });
    });
  }

  // The model may have changed on this very tab, so look again whenever Settings opens.
  const settingsTab = document.querySelector('.top-tab[data-tab="settings"]');
  if (settingsTab) settingsTab.addEventListener("click", mountConsent);
  mountConsent();
})(window);
