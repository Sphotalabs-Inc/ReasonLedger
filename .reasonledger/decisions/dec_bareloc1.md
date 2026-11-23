---
id: dec_bareloc1
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- packages/mcp/src/reasonledger_mcp/tools.py::_bare_path_warnings
- packages/mcp/src/reasonledger_mcp/tools.py::call_record_decision
- packages/mcp/src/reasonledger_mcp/server.py::create_mcp_server
watchers: []
confidence: high
context: Agents pass bare file paths as justifies, which match at the coarsest tier
  and make rl why return low-precision hits; the MCP server also had its own copy
  of record_decision that skipped symbol anchoring. What should recording do about
  both?
choice: record_decision returns a warnings list naming every bare-path locus and suggesting
  path::symbol or path:START-END, but still saves the record. The MCP server tool
  now delegates to call_record_decision so there is one record path.
alternatives_rejected:
- 'Reject records with bare paths: blocks the capture the product exists for, and
  some files have no meaningful symbol'
- 'Silently auto-pick a symbol for bare paths: guesses at what the decision explains'
- 'Leave the duplicated server implementation and patch both: the two copies had already
  drifted'
assumptions:
- Agents read the tool result, so a warning in it is seen
---

## Context

Agents pass bare file paths as justifies, which match at the coarsest tier and make rl why return low-precision hits; the MCP server also had its own copy of record_decision that skipped symbol anchoring. What should recording do about both?

## Choice

record_decision returns a warnings list naming every bare-path locus and suggesting path::symbol or path:START-END, but still saves the record. The MCP server tool now delegates to call_record_decision so there is one record path.

## Alternatives rejected

- Reject records with bare paths: blocks the capture the product exists for, and some files have no meaningful symbol
- Silently auto-pick a symbol for bare paths: guesses at what the decision explains
- Leave the duplicated server implementation and patch both: the two copies had already drifted

## Assumptions

- Agents read the tool result, so a warning in it is seen
