---
id: dec_41f1lh
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-17T04:51:32.788026Z'
justifies:
- scripts/release_gate.sh:13-18
- SECURITY.md:12
- tests/test_legal_files.py::test_license_copies_are_identical
anchor_hashes:
  scripts/release_gate.sh:13-18: sha256:f338b4f5e2bece33
  SECURITY.md:12: sha256:d0cf2a7edc513090
watchers: []
confidence: high
context: Spec 16 S54 requires a SECURITY.md with a private reporting address that
  only the maintainer can supply, and the README must link to it. Until the address
  exists, what should the file say, and what stops it being published unfinished?
choice: Commit SECURITY.md with an obvious placeholder token in place of the address,
  and make scripts/release_gate.sh fail while the token is present. The pytest suite
  stays green so CI and day-to-day work are not blocked, but a release cannot be cut
  with the placeholder. NOTICE is a real file duplicated at the root and in each package,
  pinned identical by test, because a symlink escapes the sdist.
alternatives_rejected:
- 'Invent or reuse an address found in the repo or git identity: a reporting contact
  is a public commitment only the maintainer can make, and a wrong address silently
  drops reports'
- 'Make a pytest fail while the placeholder remains: it would turn CI red for every
  unrelated change until the maintainer acts'
- 'Leave SECURITY.md out until the address exists: the README and spec require it,
  and nothing would remind the maintainer before release'
- 'Symlink the package NOTICE files to the root copy: the earlier LICENSE symlinks
  made uv build fail and shipped dangling links in sdists'
assumptions:
- The maintainer runs release_gate.sh before every upload, as docs/releasing.md requires
---

## Context

Spec 16 S54 requires a SECURITY.md with a private reporting address that only the maintainer can supply, and the README must link to it. Until the address exists, what should the file say, and what stops it being published unfinished?

## Choice

Commit SECURITY.md with an obvious placeholder token in place of the address, and make scripts/release_gate.sh fail while the token is present. The pytest suite stays green so CI and day-to-day work are not blocked, but a release cannot be cut with the placeholder. NOTICE is a real file duplicated at the root and in each package, pinned identical by test, because a symlink escapes the sdist.

## Alternatives rejected

- Invent or reuse an address found in the repo or git identity: a reporting contact is a public commitment only the maintainer can make, and a wrong address silently drops reports
- Make a pytest fail while the placeholder remains: it would turn CI red for every unrelated change until the maintainer acts
- Leave SECURITY.md out until the address exists: the README and spec require it, and nothing would remind the maintainer before release
- Symlink the package NOTICE files to the root copy: the earlier LICENSE symlinks made uv build fail and shipped dangling links in sdists

## Assumptions

- The maintainer runs release_gate.sh before every upload, as docs/releasing.md requires
