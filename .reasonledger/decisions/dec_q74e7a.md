---
id: dec_q74e7a
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-17T05:01:30.870121Z'
justifies:
- SECURITY.md:12
- tests/test_legal_files.py::test_security_policy_names_a_reporting_address
- tests/test_legal_files.py::test_license_copies_are_identical
anchor_hashes:
  SECURITY.md:12: sha256:88d0a8c2ba16f69e
watchers: []
confidence: high
context: dec_41f1lh chose a placeholder in SECURITY.md plus a release-gate check that
  failed while the placeholder remained. The maintainer has now supplied the reporting
  address, so the placeholder and its gate are transitional code with nothing left
  to guard. How should the policy file's contact stay trustworthy from here?
choice: SECURITY.md carries the real address, the placeholder token and its release_gate.sh
  check are removed, and a phase_3 test requires SECURITY.md to contain an email address,
  so a later edit cannot leave reporters with no contact. NOTICE stays a real file
  duplicated at the root and in each package, pinned identical by test, because a
  symlink escapes the sdist.
alternatives_rejected:
- 'Keep the placeholder check in release_gate.sh: the token no longer exists, so the
  check would be dead code that guards against a state that was only transitional'
- 'Pin the exact address in a test: the address will change over time and the test
  would fail for a legitimate edit, while requiring any address catches the real failure
  of having none'
- 'Symlink the package NOTICE files to the root copy: the earlier LICENSE symlinks
  made uv build fail and shipped dangling links in sdists'
assumptions:
- A generic address pattern in SECURITY.md is enough to show a contact exists; whether
  the mailbox is monitored is the maintainer's responsibility
supersedes: dec_41f1lh
---

## Context

dec_41f1lh chose a placeholder in SECURITY.md plus a release-gate check that failed while the placeholder remained. The maintainer has now supplied the reporting address, so the placeholder and its gate are transitional code with nothing left to guard. How should the policy file's contact stay trustworthy from here?

## Choice

SECURITY.md carries the real address, the placeholder token and its release_gate.sh check are removed, and a phase_3 test requires SECURITY.md to contain an email address, so a later edit cannot leave reporters with no contact. NOTICE stays a real file duplicated at the root and in each package, pinned identical by test, because a symlink escapes the sdist.

## Alternatives rejected

- Keep the placeholder check in release_gate.sh: the token no longer exists, so the check would be dead code that guards against a state that was only transitional
- Pin the exact address in a test: the address will change over time and the test would fail for a legitimate edit, while requiring any address catches the real failure of having none
- Symlink the package NOTICE files to the root copy: the earlier LICENSE symlinks made uv build fail and shipped dangling links in sdists

## Assumptions

- A generic address pattern in SECURITY.md is enough to show a contact exists; whether the mailbox is monitored is the maintainer's responsibility
