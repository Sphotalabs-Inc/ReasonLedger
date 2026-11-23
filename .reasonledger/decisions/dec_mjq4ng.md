---
id: dec_mjq4ng
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
justifies:
- packages/core/src/reasonledger_core/views/ledger.py::DecisionSummary
- packages/core/src/reasonledger_core/views/ledger.py::_decision_summary
- packages/cli/src/reasonledger_cli/ui_assets/render.js:151-187
watchers: []
confidence: high
context: The Approve button sat next to a card showing only context and choice, so
  a reviewer vouched for a decision without seeing the assumptions it rests on or
  the alternatives it rejected. LedgerView's DecisionSummary did not carry either
  field. How should the card get them to the reviewer?
choice: Widen DecisionSummary with assumptions and alternatives_rejected, both defaulting
  to empty, and render them in the shared decisionItem renderer inside a collapsed
  details element whose summary line shows the counts. The same payload feeds the
  live UI and the static export, and the spec's DecisionSummary field list is updated
  to match.
alternatives_rejected:
- 'Fetch the two fields from a new endpoint when a card is expanded: a second round
  trip and a second contract for text that is already on disk and small, and the read-only
  export could not use it'
- 'Show them always expanded: a ledger of many decisions becomes a wall of text, and
  the reviewer scanning for pending items loses the one-line card'
- 'Show them only on pending decisions: assumptions matter just as much when re-reading
  an approved decision, and the renderer would need a second code path'
- 'Make the new fields required on DecisionSummary: breaks any caller constructing
  one directly for no benefit, since an empty list already means none recorded'
assumptions:
- Assumptions and alternatives are short free-text lists, so carrying them in every
  view payload and in the static export is cheap
- Both fields already pass the PII linter at record time, so surfacing them in the
  export adds no new disclosure
- The view cache is in-memory only, so a widened model cannot meet a stale serialized
  shape
---

## Context

The Approve button sat next to a card showing only context and choice, so a reviewer vouched for a decision without seeing the assumptions it rests on or the alternatives it rejected. LedgerView's DecisionSummary did not carry either field. How should the card get them to the reviewer?

## Choice

Widen DecisionSummary with assumptions and alternatives_rejected, both defaulting to empty, and render them in the shared decisionItem renderer inside a collapsed details element whose summary line shows the counts. The same payload feeds the live UI and the static export, and the spec's DecisionSummary field list is updated to match.

## Alternatives rejected

- Fetch the two fields from a new endpoint when a card is expanded: a second round trip and a second contract for text that is already on disk and small, and the read-only export could not use it
- Show them always expanded: a ledger of many decisions becomes a wall of text, and the reviewer scanning for pending items loses the one-line card
- Show them only on pending decisions: assumptions matter just as much when re-reading an approved decision, and the renderer would need a second code path
- Make the new fields required on DecisionSummary: breaks any caller constructing one directly for no benefit, since an empty list already means none recorded

## Assumptions

- Assumptions and alternatives are short free-text lists, so carrying them in every view payload and in the static export is cheap
- Both fields already pass the PII linter at record time, so surfacing them in the export adds no new disclosure
- The view cache is in-memory only, so a widened model cannot meet a stale serialized shape
