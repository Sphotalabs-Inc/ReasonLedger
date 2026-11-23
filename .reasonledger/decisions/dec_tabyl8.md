---
id: dec_tabyl8
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-12T18:18:08.247557Z'
justifies:
- packages/core/src/reasonledger_core/decisions/lifecycle.py::supersede_decision
- packages/core/src/reasonledger_core/decisions/service.py::superseded_by_map
- packages/core/src/reasonledger_core/models/decision.py::DecisionFrontmatter
- packages/core/src/reasonledger_core/privacy/pii_linter.py::lint_decision_text
- packages/core/src/reasonledger_core/decisions/identity_check.py:27-33
- packages/cli/src/reasonledger_cli/supersede_cmd.py::run_supersede_cmd
- packages/cli/src/reasonledger_cli/ui_approve.py::_supersede
- packages/cli/src/reasonledger_cli/ui_assets/ledger_list.js:33-73
- packages/cli/src/reasonledger_cli/ui_assets/review.js:28-35
- packages/cli/src/reasonledger_cli/ui_assets/review.js:104-117
anchor_hashes:
  packages/core/src/reasonledger_core/decisions/identity_check.py:27-33: sha256:30e47b3d862542a3
  packages/cli/src/reasonledger_cli/ui_assets/ledger_list.js:33-73: sha256:720c33b64590584d
  packages/cli/src/reasonledger_cli/ui_assets/review.js:28-35: sha256:f357c77dd016e492
  packages/cli/src/reasonledger_cli/ui_assets/review.js:104-117: sha256:8e6b31b8a060187f
watchers: []
context: A judged conflict in the UI offered one action, Dismiss as not a conflict,
  so a real clash between two decisions in force had no way out except finding one
  and retiring it. Superseding existed only as a side effect of recording a brand-new
  decision with supersedes set, and it stored no who, when or why. When a person looks
  at two existing decisions and picks the one that stands, how should the losing decision
  be recorded, and what should a conflict card offer?
choice: 'A new core action, supersede_decision, writes everything on the decision
  that lost: status superseded plus four optional frontmatter fields (superseded_by
  with the id of the one that stands, superseded_decided_by, superseded_at, superseded_reason).
  The decision that stands is only read, so a verdict it carries is never rewritten.
  A person and a reason are required, both decisions must be in force and different,
  the reason goes through the PII linter and the person''s name gets the same exemption
  as approved_by. superseded_by_map merges this with the existing successor-names-it
  route, so views, why and MCP hits show one successor either way. It is exposed as
  reasonledger supersede <id> --successor <id> --reason and as a third action on the
  UI decision endpoint, where the actor comes from the git identity. In the Review
  queue a conflict between two decisions in force shows Keep on each side, which opens
  the review dialog on the other decision in a supersede mode with a required reason;
  under a disclosure it also offers Retire for either one and a copyable prompt asking
  the coding agent to record a replacement. A pair with a proposal on one side keeps
  Dismiss only.'
alternatives_rejected:
- 'Retire the loser with a reason that names the winner: no format change, but the
  record would read retired, and why and the views would not point readers to the
  decision that stands'
- 'Write supersedes on the winner, reusing the existing field: it rewrites a record
  that may already be approved, stores no who, when or why, and fails when the winner
  already supersedes something'
- 'A separate append-only log of supersede events: a second place to read a decision''s
  state from, when every other transition lives in the record''s own frontmatter'
- 'Let Keep act on one click with a browser prompt for the reason: a verdict is given
  with the whole record in view (dec_be0usd), and the loser is the record being changed'
- 'Name the person field superseded_by to match retired_by: views, why and MCP hits
  already use superseded_by for the successor''s id'
- 'A UI form that records a brand-new replacing decision: the UI cannot author decisions
  today, and an agent with the code in view writes a better one'
assumptions:
- A successor must be in force, so a chain never ends on a decision that is itself
  retired or superseded at the time of choosing
- One successor per superseded decision is enough; when a new decision replaces both
  sides, the agent supersedes one and the person supersedes the other with the command
- Older files without the four fields load and round-trip unchanged, since all are
  optional and omitted when unset
---

## Context

A judged conflict in the UI offered one action, Dismiss as not a conflict, so a real clash between two decisions in force had no way out except finding one and retiring it. Superseding existed only as a side effect of recording a brand-new decision with supersedes set, and it stored no who, when or why. When a person looks at two existing decisions and picks the one that stands, how should the losing decision be recorded, and what should a conflict card offer?

## Choice

A new core action, supersede_decision, writes everything on the decision that lost: status superseded plus four optional frontmatter fields (superseded_by with the id of the one that stands, superseded_decided_by, superseded_at, superseded_reason). The decision that stands is only read, so a verdict it carries is never rewritten. A person and a reason are required, both decisions must be in force and different, the reason goes through the PII linter and the person's name gets the same exemption as approved_by. superseded_by_map merges this with the existing successor-names-it route, so views, why and MCP hits show one successor either way. It is exposed as reasonledger supersede <id> --successor <id> --reason and as a third action on the UI decision endpoint, where the actor comes from the git identity. In the Review queue a conflict between two decisions in force shows Keep on each side, which opens the review dialog on the other decision in a supersede mode with a required reason; under a disclosure it also offers Retire for either one and a copyable prompt asking the coding agent to record a replacement. A pair with a proposal on one side keeps Dismiss only.

## Alternatives rejected

- Retire the loser with a reason that names the winner: no format change, but the record would read retired, and why and the views would not point readers to the decision that stands
- Write supersedes on the winner, reusing the existing field: it rewrites a record that may already be approved, stores no who, when or why, and fails when the winner already supersedes something
- A separate append-only log of supersede events: a second place to read a decision's state from, when every other transition lives in the record's own frontmatter
- Let Keep act on one click with a browser prompt for the reason: a verdict is given with the whole record in view (dec_be0usd), and the loser is the record being changed
- Name the person field superseded_by to match retired_by: views, why and MCP hits already use superseded_by for the successor's id
- A UI form that records a brand-new replacing decision: the UI cannot author decisions today, and an agent with the code in view writes a better one

## Assumptions

- A successor must be in force, so a chain never ends on a decision that is itself retired or superseded at the time of choosing
- One successor per superseded decision is enough; when a new decision replaces both sides, the agent supersedes one and the person supersedes the other with the command
- Older files without the four fields load and round-trip unchanged, since all are optional and omitted when unset
