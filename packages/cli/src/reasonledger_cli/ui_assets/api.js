/* ReasonLedger UI — the one authenticated request every live panel shares.
 *
 * Live mode only. It reads the session token from the bootstrap JSON and sends it on
 * every call, so the static export leaves this file out: an export carries no token and
 * no way to send one (see test_status_html_export).
 */
(function (global) {
  let token = "";
  try {
    const bootEl = document.getElementById("rl-bootstrap");
    token = JSON.parse((bootEl && bootEl.textContent) || "{}").token || "";
  } catch (err) {
    token = "";
  }

  /** Request a path with the session token; resolves to parsed JSON, rejects with the server's message. */
  async function request(path, options) {
    const headers = Object.assign({}, (options && options.headers) || {});
    headers["X-RL-Token"] = token;
    const res = await fetch(path, Object.assign({}, options, { headers: headers }));
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (err) {
      data = { error: text || "invalid response" };
    }
    if (!res.ok) {
      throw new Error((data && data.error) || res.statusText || "request failed");
    }
    return data;
  }

  global.RLApi = { request: request };
})(window);
