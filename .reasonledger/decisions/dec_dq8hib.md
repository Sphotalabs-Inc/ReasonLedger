---
id: dec_dq8hib
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
status: active
proposed_by: ai
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/metrics.py::emit_once_many
- packages/core/src/reasonledger_core/metrics.py::emit_once
- packages/core/src/reasonledger_core/metrics.py::_append
- packages/core/src/reasonledger_core/views/related_view.py::project_related
watchers: []
confidence: high
context: With metrics on, building a ledger view re-read and re-parsed the whole metrics
  log once per surfaced conflict pair, so a build was quadratic in its own output
  (10-13s for 500 decisions against a 2s budget). How should the already-emitted check
  avoid the repeated scans without changing what is logged?
choice: Add emit_once_many, which scans the log once for already-emitted pairs, tracks
  the pairs it adds during the batch, and appends all new lines in a single write;
  emit_once becomes a one-entry call into it and project_related passes every surfaced
  pair in one call. The log stays the authority on what was emitted, and an empty
  batch skips the scan entirely.
alternatives_rejected:
- 'A module-level in-process cache of emitted pairs keyed by root: goes stale when
  the CLI and the editor-spawned MCP server write the same log from different processes,
  which re-emits pairs and inflates the surfaced count the dismissal rate is divided
  by'
- 'Cache load_metrics results by file mtime and size: still re-parses after every
  append inside a build, and a coarse mtime can hide a write from another process'
- 'Drop dedup from the view build and dedupe when reading metrics: changes what is
  written to the log and moves the cost to every status --metrics read'
- 'Keep a separate small index file of surfaced pairs: a second source of truth that
  can drift from the log, and a lost index re-emits pairs and inflates the dismissal-rate
  denominator'
- 'Pass a pre-loaded seen set as an optional parameter of emit_once: leaks the dedup
  bookkeeping into every caller and keeps one file open per emitted line'
assumptions:
- Pair keys are generated decision ids, so a pair that fails the shape check never
  reaches the log and deduping it within a batch is harmless
- A batch fits comfortably in memory and a single append write is as safe against
  concurrent writers as the per-line appends it replaces
- emit_once has no caller besides the view projection, so changing its internals needs
  no migration
- The remaining scan is linear in log size (about 0.15s at 50,000 lines), which is
  acceptable at current event rates; a tail-read cache is the next step if it stops
  being so
---

## Context

With metrics on, building a ledger view re-read and re-parsed the whole metrics log once per surfaced conflict pair, so a build was quadratic in its own output (10-13s for 500 decisions against a 2s budget). How should the already-emitted check avoid the repeated scans without changing what is logged?

## Choice

Add emit_once_many, which scans the log once for already-emitted pairs, tracks the pairs it adds during the batch, and appends all new lines in a single write; emit_once becomes a one-entry call into it and project_related passes every surfaced pair in one call. The log stays the authority on what was emitted, and an empty batch skips the scan entirely.

## Alternatives rejected

- A module-level in-process cache of emitted pairs keyed by root: goes stale when the CLI and the editor-spawned MCP server write the same log from different processes, which re-emits pairs and inflates the surfaced count the dismissal rate is divided by
- Cache load_metrics results by file mtime and size: still re-parses after every append inside a build, and a coarse mtime can hide a write from another process
- Drop dedup from the view build and dedupe when reading metrics: changes what is written to the log and moves the cost to every status --metrics read
- Keep a separate small index file of surfaced pairs: a second source of truth that can drift from the log, and a lost index re-emits pairs and inflates the dismissal-rate denominator
- Pass a pre-loaded seen set as an optional parameter of emit_once: leaks the dedup bookkeeping into every caller and keeps one file open per emitted line

## Assumptions

- Pair keys are generated decision ids, so a pair that fails the shape check never reaches the log and deduping it within a batch is harmless
- A batch fits comfortably in memory and a single append write is as safe against concurrent writers as the per-line appends it replaces
- emit_once has no caller besides the view projection, so changing its internals needs no migration
- The remaining scan is linear in log size (about 0.15s at 50,000 lines), which is acceptable at current event rates; a tail-read cache is the next step if it stops being so
