---
id: dec_yk5ty2
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-13T06:03:46.691058Z'
justifies:
- packages/core/src/reasonledger_core/decisions/service.py::approve_decision
- packages/core/src/reasonledger_core/decisions/service.py::superseded_by_map
- packages/core/src/reasonledger_core/decisions/service.py::record_decision_to_path
watchers: []
context: record_decision with supersedes marked the old decision superseded immediately,
  even though the AI-proposed replacement was still pending, so a reviewed decision
  left force before any person approved its replacement. When should a replacement
  take the old decision out of force?
choice: Writing a record that names supersedes only checks that the old decision is
  in force; it no longer changes it. approve_decision marks the old one superseded
  when the replacement gets a reviewed or modified verdict, and does nothing for rejected.
  superseded_by_map ignores a pending or rejected successor unless the old record
  already left force. This narrows dec_cxvcn7, which had the write do the marking;
  its retired status is unchanged.
alternatives_rejected:
- 'Keep marking on write and add an undo when the replacement is rejected: the old
  decision is wrongly out of force for the whole pending window'
- 'Add a separate pending-supersession status: a new lifecycle state and migration
  for what approval already expresses'
assumptions:
- Every path that gives a decision a verdict goes through approve_decision, including
  the UI and the CLI
---

## Context

record_decision with supersedes marked the old decision superseded immediately, even though the AI-proposed replacement was still pending, so a reviewed decision left force before any person approved its replacement. When should a replacement take the old decision out of force?

## Choice

Writing a record that names supersedes only checks that the old decision is in force; it no longer changes it. approve_decision marks the old one superseded when the replacement gets a reviewed or modified verdict, and does nothing for rejected. superseded_by_map ignores a pending or rejected successor unless the old record already left force. This narrows dec_cxvcn7, which had the write do the marking; its retired status is unchanged.

## Alternatives rejected

- Keep marking on write and add an undo when the replacement is rejected: the old decision is wrongly out of force for the whole pending window
- Add a separate pending-supersession status: a new lifecycle state and migration for what approval already expresses

## Assumptions

- Every path that gives a decision a verdict goes through approve_decision, including the UI and the CLI
