---
id: dec_b4j1by
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: active
proposed_by: human
justifies:
- packages/core/src/reasonledger_core/views/ledger.py::_decision_summary
- packages/core/src/reasonledger_core/sync/repo.py::first_commit_dates
- packages/core/src/reasonledger_core/decisions/service.py::build_decision_record
- packages/core/src/reasonledger_core/decisions/service.py::approve_decision
- packages/cli/src/reasonledger_cli/ui_assets/provenance.js:33-48
watchers: []
confidence: high
context: Recorded decisions carried no timestamp, and approved_by was stored but never
  shown, so a card could not say who recorded or approved a decision or when. New
  records can be stamped, but existing ones have no date in the file. What do the
  cards show, and what happens to old records?
choice: Add recorded_at and approved_at to the frontmatter, stamped by the caller
  at write time, and list recorded, approved, retired and superseded events with name
  and UTC time on every card. A record with no recorded_at shows the author date of
  the commit that added its file, fetched with one git log for the decisions directory
  and flagged recorded_at_from_git so the page labels it; with no commit it says the
  date was not recorded. Old files are not rewritten.
alternatives_rejected:
- 'Show nothing for old records: every decision made before this change would read
  as undated'
- 'A one-off backfill command writing git dates into the files: rewrites every old
  record and turns an inferred date into one that looks recorded'
- 'Default recorded_at to now when loading a record without one: a false date, which
  the decided_at field already forbids'
- 'File modification time: changes on checkout and clone'
assumptions:
- Decision files in this repo are committed; where a project gitignores them the fallback
  finds nothing and the card says so
- One git log over the decisions directory stays cheap at ledger scale and is skipped
  once every record carries its own date
---

## Context

Recorded decisions carried no timestamp, and approved_by was stored but never shown, so a card could not say who recorded or approved a decision or when. New records can be stamped, but existing ones have no date in the file. What do the cards show, and what happens to old records?

## Choice

Add recorded_at and approved_at to the frontmatter, stamped by the caller at write time, and list recorded, approved, retired and superseded events with name and UTC time on every card. A record with no recorded_at shows the author date of the commit that added its file, fetched with one git log for the decisions directory and flagged recorded_at_from_git so the page labels it; with no commit it says the date was not recorded. Old files are not rewritten.

## Alternatives rejected

- Show nothing for old records: every decision made before this change would read as undated
- A one-off backfill command writing git dates into the files: rewrites every old record and turns an inferred date into one that looks recorded
- Default recorded_at to now when loading a record without one: a false date, which the decided_at field already forbids
- File modification time: changes on checkout and clone

## Assumptions

- Decision files in this repo are committed; where a project gitignores them the fallback finds nothing and the card says so
- One git log over the decisions directory stays cheap at ledger scale and is skipped once every record carries its own date
