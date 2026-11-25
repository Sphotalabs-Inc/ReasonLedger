---
id: dec_q9lj3d
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-25T05:38:36.119621Z'
justifies:
- packages/core/src/reasonledger_core/reasoning/embeddings.py:33-39
anchor_hashes:
  packages/core/src/reasonledger_core/reasoning/embeddings.py:33-39: sha256:49ec09b78a709836
watchers: []
context: The message shown when the local embedder is missing told users to run `pip
  install 'reasonledger[embeddings]'`. While every release is a pre-release, pip skips
  them unless one is named, so the command found nothing. How should the hint name
  what to install?
choice: 'Name the exact installed release: the hint is built from the reasonledger-core
  version (the three packages are released together), so it reads `pip install ''reasonledger[embeddings]==<this
  version>''`. A test checks it matches the installed version.'
alternatives_rejected:
- 'Add --pre to the command: once a stable release exists it would also admit pre-releases
  of every dependency'
- 'Keep the bare command and wait for a stable release: the hint stays broken for
  every alpha tester'
- 'Point only at the install docs: one more step for a fix that fits on one line'
assumptions:
- reasonledger-core and reasonledger always share a version, as the release tag check
  enforces
---

## Context

The message shown when the local embedder is missing told users to run `pip install 'reasonledger[embeddings]'`. While every release is a pre-release, pip skips them unless one is named, so the command found nothing. How should the hint name what to install?

## Choice

Name the exact installed release: the hint is built from the reasonledger-core version (the three packages are released together), so it reads `pip install 'reasonledger[embeddings]==<this version>'`. A test checks it matches the installed version.

## Alternatives rejected

- Add --pre to the command: once a stable release exists it would also admit pre-releases of every dependency
- Keep the bare command and wait for a stable release: the hint stays broken for every alpha tester
- Point only at the install docs: one more step for a fix that fits on one line

## Assumptions

- reasonledger-core and reasonledger always share a version, as the release tag check enforces
