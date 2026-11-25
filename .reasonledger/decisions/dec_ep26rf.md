---
id: dec_ep26rf
ai_tool: claude-code
model: claude-opus-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-22T06:40:02.451083Z'
justifies:
- packages/core/src/reasonledger_core/importer/scan.py::commit_sources
- packages/core/src/reasonledger_core/importer/scan.py:36-41
anchor_hashes:
  packages/core/src/reasonledger_core/importer/scan.py:36-41: sha256:fac235abecdb6a8c
watchers: []
context: Commit messages sent as repo_text carry Co-Authored-By and Signed-off-by
  trailers with names and emails. The consent text says author names are never sent,
  and with the new pre-send check every co-authored commit was held for an email (123
  of 123 on this repo). What should happen to those trailer lines?
choice: 'commit_sources removes every line of the form `<Word>-by: ...` (case-insensitive)
  before the length floor is measured and before the text is used, so person trailers
  neither count towards MIN_COMMIT_MESSAGE_CHARS nor leave the machine, and a commit
  whose body is only trailers is dropped.'
alternatives_rejected:
- Leave trailers in and let the pre-send check hold every co-authored commit
- Allow the trailer emails through the PII check as an exception
- Remove only the email inside each trailer and keep the name
assumptions:
- 'A prose line starting with a word ending in -by: is rare enough to lose'
---

## Context

Commit messages sent as repo_text carry Co-Authored-By and Signed-off-by trailers with names and emails. The consent text says author names are never sent, and with the new pre-send check every co-authored commit was held for an email (123 of 123 on this repo). What should happen to those trailer lines?

## Choice

commit_sources removes every line of the form `<Word>-by: ...` (case-insensitive) before the length floor is measured and before the text is used, so person trailers neither count towards MIN_COMMIT_MESSAGE_CHARS nor leave the machine, and a commit whose body is only trailers is dropped.

## Alternatives rejected

- Leave trailers in and let the pre-send check hold every co-authored commit
- Allow the trailer emails through the PII check as an exception
- Remove only the email inside each trailer and keep the name

## Assumptions

- A prose line starting with a word ending in -by: is rare enough to lose
