---
id: dec_afepr6
ai_tool: claude-code
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/reasoning/dismissals.py::pair_fingerprint
- packages/core/src/reasonledger_core/reasoning/dismissals.py::dismissal_still_applies
- packages/core/src/reasonledger_core/reasoning/dismissals.py::add_dismissal
- packages/core/src/reasonledger_core/views/ledger.py::build_ledger_view
- packages/cli/src/reasonledger_cli/check_decisions_cmd.py::_is_dismissed
watchers: []
confidence: high
context: Conflict dismissals were keyed only on the unordered decision-id pair, so
  a recorded dismissal suppressed that pair forever. If either decision's context
  or choice was later edited into a genuine contradiction, the stale verdict kept
  hiding it — a silently suppressed real conflict in a product that claims to be evidence-grade.
  The question was how to scope a dismissal to what the reviewer actually judged.
choice: Scope each dismissal to a SHA-256 fingerprint of both decisions' context and
  choice, taken at dismissal time and stored in dismissed.yml. When the current fingerprint
  no longer matches, the conflict re-surfaces as ConflictStatus.REOPENED instead of
  being suppressed, and re-dismissing it replaces the stale entry so a re-opened pair
  can be settled again.
alternatives_rejected:
- Fingerprint the whole decision record — a typo fix in the body would resurrect a
  settled dismissal, training reviewers to ignore the conflict panel
- 'Expire dismissals after a fixed period — arbitrary, and wrong in both directions:
  too short nags, too long hides'
- Leave dismissals permanent and rely on reviewers noticing — the failure mode is
  invisible by construction, which is what made this a bug rather than a limit
assumptions:
- Only context and choice feed conflict classification, so they are the whole of the
  classifier's input surface (conflicts.classify_pair)
- Legacy entries carrying no fingerprint must keep suppressing, so upgrading does
  not re-open every previously settled pair at once
---

## Why this was a correctness bug, not a preference

A dismissal encodes the judgement "these two decisions, as they read today, do not contradict each other". Keying it on ids alone silently widened that into "this pair may never conflict again", which is a claim the reviewer never made.

## Scope of the fix

Applied at every surface that consumes dismissals, not just the view: the ledger projection, the CI gate (`check_decisions`), the `dismiss` CLI, and the UI dismiss endpoint. Fixing only the view would have left a UI that re-opens and a build gate that stays quiet — a worse state than the original bug.

## Re-arm path

`add_dismissal` replaces an entry whose fingerprint has drifted rather than no-opping. Without that, a re-opened conflict could never be settled again and would nag forever, which is the exact failure the dismissal file exists to prevent.
