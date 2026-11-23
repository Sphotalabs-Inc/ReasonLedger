---
id: dec_tkhnpk
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
status: active
proposed_by: ai
approved_by: iharpreet
approved_at: '2026-11-12T04:57:35.139099Z'
recorded_at: '2026-11-09T22:37:40.443010Z'
justifies:
- packages/cli/src/reasonledger_cli/agent_targets.py::TARGETS
- packages/cli/src/reasonledger_cli/agent_targets.py::write_rule
- packages/cli/src/reasonledger_cli/agent_targets.py::write_mcp_config
- packages/cli/src/reasonledger_cli/agent_targets.py::mcp_server_entry
watchers: []
confidence: medium
context: init wrote two MCP configs and only printed the agent rule, so a repo where
  nobody pasted it recorded nothing; supporting VS Code and AGENTS.md readers would
  add more per-agent code paths. How should init install the rule and config for every
  agent?
choice: 'One table of agent targets drives both the MCP config and the rule file.
  Rules are written: the whole file where ReasonLedger owns it (.cursor/rules/reasonledger.mdc),
  otherwise a block between begin/end markers appended or replaced in place, with
  raw bytes preserved. MCP configs are still only created when absent, and an existing
  file without our entry is left alone and the entry printed. The server command falls
  back to uvx when reasonledger-mcp is not on PATH.'
alternatives_rejected:
- 'Keep printing the rule for the user to paste: measured to produce zero captures
  when nobody pastes it'
- 'Overwrite or merge into existing MCP configs: edits files the user owns and can
  corrupt hand-written JSON'
- 'Per-agent init functions: three copies of the write, ignore and idempotency logic
  that drift'
assumptions:
- VS Code still reads .vscode/mcp.json with a servers root key; its docs call it a
  compatibility location, so this may need revisiting
- uvx is available to a user who ran uvx reasonledger init
---

## Context

init wrote two MCP configs and only printed the agent rule, so a repo where nobody pasted it recorded nothing; supporting VS Code and AGENTS.md readers would add more per-agent code paths. How should init install the rule and config for every agent?

## Choice

One table of agent targets drives both the MCP config and the rule file. Rules are written: the whole file where ReasonLedger owns it (.cursor/rules/reasonledger.mdc), otherwise a block between begin/end markers appended or replaced in place, with raw bytes preserved. MCP configs are still only created when absent, and an existing file without our entry is left alone and the entry printed. The server command falls back to uvx when reasonledger-mcp is not on PATH.

## Alternatives rejected

- Keep printing the rule for the user to paste: measured to produce zero captures when nobody pastes it
- Overwrite or merge into existing MCP configs: edits files the user owns and can corrupt hand-written JSON
- Per-agent init functions: three copies of the write, ignore and idempotency logic that drift

## Assumptions

- VS Code still reads .vscode/mcp.json with a servers root key; its docs call it a compatibility location, so this may need revisiting
- uvx is available to a user who ran uvx reasonledger init
