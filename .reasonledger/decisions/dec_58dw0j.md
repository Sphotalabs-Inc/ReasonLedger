---
id: dec_58dw0j
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-17T04:41:02.436665Z'
justifies:
- packages/core/src/reasonledger_core/privacy/pii_linter.py:16-43
- packages/core/src/reasonledger_core/privacy/pii_linter.py::lint_text
anchor_hashes:
  packages/core/src/reasonledger_core/privacy/pii_linter.py:16-43: sha256:0dc6fce231cccd4c
watchers: []
confidence: medium
context: 'The PII linter missed most real secrets (Anthropic sk-ant-, OpenAI sk-proj-,
  fine-grained GitHub, Slack, JWT, PEM headers) because its key pattern allowed only
  alphanumerics after sk-, yet blocked ordinary technical text: any 10-digit run,
  such as a Unix timestamp, read as a phone number, and an SSH remote URL read as
  an email. Agents recording legitimate decisions hit the false positives while real
  keys passed. How should the patterns change?'
choice: Widen the key pattern to one documented-prefix alternative per provider (plus
  a separate PEM private-key header rule), and tighten the phone rule to North American
  numbers written with separators or parentheses whose area code and exchange start
  2-9, so bare digit runs and grouped counts no longer match. An email whose user
  part is the SSH remote user is skipped. A secret with no recognisable shape, such
  as a bare AWS secret access key, is still not caught, and the module docstring says
  so.
alternatives_rejected:
- 'Add a generic high-entropy string detector: it would flag hashes, UUIDs, base64
  fixtures and commit shas that decisions routinely cite, so the false-positive problem
  would get worse'
- 'Keep phone matching on bare 10-digit runs and instead allowlist timestamps: an
  allowlist cannot enumerate every id or count format, while requiring formatting
  removes the whole class'
- 'Drop the phone rule entirely: a pasted support number is a real leak this linter
  exists to stop'
assumptions:
- Phone numbers worth blocking in decision text are written with separators; a bare
  10-digit number is more likely an id or timestamp
- Non-NANP international numbers were never covered and stay out of scope for this
  change
---

## Context

The PII linter missed most real secrets (Anthropic sk-ant-, OpenAI sk-proj-, fine-grained GitHub, Slack, JWT, PEM headers) because its key pattern allowed only alphanumerics after sk-, yet blocked ordinary technical text: any 10-digit run, such as a Unix timestamp, read as a phone number, and an SSH remote URL read as an email. Agents recording legitimate decisions hit the false positives while real keys passed. How should the patterns change?

## Choice

Widen the key pattern to one documented-prefix alternative per provider (plus a separate PEM private-key header rule), and tighten the phone rule to North American numbers written with separators or parentheses whose area code and exchange start 2-9, so bare digit runs and grouped counts no longer match. An email whose user part is the SSH remote user is skipped. A secret with no recognisable shape, such as a bare AWS secret access key, is still not caught, and the module docstring says so.

## Alternatives rejected

- Add a generic high-entropy string detector: it would flag hashes, UUIDs, base64 fixtures and commit shas that decisions routinely cite, so the false-positive problem would get worse
- Keep phone matching on bare 10-digit runs and instead allowlist timestamps: an allowlist cannot enumerate every id or count format, while requiring formatting removes the whole class
- Drop the phone rule entirely: a pasted support number is a real leak this linter exists to stop

## Assumptions

- Phone numbers worth blocking in decision text are written with separators; a bare 10-digit number is more likely an id or timestamp
- Non-NANP international numbers were never covered and stay out of scope for this change
