---
id: dec_be0usd
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: active
proposed_by: human
justifies:
- packages/cli/src/reasonledger_cli/ui_assets/review.js:117-159
- packages/cli/src/reasonledger_cli/ui_assets/review.js:50-58
- packages/cli/src/reasonledger_cli/ui_assets/needs.js:15-17
watchers: []
confidence: high
context: The Waiting on you rows clip a decision to 110 characters of context and
  show no choice, yet each carried an Approve button, so a verdict could be given
  on text the reviewer had not seen. dec_54yz9f put Approve on those rows and dec_7vehg9
  kept approval in place on the card. Where does a person approve from?
choice: Rows and cards carry a Review button that opens a modal dialog rendering the
  whole record through the shared decisionItem renderer with every detail open, plus
  its code loci and provenance; Approve and Retire live only inside it, beside the
  name the action will be recorded under. This diverges from dec_54yz9f and dec_7vehg9
  on where the Approve button sits; the row-links-to-card rule and the single anchor
  per record are kept, since the dialog copy drops its id.
alternatives_rejected:
- 'Stop clipping and show the full decision inline in each row: five pending decisions
  make the card several screens long'
- 'Remove Approve from rows and leave it only on the full card: the card still hides
  assumptions and alternatives behind a collapsed details element'
- 'Keep window.prompt and add a confirm step: a prompt cannot show the record'
assumptions:
- The native dialog element is available in every browser the local UI is opened in
- Only reviewed is offered here; modified and rejected stay with the CLI as dec_7vehg9
  decided
---

## Context

The Waiting on you rows clip a decision to 110 characters of context and show no choice, yet each carried an Approve button, so a verdict could be given on text the reviewer had not seen. dec_54yz9f put Approve on those rows and dec_7vehg9 kept approval in place on the card. Where does a person approve from?

## Choice

Rows and cards carry a Review button that opens a modal dialog rendering the whole record through the shared decisionItem renderer with every detail open, plus its code loci and provenance; Approve and Retire live only inside it, beside the name the action will be recorded under. This diverges from dec_54yz9f and dec_7vehg9 on where the Approve button sits; the row-links-to-card rule and the single anchor per record are kept, since the dialog copy drops its id.

## Alternatives rejected

- Stop clipping and show the full decision inline in each row: five pending decisions make the card several screens long
- Remove Approve from rows and leave it only on the full card: the card still hides assumptions and alternatives behind a collapsed details element
- Keep window.prompt and add a confirm step: a prompt cannot show the record

## Assumptions

- The native dialog element is available in every browser the local UI is opened in
- Only reviewed is offered here; modified and rejected stay with the CLI as dec_7vehg9 decided
