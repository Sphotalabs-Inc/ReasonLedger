---
id: dec_fiz4fj
ai_tool: claude-code
model: claude-opus-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-22T06:40:02.504004Z'
justifies:
- packages/core/src/reasonledger_core/importer/endpoint.py::validate_base_url
- packages/core/src/reasonledger_core/importer/endpoint.py::origin
- packages/core/src/reasonledger_core/importer/config.py::ExtractorConfig
- packages/core/src/reasonledger_core/importer/config.py::parse_extractor_config
- packages/core/src/reasonledger_core/importer/llm.py::http_post_json
- packages/core/src/reasonledger_core/consent.py::destination
watchers: []
context: ExtractorConfig.base_url accepted any string, so prompts and API keys could
  go over plain HTTP or carry credentials in the committed URL; urllib followed 301/302/303
  and re-sent the API key headers to any host; and consent was bound to the hostname,
  so changing scheme or port did not ask again. How should the destination of a model
  call be constrained?
choice: 'A base URL is validated on the config model: http(s) only, https unless the
  host is loopback, and no userinfo, query or fragment; errors never echo the URL.
  Consent is bound to the normalized origin (scheme, host, non-default port), so old
  host-only grants match nothing and are asked for again. http_post_json uses an opener
  that follows no redirect and reports one as an error naming base_url.'
alternatives_rejected:
- Allow plain http to private LAN ranges for a model on another machine
- Follow redirects but strip credentials when the origin changes
- Keep host-only consent and migrate old grants to origins
assumptions:
- Hosted model providers do not rely on redirects for their API endpoints
- Users with a LAN model can front it with https or reach it over localhost
---

## Context

ExtractorConfig.base_url accepted any string, so prompts and API keys could go over plain HTTP or carry credentials in the committed URL; urllib followed 301/302/303 and re-sent the API key headers to any host; and consent was bound to the hostname, so changing scheme or port did not ask again. How should the destination of a model call be constrained?

## Choice

A base URL is validated on the config model: http(s) only, https unless the host is loopback, and no userinfo, query or fragment; errors never echo the URL. Consent is bound to the normalized origin (scheme, host, non-default port), so old host-only grants match nothing and are asked for again. http_post_json uses an opener that follows no redirect and reports one as an error naming base_url.

## Alternatives rejected

- Allow plain http to private LAN ranges for a model on another machine
- Follow redirects but strip credentials when the origin changes
- Keep host-only consent and migrate old grants to origins

## Assumptions

- Hosted model providers do not rely on redirects for their API endpoints
- Users with a LAN model can front it with https or reach it over localhost
