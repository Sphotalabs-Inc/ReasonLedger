---
id: dec_0tao1p
ai_tool: claude-code
model: claude-fable-5-2
oversight: reviewed
status: superseded
proposed_by: ai
approved_by: iharpreet
approved_at: '2026-11-11T03:47:11.268273Z'
recorded_at: '2026-11-10T18:43:40.741569Z'
justifies:
- packages/core/src/reasonledger_core/views/stats.py::build_stats
- packages/core/src/reasonledger_core/views/stats.py::LedgerStats
- packages/cli/src/reasonledger_cli/stats_cmd.py::run_stats
- packages/cli/src/reasonledger_cli/ui_stats.py::handle_get_stats
- packages/cli/src/reasonledger_cli/ui_assets/stats.js::pie
- packages/cli/src/reasonledger_cli/ui_assets/stats.js::modulesPanel
watchers: []
context: The owner asked for charts in the review UI (decision type, status, per month)
  and accepted a narrower summary strip plus a matching status flag. The ledger view
  already carried a few of the needed counts and the map view carried per-module tiles.
  Where should the figures behind the strip be computed and served so the browser
  and the command line cannot disagree, and which figures are honest to draw from
  the records as they are?
choice: 'One framework-free function, build_stats, derives a LedgerStats object from
  the two views that already exist (the ledger view''s decision summaries and the
  map overview) and reads no file itself. It counts decisions in force only: judged
  against pending, who proposed, and per feature or foundation module the decisions,
  pending count and coverage, ranked by decisions, with buckets left out. status --stats
  prints it (JSON with --json) and a new read-only GET /api/stats serves the same
  object to a live-only strip that tallies nothing in the browser. The strip draws
  inline SVG: the two part-of-whole breakdowns as pie charts, which the owner asked
  for after seeing stacked bars, and the modules as bars because their counts overlap
  and do not sum to a whole. The strip is left out of the static export. No type,
  status or per-month chart is drawn, because records carry no type field, almost
  all are active, and most have no date.'
alternatives_rejected:
- 'Compute the breakdown in the browser from the /api/view payload the page already
  has: no new endpoint, but the tally would exist twice (JS and the CLI) and could
  drift, and the charter keeps domain logic in core'
- 'Add a stats field to LedgerView so the static export gets the strip too: the per-module
  figures need the module map, which the ledger view does not load, and every status
  --json consumer would pay for and receive it'
- 'A separate Stats tab with status, model and monthly charts as first asked: on this
  ledger a status chart is one solid bar and a monthly chart would rest on git-derived
  dates for a minority of records, which is decoration in an evidence product'
- 'A charting library: the local UI ships as static assets with no Node runtime and
  no external requests'
- 'A pie for the module panel too: a decision anchored in two modules counts in both,
  so the slices would not be shares of one total'
assumptions:
- The module map overview stays cheap enough to build when the Review tab loads; the
  strip fetches after the page renders so a slow map does not block it
- Pending in the strip must equal the pending_approval count status already reports;
  a test pins this
- A chart over time becomes worth adding once every record carries recorded_at
superseded_by: dec_54yz9f
superseded_decided_by: iharpreet
superseded_at: '2026-11-12T18:49:29.961095Z'
superseded_reason: Newer more user friendly view.
---

## Context

The owner asked for charts in the review UI (decision type, status, per month) and accepted a narrower summary strip plus a matching status flag. The ledger view already carried a few of the needed counts and the map view carried per-module tiles. Where should the figures behind the strip be computed and served so the browser and the command line cannot disagree, and which figures are honest to draw from the records as they are?

## Choice

One framework-free function, build_stats, derives a LedgerStats object from the two views that already exist (the ledger view's decision summaries and the map overview) and reads no file itself. It counts decisions in force only: judged against pending, who proposed, and per feature or foundation module the decisions, pending count and coverage, ranked by decisions, with buckets left out. status --stats prints it (JSON with --json) and a new read-only GET /api/stats serves the same object to a live-only strip that tallies nothing in the browser. The strip draws inline SVG: the two part-of-whole breakdowns as pie charts, which the owner asked for after seeing stacked bars, and the modules as bars because their counts overlap and do not sum to a whole. The strip is left out of the static export. No type, status or per-month chart is drawn, because records carry no type field, almost all are active, and most have no date.

## Alternatives rejected

- Compute the breakdown in the browser from the /api/view payload the page already has: no new endpoint, but the tally would exist twice (JS and the CLI) and could drift, and the charter keeps domain logic in core
- Add a stats field to LedgerView so the static export gets the strip too: the per-module figures need the module map, which the ledger view does not load, and every status --json consumer would pay for and receive it
- A separate Stats tab with status, model and monthly charts as first asked: on this ledger a status chart is one solid bar and a monthly chart would rest on git-derived dates for a minority of records, which is decoration in an evidence product
- A charting library: the local UI ships as static assets with no Node runtime and no external requests
- A pie for the module panel too: a decision anchored in two modules counts in both, so the slices would not be shares of one total

## Assumptions

- The module map overview stays cheap enough to build when the Review tab loads; the strip fetches after the page renders so a slow map does not block it
- Pending in the strip must equal the pending_approval count status already reports; a test pins this
- A chart over time becomes worth adding once every record carries recorded_at
