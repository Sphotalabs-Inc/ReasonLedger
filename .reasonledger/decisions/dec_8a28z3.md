---
id: dec_8a28z3
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
justifies:
- packages/cli/src/reasonledger_cli/ui_organize.py::OrganizeSession
- packages/core/src/reasonledger_core/modules/organize.py::preview_move
- packages/core/src/reasonledger_core/modules/organize.py::move_labels
- packages/core/src/reasonledger_core/modules/organize.py::folder_rule
- packages/core/src/reasonledger_core/modules/editing.py::create_module
- packages/core/src/reasonledger_core/views/organize_files.py::list_files
- packages/core/src/reasonledger_core/modules/globs.py::_RuleSet
- packages/cli/src/reasonledger_cli/ui_assets/organize.js:145-170
watchers: []
context: The map needs an editing surface where a person moves files, renames, merges,
  rejects and creates modules without the CLI. How should a move be stored, what should
  a person see before one is made, how should an edit be undone, and how should an
  organizing view stay responsive on a repo of a couple of thousand files?
choice: Every edit from the browser is one write of modules.yml through the same core
  functions as the CLI. A move is a label, one per file, and a folder rule is a single
  dir/** label; a new module made from a selection is confirmed by its maker and takes
  its files from labels. Before any write a preview shows the files moving, where
  they come from and each decision that would change module, computed by placing decisions
  under the manifest before and after. Undo is a stack of manifests kept by the running
  UI, and it refuses when modules.yml changed from anywhere else since the edit, so
  it never overwrites an outside change. A selection can be explicit paths or all
  files of a module matching a filter, resolved on the server. A hint is shown when
  more than half of the files beside one, at least two, sit in another module; it
  only fills in a selection and a target and never moves anything. The path matcher
  indexes exact paths in a dictionary and compiles each glob once, and the manifest
  loads with libyaml where available. This extends dec_jkmyxy and dec_h1uhrq.
alternatives_rejected:
- 'Edit the module path lists to move a file: two explicit paths for one file tie
  by id order, and a re-map replaces proposed modules, so a person''s moves would
  be lost or arbitrary'
- 'Undo by shelling out to git: modules.yml may be untracked or ignored, and a git
  revert would also discard the person''s other uncommitted edits to it'
- 'Keep a persistent undo history on disk: it adds a committed or cached file to reason
  about, goes stale across sessions and branches, and the manifest on disk is already
  the source of truth'
- 'Let undo restore the last manifest unconditionally: an edit made with the CLI between
  the two would be silently erased'
- 'Send every selected path from the browser for select-all: a 223-file module would
  be paged by hand and the request would grow with the selection, while the filter
  is already known to the server'
- 'Show a confirmation dialog in place of a preview: it says that something will happen
  but not which decisions change module, which is what a person needs to judge a move'
- 'Apply the sibling hint automatically: it is a majority guess from folder neighbours,
  and nothing here may move a file the person did not choose; suggestions with evidence
  are a later phase'
- 'Cache the whole map on the server keyed by file time: a stale answer after an outside
  edit would show wrong counts, and the indexing and parser changes already took a
  file list from 1.4 s to 0.1 s'
assumptions:
- 'An undo stack that lives for the life of the running UI is enough: the manifest
  itself is on disk, and a restart only forgets how to step back'
- The content-hash check protects against edits from another process, but two browser
  tabs editing at once are serialised only by a lock inside this one server
- More than half of at least two neighbours is a reasonable hint threshold; it has
  not been checked against a rated sample
- I drove the workbench through scripted clicks on the Docmost clone (filter, range
  select, preview, move, rule, new module, rename, confirm, merge, reject, undo, hint);
  no person has used it yet
---

## Context

The map needs an editing surface where a person moves files, renames, merges, rejects and creates modules without the CLI. How should a move be stored, what should a person see before one is made, how should an edit be undone, and how should an organizing view stay responsive on a repo of a couple of thousand files?

## Choice

Every edit from the browser is one write of modules.yml through the same core functions as the CLI. A move is a label, one per file, and a folder rule is a single dir/** label; a new module made from a selection is confirmed by its maker and takes its files from labels. Before any write a preview shows the files moving, where they come from and each decision that would change module, computed by placing decisions under the manifest before and after. Undo is a stack of manifests kept by the running UI, and it refuses when modules.yml changed from anywhere else since the edit, so it never overwrites an outside change. A selection can be explicit paths or all files of a module matching a filter, resolved on the server. A hint is shown when more than half of the files beside one, at least two, sit in another module; it only fills in a selection and a target and never moves anything. The path matcher indexes exact paths in a dictionary and compiles each glob once, and the manifest loads with libyaml where available. This extends dec_jkmyxy and dec_h1uhrq.

## Alternatives rejected

- Edit the module path lists to move a file: two explicit paths for one file tie by id order, and a re-map replaces proposed modules, so a person's moves would be lost or arbitrary
- Undo by shelling out to git: modules.yml may be untracked or ignored, and a git revert would also discard the person's other uncommitted edits to it
- Keep a persistent undo history on disk: it adds a committed or cached file to reason about, goes stale across sessions and branches, and the manifest on disk is already the source of truth
- Let undo restore the last manifest unconditionally: an edit made with the CLI between the two would be silently erased
- Send every selected path from the browser for select-all: a 223-file module would be paged by hand and the request would grow with the selection, while the filter is already known to the server
- Show a confirmation dialog in place of a preview: it says that something will happen but not which decisions change module, which is what a person needs to judge a move
- Apply the sibling hint automatically: it is a majority guess from folder neighbours, and nothing here may move a file the person did not choose; suggestions with evidence are a later phase
- Cache the whole map on the server keyed by file time: a stale answer after an outside edit would show wrong counts, and the indexing and parser changes already took a file list from 1.4 s to 0.1 s

## Assumptions

- An undo stack that lives for the life of the running UI is enough: the manifest itself is on disk, and a restart only forgets how to step back
- The content-hash check protects against edits from another process, but two browser tabs editing at once are serialised only by a lock inside this one server
- More than half of at least two neighbours is a reasonable hint threshold; it has not been checked against a rated sample
- I drove the workbench through scripted clicks on the Docmost clone (filter, range select, preview, move, rule, new module, rename, confirm, merge, reject, undo, hint); no person has used it yet
