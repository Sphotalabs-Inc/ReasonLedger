---
id: dec_d756c8
ai_tool: cursor
model: grok-4.7
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-15T06:49:58.083624Z'
justifies:
- packages/core/src/reasonledger_core/importer/agent_route.py::import_task
- packages/core/src/reasonledger_core/importer/agent_route.py::submit_candidates
- packages/cli/src/reasonledger_cli/ui_assets/agent_card.js:34-36
anchor_hashes:
  packages/cli/src/reasonledger_cli/ui_assets/agent_card.js:34-36: sha256:fc1f5a8b1045ac1d
watchers: []
confidence: high
context: Importing decisions from docs and commit messages required a configured model,
  so a person who only has a coding agent could not backfill. Should that agent do
  the extraction?
choice: Add get_import_task and submit_candidates. The task lists document paths without
  their text and includes commit messages because they are not files. Submissions
  are proposals through the existing import gate. A finished source is remembered
  by a hash of its text and returns only when that text changes.
alternatives_rejected:
- Keep import behind a configured model API key or a local model.
- Put document bodies in the task. The agent can open those files, and a large doc
  would be copied into the tool result.
- Have the agent call record_decision for old prose. That writes ledger records instead
  of proposals and skips import's source_ref idempotency.
assumptions:
- The agent's own model still sees the text when it reads the files.
- A person confirms every proposal before it enters the ledger.
---

## Context

Importing decisions from docs and commit messages required a configured model, so a person who only has a coding agent could not backfill. Should that agent do the extraction?

## Choice

Add get_import_task and submit_candidates. The task lists document paths without their text and includes commit messages because they are not files. Submissions are proposals through the existing import gate. A finished source is remembered by a hash of its text and returns only when that text changes.

## Alternatives rejected

- Keep import behind a configured model API key or a local model.
- Put document bodies in the task. The agent can open those files, and a large doc would be copied into the tool result.
- Have the agent call record_decision for old prose. That writes ledger records instead of proposals and skips import's source_ref idempotency.

## Assumptions

- The agent's own model still sees the text when it reads the files.
- A person confirms every proposal before it enters the ledger.
