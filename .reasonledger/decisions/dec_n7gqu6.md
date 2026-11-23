---
id: dec_n7gqu6
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: superseded
proposed_by: human
recorded_at: '2026-11-13T04:54:17.603538Z'
justifies:
- packages/core/src/reasonledger_core/reasoning/anchors.py::locus_problem
- packages/core/src/reasonledger_core/reasoning/anchors.py::_is_defined
- packages/core/src/reasonledger_core/views/ledger.py::_orphan_views
watchers: []
context: 'The orphan check reported symbols as missing when the TS/JS extractor, which
  only sees top-level functions, could not find them: functions nested in an IIFE
  wrapper (every UI asset) and Python module constants. Roughly half the orphaned
  list was false positives. How should a symbol locus be judged missing without weakening
  the conservative extractor?'
choice: 'Leave the extractors untouched and add a second check in locus_problem: when
  the extractor finds no symbol, search the file for a line-start definition of the
  symbol''s last name (def, class, function, const, let, var, or a NAME = assignment).
  Only if both fail is the locus missing_symbol. Orphan lists also now cover only
  decisions in force.'
alternatives_rejected:
- 'Teach the TS/JS extractor to descend into IIFE wrappers and nested scopes: higher
  risk of wrong spans, and the extractor is deliberately conservative so a wrong symbol
  never beats none'
- 'Treat every symbol in a TS/JS file as present once the file exists: removes all
  false positives but also hides genuinely deleted symbols'
- 'Leave the check as is and rely on users to ignore noisy orphans: erodes trust in
  the orphaned list'
assumptions:
- A definition at line start is a good enough signal that the symbol still exists;
  a deleted symbol still named in a line-start assignment would be missed
---

## Context

The orphan check reported symbols as missing when the TS/JS extractor, which only sees top-level functions, could not find them: functions nested in an IIFE wrapper (every UI asset) and Python module constants. Roughly half the orphaned list was false positives. How should a symbol locus be judged missing without weakening the conservative extractor?

## Choice

Leave the extractors untouched and add a second check in locus_problem: when the extractor finds no symbol, search the file for a line-start definition of the symbol's last name (def, class, function, const, let, var, or a NAME = assignment). Only if both fail is the locus missing_symbol. Orphan lists also now cover only decisions in force.

## Alternatives rejected

- Teach the TS/JS extractor to descend into IIFE wrappers and nested scopes: higher risk of wrong spans, and the extractor is deliberately conservative so a wrong symbol never beats none
- Treat every symbol in a TS/JS file as present once the file exists: removes all false positives but also hides genuinely deleted symbols
- Leave the check as is and rely on users to ignore noisy orphans: erodes trust in the orphaned list

## Assumptions

- A definition at line start is a good enough signal that the symbol still exists; a deleted symbol still named in a line-start assignment would be missed
