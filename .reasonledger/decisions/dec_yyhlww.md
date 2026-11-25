---
id: dec_yyhlww
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-25T05:27:06.241307Z'
justifies:
- AGENTS.md:135-143
- .cursor/rules/index.mdc:18-18
anchor_hashes:
  AGENTS.md:135-143: sha256:79f33ac432ca8115
  .cursor/rules/index.mdc:18-18: sha256:91f436c5568cfbe1
watchers: []
context: 'This repository''s decision ledger is published with it, and some records
  written while building it named work outside it: internal documents, test sessions
  and other projects. Should the ledger stay public as a working example of the product,
  and if so, what may a public record contain?'
choice: 'Keep the ledger public and keep capture mandatory, but limit each record
  to explaining code in this repository, in text a reader with only this repository
  can follow: no other repositories or projects, customers, testers or pilots, internal
  documents or their sections, or plans for work elsewhere. Decisions about work outside
  this repository are recorded where that work lives. The rule is in AGENTS.md section
  10 and summarised in the Cursor rule.'
alternatives_rejected:
- 'Stop tracking the ledger in this repository and keep it private: removes the live
  example of the product on its own code and leaves security-relevant code without
  its reasons'
- 'Keep publishing every record as written: lets records name work and people outside
  this repository'
- 'Rewrite public history to remove earlier records: breaks the release tags and every
  existing clone'
assumptions:
- Records already in public history stay there; the rule applies from now on
- Agents follow a charter rule stated in AGENTS.md and the always-applied Cursor rule
---

## Context

This repository's decision ledger is published with it, and some records written while building it named work outside it: internal documents, test sessions and other projects. Should the ledger stay public as a working example of the product, and if so, what may a public record contain?

## Choice

Keep the ledger public and keep capture mandatory, but limit each record to explaining code in this repository, in text a reader with only this repository can follow: no other repositories or projects, customers, testers or pilots, internal documents or their sections, or plans for work elsewhere. Decisions about work outside this repository are recorded where that work lives. The rule is in AGENTS.md section 10 and summarised in the Cursor rule.

## Alternatives rejected

- Stop tracking the ledger in this repository and keep it private: removes the live example of the product on its own code and leaves security-relevant code without its reasons
- Keep publishing every record as written: lets records name work and people outside this repository
- Rewrite public history to remove earlier records: breaks the release tags and every existing clone

## Assumptions

- Records already in public history stay there; the rule applies from now on
- Agents follow a charter rule stated in AGENTS.md and the always-applied Cursor rule
