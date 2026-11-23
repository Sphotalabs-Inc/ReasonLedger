---
id: dec_c9m1zt
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: superseded
proposed_by: ai
recorded_at: '2026-11-12T05:51:19.424221Z'
justifies:
- packages/cli/src/reasonledger_cli/ui_assets/app.js:52-63
- packages/cli/src/reasonledger_cli/ui_assets/app.js:115-154
- packages/cli/src/reasonledger_cli/ui_assets/ledger_list.js:61-183
- packages/cli/src/reasonledger_cli/ui_assets/setup.js:88-102
- packages/cli/src/reasonledger_cli/ui_assets/setup.js:147-258
- packages/cli/src/reasonledger_cli/ui_assets/render.js:79-103
- packages/cli/src/reasonledger_cli/ui_assets/render.js:328-355
watchers: []
context: A walk through the live UI as a first-time user found the Review tab on this
  repo ran to about 20,400px (39 decision cards fully open, the same records also
  listed in Waiting on you and in Find a decision), led with an optional amber notice
  about unjudged pairs, and showed twelve count chips of which six read zero. On an
  empty repo the checklist was followed by an empty search, twelve zero chips and
  six empty sections, and its first two steps were the same command. What should Review
  show when the ledger is empty, and how much of the ledger should it lay out by default
  once it is not?
choice: 'Two layouts chosen from the view. With no decisions and no proposals, Review
  renders only the Getting started checklist plus who is acting and Refresh; search,
  stats, chips, sections and the legend are left out, the setup and connect steps
  merge into one when neither is done, and the map step leads with the local quick
  map and folds the two model routes under a disclosure. Otherwise the order is Waiting
  on you, the checklist (collapsed once any record exists), lookup, stats, then the
  ledger: only non-zero chips, the Decisions section closed on arrival, and each decision
  a one-line details row (id, badges, clipped context, Review button if pending) that
  opens to the same card in place. The card inside the row still carries the record''s
  single anchor, and one delegated click handler opens every details element around
  a link''s target. The unjudged-pairs notice moves into the Related decisions section;
  the degraded-embedder warning stays at the top. This diverges from dec_7vehg9 on
  two points only (Decisions no longer opens on arrival when something is pending,
  and records are rows rather than open cards) and keeps dec_54yz9f''s rows-link-to-card
  and pending-first rules and dec_be0usd''s verdict-only-in-the-dialog rule, so neither
  record is superseded. The static export is unchanged. The list code moved from app.js
  to ledger_list.js and the consent panel from setup.js to consent.js to stay under
  the file limit.'
alternatives_rejected:
- 'Hide the empty-state clutter with a CSS class on the layout: the search and stats
  would still mount and call their endpoints for nothing, and the legend sits outside
  the layout'
- 'Rows that open the review dialog instead of expanding in place: the dialog is where
  a verdict is given, and reading a settled decision should not look like being asked
  for one; it would also leave no element to carry the anchor that item links target'
- 'Paginate or cap the Decisions list: links to a record beyond the cap would have
  no target, and one line per record is already short enough at this ledger size'
- 'Drop the full Decisions list from Review and rely on search and the Map: retire
  has no other entry point, and item links from conflicts, orphans and Waiting on
  you need a target on the page'
- 'Supersede dec_7vehg9: most of it (approve handler, pending badge, chip, legend
  wording) still holds, and superseding would mark all of that as out of force'
- 'Give the collapsed row its own id and strip the card''s: the review dialog and
  the export render the same card through decisionItem, so the id belongs on the shared
  element'
- 'Move lookup to its own tab and regroup the status vocabulary in the same change:
  both were proposed but not accepted for this slice'
assumptions:
- 'A ledger with a proposal but no decision is not first-run: something is already
  waiting on a person'
- Waiting on you is always rendered above the fold when anything is pending, so a
  closed Decisions section cannot hide an unreviewed record
- Ledgers stay small enough (tens to low hundreds of records) that one line per decision
  needs no paging
- Proposals keep full open cards for now; a large import would lengthen the page again
  and is left for a later change
---

## Context

A walk through the live UI as a first-time user found the Review tab on this repo ran to about 20,400px (39 decision cards fully open, the same records also listed in Waiting on you and in Find a decision), led with an optional amber notice about unjudged pairs, and showed twelve count chips of which six read zero. On an empty repo the checklist was followed by an empty search, twelve zero chips and six empty sections, and its first two steps were the same command. What should Review show when the ledger is empty, and how much of the ledger should it lay out by default once it is not?

## Choice

Two layouts chosen from the view. With no decisions and no proposals, Review renders only the Getting started checklist plus who is acting and Refresh; search, stats, chips, sections and the legend are left out, the setup and connect steps merge into one when neither is done, and the map step leads with the local quick map and folds the two model routes under a disclosure. Otherwise the order is Waiting on you, the checklist (collapsed once any record exists), lookup, stats, then the ledger: only non-zero chips, the Decisions section closed on arrival, and each decision a one-line details row (id, badges, clipped context, Review button if pending) that opens to the same card in place. The card inside the row still carries the record's single anchor, and one delegated click handler opens every details element around a link's target. The unjudged-pairs notice moves into the Related decisions section; the degraded-embedder warning stays at the top. This diverges from dec_7vehg9 on two points only (Decisions no longer opens on arrival when something is pending, and records are rows rather than open cards) and keeps dec_54yz9f's rows-link-to-card and pending-first rules and dec_be0usd's verdict-only-in-the-dialog rule, so neither record is superseded. The static export is unchanged. The list code moved from app.js to ledger_list.js and the consent panel from setup.js to consent.js to stay under the file limit.

## Alternatives rejected

- Hide the empty-state clutter with a CSS class on the layout: the search and stats would still mount and call their endpoints for nothing, and the legend sits outside the layout
- Rows that open the review dialog instead of expanding in place: the dialog is where a verdict is given, and reading a settled decision should not look like being asked for one; it would also leave no element to carry the anchor that item links target
- Paginate or cap the Decisions list: links to a record beyond the cap would have no target, and one line per record is already short enough at this ledger size
- Drop the full Decisions list from Review and rely on search and the Map: retire has no other entry point, and item links from conflicts, orphans and Waiting on you need a target on the page
- Supersede dec_7vehg9: most of it (approve handler, pending badge, chip, legend wording) still holds, and superseding would mark all of that as out of force
- Give the collapsed row its own id and strip the card's: the review dialog and the export render the same card through decisionItem, so the id belongs on the shared element
- Move lookup to its own tab and regroup the status vocabulary in the same change: both were proposed but not accepted for this slice

## Assumptions

- A ledger with a proposal but no decision is not first-run: something is already waiting on a person
- Waiting on you is always rendered above the fold when anything is pending, so a closed Decisions section cannot hide an unreviewed record
- Ledgers stay small enough (tens to low hundreds of records) that one line per decision needs no paging
- Proposals keep full open cards for now; a large import would lengthen the page again and is left for a later change
