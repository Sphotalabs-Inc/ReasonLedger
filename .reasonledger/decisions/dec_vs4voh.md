---
id: dec_vs4voh
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-25T04:30:34.821748Z'
justifies:
- packages/mcp/src/reasonledger_mcp/server.py::create_mcp_server
- packages/mcp/tests/test_mcp_contract.py::test_mcp_stdio_list_and_call_tools
watchers: []
context: The MCP server's initialize reply reported the mcp SDK's version (1.30.0)
  as serverInfo.version, because FastMCP accepts no version argument. Should the server
  report its own version, and how?
choice: Set the underlying low-level server's version after constructing FastMCP (`mcp._mcp_server.version
  = package_version("reasonledger-mcp")`), and assert serverInfo name and version
  in the real stdio contract test so an SDK change that moves the attribute fails
  loudly.
alternatives_rejected:
- 'Leave the SDK version in serverInfo: misleads agents and bug reports about which
  ReasonLedger is running'
- 'Build the server on mcp.server.lowlevel.Server directly: rewrites every tool registration
  for a one-field fix'
- 'Subclass FastMCP to accept a version: same private attribute, more code'
assumptions:
- mcp<2 keeps FastMCP._mcp_server as the low-level Server whose version feeds initialize;
  the contract test is the guard if not
---

## Context

The MCP server's initialize reply reported the mcp SDK's version (1.30.0) as serverInfo.version, because FastMCP accepts no version argument. Should the server report its own version, and how?

## Choice

Set the underlying low-level server's version after constructing FastMCP (`mcp._mcp_server.version = package_version("reasonledger-mcp")`), and assert serverInfo name and version in the real stdio contract test so an SDK change that moves the attribute fails loudly.

## Alternatives rejected

- Leave the SDK version in serverInfo: misleads agents and bug reports about which ReasonLedger is running
- Build the server on mcp.server.lowlevel.Server directly: rewrites every tool registration for a one-field fix
- Subclass FastMCP to accept a version: same private attribute, more code

## Assumptions

- mcp<2 keeps FastMCP._mcp_server as the low-level Server whose version feeds initialize; the contract test is the guard if not
