---
id: dec_ykz9qi
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-11T17:05:16.882655Z'
justifies:
- packages/core/src/reasonledger_core/reasoning/retrieval.py::semantic_recall
- packages/mcp/src/reasonledger_mcp/tools.py::call_query_decisions
watchers: []
confidence: high
context: MCP query_decisions with semantic=true resolved its embedder from env settings,
  so in a repo whose conflict.yml selects the local model it silently ranked with
  the hash embedder, while status, ui, judge and check used the configured one. Main's
  tool also changed shape since the fix was first written (limit, full, total and
  truncated replaced top_k). How should semantic recall pick its embedder, report
  a fallback, and fit main's current response?
choice: Add core semantic_recall, which resolves the embedder exactly as status and
  judge do, wraps it in the repo's CachingEmbedder, and returns its EmbedderStatus.
  call_query_decisions uses it for semantic mode, still ranks every record, and applies
  the existing limit cap, so total and truncated keep their meaning and top_k is not
  reintroduced. A fallback is reported in an always-present warnings list in the result
  rather than degrading silently.
alternatives_rejected:
- 'Keep top_k next to limit: two knobs for the same cap, and main''s tool already
  ranks everything then caps by limit'
- 'Emit warnings only when non-empty: the result shape would vary by call, and an
  agent could not tell no-warning from a client that predates the field'
- 'Leave the embedder to the RL_EMBEDDING_PROVIDER env var in the MCP config: it must
  be set in every editor-spawned process and disagrees with the conflict.yml that
  init writes, which is the original silent mismatch'
- 'Fail the call when the configured embedder cannot start: breaks recall on a teammate''s
  machine that never installed the extra, where answering on word matching with a
  visible warning is more useful'
assumptions:
- The first semantic call after a fresh clone embeds every decision and is slow; later
  calls read vectors from the gitignored .reasonledger/cache/embeddings
- get_embedder reuses one loaded local model per process, so an MCP server resolving
  the embedder on every query does not reload it
- Ranking every record before the limit cap is acceptable at current ledger sizes
  (tens to low hundreds of decisions)
---

## Context

MCP query_decisions with semantic=true resolved its embedder from env settings, so in a repo whose conflict.yml selects the local model it silently ranked with the hash embedder, while status, ui, judge and check used the configured one. Main's tool also changed shape since the fix was first written (limit, full, total and truncated replaced top_k). How should semantic recall pick its embedder, report a fallback, and fit main's current response?

## Choice

Add core semantic_recall, which resolves the embedder exactly as status and judge do, wraps it in the repo's CachingEmbedder, and returns its EmbedderStatus. call_query_decisions uses it for semantic mode, still ranks every record, and applies the existing limit cap, so total and truncated keep their meaning and top_k is not reintroduced. A fallback is reported in an always-present warnings list in the result rather than degrading silently.

## Alternatives rejected

- Keep top_k next to limit: two knobs for the same cap, and main's tool already ranks everything then caps by limit
- Emit warnings only when non-empty: the result shape would vary by call, and an agent could not tell no-warning from a client that predates the field
- Leave the embedder to the RL_EMBEDDING_PROVIDER env var in the MCP config: it must be set in every editor-spawned process and disagrees with the conflict.yml that init writes, which is the original silent mismatch
- Fail the call when the configured embedder cannot start: breaks recall on a teammate's machine that never installed the extra, where answering on word matching with a visible warning is more useful

## Assumptions

- The first semantic call after a fresh clone embeds every decision and is slow; later calls read vectors from the gitignored .reasonledger/cache/embeddings
- get_embedder reuses one loaded local model per process, so an MCP server resolving the embedder on every query does not reload it
- Ranking every record before the limit cap is acceptable at current ledger sizes (tens to low hundreds of decisions)
