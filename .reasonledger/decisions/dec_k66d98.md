---
id: dec_k66d98
ai_tool: claude-code
model: claude-opus-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-22T06:40:02.549775Z'
justifies:
- packages/core/src/reasonledger_core/repo_files.py::contained_dir
- packages/core/src/reasonledger_core/repo_files.py::read_repo_text
- packages/core/src/reasonledger_core/importer/scan.py::scan_docs
- packages/core/src/reasonledger_core/decisions/format.py::write_decision_file
- packages/core/src/reasonledger_core/reasoning/anchors.py::locus_problem
- packages/mcp/src/reasonledger_mcp/tools.py::_anchor_symbols
watchers: []
context: A committed symlink let scan_docs read a file outside the checkout and send
  it to a model, decision writes followed symlinked files and a symlinked ledger directory,
  and locus reads in MCP anchoring and orphan checks were unbounded. Where should
  the repository boundary be enforced, and how?
choice: 'One repo_files module decides membership by where a path resolves: scan_docs
  and count_scannable_docs skip a doc resolving outside the root (links inside stay
  allowed); read_lines, locus_problem and MCP _anchor_symbols read through read_repo_text;
  every ledger writer gets its directory from contained_dir, which refuses one resolving
  outside the root; and write_decision_file refuses a symlinked file (broken or not)
  and opens with O_NOFOLLOW where available.'
alternatives_rejected:
- Skip every symlink, including links that stay inside the repo
- Add a required root parameter to write_decision_file at every call site
- Check only the scan, the one escape reproduced
assumptions:
- Ledger directories are always computed as root plus a relative path by the writers
- Reads of decision files through a symlinked ledger directory stay out of scope for
  now
---

## Context

A committed symlink let scan_docs read a file outside the checkout and send it to a model, decision writes followed symlinked files and a symlinked ledger directory, and locus reads in MCP anchoring and orphan checks were unbounded. Where should the repository boundary be enforced, and how?

## Choice

One repo_files module decides membership by where a path resolves: scan_docs and count_scannable_docs skip a doc resolving outside the root (links inside stay allowed); read_lines, locus_problem and MCP _anchor_symbols read through read_repo_text; every ledger writer gets its directory from contained_dir, which refuses one resolving outside the root; and write_decision_file refuses a symlinked file (broken or not) and opens with O_NOFOLLOW where available.

## Alternatives rejected

- Skip every symlink, including links that stay inside the repo
- Add a required root parameter to write_decision_file at every call site
- Check only the scan, the one escape reproduced

## Assumptions

- Ledger directories are always computed as root plus a relative path by the writers
- Reads of decision files through a symlinked ledger directory stay out of scope for now
