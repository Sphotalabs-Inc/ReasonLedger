---
id: dec_28c3xi
ai_tool: claude-code
model: claude-fable-5-2
oversight: reviewed
status: retired
proposed_by: human
approved_by: iharpreet
approved_at: '2026-11-12T17:15:51.574045Z'
recorded_at: '2026-11-12T16:29:54.930390Z'
justifies:
- packages/cli/src/reasonledger_cli/ui_assets/app.js:53-196
- packages/cli/src/reasonledger_cli/ui_assets/overview.js:12-82
- packages/cli/src/reasonledger_cli/ui_assets/ask.js:11-122
- packages/cli/src/reasonledger_cli/ui_assets/ledger_list.js:61-211
- packages/cli/src/reasonledger_cli/ui_assets/review.js:56-69
- packages/cli/src/reasonledger_cli/ui_assets/conflict_config.js:27-34
- packages/cli/src/reasonledger_cli/ui_assets/setup.js:88-102
- packages/cli/src/reasonledger_cli/ui_assets/setup.js:147-258
anchor_hashes:
  packages/cli/src/reasonledger_cli/ui_assets/app.js:53-196: sha256:7df55ed2e56c85f2
  packages/cli/src/reasonledger_cli/ui_assets/overview.js:12-82: sha256:c2bd144e83870b0b
  packages/cli/src/reasonledger_cli/ui_assets/ask.js:11-122: sha256:f67618b8ecec4ccb
  packages/cli/src/reasonledger_cli/ui_assets/ledger_list.js:61-211: sha256:92c415e53ac1582e
  packages/cli/src/reasonledger_cli/ui_assets/review.js:56-69: sha256:7e07387f07fd0e92
  packages/cli/src/reasonledger_cli/ui_assets/conflict_config.js:27-34: sha256:542401c9a28c3989
  packages/cli/src/reasonledger_cli/ui_assets/setup.js:88-102: sha256:ae99aaa7cfe96101
  packages/cli/src/reasonledger_cli/ui_assets/setup.js:147-258: sha256:630287b6fbe4f318
watchers: []
context: 'The local UI put four jobs on one Review page: charts, a queue of what waits
  on a person, lookup, and the whole ledger as chips plus six sections. A first-time-user
  walk measured it at about 20,400px on this repo, and a first pass (dec_c9m1zt) shortened
  the page but kept all four jobs on it, with lookup above the charts. The owner then
  asked for lookup as its own tab, the pie charts on top, and a rethink of the structure.
  How should the UI be divided into tabs, where does each list of records live, and
  how does a link to a record find it once records are spread over tabs?'
choice: 'Five tabs with one job each: Overview, Review, Ask, Map, Settings; the app
  opens on Overview. Overview leads with the stats strip, then one line counting what
  waits on a person with a button to Review, a Why box that hands its question to
  Ask, links to the non-empty side lists, and the Getting started checklist; with
  an empty ledger it shows the checklist alone. Review is only the queue: pending
  decisions as one-line rows that open to the card, proposals, and judged conflicts,
  with the count on the tab. Ask holds Find and Why, and one Show select replaces
  the count chips and sections: all decisions, needs review, history, and the side
  lists that hold something (orphaned, stale and watchers, related pairs). Retire
  is offered on an Ask hit, since settled decisions are listed nowhere else. A decision
  card has an anchor only while it is in the Review queue; a link to any other decision
  searches Ask for its id. Organize stops being a tab and becomes the Map tab''s Edit
  map mode, and related-decision tuning sits under an Advanced fold in Settings. Tab
  links, the map mode switch and every data-action button are handled by delegated
  listeners in app.js, so a list can be drawn in any pane. The static export is unchanged.'
alternatives_rejected:
- 'Keep one Review page and only reorder it with the charts first: the page would
  still carry four jobs, and the owner asked for lookup as its own tab'
- 'Charts on top of the Review queue instead of a separate Overview: a person who
  opens Review to approve things would scroll past charts every time, and the charts
  say nothing on an empty ledger'
