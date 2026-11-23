---
id: dec_wh3do8
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
proposed_by: ai
status: active
justifies:
- packages/core/src/reasonledger_core/models/decision.py::DecisionProposer
- packages/core/src/reasonledger_core/models/decision.py::RecordDecisionInput
- packages/mcp/src/reasonledger_mcp/tools.py::_proposed_by_warnings
- packages/core/src/reasonledger_core/views/ledger.py::_count_proposed_by
- packages/cli/src/reasonledger_cli/ui_assets/render.js:162-175
watchers: []
confidence: high
context: Records said whether a person reviewed a decision (oversight) but not whose
  idea the choice was, so a choice the user directed and one the agent picked then
  got approved both read as reviewed. How should the ledger capture origin, and how
  strictly should agents be made to supply it?
choice: Add an optional proposed_by field (human or ai) to the decision frontmatter
  and to record_decision, independent of oversight. It is optional so existing records
  and agents keep working; a record saved without it returns a warning telling the
  agent to set it. The UI shows human as an agreed badge and ai as a recommended badge,
  plus two count chips, and records without the field show no badge. Agent instructions
  say to claim human only when the user stated or accepted the choice in chat.
alternatives_rejected:
- 'Fold origin into the source field: source already means how a record was captured
  (recorded, doc-import, harvested), and an MCP-recorded decision can be either user-directed
  or agent-chosen, so one field would conflate two questions'
- 'Add agreed and recommended as new oversight values: oversight is the human verdict
  on a record, and an AI recommendation a person approves would then have no honest
  value, losing exactly the case this exists to show'
- 'Make proposed_by required on record_decision: breaks every existing agent configuration
  and old records, the same reason dec_aitool01 kept model validation at record time
  only; a warning nudges without breaking'
- 'Infer proposed_by from ai_tool: ai_tool none can still be an agent decision and
  an agent tool can record what the user dictated, so inference would claim evidence
  nobody provided'
assumptions:
- The agent can tell from the conversation whether the user stated or accepted a choice,
  and the instruction to claim human only on explicit user statement is followed;
  the field is self-reported, not verified
- Doc imports leave the field unset because a document does not say who originated
  its decisions
---

## Context

Records said whether a person reviewed a decision (oversight) but not whose idea the choice was, so a choice the user directed and one the agent picked then got approved both read as reviewed. How should the ledger capture origin, and how strictly should agents be made to supply it?

## Choice

Add an optional proposed_by field (human or ai) to the decision frontmatter and to record_decision, independent of oversight. It is optional so existing records and agents keep working; a record saved without it returns a warning telling the agent to set it. The UI shows human as an agreed badge and ai as a recommended badge, plus two count chips, and records without the field show no badge. Agent instructions say to claim human only when the user stated or accepted the choice in chat.

## Alternatives rejected

- Fold origin into the source field: source already means how a record was captured (recorded, doc-import, harvested), and an MCP-recorded decision can be either user-directed or agent-chosen, so one field would conflate two questions
- Add agreed and recommended as new oversight values: oversight is the human verdict on a record, and an AI recommendation a person approves would then have no honest value, losing exactly the case this exists to show
- Make proposed_by required on record_decision: breaks every existing agent configuration and old records, the same reason dec_aitool01 kept model validation at record time only; a warning nudges without breaking
- Infer proposed_by from ai_tool: ai_tool none can still be an agent decision and an agent tool can record what the user dictated, so inference would claim evidence nobody provided

## Assumptions

- The agent can tell from the conversation whether the user stated or accepted a choice, and the instruction to claim human only on explicit user statement is followed; the field is self-reported, not verified
- Doc imports leave the field unset because a document does not say who originated its decisions
