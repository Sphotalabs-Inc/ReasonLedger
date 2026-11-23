---
id: dec_1nozh3
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-13T05:12:02.288725Z'
justifies:
- packages/cli/src/reasonledger_cli/ui_assets/ask.js::DECISION_FILTERS
- packages/cli/src/reasonledger_cli/ui_assets/browse.js::replacedHtml
- packages/cli/src/reasonledger_cli/ui_assets/browse.js::indexReplaced
watchers: []
context: The Ask tab listed every decision, replaced and retired ones included, so
  history crowded out what is currently true. How should the default list cut that
  noise while keeping the reasoning behind what replaced what?
choice: The default filter, now called Active decisions, lists only decisions in force.
  A decision that replaced others carries a collapsed Replaces N earlier decisions
  line on its card, built from the full record set, giving each old choice and the
  reason it was replaced and following the chain back. Replaced and retired decisions
  stay one filter away under History, and searching for the id of one opens History.
alternatives_rejected:
- 'Keep every decision in the default list with history greyed out: still the same
  volume, and the owner asked for less'
- 'Delete or auto-archive replaced and retired decisions after a time: loses the rejected-alternatives
  evidence the product exists to keep'
- 'Show replaced decisions as their own rows beside their successor: doubles the rows
  for each replacement instead of folding them into one card'
assumptions:
- Retired decisions with no successor have nothing to attach to, so they appear only
  under History
---

## Context

The Ask tab listed every decision, replaced and retired ones included, so history crowded out what is currently true. How should the default list cut that noise while keeping the reasoning behind what replaced what?

## Choice

The default filter, now called Active decisions, lists only decisions in force. A decision that replaced others carries a collapsed Replaces N earlier decisions line on its card, built from the full record set, giving each old choice and the reason it was replaced and following the chain back. Replaced and retired decisions stay one filter away under History, and searching for the id of one opens History.

## Alternatives rejected

- Keep every decision in the default list with history greyed out: still the same volume, and the owner asked for less
- Delete or auto-archive replaced and retired decisions after a time: loses the rejected-alternatives evidence the product exists to keep
- Show replaced decisions as their own rows beside their successor: doubles the rows for each replacement instead of folding them into one card

## Assumptions

- Retired decisions with no successor have nothing to attach to, so they appear only under History
