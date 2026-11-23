---
id: dec_cxvcn7
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: active
proposed_by: human
justifies:
- packages/core/src/reasonledger_core/decisions/lifecycle.py::retire_decision
- packages/core/src/reasonledger_core/decisions/lifecycle.py::mark_superseded
- packages/core/src/reasonledger_core/decisions/service.py::record_decision_to_path
- packages/core/src/reasonledger_core/models/decision.py::DecisionStatus
- packages/cli/src/reasonledger_cli/retire_cmd.py::run_retire_cmd
- packages/core/src/reasonledger_core/reasoning/related.py::is_retired
watchers: []
confidence: high
context: An active decision could leave force only when an imported proposal replaced
  it. A decision approved once and no longer relevant had no exit, and record_decision
  could not name the record it replaces even though agents are told to supersede explicitly.
  How does a ledger decision go out of force?
choice: Add a retired status with retired_by, retired_at and a required retired_reason,
  set by reasonledger retire or the Retire button; and add supersedes to record_decision,
  which marks the named record superseded after the new one is written. Neither rewrites
  the record or its verdict. Retired and superseded share one OUT_OF_FORCE set that
  conflicts, coverage, the unplaced list and the pending count all exclude.
alternatives_rejected:
- 'Reuse superseded with no successor for retiring: no new status value, but superseded
  would sometimes mean replaced by nothing and why would point at a successor that
  does not exist'
- 'Supersede only, with no standalone retire: a decision about removed code has nothing
  to replace it'
- 'Delete the file or flip oversight to rejected: destroys or falsifies the evidence
  that it was once approved'
assumptions:
- A pending decision may be retired too, and then stops waiting on a person
- Retiring is not reversible from the UI or CLI; undoing one is an edit to the file
  under git
---

## Context

An active decision could leave force only when an imported proposal replaced it. A decision approved once and no longer relevant had no exit, and record_decision could not name the record it replaces even though agents are told to supersede explicitly. How does a ledger decision go out of force?

## Choice

Add a retired status with retired_by, retired_at and a required retired_reason, set by reasonledger retire or the Retire button; and add supersedes to record_decision, which marks the named record superseded after the new one is written. Neither rewrites the record or its verdict. Retired and superseded share one OUT_OF_FORCE set that conflicts, coverage, the unplaced list and the pending count all exclude.

## Alternatives rejected

- Reuse superseded with no successor for retiring: no new status value, but superseded would sometimes mean replaced by nothing and why would point at a successor that does not exist
- Supersede only, with no standalone retire: a decision about removed code has nothing to replace it
- Delete the file or flip oversight to rejected: destroys or falsifies the evidence that it was once approved

## Assumptions

- A pending decision may be retired too, and then stops waiting on a person
- Retiring is not reversible from the UI or CLI; undoing one is an edit to the file under git
