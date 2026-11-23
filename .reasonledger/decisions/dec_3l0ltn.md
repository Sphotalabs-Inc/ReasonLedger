---
id: dec_3l0ltn
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
status: active
proposed_by: ai
approved_by: iharpreet
approved_at: '2026-11-11T03:51:27.721753Z'
justifies:
- packages/core/src/reasonledger_core/modules/placement.py::place_decisions
- packages/core/src/reasonledger_core/views/map_view.py::overview
- packages/core/src/reasonledger_core/views/map_view.py::module_page
- packages/core/src/reasonledger_core/views/map_view.py::_anchored_files
- packages/cli/src/reasonledger_cli/ui_map.py::handle_get_map
- packages/cli/src/reasonledger_cli/ui_assets/map.js:30-40
- packages/cli/src/reasonledger_cli/ui_assets/map_page.js:43-62
watchers: []
context: The spec asked for a module map UI where decisions attach to modules by their
  code anchors, with overlap shown and totals counting each decision once. How should
  membership be computed, where should the map live, and how should a tile show size
  and coverage, given that S35 AI share needs commit history that is not built yet?
choice: Membership is computed on each request from modules.yml, the decisions on
  disk and the labels, and nothing about it is stored. The map is a Map tab inside
  reasonledger ui, served by two read-only endpoints in their own handler module,
  and the live tab is left out of the static export. A decision belongs to every module
  or bucket its anchors fall in; a cross-cutting one (over four modules) is listed
  once apart and under foundations only; unplaced and superseded decisions are shown,
  labelled, and left out of counts and coverage. Tile size follows file count, square-root
  scaled into five steps. Coverage is the share of a module's files that a live decision's
  locus names, whether as a file, a line range or a symbol. AI share is left out until
  S35 can read commit trailers, so no stand-in number is shown. This implements dec_gtll6j.
alternatives_rejected:
- 'Store each decision''s modules in its frontmatter or an index file: it goes stale
  whenever modules.yml, a label or a file moves, and every re-map would have to rewrite
  decision records'
- 'Build the map as a separate page or a scan --html export first: the live tab reuses
  the session token, the Review tab''s cached conflicts and the same assets, and an
  export can follow once the live view settles'
- 'Size tiles linearly by file count or as a true treemap: one module of 223 files
  out of 1,765 would crowd every small module to a sliver, and a treemap needs a layout
  library the stdlib-only UI avoids'
- 'Count a file as covered only when a decision names a line range inside it: symbol
  and file anchors are the common form, so line-level coverage would read near zero
  for repos that anchor by symbol'
- 'Show an AI share from the decisions'' proposed_by field in the meantime: it measures
  who proposed decisions, not how much code AI touched, and the spec says to label
  the real metric a lower bound, so a stand-in would be a false number'
assumptions:
- Computing membership per request is cheap at ledger scale (tens to low thousands
  of decisions) because it is a glob match per locus; a very large ledger may need
  a cache like the ledger view has
- Decision anchors are file-granular enough that placing a decision by the file of
  each locus is a fair proxy for the modules it concerns
- Running it on Docmost with twelve demo decisions showed the overlap marking, cross-cutting
  group, buckets band and search working in a real browser, but a person has not yet
  judged whether the layout reads well on real decisions
- The map tab tolerates a repo whose modules.yml is proposed only; confirming modules
  is still a separate, unbuilt step
---

## Context

The spec asked for a module map UI where decisions attach to modules by their code anchors, with overlap shown and totals counting each decision once. How should membership be computed, where should the map live, and how should a tile show size and coverage, given that S35 AI share needs commit history that is not built yet?

## Choice

Membership is computed on each request from modules.yml, the decisions on disk and the labels, and nothing about it is stored. The map is a Map tab inside reasonledger ui, served by two read-only endpoints in their own handler module, and the live tab is left out of the static export. A decision belongs to every module or bucket its anchors fall in; a cross-cutting one (over four modules) is listed once apart and under foundations only; unplaced and superseded decisions are shown, labelled, and left out of counts and coverage. Tile size follows file count, square-root scaled into five steps. Coverage is the share of a module's files that a live decision's locus names, whether as a file, a line range or a symbol. AI share is left out until S35 can read commit trailers, so no stand-in number is shown. This implements dec_gtll6j.

## Alternatives rejected

- Store each decision's modules in its frontmatter or an index file: it goes stale whenever modules.yml, a label or a file moves, and every re-map would have to rewrite decision records
- Build the map as a separate page or a scan --html export first: the live tab reuses the session token, the Review tab's cached conflicts and the same assets, and an export can follow once the live view settles
- Size tiles linearly by file count or as a true treemap: one module of 223 files out of 1,765 would crowd every small module to a sliver, and a treemap needs a layout library the stdlib-only UI avoids
- Count a file as covered only when a decision names a line range inside it: symbol and file anchors are the common form, so line-level coverage would read near zero for repos that anchor by symbol
- Show an AI share from the decisions' proposed_by field in the meantime: it measures who proposed decisions, not how much code AI touched, and the spec says to label the real metric a lower bound, so a stand-in would be a false number

## Assumptions

- Computing membership per request is cheap at ledger scale (tens to low thousands of decisions) because it is a glob match per locus; a very large ledger may need a cache like the ledger view has
- Decision anchors are file-granular enough that placing a decision by the file of each locus is a fair proxy for the modules it concerns
- Running it on Docmost with twelve demo decisions showed the overlap marking, cross-cutting group, buckets band and search working in a real browser, but a person has not yet judged whether the layout reads well on real decisions
- The map tab tolerates a repo whose modules.yml is proposed only; confirming modules is still a separate, unbuilt step
