---
id: dec_h1uhrq
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
justifies:
- packages/core/src/reasonledger_core/modules/editing.py::confirm_modules
- packages/core/src/reasonledger_core/modules/editing.py::rename_module
- packages/core/src/reasonledger_core/modules/editing.py::merge_modules
- packages/core/src/reasonledger_core/modules/editing.py::reject_module
- packages/core/src/reasonledger_core/modules/review.py::pending_queue
- packages/core/src/reasonledger_core/modules/manifest.py::merge_proposals
- packages/cli/src/reasonledger_cli/modules_cmd.py::run_modules_cmd
watchers: []
context: The spec's confirm queue needs commands a person uses to decide on proposed
  modules. A mapper proposes different paths on every run, and a model-first map is
  mostly low confidence. Who is recorded as confirming, how does a rejection stay
  down when the paths change, what do rename and merge do to identity and confirmation,
  and what may bulk confirm take?
choice: Confirming needs --by, with no default identity, and is all or nothing. A
  rejection stays down while a new proposal's files overlap the rejected module's
  files by at least 0.7 (Jaccard, over the source files each path set matches), and
  with no file list only identical paths stay down. Rename changes the name and the
  id it makes and rewrites the labels and suggestions that pointed at the old id.
  Merge keeps the first module's id, name and status, unites the paths, clears the
  tier when the two differ and keeps the lower confidence, and refuses to fold a confirmed
  module into a proposed one. Reject refuses confirmed modules, and buckets can be
  confirmed but not renamed, merged or rejected. Bulk confirm takes only proposed
  modules with high confidence. The queue shows five proposals at a time, most trusted
  first. This extends dec_j18a1i.
alternatives_rejected:
- 'Default the confirmer to the git user name: it would record a person as having
  looked when they only ran a command, and it copies a name from git config into a
  committed file without their say'
- 'Keep the exact path fingerprint for rejections: a model proposes different paths
  every run (74 to 84 percent agreement earlier), so a rejection would rarely stick;
  on Docmost a proposal missing one of four files still matched at 75 percent'
- 'Rename only the display name and keep the id: the id is what people type and what
  labels point at, so after renaming templates to data extraction the old id would
  keep misleading'
- 'Let a merge inherit confirmation when either side is confirmed: the proposed side''s
  files would be confirmed without anyone looking, so the safe direction is required
  instead'
- 'Add a confirm --all for every proposal: the spec limits bulk confirm to high confidence
  to prevent click-through, and the person can still name any ids they have reviewed'
- 'Let reject delete a confirmed module: confirmed modules are a person''s earlier
  decision and a re-map never touches them, so removing one is an edit to modules.yml'
assumptions:
- 'Confidence from corroboration orders the queue usefully, but on a model-first map
  most proposals are low: on Docmost 2 of 65 are high, so bulk confirm helps little
  there and a person will name ids from their review'
- 'The 0.7 overlap comes from the spec and was checked on one repo only: a proposal
  covering 3 of a rejected module''s 4 files stayed down and one adding 8 other files
  came back'
- A confirmed module can only be removed by editing modules.yml; an unconfirm command
  is not built
- A proposed module that is renamed is still replaced by the next map, which the command
  says; it does not confirm on the person's behalf
---

## Context

The spec's confirm queue needs commands a person uses to decide on proposed modules. A mapper proposes different paths on every run, and a model-first map is mostly low confidence. Who is recorded as confirming, how does a rejection stay down when the paths change, what do rename and merge do to identity and confirmation, and what may bulk confirm take?

## Choice

Confirming needs --by, with no default identity, and is all or nothing. A rejection stays down while a new proposal's files overlap the rejected module's files by at least 0.7 (Jaccard, over the source files each path set matches), and with no file list only identical paths stay down. Rename changes the name and the id it makes and rewrites the labels and suggestions that pointed at the old id. Merge keeps the first module's id, name and status, unites the paths, clears the tier when the two differ and keeps the lower confidence, and refuses to fold a confirmed module into a proposed one. Reject refuses confirmed modules, and buckets can be confirmed but not renamed, merged or rejected. Bulk confirm takes only proposed modules with high confidence. The queue shows five proposals at a time, most trusted first. This extends dec_j18a1i.

## Alternatives rejected

- Default the confirmer to the git user name: it would record a person as having looked when they only ran a command, and it copies a name from git config into a committed file without their say
- Keep the exact path fingerprint for rejections: a model proposes different paths every run (74 to 84 percent agreement earlier), so a rejection would rarely stick; on Docmost a proposal missing one of four files still matched at 75 percent
- Rename only the display name and keep the id: the id is what people type and what labels point at, so after renaming templates to data extraction the old id would keep misleading
- Let a merge inherit confirmation when either side is confirmed: the proposed side's files would be confirmed without anyone looking, so the safe direction is required instead
- Add a confirm --all for every proposal: the spec limits bulk confirm to high confidence to prevent click-through, and the person can still name any ids they have reviewed
- Let reject delete a confirmed module: confirmed modules are a person's earlier decision and a re-map never touches them, so removing one is an edit to modules.yml

## Assumptions

- Confidence from corroboration orders the queue usefully, but on a model-first map most proposals are low: on Docmost 2 of 65 are high, so bulk confirm helps little there and a person will name ids from their review
- The 0.7 overlap comes from the spec and was checked on one repo only: a proposal covering 3 of a rejected module's 4 files stayed down and one adding 8 other files came back
- A confirmed module can only be removed by editing modules.yml; an unconfirm command is not built
- A proposed module that is renamed is still replaced by the next map, which the command says; it does not confirm on the person's behalf
