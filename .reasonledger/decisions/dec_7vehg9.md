---
id: dec_7vehg9
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
justifies:
- packages/cli/src/reasonledger_cli/ui_approve.py::handle_approve
- packages/cli/src/reasonledger_cli/ui_cmd.py:207-217
- packages/cli/src/reasonledger_cli/ui_assets/app.js:86-93
- packages/cli/src/reasonledger_cli/ui_assets/app.js:371-379
- packages/cli/src/reasonledger_cli/ui_assets/render.js:146-149
watchers: []
confidence: high
context: 'An agent-recorded decision is saved as active with oversight pending, but
  the local UI never showed that state and offered no way to clear it: Decisions rendered
  only the status badge, the pending_approval count had no chip, and approval was
  CLI-only. A reviewer who opened the UI looking for agent decisions found an empty
  Proposals section and concluded they had not been captured. How should the UI surface
  pending decisions and let a person approve them?'
choice: Mark and act in place. Pending decisions stay in the Decisions section with
  a pending-review badge and an Approve button; a pending-review count chip links
  there and the section opens on arrival when any are pending. Approve posts to a
  new /api/decisions/<id>/approve handler in its own module, which calls the same
  approve_decision the CLI uses and only ever grants reviewed. The legend now says
  agent-recorded decisions live under Decisions, never Proposals.
alternatives_rejected:
- 'A separate Awaiting review section listing pending decisions: the same record would
  render in two sections with duplicate item anchors, or be hidden from Decisions
  and break the active count'
- 'Offer all three verdicts (reviewed, modified, rejected) in the UI: modified and
  rejected change what the ledger asserts, and a rejected verdict on a record that
  stays active has no agreed meaning yet, so they stay CLI-only'
- 'Reuse the proposals confirm endpoint for pending decisions: confirm moves a file
  from staging and sets confirmed_by, a different transition from approve_decision,
  and sharing a route would blur the two'
- 'Add the handler inline in ui_cmd.py: it was 368 lines against a 400 hard limit,
  and ui_config.py and conflict_config_ui.py already set the pattern of a handler
  module per endpoint family'
assumptions:
- The local UI is a human-only surface behind a per-session token and Origin check,
  so a click there is a person's verdict, as confirm already assumes
- approve_decision refuses to rewrite any existing verdict, so a double click or a
  stale tab cannot overwrite one
- app.js was already 424 lines before this change, past the 400-line hard limit, and
  now sits at 460; splitting it is a separate refactor
---

## Context

An agent-recorded decision is saved as active with oversight pending, but the local UI never showed that state and offered no way to clear it: Decisions rendered only the status badge, the pending_approval count had no chip, and approval was CLI-only. A reviewer who opened the UI looking for agent decisions found an empty Proposals section and concluded they had not been captured. How should the UI surface pending decisions and let a person approve them?

## Choice

Mark and act in place. Pending decisions stay in the Decisions section with a pending-review badge and an Approve button; a pending-review count chip links there and the section opens on arrival when any are pending. Approve posts to a new /api/decisions/<id>/approve handler in its own module, which calls the same approve_decision the CLI uses and only ever grants reviewed. The legend now says agent-recorded decisions live under Decisions, never Proposals.

## Alternatives rejected

- A separate Awaiting review section listing pending decisions: the same record would render in two sections with duplicate item anchors, or be hidden from Decisions and break the active count
- Offer all three verdicts (reviewed, modified, rejected) in the UI: modified and rejected change what the ledger asserts, and a rejected verdict on a record that stays active has no agreed meaning yet, so they stay CLI-only
- Reuse the proposals confirm endpoint for pending decisions: confirm moves a file from staging and sets confirmed_by, a different transition from approve_decision, and sharing a route would blur the two
- Add the handler inline in ui_cmd.py: it was 368 lines against a 400 hard limit, and ui_config.py and conflict_config_ui.py already set the pattern of a handler module per endpoint family

## Assumptions

- The local UI is a human-only surface behind a per-session token and Origin check, so a click there is a person's verdict, as confirm already assumes
- approve_decision refuses to rewrite any existing verdict, so a double click or a stale tab cannot overwrite one
- app.js was already 424 lines before this change, past the 400-line hard limit, and now sits at 460; splitting it is a separate refactor
