---
id: dec_47oeff
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-17T04:40:55.569057Z'
justifies:
- packages/core/src/reasonledger_core/settings.py::Settings
watchers: []
confidence: high
context: After the open-core split, Settings still declared OIDC, GitHub App, attestation-key,
  fixtures-root, backfill and critical-path fields that nothing reads, and loaded
  a .env file from the current directory. The wheel shipped enterprise-shaped config,
  and a tool run inside someone else's repo read that repo's .env. What should Settings
  keep?
choice: Keep only embedding_provider, the one field with a reader, and read RL_* environment
  variables alone with no env_file. .env.example is rewritten to list only variables
  the tool honours.
alternatives_rejected:
- 'Leave the fields as dormant placeholders for the commercial tier: they ship in
  an Apache-2.0 wheel and contradict the no-dead-code rule'
- 'Keep env_file for convenience: the tool would load the host project''s secrets
  file, and no documented workflow relies on it'
assumptions:
- The commercial tier's own repository defines its own settings and needs nothing
  from this module
---

## Context

After the open-core split, Settings still declared OIDC, GitHub App, attestation-key, fixtures-root, backfill and critical-path fields that nothing reads, and loaded a .env file from the current directory. The wheel shipped enterprise-shaped config, and a tool run inside someone else's repo read that repo's .env. What should Settings keep?

## Choice

Keep only embedding_provider, the one field with a reader, and read RL_* environment variables alone with no env_file. .env.example is rewritten to list only variables the tool honours.

## Alternatives rejected

- Leave the fields as dormant placeholders for the commercial tier: they ship in an Apache-2.0 wheel and contradict the no-dead-code rule
- Keep env_file for convenience: the tool would load the host project's secrets file, and no documented workflow relies on it

## Assumptions

- The commercial tier's own repository defines its own settings and needs nothing from this module
