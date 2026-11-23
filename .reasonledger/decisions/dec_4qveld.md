---
id: dec_4qveld
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
status: active
approved_by: iharpreet
approved_at: '2026-11-12T18:55:45.560706Z'
justifies:
- packages/core/src/reasonledger_core/reasoning/judge.py::pending_pairs
- packages/core/src/reasonledger_core/reasoning/judge.py::JudgeQueue
- packages/core/src/reasonledger_core/reasoning/judge.py::_dismissal_applies
- packages/cli/src/reasonledger_cli/judge_cmd.py::run_judge_cmd
watchers: []
confidence: high
context: reasonledger judge sent every shortlisted pair that lacked a model verdict
  to the model, including pairs a person had already dismissed. On the reference app that was
  41 of 151 calls spent on pairs the view then hides anyway, at about 12 seconds each
  on a local model. Should the judge skip dismissed pairs, and how should it treat
  a dismissal that has gone stale?
choice: pending_pairs now returns a JudgeQueue that splits the shortlist into pending,
  already judged and dismissed. A pair is dismissed for this purpose only while its
  dismissal fingerprint still matches the two decisions as they read now, the same
  rule the view applies, so a pair edited since is judged again. The dry run and the
  final run line report the dismissed count.
alternatives_rejected:
- 'Judge dismissed pairs anyway to catch a model disagreement: a person''s verdict
  outranks a model''s and the view hides the pair regardless, so the call is pure
  cost'
- 'Add an --include-dismissed flag: a speculative parameter, since editing either
  decision already re-opens a pair for judging'
- 'Skip any pair that has a dismissal entry regardless of fingerprint: contradicts
  dec_afepr6, where a stale dismissal hid a real conflict'
- 'Drop dismissed pairs inside shortlist(): status and the UI need them in the shortlist
  to count and re-open them'
assumptions:
- A legacy dismissal with no fingerprint keeps suppressing, as in the view, so upgrading
  does not suddenly queue every previously settled pair
- The fingerprint covers context and choice, which are exactly the fields the judge
  reads, so a dismissal lapses precisely when the judge's input changes
---

## Context

reasonledger judge sent every shortlisted pair that lacked a model verdict to the model, including pairs a person had already dismissed. On the reference app that was 41 of 151 calls spent on pairs the view then hides anyway, at about 12 seconds each on a local model. Should the judge skip dismissed pairs, and how should it treat a dismissal that has gone stale?

## Choice

pending_pairs now returns a JudgeQueue that splits the shortlist into pending, already judged and dismissed. A pair is dismissed for this purpose only while its dismissal fingerprint still matches the two decisions as they read now, the same rule the view applies, so a pair edited since is judged again. The dry run and the final run line report the dismissed count.

## Alternatives rejected

- Judge dismissed pairs anyway to catch a model disagreement: a person's verdict outranks a model's and the view hides the pair regardless, so the call is pure cost
- Add an --include-dismissed flag: a speculative parameter, since editing either decision already re-opens a pair for judging
- Skip any pair that has a dismissal entry regardless of fingerprint: contradicts dec_afepr6, where a stale dismissal hid a real conflict
- Drop dismissed pairs inside shortlist(): status and the UI need them in the shortlist to count and re-open them

## Assumptions

- A legacy dismissal with no fingerprint keeps suppressing, as in the view, so upgrading does not suddenly queue every previously settled pair
- The fingerprint covers context and choice, which are exactly the fields the judge reads, so a dismissal lapses precisely when the judge's input changes
