---
id: dec_vvz19e
ai_tool: claude-code
model: claude-opus-5-5
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/reasoning/related.py::is_retired
- packages/core/src/reasonledger_core/reasoning/related.py::is_replacement_pair
- packages/core/src/reasonledger_core/reasoning/conflicts.py::detect_conflicts
- packages/core/src/reasonledger_core/reasoning/related.py::shortlist
watchers: []
confidence: high
context: Conflict detection compared every ledger record pairwise, including superseded
  ones, so a replacement and the decision it retired surfaced as a conflict; in a
  40-decision pilot ledger the two highest-scoring pairs were exactly such replacements.
  Should retired records drop out of conflict detection, or stay in and be marked
  the way dec_iswj2b marks them for `why`?
choice: Drop them. detect_conflicts and detect_conflicts_among filter status=superseded
  records before embedding and skip any pair where one record's `supersedes` names
  the other, so status, ui, import and check-decisions all inherit the rule from core.
alternatives_rejected:
- 'Keep superseded pairs and label them, mirroring dec_iswj2b: that decision governs
  retrieval, where hiding a record can turn a real hit into a false miss; a conflict
  is a call to act, and a retired decision holds no live position to contradict, so
  labelled pairs would only add the noise that erodes trust in the panel'
- 'Filter only in views/ledger.py: check-decisions and import would still flag replacements,
  leaving three surfaces that disagree'
- 'Skip only direct replacement pairs: a retired record would still be compared against
  every unrelated active decision'
assumptions:
- Retired status is set by confirm_proposed or by hand when a successor lands; the
  direct-pair skip covers ledgers where it was not
---

## Context

Conflict detection compared every ledger record pairwise, including superseded ones, so a replacement and the decision it retired surfaced as a conflict; in a 40-decision pilot ledger the two highest-scoring pairs were exactly such replacements. Should retired records drop out of conflict detection, or stay in and be marked the way dec_iswj2b marks them for `why`?

## Choice

Drop them. detect_conflicts and detect_conflicts_among filter status=superseded records before embedding and skip any pair where one record's `supersedes` names the other, so status, ui, import and check-decisions all inherit the rule from core.

## Alternatives rejected

- Keep superseded pairs and label them, mirroring dec_iswj2b: that decision governs retrieval, where hiding a record can turn a real hit into a false miss; a conflict is a call to act, and a retired decision holds no live position to contradict, so labelled pairs would only add the noise that erodes trust in the panel
- Filter only in views/ledger.py: check-decisions and import would still flag replacements, leaving three surfaces that disagree
- Skip only direct replacement pairs: a retired record would still be compared against every unrelated active decision

## Assumptions

- Retired status is set by confirm_proposed or by hand when a successor lands; the direct-pair skip covers ledgers where it was not
