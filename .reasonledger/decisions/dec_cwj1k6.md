---
id: dec_cwj1k6
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-09T22:27:49.069358Z'
justifies:
- packages/mcp/src/reasonledger_mcp/tools.py::call_record_decision
- packages/mcp/src/reasonledger_mcp/tools.py::_verdict_warnings
- packages/cli/src/reasonledger_cli/identity.py::resolve_identity
- packages/core/src/reasonledger_core/decisions/identity_check.py::identity_mismatches
watchers: []
confidence: high
context: MCP record_decision accepted approved_by and oversight, so an agent could
  write a record as reviewed under any name, which defeats the identity work. How
  should the tool treat a verdict supplied by the caller?
choice: 'Keep both parameters in the tool signature for one release but ignore them:
  every MCP-written record is saved pending with no approver, and the result carries
  a warning naming reasonledger approve. Confirm and modules confirm/place resolve
  the acting person through one shared identity helper that defaults to git user.name.'
alternatives_rejected:
- 'Remove the parameters from the signature: breaks existing rule files that still
  pass approved_by, so capture would fail instead of degrading'
- 'Reject the call with an error when a verdict is passed: loses the decision the
  agent was trying to record'
- 'Keep honoring approved_by and rely on rule text: the agent can still claim any
  name'
assumptions:
- Agents read the warning in the tool result
- Git author names are a reasonable independent witness for the CI identity check,
  which therefore warns by default
---

## Context

MCP record_decision accepted approved_by and oversight, so an agent could write a record as reviewed under any name, which defeats the identity work. How should the tool treat a verdict supplied by the caller?

## Choice

Keep both parameters in the tool signature for one release but ignore them: every MCP-written record is saved pending with no approver, and the result carries a warning naming reasonledger approve. Confirm and modules confirm/place resolve the acting person through one shared identity helper that defaults to git user.name.

## Alternatives rejected

- Remove the parameters from the signature: breaks existing rule files that still pass approved_by, so capture would fail instead of degrading
- Reject the call with an error when a verdict is passed: loses the decision the agent was trying to record
- Keep honoring approved_by and rely on rule text: the agent can still claim any name

## Assumptions

- Agents read the warning in the tool result
- Git author names are a reasonable independent witness for the CI identity check, which therefore warns by default
