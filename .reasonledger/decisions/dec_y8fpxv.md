---
id: dec_y8fpxv
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
justifies:
- packages/core/src/reasonledger_core/modules/resolve.py::resolve_modules
- packages/core/src/reasonledger_core/modules/resolve.py::_dependents
- packages/core/src/reasonledger_core/modules/signals/cochange.py::cochange_candidates
- packages/core/src/reasonledger_core/modules/signals/layout.py::layout_candidates
- packages/core/src/reasonledger_core/modules/scan.py::scan_repo
- packages/core/src/reasonledger_core/sync/repo.py::recent_commit_changes
watchers: []
context: How should a scan turn a bare git repo into proposed modules without a model,
  across layered apps, workspace monorepos, flat libraries and squash-merge histories,
  without proposing noise? The first corpus run over seven open-source repos showed
  scans taking 10 to 40 seconds or timing out, translation docs and tests forming
  the biggest co-change clusters, and every module in squash-merge repos looking like
  a foundation.
choice: Gather independent signals (workspace manifests, spec key files, CODEOWNERS,
  directory layout, git co-change), merge candidates whose files agree by Jaccard,
  give each file to the strongest then smallest candidate, and dissolve weak candidates
  that keep too little. Keep modules flat, so sub-modules come from longer declared
  globs. Read history without rename detection, exclude support directories (tests,
  docs, examples, fixtures) from co-change and layout, link files by the shared-commit
  share of the busier file, and propose foundations from names plus how many modules
  routinely change alongside one, switched off on squash-merged history.
alternatives_rejected:
- 'Hierarchical modules with nested children: adds a tree to the manifest, the UI
  and membership for v1, while flat modules with longest-glob specificity already
  let a person declare a sub-module inside a package'
- 'Link co-changing files by the larger of the two conditional probabilities: a utility
  file that changes with everything pulls every cluster into one blob, so the busier
  file''s share is used'
- 'Foundation by raw count of other modules co-changed with: every module in a squash-merge
  repo scored 30 to 44 partners, so foundations are judged by the share of the other
  module''s commits and are not proposed from history at all when it is squash-merged'
- 'Keep tests and docs in co-change: translation pages and test files formed the largest
  clusters in fastapi and flask, so support directories stay outside every module'
- 'Default git log with rename detection: on a partial clone it fetches file contents
  per commit and scans took 30 seconds or timed out, while names-only history took
  under a second'
assumptions:
- Thresholds are initial guesses and are frozen only after a person rates the corpus
  report, as the spec requires
- Most useful modules are one level deep; very large workspace packages stay whole
  until a person splits them
- A repo whose subjects mostly end in a pull-request number is squash-merged, so co-change
  there groups whole pull requests
---

## Context

How should a scan turn a bare git repo into proposed modules without a model, across layered apps, workspace monorepos, flat libraries and squash-merge histories, without proposing noise? The first corpus run over seven open-source repos showed scans taking 10 to 40 seconds or timing out, translation docs and tests forming the biggest co-change clusters, and every module in squash-merge repos looking like a foundation.

## Choice

Gather independent signals (workspace manifests, spec key files, CODEOWNERS, directory layout, git co-change), merge candidates whose files agree by Jaccard, give each file to the strongest then smallest candidate, and dissolve weak candidates that keep too little. Keep modules flat, so sub-modules come from longer declared globs. Read history without rename detection, exclude support directories (tests, docs, examples, fixtures) from co-change and layout, link files by the shared-commit share of the busier file, and propose foundations from names plus how many modules routinely change alongside one, switched off on squash-merged history.

## Alternatives rejected

- Hierarchical modules with nested children: adds a tree to the manifest, the UI and membership for v1, while flat modules with longest-glob specificity already let a person declare a sub-module inside a package
- Link co-changing files by the larger of the two conditional probabilities: a utility file that changes with everything pulls every cluster into one blob, so the busier file's share is used
- Foundation by raw count of other modules co-changed with: every module in a squash-merge repo scored 30 to 44 partners, so foundations are judged by the share of the other module's commits and are not proposed from history at all when it is squash-merged
- Keep tests and docs in co-change: translation pages and test files formed the largest clusters in fastapi and flask, so support directories stay outside every module
- Default git log with rename detection: on a partial clone it fetches file contents per commit and scans took 30 seconds or timed out, while names-only history took under a second

## Assumptions

- Thresholds are initial guesses and are frozen only after a person rates the corpus report, as the spec requires
- Most useful modules are one level deep; very large workspace packages stay whole until a person splits them
- A repo whose subjects mostly end in a pull-request number is squash-merged, so co-change there groups whole pull requests
