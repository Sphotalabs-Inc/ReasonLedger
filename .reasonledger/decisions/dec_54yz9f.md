---
id: dec_54yz9f
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
status: retired
proposed_by: ai
approved_by: iharpreet
approved_at: '2026-11-12T17:17:32.587317Z'
justifies:
- packages/cli/src/reasonledger_cli/ui_assets/needs.js::html
- packages/cli/src/reasonledger_cli/ui_assets/needs.js::pendingFirst
- packages/cli/src/reasonledger_cli/ui_assets/app.js::render
- packages/cli/src/reasonledger_cli/ui_assets/agent_card.js:1-38
- packages/cli/src/reasonledger_cli/ui_assets/needs.js:1-100
- packages/cli/src/reasonledger_cli/ui_assets/app.js:182-186
- packages/cli/src/reasonledger_cli/ui_assets/app.js:211-218
- packages/cli/src/reasonledger_cli/ui_assets/browse.js:191-196
- packages/cli/src/reasonledger_cli/ui_assets/browse.js:359-366
- packages/cli/src/reasonledger_cli/ui_html.py:119-143
- packages/cli/src/reasonledger_cli/ui_assets/browse.js::areaBrowserHtml
- packages/cli/src/reasonledger_cli/ui_html.py::STATIC_NAMES
watchers: []
context: The Review tab opened on a read-only decision lookup, the one decision waiting
  for approval sat eighth in the list under a notice that only said "below", the lookup's
  hint pointed at the topics command that the spec removes once the map exists, and
  Settings never mentioned the coding-agent route. dec_7vehg9 chose to mark and act
  in place, without a separate awaiting-review section, to avoid one record rendering
  twice with duplicate anchors. The owner asked for what needs a decision at the top,
  pending decisions first, and an agent option in Settings. How should the UI surface
  what needs a person, and where does the agent route belong?
choice: 'Add a Waiting on you card at the top of Review that lists pending decisions
  with Approve and proposals with Confirm and Reject as short rows that link to the
  full card, so no record gets a second anchor and Decisions keeps its count; sort
  pending decisions first in Decisions; say plainly when nothing is waiting. Replace
  the topics hint with a link to the Map tab. Add a static Use your coding agent card
  under Model settings holding the build-map, judge and record prompts, the MCP files
  init writes, and a note that import and catchup still need a provider; it is not
  a provider option. Move the static asset allowlist to ui_html.py and guard it against
  the assets folder. This narrows dec_7vehg9''s rejected alternative to the case it
  named: a second full card.'
alternatives_rejected:
- 'A separate Awaiting review section that renders the full decision cards, as dec_7vehg9
  rejected: the same record would have two anchors or leave Decisions, so the card
  shows short rows that link to the one card'
- 'Only sort pending decisions first and open the section: the first screen would
  still lead with the read-only lookup, which is what the owner found pointless'
- 'List Waiting on you at the top for conflicts too, with Dismiss: a dismissal needs
  a written reason and a person''s name, which a row cannot hold, so the card shows
  the count and links to Conflicts'
- 'Add the coding agent as a provider in the Settings dropdown: a provider is what
  ReasonLedger calls, the agent route covers only the map, judging and recording,
  and a dropdown entry would imply import and catchup work through it'
- 'Fetch the MCP wiring state for the agent card from /api/setup: that call scans
  docs and commit subjects on every load, and the checklist already reports it, so
  the card states what init writes instead'
- 'Remove the topics command, field and docs now: the spec says to, but it touches
  the owner''s manual and the record_decision interface, so it is a separate change
  that was not asked for'
- 'Add the two new asset names to the list in ui_cmd.py: that file was 420 lines against
  a 400 hard limit, so the allowlist moved to ui_html.py with a test that it matches
  the assets folder'
assumptions:
- The first screen should lead with what only a person can do, which is the owner's
  reading from trying the demo; one reviewer has said it, and a pending decision count
  of zero is the common state once approved
- Showing five rows per kind and linking the rest is enough, since agents record a
  few decisions at a time; a long backlog is reached through the Decisions link
- The card is live-only, as the static export has no way to approve; it reuses app.js
  handlers by being rendered inside the same root, which only holds while the card
  is built in app.js's render
- Rows show the decision's question clipped to 110 characters, which is a guess at
  what identifies it, and no person has used the card yet
- topics remains in the data, CLI and manual until a separate change removes it, so
  the filed-by-function grouping still renders when a repo has topics
retired_by: iharpreet
retired_at: '2026-11-13T05:24:35.436688Z'
retired_reason: Moved to Ask UI - UI change
---

## Context

The Review tab opened on a read-only decision lookup, the one decision waiting for approval sat eighth in the list under a notice that only said "below", the lookup's hint pointed at the topics command that the spec removes once the map exists, and Settings never mentioned the coding-agent route. dec_7vehg9 chose to mark and act in place, without a separate awaiting-review section, to avoid one record rendering twice with duplicate anchors. The owner asked for what needs a decision at the top, pending decisions first, and an agent option in Settings. How should the UI surface what needs a person, and where does the agent route belong?

## Choice

Add a Waiting on you card at the top of Review that lists pending decisions with Approve and proposals with Confirm and Reject as short rows that link to the full card, so no record gets a second anchor and Decisions keeps its count; sort pending decisions first in Decisions; say plainly when nothing is waiting. Replace the topics hint with a link to the Map tab. Add a static Use your coding agent card under Model settings holding the build-map, judge and record prompts, the MCP files init writes, and a note that import and catchup still need a provider; it is not a provider option. Move the static asset allowlist to ui_html.py and guard it against the assets folder. This narrows dec_7vehg9's rejected alternative to the case it named: a second full card.

## Alternatives rejected

- A separate Awaiting review section that renders the full decision cards, as dec_7vehg9 rejected: the same record would have two anchors or leave Decisions, so the card shows short rows that link to the one card
- Only sort pending decisions first and open the section: the first screen would still lead with the read-only lookup, which is what the owner found pointless
- List Waiting on you at the top for conflicts too, with Dismiss: a dismissal needs a written reason and a person's name, which a row cannot hold, so the card shows the count and links to Conflicts
- Add the coding agent as a provider in the Settings dropdown: a provider is what ReasonLedger calls, the agent route covers only the map, judging and recording, and a dropdown entry would imply import and catchup work through it
- Fetch the MCP wiring state for the agent card from /api/setup: that call scans docs and commit subjects on every load, and the checklist already reports it, so the card states what init writes instead
- Remove the topics command, field and docs now: the spec says to, but it touches the owner's manual and the record_decision interface, so it is a separate change that was not asked for
- Add the two new asset names to the list in ui_cmd.py: that file was 420 lines against a 400 hard limit, so the allowlist moved to ui_html.py with a test that it matches the assets folder

## Assumptions

- The first screen should lead with what only a person can do, which is the owner's reading from trying the demo; one reviewer has said it, and a pending decision count of zero is the common state once approved
- Showing five rows per kind and linking the rest is enough, since agents record a few decisions at a time; a long backlog is reached through the Decisions link
- The card is live-only, as the static export has no way to approve; it reuses app.js handlers by being rendered inside the same root, which only holds while the card is built in app.js's render
- Rows show the decision's question clipped to 110 characters, which is a guess at what identifies it, and no person has used the card yet
- topics remains in the data, CLI and manual until a separate change removes it, so the filed-by-function grouping still renders when a repo has topics
