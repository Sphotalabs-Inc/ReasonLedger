---
id: dec_vlferf
ai_tool: claude-code
model: claude-opus-5-5
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/reasoning/conflict_config.py::resolve_conflict_embedder_with_status
- packages/core/src/reasonledger_core/reasoning/conflict_config.py::unavailable_provider_error
- packages/core/src/reasonledger_core/reasoning/embeddings.py::local_embedder_available
- packages/core/src/reasonledger_core/views/ledger.py::build_ledger_view
watchers: []
confidence: high
context: When the configured conflict embedder cannot be built (the optional embeddings
  extra is missing, the model download is blocked, or a remote endpoint is misconfigured)
  status and the UI crashed with an ImportError. A committed conflict.yml choosing
  `local` reaches teammates who never installed the extra. What should detection do
  instead?
choice: Degrade visibly. resolve_conflict_embedder_with_status falls back to the deterministic
  hash embedder and returns an EmbedderStatus (requested, model_id, fallback_reason)
  that LedgerView carries; status and check-decisions print it, the UI and HTML export
  show a warning banner. Both config doors refuse saving `local` up front when the
  extra is absent.
alternatives_rejected:
- 'Fail hard: one teammate without the optional extra loses status, ui and import
  entirely'
- 'Disable related-decision detection when the embedder is missing: an empty list
  reads as an all-clear the tool never checked'
- 'Fall back silently: hash-based hints are far noisier, and users would blame the
  model they configured for the noise'
assumptions: []
---

## Context

When the configured conflict embedder cannot be built (the optional embeddings extra is missing, the model download is blocked, or a remote endpoint is misconfigured) status and the UI crashed with an ImportError. A committed conflict.yml choosing `local` reaches teammates who never installed the extra. What should detection do instead?

## Choice

Degrade visibly. resolve_conflict_embedder_with_status falls back to the deterministic hash embedder and returns an EmbedderStatus (requested, model_id, fallback_reason) that LedgerView carries; status and check-decisions print it, the UI and HTML export show a warning banner. Both config doors refuse saving `local` up front when the extra is absent.

## Alternatives rejected

- Fail hard: one teammate without the optional extra loses status, ui and import entirely
- Disable related-decision detection when the embedder is missing: an empty list reads as an all-clear the tool never checked
- Fall back silently: hash-based hints are far noisier, and users would blame the model they configured for the noise
