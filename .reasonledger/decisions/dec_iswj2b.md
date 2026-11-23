---
id: dec_iswj2b
ai_tool: claude-code
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/decisions/service.py::superseded_by_map
- packages/core/src/reasonledger_core/reasoning/why.py::resolve_why
- packages/core/src/reasonledger_core/reasoning/why.py::WhyHit
- packages/cli/src/reasonledger_cli/main.py::run_why
- packages/cli/src/reasonledger_cli/ui_cmd.py::_why_payload
- packages/mcp/src/reasonledger_mcp/tools.py::call_query_decisions
watchers: []
confidence: high
context: '`rl why` and `query_decisions` matched decisions purely on code locus /
  text, never reading `frontmatter.status` — so a decision retired via `confirm_proposed`
  to `status: superseded` surfaced identically to its active replacement, with no
  indication it no longer reflects current reasoning. The question was how to close
  that gap: filter superseded records out of results, or keep them but mark them.'
choice: Mark, don't hide. Added `superseded_by_map()` in `decisions/service.py` to
  compute the reverse pointer (old id -> new id) live from `frontmatter.supersedes`,
  threaded a `superseded_by` field through `WhyHit` in `resolve_why`, and surfaced
  `status`/`superseded_by` at every display surface (CLI `why` text + `--json`, the
  local UI's `_why_payload`, and the MCP `call_query_decisions` tool) without removing
  any record from the result set.
alternatives_rejected:
- Filter superseded records out of `why`/`query_decisions` results by default (e.g.
  an `include_superseded` flag defaulting to False) — rejected because `supersedes`
  is only a forward pointer and the successor's `justifies` loci are not guaranteed
  to cover the same locus as the retired record; hiding it risked turning a real hit
  into a false 'no decision justifies this line yet' miss, which is worse than showing
  stale-but-labeled evidence in an audit product.
- Add a new stored `superseded_by` frontmatter field written at confirm time — rejected
  in favor of computing it live from existing `supersedes` pointers, so the reverse
  link can never drift from the ledger and no migration or schema change was needed.
- Reorder `why` hits so superseded records sort after active ones — rejected to keep
  the change minimal; existing `resolve_why` tests pin hit order by id, and marking
  alone (without hiding) already removes the misleading ambiguity the gap caused.
assumptions: []
---

## Context

`rl why` and `query_decisions` matched decisions purely on code locus / text, never reading `frontmatter.status` — so a decision retired via `confirm_proposed` to `status: superseded` surfaced identically to its active replacement, with no indication it no longer reflects current reasoning. The question was how to close that gap: filter superseded records out of results, or keep them but mark them.

## Choice

Mark, don't hide. Added `superseded_by_map()` in `decisions/service.py` to compute the reverse pointer (old id -> new id) live from `frontmatter.supersedes`, threaded a `superseded_by` field through `WhyHit` in `resolve_why`, and surfaced `status`/`superseded_by` at every display surface (CLI `why` text + `--json`, the local UI's `_why_payload`, and the MCP `call_query_decisions` tool) without removing any record from the result set.

## Alternatives rejected

- Filter superseded records out of `why`/`query_decisions` results by default (e.g. an `include_superseded` flag defaulting to False) — rejected because `supersedes` is only a forward pointer and the successor's `justifies` loci are not guaranteed to cover the same locus as the retired record; hiding it risked turning a real hit into a false 'no decision justifies this line yet' miss, which is worse than showing stale-but-labeled evidence in an audit product.
- Add a new stored `superseded_by` frontmatter field written at confirm time — rejected in favor of computing it live from existing `supersedes` pointers, so the reverse link can never drift from the ledger and no migration or schema change was needed.
- Reorder `why` hits so superseded records sort after active ones — rejected to keep the change minimal; existing `resolve_why` tests pin hit order by id, and marking alone (without hiding) already removes the misleading ambiguity the gap caused.
