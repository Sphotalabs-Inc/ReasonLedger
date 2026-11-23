---
id: dec_f0y9lv
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-13T06:03:46.733194Z'
justifies:
- packages/core/src/reasonledger_core/reasoning/embeddings.py::get_embedder
- packages/core/src/reasonledger_core/settings.py::Settings
- packages/mcp/src/reasonledger_mcp/server.py::main
watchers: []
context: The remote embedding provider POSTed decision text to a configured URL without
  passing the consent system, and the MCP server could listen over HTTP with no authentication
  or TLS. For the alpha, enforce consent and authentication at those two points, or
  remove them?
choice: Remove both. The remote embedding provider, RemoteEmbedder and its four settings
  are deleted, so embeddings are deterministic or local and never touch the network.
  The MCP server accepts no --transport, --host or --port and always runs over stdio.
alternatives_rejected:
- 'Check consent immediately before the embedding request: adds a consent kind and
  a prompt path to a provider nobody has asked for'
- 'Keep streamable-http but require a token and loopback only: new auth code and a
  secret to manage for a debugging feature'
assumptions:
- No alpha user relies on the remote provider or the HTTP transport; both were opt-in
  and undocumented beyond a debugging note
---

## Context

The remote embedding provider POSTed decision text to a configured URL without passing the consent system, and the MCP server could listen over HTTP with no authentication or TLS. For the alpha, enforce consent and authentication at those two points, or remove them?

## Choice

Remove both. The remote embedding provider, RemoteEmbedder and its four settings are deleted, so embeddings are deterministic or local and never touch the network. The MCP server accepts no --transport, --host or --port and always runs over stdio.

## Alternatives rejected

- Check consent immediately before the embedding request: adds a consent kind and a prompt path to a provider nobody has asked for
- Keep streamable-http but require a token and loopback only: new auth code and a secret to manage for a debugging feature

## Assumptions

- No alpha user relies on the remote provider or the HTTP transport; both were opt-in and undocumented beyond a debugging note
