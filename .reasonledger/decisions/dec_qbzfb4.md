---
id: dec_qbzfb4
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-17T04:40:55.540048Z'
justifies:
- packages/cli/src/reasonledger_cli/ui_cmd.py::make_ui_handler
- packages/cli/tests/test_ui_server.py::test_ui_refuses_a_foreign_host_header
watchers: []
confidence: high
context: The loopback review UI checked a session token and the Origin header, but
  served the page, which embeds the token, to any request regardless of its Host header.
  A site that rebinds its DNS name to 127.0.0.1 could load the page as its own origin,
  read the token and issue GETs, which carry no Origin. Where and how strictly should
  the server check Host?
choice: Override parse_request on the handler so every request, whatever the method
  or path, is refused with 403 unless its Host header equals the exact host:port the
  server bound; localhost is not accepted. The error text names the correct URL so
  a user who typed localhost knows where to go.
alternatives_rejected:
- 'Check Host inside the existing API guard only: the HTML page that carries the token
  and the static assets would still be served to a rebound origin'
- 'Also accept localhost:<port>: the Origin check already rejects POSTs from it, so
  accepting it for GET would half-work and widen the rebinding surface'
- 'Add a Content-Security-Policy or CORS headers instead: neither stops a same-origin
  rebound page from reading responses'
assumptions:
- Everything legitimate reaches the UI at the 127.0.0.1 address it prints, including
  the browser it opens
---

## Context

The loopback review UI checked a session token and the Origin header, but served the page, which embeds the token, to any request regardless of its Host header. A site that rebinds its DNS name to 127.0.0.1 could load the page as its own origin, read the token and issue GETs, which carry no Origin. Where and how strictly should the server check Host?

## Choice

Override parse_request on the handler so every request, whatever the method or path, is refused with 403 unless its Host header equals the exact host:port the server bound; localhost is not accepted. The error text names the correct URL so a user who typed localhost knows where to go.

## Alternatives rejected

- Check Host inside the existing API guard only: the HTML page that carries the token and the static assets would still be served to a rebound origin
- Also accept localhost:<port>: the Origin check already rejects POSTs from it, so accepting it for GET would half-work and widen the rebinding surface
- Add a Content-Security-Policy or CORS headers instead: neither stops a same-origin rebound page from reading responses

## Assumptions

- Everything legitimate reaches the UI at the 127.0.0.1 address it prints, including the browser it opens
