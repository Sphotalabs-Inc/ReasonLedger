---
id: dec_617ali
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-17T02:37:07.712431Z'
justifies:
- packages/core/src/reasonledger_core/importer/agent_route.py::_summary
- packages/core/src/reasonledger_core/importer/agent_route.py::import_task
- packages/core/src/reasonledger_core/importer/agent_route.py::submit_candidates
watchers: []
confidence: medium
context: 'An agent running the MCP import saw nothing when a batch of files held no
  decisions: the tool results were bare counts and the agent had no cue to report,
  so a first-time user could not tell a quiet batch from a stalled import. Where should
  the progress signal live?'
choice: The import tools return the signal themselves. get_import_task adds total
  and done, and submit_candidates adds a one-line summary (sources read, proposals
  staged or none found, how many remain, what to run next). The agent instructions
  tell the agent to relay that line to the user after every batch. The batch size
  stays at 8.
alternatives_rejected:
- 'Show import progress in the UI Overview only: the user is watching the agent chat
  when the batches run, and the UI cannot make the agent speak'
- 'Raise the default batch from 8 to the 20 maximum: it cuts round trips but does
  not fix the silence, and changes how much text one tool call hands an agent'
- 'Have the agent loop through every batch without reporting until done: a 200-file
  import would stay silent for many minutes'
assumptions:
- Coding agents relay a plain-language line from a tool result when the tool instructions
  ask them to
---

## Context

An agent running the MCP import saw nothing when a batch of files held no decisions: the tool results were bare counts and the agent had no cue to report, so a first-time user could not tell a quiet batch from a stalled import. Where should the progress signal live?

## Choice

The import tools return the signal themselves. get_import_task adds total and done, and submit_candidates adds a one-line summary (sources read, proposals staged or none found, how many remain, what to run next). The agent instructions tell the agent to relay that line to the user after every batch. The batch size stays at 8.

## Alternatives rejected

- Show import progress in the UI Overview only: the user is watching the agent chat when the batches run, and the UI cannot make the agent speak
- Raise the default batch from 8 to the 20 maximum: it cuts round trips but does not fix the silence, and changes how much text one tool call hands an agent
- Have the agent loop through every batch without reporting until done: a 200-file import would stay silent for many minutes

## Assumptions

- Coding agents relay a plain-language line from a tool result when the tool instructions ask them to
