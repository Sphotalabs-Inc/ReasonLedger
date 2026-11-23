---
id: dec_7uht0r
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-13T20:53:13.699230Z'
justifies:
- packages/core/src/reasonledger_core/reasoning/why_nearby.py::find_nearby
- packages/core/src/reasonledger_core/reasoning/why.py::why_payload
- packages/cli/src/reasonledger_cli/why_render.py::render_miss
- packages/cli/src/reasonledger_cli/ui_assets/browse.js::whyMissHtml
watchers: []
context: '`why` at a line with no anchor said "no decision justifies this line yet"
  even when the file held an approved decision at other lines (spec 16 F4). How should
  a miss be reported, and how does `--json` carry it without breaking existing consumers?'
choice: Core find_nearby lists the file's anchors (in-force, nearest the asked line
  first, capped at 5; retired/superseded counted), shared by the CLI text, the UI
  and `--json`. why_payload gains one additive `nearby` key that lists in-force entries
  then out-of-force ones with a status; the match metric records `near`, allow-listed
  apart from `miss`. A nonexistent path keeps the old miss message, extended to say
  there is no such file.
alternatives_rejected:
- 'Compute nearby separately in the CLI and the UI: two implementations of the trust
  fix would drift, the reason why_payload is shared'
- 'Add a retired-count key to --json: spec allows only `nearby`, so out-of-force entries
  ride in the same list with their status'
- 'Record near misses as `miss`: the pilot would not be able to tell an uncovered
  file from a wrong line'
- 'Make a near miss exit non-zero: exit codes must not change'
assumptions: []
---

## Context

`why` at a line with no anchor said "no decision justifies this line yet" even when the file held an approved decision at other lines (spec 16 F4). How should a miss be reported, and how does `--json` carry it without breaking existing consumers?

## Choice

Core find_nearby lists the file's anchors (in-force, nearest the asked line first, capped at 5; retired/superseded counted), shared by the CLI text, the UI and `--json`. why_payload gains one additive `nearby` key that lists in-force entries then out-of-force ones with a status; the match metric records `near`, allow-listed apart from `miss`. A nonexistent path keeps the old miss message, extended to say there is no such file.

## Alternatives rejected

- Compute nearby separately in the CLI and the UI: two implementations of the trust fix would drift, the reason why_payload is shared
- Add a retired-count key to --json: spec allows only `nearby`, so out-of-force entries ride in the same list with their status
- Record near misses as `miss`: the pilot would not be able to tell an uncovered file from a wrong line
- Make a near miss exit non-zero: exit codes must not change
