---
id: dec_4ac36r
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-17T03:52:11.091255Z'
justifies:
- packages/core/src/reasonledger_core/models/reasoning.py::ConflictWithDetails
- packages/core/src/reasonledger_core/reasoning/verdicts.py::stored_verdict_source
- packages/cli/src/reasonledger_cli/ui_assets/render.js::verdictHtml
watchers: []
confidence: medium
context: A judged pair showed only the verdict's reason text, so a reviewer could
  not tell it was a verdict, which agent or model gave it, or when. The facts already
  sit in verdicts.yml as model and judged_at, but the pair objects the UI reads did
  not carry them. How should the UI get them?
choice: 'Carry judged_by and judged_at on ConflictVerdict, Conflict and ConflictWithDetails,
  both optional and empty until a pair is judged, filled when a stored verdict is
  looked up. The pair card leads a judged pair with "Verdict: Conflict." or "Verdict:
  Compatible." then the reason, and a line "Judged by <tool/model> on <date>"; an
  unjudged pair keeps its plain explanation. The date uses the same UTC stamp as decision
  provenance. The person who ran the check is not recorded, so only the agent or model
  is shown.'
alternatives_rejected:
- 'Have the UI fetch verdicts.yml separately and join by pair key: a second request
  and a second place that must agree on pair keys and fingerprints'
- 'Record the git identity of whoever triggered the check in each verdict: a schema
  change to verdicts.yml and every writer, and the agent route cannot know who the
  user is'
- 'Put the who and when only in the Overview or a tooltip: it would still not sit
  beside the verdict text a reviewer is reading'
assumptions:
- The tool-and-model string a judge supplies is enough to say which agent gave the
  verdict
---

## Context

A judged pair showed only the verdict's reason text, so a reviewer could not tell it was a verdict, which agent or model gave it, or when. The facts already sit in verdicts.yml as model and judged_at, but the pair objects the UI reads did not carry them. How should the UI get them?

## Choice

Carry judged_by and judged_at on ConflictVerdict, Conflict and ConflictWithDetails, both optional and empty until a pair is judged, filled when a stored verdict is looked up. The pair card leads a judged pair with "Verdict: Conflict." or "Verdict: Compatible." then the reason, and a line "Judged by <tool/model> on <date>"; an unjudged pair keeps its plain explanation. The date uses the same UTC stamp as decision provenance. The person who ran the check is not recorded, so only the agent or model is shown.

## Alternatives rejected

- Have the UI fetch verdicts.yml separately and join by pair key: a second request and a second place that must agree on pair keys and fingerprints
- Record the git identity of whoever triggered the check in each verdict: a schema change to verdicts.yml and every writer, and the agent route cannot know who the user is
- Put the who and when only in the Overview or a tooltip: it would still not sit beside the verdict text a reviewer is reading

## Assumptions

- The tool-and-model string a judge supplies is enough to say which agent gave the verdict
