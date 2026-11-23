---
id: dec_aitool01
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/models/decision.py::normalize_ai_tool
- packages/core/src/reasonledger_core/models/decision.py::RecordDecisionInput
- packages/mcp/src/reasonledger_mcp/tools.py::call_record_decision
watchers: []
confidence: high
context: record_decision silently coerced any ai_tool outside a five-value enum to
  'other', so claude, grok and codex all lost their identity, and model was optional
  so three ledger records have none. What should the contract be for naming the tool
  and model that produced a decision?
choice: ai_tool is a free-form string, lowercased and hyphenated with claude and claudecode
  aliased to claude-code; model is required on RecordDecisionInput unless ai_tool
  is none. The check lives at record time only, so existing records without a model
  still load.
alternatives_rejected:
- 'Grow the enum (codex, gemini, grok...): every new agent needs a release and unknown
  names would still collapse to other'
- 'Reject unknown ai_tool values with an error listing the valid ones: strictest,
  but breaks every agent that spells its name differently and gains little over normalising'
- 'Keep model optional and only document it: three of six records here already show
  agents skip optional fields'
- 'Validate model on DecisionFrontmatter: would make older records unreadable'
assumptions:
- Model ids are not PII, so they can be stored verbatim
- Human-made decisions are the only legitimate case with no model
---

## Context

record_decision silently coerced any ai_tool outside a five-value enum to 'other', so claude, grok and codex all lost their identity, and model was optional so three ledger records have none. What should the contract be for naming the tool and model that produced a decision?

## Choice

ai_tool is a free-form string, lowercased and hyphenated with claude and claudecode aliased to claude-code; model is required on RecordDecisionInput unless ai_tool is none. The check lives at record time only, so existing records without a model still load.

## Alternatives rejected

- Grow the enum (codex, gemini, grok...): every new agent needs a release and unknown names would still collapse to other
- Reject unknown ai_tool values with an error listing the valid ones: strictest, but breaks every agent that spells its name differently and gains little over normalising
- Keep model optional and only document it: three of six records here already show agents skip optional fields
- Validate model on DecisionFrontmatter: would make older records unreadable

## Assumptions

- Model ids are not PII, so they can be stored verbatim
- Human-made decisions are the only legitimate case with no model
