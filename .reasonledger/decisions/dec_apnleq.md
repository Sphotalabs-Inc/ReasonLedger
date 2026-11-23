---
id: dec_apnleq
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
justifies:
- packages/core/src/reasonledger_core/reasoning/why.py::why_payload
- packages/core/src/reasonledger_core/reasoning/why.py::target_exists
- packages/cli/src/reasonledger_cli/ui_assets/browse.js::groupByArea
- packages/cli/src/reasonledger_cli/ui_assets/browse.js::whyResultsHtml
- packages/cli/src/reasonledger_cli/ui_cmd.py::make_ui_handler
- packages/cli/src/reasonledger_cli/main.py::run_why
watchers: []
context: The local UI's Why box needed a file path the reader had to already know,
  and returned only id and choice, hiding the question each decision answered, how
  precisely it anchored to the code, and what a miss meant. How should the UI let
  a reader start from a topic or area, and what should Why show?
choice: 'Add a find-a-decision card built from the already-loaded view: decisions
  grouped by the directory of their justifies anchors, with text search, cards led
  by the context question, and anchored loci that link into Why. Why results are ranked
  by match precision with a plain-language precision badge, matched loci, assumptions
  and alternatives, and tell a missing path apart from a file with no decisions. CLI
  why --json and the UI share one core why_payload, and the live-only code moves into
  a new browse.js.'
alternatives_rejected:
- 'A new /api/areas endpoint that groups and searches on the server: the view already
  carries every justifies anchor, so it adds a second contract and a round trip for
  no new data'
- 'Keep the duplicated payload dict in main.py and ui_cmd.py and add the new fields
  in both: the two copies had already been kept in step by a comment alone'
- 'Put browse and Why wiring in app.js: it was already past the 400-line hard limit,
  and the live-only code is better isolated from the static export'
- 'Group by exact file instead of directory: a file-per-group list is as hard to scan
  as the flat ledger it replaces'
assumptions:
- Directory depth of three separates services, routes and components well enough for
  typical layouts; AREA_DEPTH is one constant to tune
- The ledger fits in one view payload, so client-side search over all decisions stays
  responsive
- The static export does not need browse or Why, since both are live-only
---

## Context

The local UI's Why box needed a file path the reader had to already know, and returned only id and choice, hiding the question each decision answered, how precisely it anchored to the code, and what a miss meant. How should the UI let a reader start from a topic or area, and what should Why show?

## Choice

Add a find-a-decision card built from the already-loaded view: decisions grouped by the directory of their justifies anchors, with text search, cards led by the context question, and anchored loci that link into Why. Why results are ranked by match precision with a plain-language precision badge, matched loci, assumptions and alternatives, and tell a missing path apart from a file with no decisions. CLI why --json and the UI share one core why_payload, and the live-only code moves into a new browse.js.

## Alternatives rejected

- A new /api/areas endpoint that groups and searches on the server: the view already carries every justifies anchor, so it adds a second contract and a round trip for no new data
- Keep the duplicated payload dict in main.py and ui_cmd.py and add the new fields in both: the two copies had already been kept in step by a comment alone
- Put browse and Why wiring in app.js: it was already past the 400-line hard limit, and the live-only code is better isolated from the static export
- Group by exact file instead of directory: a file-per-group list is as hard to scan as the flat ledger it replaces

## Assumptions

- Directory depth of three separates services, routes and components well enough for typical layouts; AREA_DEPTH is one constant to tune
- The ledger fits in one view payload, so client-side search over all decisions stays responsive
- The static export does not need browse or Why, since both are live-only
