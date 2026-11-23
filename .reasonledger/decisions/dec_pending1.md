---
id: dec_pending1
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/models/decision.py::DecisionOversight
- packages/core/src/reasonledger_core/models/decision.py::RecordDecisionInput.resolved_oversight
- packages/core/src/reasonledger_core/decisions/service.py::approve_decision
- packages/core/src/reasonledger_core/importer/propose.py::confirm_proposed
- packages/cli/src/reasonledger_cli/check_decisions_cmd.py::run_check_decisions
watchers: []
confidence: high
context: Every oversight value (reviewed, modified, rejected) claims a human looked,
  so an agent recording before approval either stalled or claimed reviewed falsely,
  and harvested or imported proposals were stamped reviewed with no approver. How
  should a record that no person has judged yet be represented?
choice: Add a pending oversight value. A record is reviewed only when approved_by
  is supplied; otherwise it is pending, and approve_decision is the single transition
  out of pending, refusing to rewrite any existing verdict. Harvested and imported
  proposals start pending and confirm sets reviewed with the confirmer. status and
  check --decisions surface pending records as warnings, not failures.
alternatives_rejected:
- 'Let agents pass an unreviewed alias or none: still has to be a stored value, so
  it is pending under another name'
- 'Require approved_by for reviewed and leave the rest unset: a missing field is indistinguishable
  from a legacy record'
- 'Fail the CI gate on pending records: blocks the PR that holds the record before
  its author can approve it'
- 'Allow approve to overwrite any verdict: a verdict is evidence, changing it belongs
  in a superseding record'
assumptions:
- Oversight counts that matter are per-decision here; the PR-level coverage metrics
  use a separate OversightClassification and are unaffected
---

## Context

Every oversight value (reviewed, modified, rejected) claims a human looked, so an agent recording before approval either stalled or claimed reviewed falsely, and harvested or imported proposals were stamped reviewed with no approver. How should a record that no person has judged yet be represented?

## Choice

Add a pending oversight value. A record is reviewed only when approved_by is supplied; otherwise it is pending, and approve_decision is the single transition out of pending, refusing to rewrite any existing verdict. Harvested and imported proposals start pending and confirm sets reviewed with the confirmer. status and check --decisions surface pending records as warnings, not failures.

## Alternatives rejected

- Let agents pass an unreviewed alias or none: still has to be a stored value, so it is pending under another name
- Require approved_by for reviewed and leave the rest unset: a missing field is indistinguishable from a legacy record
- Fail the CI gate on pending records: blocks the PR that holds the record before its author can approve it
- Allow approve to overwrite any verdict: a verdict is evidence, changing it belongs in a superseding record

## Assumptions

- Oversight counts that matter are per-decision here; the PR-level coverage metrics use a separate OversightClassification and are unaffected
