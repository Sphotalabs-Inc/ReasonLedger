---
id: dec_zfty5t
ai_tool: claude-code
model: claude-opus-5-5
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/reasoning/related.py::shortlist
- packages/core/src/reasonledger_core/reasoning/related.py::relate_decisions
- packages/core/src/reasonledger_core/reasoning/judge.py::judge_pending
- packages/core/src/reasonledger_core/reasoning/judge.py::ModelJudge
- packages/core/src/reasonledger_core/reasoning/verdicts.py::stored_verdict_source
- packages/core/src/reasonledger_core/reasoning/verdicts.py::relate_in_repo
- packages/cli/src/reasonledger_cli/check_decisions_cmd.py::run_check_decisions
watchers: []
confidence: medium
context: 'Embedding similarity measures shared topic, not contradiction: on a 40-decision
  pilot ledger the hash embedder flagged 39% of all pairs, and with bge-small the
  one real same-question pair had higher choice similarity than unrelated pairs, so
  no gate/ceiling setting could separate conflicts. How should conflicts be decided,
  and where may a model run?'
choice: Similarity only shortlists each decision's k nearest neighbours by context;
  a model judge on the importer's provider decides same-question-and-incompatible
  per pair, but only inside the explicit `reasonledger judge` command. Verdicts are
  committed to .reasonledger/verdicts.yml under the dismissal fingerprint; status,
  ui and check --decisions only read them, and the CI gate fails only on judged conflicts
  while unjudged pairs warn. The choice_divergence_ceiling setting is removed.
alternatives_rejected:
- 'Retune similarity thresholds per embedder: measured to fail; choice similarity
  does not separate a real conflict from unrelated pairs within one project'
- 'Judge inline inside status and the UI: hidden model calls and cost on a read-only
  command, writes from a view that promises never to write, and a CI gate that would
  need a live model'
- 'Keep verdicts in a local, uncommitted cache: CI could not gate without calling
  a model, and every teammate would pay again for the same pairs'
- 'A separate judge provider configuration: a second place to configure and consent;
  an optional judge_model override covers the cheaper-model case'
- 'Keep failing CI on unjudged similarity hits: a gate that fails builds on topic
  overlap is what eroded trust in the first place'
assumptions:
- The importer's provider is acceptable for judging decision context and choice text;
  both fields are already PII-linted at record time
---

## Context

Embedding similarity measures shared topic, not contradiction: on a 40-decision pilot ledger the hash embedder flagged 39% of all pairs, and with bge-small the one real same-question pair had higher choice similarity than unrelated pairs, so no gate/ceiling setting could separate conflicts. How should conflicts be decided, and where may a model run?

## Choice

Similarity only shortlists each decision's k nearest neighbours by context; a model judge on the importer's provider decides same-question-and-incompatible per pair, but only inside the explicit `reasonledger judge` command. Verdicts are committed to .reasonledger/verdicts.yml under the dismissal fingerprint; status, ui and check --decisions only read them, and the CI gate fails only on judged conflicts while unjudged pairs warn. The choice_divergence_ceiling setting is removed.

## Alternatives rejected

- Retune similarity thresholds per embedder: measured to fail; choice similarity does not separate a real conflict from unrelated pairs within one project
- Judge inline inside status and the UI: hidden model calls and cost on a read-only command, writes from a view that promises never to write, and a CI gate that would need a live model
- Keep verdicts in a local, uncommitted cache: CI could not gate without calling a model, and every teammate would pay again for the same pairs
- A separate judge provider configuration: a second place to configure and consent; an optional judge_model override covers the cheaper-model case
- Keep failing CI on unjudged similarity hits: a gate that fails builds on topic overlap is what eroded trust in the first place

## Assumptions

- The importer's provider is acceptable for judging decision context and choice text; both fields are already PII-linted at record time
