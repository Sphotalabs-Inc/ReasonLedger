---
id: dec_euwhua
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
justifies:
- packages/core/src/reasonledger_core/modules/suggest.py::suggest_placements
- packages/core/src/reasonledger_core/modules/suggest.py::_grade
- packages/core/src/reasonledger_core/modules/organize.py::promotion_candidates
- packages/core/src/reasonledger_core/modules/organize.py::decline_placement
- packages/core/src/reasonledger_core/modules/organize.py::bulk_move
- packages/core/src/reasonledger_core/views/inbox.py::collect_items
- packages/core/src/reasonledger_core/modules/models.py::Manifest
- packages/cli/src/reasonledger_cli/ui_assets/organize_inbox.js:58-90
watchers: []
context: Phase 2 of the map workbench should help place new files and learn from a
  person's corrections. What evidence suggests a home, how are suggestions graded
  and ordered, how do accepting and refusing feed back, what may happen without a
  click, and how many things should a person face at once?
choice: 'Suggestions come from three kinds of evidence the code computes, with no
  model: more than half of at least two files beside the new one sit in one module,
  the new file shares a leading name word with a module''s files among modules on
  its own side, and the file changed together with a module''s files in at least three
  commits of names-only git history, ignoring commits over fifty files. Each kind
  adds a fixed weight times how lopsided it is; two kinds agreeing is high, one kind
  at a set score is medium, else low. A file is never suggested across frontend and
  backend or for a module it was declined for. Nothing is applied without a click.
  Accepting writes a label, which is itself evidence for the next file. Three or more
  files placed by hand in one folder, with nothing there owned by another module,
  raise a rule offer that is listed first. Refusing a home is stored under declined
  in modules.yml so it is shared and not suggested again; skipping only hides a card
  in that window. Accept-all takes only high-confidence homes the person has not skipped,
  as one undo step. The inbox shows five cards at a time, and only the next five proposed
  modules of the confirm queue with a count of those waiting. This extends dec_8a28z3.'
alternatives_rejected:
- 'Let a model choose the home: the answer varies with the model and small local ones
  are poor at it, while evidence the code computes is explainable and identical on
  every machine; a model is a later fallback'
- 'Train a classifier from the person''s corrections: a repo yields tens of corrections,
  the result is opaque, and it would change membership without a reviewable record,
  where labels and rules are explicit, committed and reviewable'
- 'Apply high-confidence suggestions automatically: nothing here may move a file the
  person did not choose, so they are accepted in bulk with one click and one undo
  instead'
- 'Keep a refusal only in the browser session: a person''s judgment that a file is
  not X is knowledge for the whole team, and would be suggested again to everyone
  else'
- 'Allow a suggestion across frontend and backend when a name matches: it breaks the
  separation the owner required, and it happened in testing where a label-named frontend
  file matched the backend labels module'
- 'List every proposed module in the inbox: all 65 on Docmost pushed every other card
  past the cap, and the confirm queue is meant to show five at a time'
assumptions:
- The weights and thresholds (more than half of two neighbours, two files sharing
  a name word, three commits, a score of 2.0 for medium) are initial guesses that
  are pinned by tests but not tuned on rated data
- A leave-some-out check on Docmost hid a tenth of each module's files and got a suggestion
  for 91 percent, right 94 percent of the time, but the truth is the model's own map
  and the hidden files keep their neighbours, so it shows consistency and not that
  the map is correct
- Co-change needs git history; a shallow clone gives none and the inbox says so, and
  on Docmost it was the evidence in only 20 of the suggestions
- Declined entries are kept per file in modules.yml, which is fine at tens of refusals
  but may need compaction in a large repo
- I drove the inbox through scripted clicks on a carved Docmost clone (accept, undo,
  rule offer, decline, choose another, skip, show more, bulk accept); no person has
  used it yet
---

## Context

Phase 2 of the map workbench should help place new files and learn from a person's corrections. What evidence suggests a home, how are suggestions graded and ordered, how do accepting and refusing feed back, what may happen without a click, and how many things should a person face at once?

## Choice

Suggestions come from three kinds of evidence the code computes, with no model: more than half of at least two files beside the new one sit in one module, the new file shares a leading name word with a module's files among modules on its own side, and the file changed together with a module's files in at least three commits of names-only git history, ignoring commits over fifty files. Each kind adds a fixed weight times how lopsided it is; two kinds agreeing is high, one kind at a set score is medium, else low. A file is never suggested across frontend and backend or for a module it was declined for. Nothing is applied without a click. Accepting writes a label, which is itself evidence for the next file. Three or more files placed by hand in one folder, with nothing there owned by another module, raise a rule offer that is listed first. Refusing a home is stored under declined in modules.yml so it is shared and not suggested again; skipping only hides a card in that window. Accept-all takes only high-confidence homes the person has not skipped, as one undo step. The inbox shows five cards at a time, and only the next five proposed modules of the confirm queue with a count of those waiting. This extends dec_8a28z3.

## Alternatives rejected

- Let a model choose the home: the answer varies with the model and small local ones are poor at it, while evidence the code computes is explainable and identical on every machine; a model is a later fallback
- Train a classifier from the person's corrections: a repo yields tens of corrections, the result is opaque, and it would change membership without a reviewable record, where labels and rules are explicit, committed and reviewable
- Apply high-confidence suggestions automatically: nothing here may move a file the person did not choose, so they are accepted in bulk with one click and one undo instead
- Keep a refusal only in the browser session: a person's judgment that a file is not X is knowledge for the whole team, and would be suggested again to everyone else
- Allow a suggestion across frontend and backend when a name matches: it breaks the separation the owner required, and it happened in testing where a label-named frontend file matched the backend labels module
- List every proposed module in the inbox: all 65 on Docmost pushed every other card past the cap, and the confirm queue is meant to show five at a time

## Assumptions

- The weights and thresholds (more than half of two neighbours, two files sharing a name word, three commits, a score of 2.0 for medium) are initial guesses that are pinned by tests but not tuned on rated data
- A leave-some-out check on Docmost hid a tenth of each module's files and got a suggestion for 91 percent, right 94 percent of the time, but the truth is the model's own map and the hidden files keep their neighbours, so it shows consistency and not that the map is correct
- Co-change needs git history; a shallow clone gives none and the inbox says so, and on Docmost it was the evidence in only 20 of the suggestions
- Declined entries are kept per file in modules.yml, which is fine at tens of refusals but may need compaction in a large repo
- I drove the inbox through scripted clicks on a carved Docmost clone (accept, undo, rule offer, decline, choose another, skip, show more, bulk accept); no person has used it yet
