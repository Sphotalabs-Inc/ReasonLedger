# CLAUDE.md

Claude Code reads this file, not `AGENTS.md`. Rather than duplicate the charter (and let
the two drift), this file imports it.

@AGENTS.md

## Non-negotiable for this repo

**We dogfood ReasonLedger.** See §10 of the charter. Before deciding, call MCP
`query_decisions`; after a real decision, call `record_decision`. The MCP server is wired
in `.mcp.json` and writes to `.reasonledger/decisions/`.

The trigger is narrow — a choice between viable alternatives that changed the code — and
three field rules are mandatory: `context` and `choice` must differ, `justifies` must use
line or symbol loci rather than bare file paths, and `alternatives_rejected` must be
non-empty. §10 explains what breaks when each is violated.
