---
id: dec_e3v3pi
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-17T03:25:56.233245Z'
justifies:
- packages/core/src/reasonledger_core/reasoning/agent_judge.py::judging_task
- packages/mcp/src/reasonledger_mcp/tools.py::call_get_judging_task
- packages/cli/src/reasonledger_cli/ui_assets/setup.js::judgePairPrompt
- packages/cli/src/reasonledger_cli/ui_assets/conflicts.js::uncheckedActions
watchers: []
confidence: medium
context: A user who judges related decisions with their own coding agent could only
  hand it the "every pair" prompt, which the tool's instructions turn into a loop
  over all pairs. They needed to check a few pairs, or exactly one, without a configured
  model. How should the agent route support that?
choice: get_judging_task takes optional decision_a and decision_b; naming both returns
  only that pair (order does not matter) with instructions to judge it and stop, and
  a pair not waiting for a verdict returns no pairs and a note saying why. The batch
  instructions now say to continue unless the user asked for a number of pairs or
  one pair. The UI gains a few-pairs prompt (limit 5, stop after one batch) beside
  the every-pair prompt, and a copyable per-pair prompt on each unchecked pair.
alternatives_rejected:
- 'Document limit 1 as the one-by-one prompt and add nothing to the tool: it cannot
  name which pair, so a user cannot judge the pair they are looking at'
- 'Add a separate get_judging_pair tool: a second near-identical tool for the same
  rubric and verdict path, more surface for agents to choose wrongly between'
- 'Make the UI per-pair button call the agent directly: the UI server has no channel
  to the coding agent and the route is deliberately model-free'
assumptions:
- Agents follow a stop-after-one-pair instruction in the tool result when the user's
  prompt names a single pair
---

## Context

A user who judges related decisions with their own coding agent could only hand it the "every pair" prompt, which the tool's instructions turn into a loop over all pairs. They needed to check a few pairs, or exactly one, without a configured model. How should the agent route support that?

## Choice

get_judging_task takes optional decision_a and decision_b; naming both returns only that pair (order does not matter) with instructions to judge it and stop, and a pair not waiting for a verdict returns no pairs and a note saying why. The batch instructions now say to continue unless the user asked for a number of pairs or one pair. The UI gains a few-pairs prompt (limit 5, stop after one batch) beside the every-pair prompt, and a copyable per-pair prompt on each unchecked pair.

## Alternatives rejected

- Document limit 1 as the one-by-one prompt and add nothing to the tool: it cannot name which pair, so a user cannot judge the pair they are looking at
- Add a separate get_judging_pair tool: a second near-identical tool for the same rubric and verdict path, more surface for agents to choose wrongly between
- Make the UI per-pair button call the agent directly: the UI server has no channel to the coding agent and the route is deliberately model-free

## Assumptions

- Agents follow a stop-after-one-pair instruction in the tool result when the user's prompt names a single pair
