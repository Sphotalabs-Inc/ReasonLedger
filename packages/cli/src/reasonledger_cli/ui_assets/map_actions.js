/* ReasonLedger module map — what a person can do from a decision card without leaving the Map.
 *
 * Live mode only. A pending decision can be reviewed. One with no module can be given a home:
 * the folder its anchors sit in goes into a module (an existing one, or a new one), or, when no
 * anchor works, the decision is placed by hand. Each edit goes through the Organize endpoints,
 * so it is one write of modules.yml and Undo, under Edit map, takes it back.
 */
(function (global) {
  const U = global.RLMapUi;
  const esc = U.esc;
  const TARGETS_ID = "map-targets";
  let targets = [];

  /** The modules and buckets a card may name; map.js sets them with each overview. */
  function setTargets(refs) {
    targets = refs;
  }

  function optionsHtml() {
    return targets
      .map(function (t) {
        return '<option value="' + esc(t.id) + '">' + esc(t.name) + "</option>";
      })
      .join("");
  }

  function datalist() {
    return '<datalist id="' + TARGETS_ID + '">' + optionsHtml() + "</datalist>";
  }

  /** A first name for a module made from a folder: `spec/**` reads as "Spec". */
  function nameFor(pattern) {
    const folder = pattern.replace(/\/\*\*$/, "").split("/").pop();
    return folder.charAt(0).toUpperCase() + folder.slice(1);
  }

  function failHtml() {
    return '<p class="error" role="alert" hidden></p>';
  }

  function claimHtml(pattern) {
    return (
      '<form class="map-act" data-map-claim="' + esc(pattern) + '"><label><code>' + esc(pattern) +
      '</code> is in no module. Put it in <select><option value="">a new module</option>' + optionsHtml() + "</select></label>" +
      '<input type="text" aria-label="Name of the new module" value="' + esc(nameFor(pattern)) + '" />' +
      '<button type="submit" class="secondary">Place these files</button>' + failHtml() + "</form>"
    );
  }

  function placeHtml(d) {
    return (
      '<form class="map-act" data-map-place="' + esc(d.id) + '"><label>No anchor of this decision works, so say where it belongs ' +
      '<input type="text" list="' + TARGETS_ID + '" autocomplete="off" placeholder="a module id, or up to four with commas" /></label>' +
      '<button type="submit" class="secondary">Place decision</button>' + failHtml() + "</form>"
    );
  }

  function reviewHtml(d) {
    if (d.oversight !== "pending" || d.superseded) return "";
    return '<div class="map-act"><button type="button" class="primary" data-map-review="' + esc(d.id) + '">Review</button></div>';
  }

  /** The actions under one decision card; empty when it asks nothing of anyone. */
  function html(d) {
    const parts = (d.claimable || []).map(claimHtml);
    if (d.placeable) parts.push(placeHtml(d));
    const body = parts.join("") + reviewHtml(d);
    return body ? '<div class="map-acts">' + body + "</div>" : "";
  }

  /** The Organize edit a submitted form asks for. */
  function edit(form) {
    const pattern = form.getAttribute("data-map-claim");
    if (pattern) {
      const target = form.querySelector("select").value;
      const name = form.querySelector("input").value.trim();
      return { action: "claim", body: target ? { pattern: pattern, target: target } : { pattern: pattern, name: name } };
    }
    const modules = form.querySelector("input").value.split(",").map(function (m) {
      return m.trim();
    }).filter(Boolean);
    return { action: "place-decision", body: { decision: form.getAttribute("data-map-place"), modules: modules } };
  }

  async function submit(form, ctx) {
    const failed = form.querySelector(".error");
    const change = edit(form);
    try {
      const reply = await ctx.request("/api/organize/" + change.action, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(change.body),
      });
      await ctx.done(reply.message);
    } catch (err) {
      failed.textContent = err.message || String(err);
      failed.hidden = false;
    }
  }

  /** Bind a pane once. `ctx` is {request(path, options), review(id), done(message)} from map.js. */
  function bind(pane, ctx) {
    pane.addEventListener("submit", function (ev) {
      if (!ev.target.classList.contains("map-act")) return;
      ev.preventDefault();
      submit(ev.target, ctx);
    });
    pane.addEventListener("change", function (ev) {
      const form = ev.target.closest("[data-map-claim]");
      if (form && ev.target.tagName === "SELECT") form.querySelector("input").hidden = ev.target.value !== "";
    });
    pane.addEventListener("click", function (ev) {
      const button = ev.target.closest("[data-map-review]");
      if (button) ctx.review(button.getAttribute("data-map-review"));
    });
  }

  global.RLMapActions = { html: html, bind: bind, setTargets: setTargets, datalist: datalist };
})(window);
