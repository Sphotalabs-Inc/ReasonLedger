---
id: dec_g2ib1g
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-13T05:04:02.104314Z'
justifies:
- packages/core/src/reasonledger_core/reasoning/anchors.py::locus_problem
- packages/core/src/reasonledger_core/reasoning/symbols.py::declared_names
- packages/core/src/reasonledger_core/reasoning/ts_symbols.py::declared_ts_names
watchers: []
context: The first fix for false missing_symbol orphans searched raw file text with
  a regex for a line-start definition. That counts a commented-out or quoted definition
  as present and duplicates parsing the code already does when it masks comments and
  strings. How should locus_problem decide a symbol still exists when the span extractors
  skip nested functions and constants?
choice: 'Add a separate declared_names function that answers only whether a name exists
  at any depth: TS/JS reuse the masking and declaration patterns without the top-level
  filter, Python walks the AST for functions, classes and assignments. locus_problem
  tries the span extractor, then declared_names on the last name segment, and returns
  None (not flagged) when declared_names is unsure. The span extractors that rl why
  uses are unchanged.'
alternatives_rejected:
- 'Keep the raw-text regex fallback: simple, but a commented-out or quoted definition
  counts as present and it re-implements what masking already solves'
- 'Make the span extractor descend into wrappers: risks wrong spans in rl why, which
  is deliberately conservative'
- 'Flag a locus as missing when the file cannot be parsed: unsure would read as gone
  and bring false orphans back'
assumptions:
- Class methods are covered by the span extractor, and declared_names does not look
  for methods or object-literal members
- An unparseable file is rare enough that not flagging it is the safer default
supersedes: dec_n7gqu6
---

## Context

The first fix for false missing_symbol orphans searched raw file text with a regex for a line-start definition. That counts a commented-out or quoted definition as present and duplicates parsing the code already does when it masks comments and strings. How should locus_problem decide a symbol still exists when the span extractors skip nested functions and constants?

## Choice

Add a separate declared_names function that answers only whether a name exists at any depth: TS/JS reuse the masking and declaration patterns without the top-level filter, Python walks the AST for functions, classes and assignments. locus_problem tries the span extractor, then declared_names on the last name segment, and returns None (not flagged) when declared_names is unsure. The span extractors that rl why uses are unchanged.

## Alternatives rejected

- Keep the raw-text regex fallback: simple, but a commented-out or quoted definition counts as present and it re-implements what masking already solves
- Make the span extractor descend into wrappers: risks wrong spans in rl why, which is deliberately conservative
- Flag a locus as missing when the file cannot be parsed: unsure would read as gone and bring false orphans back

## Assumptions

- Class methods are covered by the span extractor, and declared_names does not look for methods or object-literal members
- An unparseable file is rare enough that not flagging it is the safer default