- 'Keep the full Decisions list as a third list beside the queue and the search: it
  was the 17,000px duplicate that the walk-through found'
- 'Keep an anchor for every decision by rendering hidden cards in Ask: the search
  already leads with a decision when asked for its id, so a second rendering would
  exist only to be a link target'
- 'Keep Organize as a top-level tab: it is the editing surface for the Map, and on
  an empty map both tabs showed the same card'
- 'Move orphaned, stale and related pairs onto Overview as sections: they need no
  action from most people and would push the charts and the call to action down'
- 'Regroup the status names (proposed, confirmed, active and so on) in the same change:
  the legend and badges are unchanged here, and renaming states touches the export
  and the CLI output too'
assumptions:
- A returning person wants the state of the ledger first and the queue one click away;
  the count on the Review tab keeps the queue visible from every tab
- Proposals and judged conflicts are few enough to list in full in the queue; a large
  import would make Review long and is left for a later change
- Searching Ask by id is an acceptable landing for a link to a settled decision, as
  it already leads with the exact match
- Orphaned, stale and related lists are consulted occasionally, so one select away
  is enough
supersedes: dec_c9m1zt
retired_by: iharpreet
retired_at: '2026-11-13T03:52:25.573384Z'
retired_reason: updated ui
---

## Context

The local UI put four jobs on one Review page: charts, a queue of what waits on a person, lookup, and the whole ledger as chips plus six sections. A first-time-user walk measured it at about 20,400px on this repo, and a first pass (dec_c9m1zt) shortened the page but kept all four jobs on it, with lookup above the charts. The owner then asked for lookup as its own tab, the pie charts on top, and a rethink of the structure. How should the UI be divided into tabs, where does each list of records live, and how does a link to a record find it once records are spread over tabs?

## Choice

Five tabs with one job each: Overview, Review, Ask, Map, Settings; the app opens on Overview. Overview leads with the stats strip, then one line counting what waits on a person with a button to Review, a Why box that hands its question to Ask, links to the non-empty side lists, and the Getting started checklist; with an empty ledger it shows the checklist alone. Review is only the queue: pending decisions as one-line rows that open to the card, proposals, and judged conflicts, with the count on the tab. Ask holds Find and Why, and one Show select replaces the count chips and sections: all decisions, needs review, history, and the side lists that hold something (orphaned, stale and watchers, related pairs). Retire is offered on an Ask hit, since settled decisions are listed nowhere else. A decision card has an anchor only while it is in the Review queue; a link to any other decision searches Ask for its id. Organize stops being a tab and becomes the Map tab's Edit map mode, and related-decision tuning sits under an Advanced fold in Settings. Tab links, the map mode switch and every data-action button are handled by delegated listeners in app.js, so a list can be drawn in any pane. The static export is unchanged.

## Alternatives rejected

- Keep one Review page and only reorder it with the charts first: the page would still carry four jobs, and the owner asked for lookup as its own tab
- Charts on top of the Review queue instead of a separate Overview: a person who opens Review to approve things would scroll past charts every time, and the charts say nothing on an empty ledger
- Keep the full Decisions list as a third list beside the queue and the search: it was the 17,000px duplicate that the walk-through found
- Keep an anchor for every decision by rendering hidden cards in Ask: the search already leads with a decision when asked for its id, so a second rendering would exist only to be a link target
- Keep Organize as a top-level tab: it is the editing surface for the Map, and on an empty map both tabs showed the same card
- Move orphaned, stale and related pairs onto Overview as sections: they need no action from most people and would push the charts and the call to action down
- Regroup the status names (proposed, confirmed, active and so on) in the same change: the legend and badges are unchanged here, and renaming states touches the export and the CLI output too

## Assumptions

- A returning person wants the state of the ledger first and the queue one click away; the count on the Review tab keeps the queue visible from every tab
- Proposals and judged conflicts are few enough to list in full in the queue; a large import would make Review long and is left for a later change
- Searching Ask by id is an acceptable landing for a link to a settled decision, as it already leads with the exact match
- Orphaned, stale and related lists are consulted occasionally, so one select away is enough
