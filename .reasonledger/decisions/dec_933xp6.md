---
id: dec_933xp6
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-13T20:49:49.642187Z'
justifies:
- packages/core/src/reasonledger_core/importer/scan.py::strip_rule_blocks
- packages/core/src/reasonledger_core/importer/scan.py::count_scannable_docs
- packages/core/src/reasonledger_core/importer/scan.py::scan_docs
watchers: []
context: init's own rule files (CLAUDE.md, AGENTS.md, copilot instructions) are markdown,
  so the doc scan counted and extracted them as decision candidates, showing 3 candidates
  in an empty repo. How does a scan tell rule-only files from real prose without opening
  every markdown file?
choice: The reasonledger:begin/end block is stripped from text before extraction (scan_docs),
  and a file with nothing left is dropped. count_scannable_docs opens only files at
  or under RULE_ONLY_MAX_BYTES (4096); larger files cannot be rule-only and are counted
  by name. A test pins the rule under that size.
alternatives_rejected:
- 'Exclude files by name (CLAUDE.md, AGENTS.md): hides real prose a team keeps in
  those files, which is where decisions often live'
- 'Read every markdown file to count: slow on large repos for one integer, which the
  count was designed to avoid'
- 'Make init scan before writing only: fixes the first run but /api/setup and import
  would still re-read the rule block'
assumptions: []
---

## Context

init's own rule files (CLAUDE.md, AGENTS.md, copilot instructions) are markdown, so the doc scan counted and extracted them as decision candidates, showing 3 candidates in an empty repo. How does a scan tell rule-only files from real prose without opening every markdown file?

## Choice

The reasonledger:begin/end block is stripped from text before extraction (scan_docs), and a file with nothing left is dropped. count_scannable_docs opens only files at or under RULE_ONLY_MAX_BYTES (4096); larger files cannot be rule-only and are counted by name. A test pins the rule under that size.

## Alternatives rejected

- Exclude files by name (CLAUDE.md, AGENTS.md): hides real prose a team keeps in those files, which is where decisions often live
- Read every markdown file to count: slow on large repos for one integer, which the count was designed to avoid
- Make init scan before writing only: fixes the first run but /api/setup and import would still re-read the rule block
