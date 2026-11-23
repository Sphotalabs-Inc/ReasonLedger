---
id: dec_bhl7vt
ai_tool: claude-code
model: claude-fable-5-2
oversight: pending
status: active
proposed_by: ai
justifies:
- packages/cli/src/reasonledger_cli/ui_identity.py::acting_as
- packages/cli/src/reasonledger_cli/ui_identity.py::handle_get_identity
- packages/cli/src/reasonledger_cli/ui_approve.py::handle_decision_action
- packages/cli/src/reasonledger_cli/ui_proposals.py::handle_confirm
- packages/cli/src/reasonledger_cli/approve_cmd.py::acting_identity
- packages/core/src/reasonledger_core/sync/repo.py::git_user_name
watchers: []
confidence: medium
context: The local UI asked the reviewer to type a name or handle in a browser prompt
  for approve, confirm, dismiss and the Organize actions, and the server stored whatever
  arrived. Anyone could approve as someone else, and every action cost an extra prompt.
  Where should the acting person's identity come from?
choice: The server reads user.name from the git config of the checkout it serves and
  ignores any identity in a request body. GET /api/identity tells the page who it
  is acting as. With no git identity the action is refused with the command that sets
  one; there is no typed fallback. The CLI keeps --by as an explicit override and
  defaults to the same git name. Git is the only source for now.
alternatives_rejected:
- 'An install-time choice of identity source: a config surface nobody has asked for,
  and every later reader of a record would need to know which source produced the
  name'
- 'The authenticated GitHub login from the gh CLI with git as fallback: stronger,
  but adds a subprocess dependency and behaves differently per machine'
- 'Keep the prompt and prefill it from git: least change, but a typed name is still
  accepted as evidence'
- 'Fall back to a typed name when git has none: reopens the hole in exactly the case
  nothing can vouch for the name'
assumptions:
- Each person approves from their own clone, so the checkout's git identity is that
  person; a shared machine or shared checkout breaks this
- 'git user.name is not authentication: it can be set to anything, so the trust is
  that of commit authorship, and the approval is published in a commit carrying the
  same name'
- The MCP record_decision approved_by parameter still takes a name from the agent;
  this decision covers the UI and CLI only
---

## Context

The local UI asked the reviewer to type a name or handle in a browser prompt for approve, confirm, dismiss and the Organize actions, and the server stored whatever arrived. Anyone could approve as someone else, and every action cost an extra prompt. Where should the acting person's identity come from?

## Choice

The server reads user.name from the git config of the checkout it serves and ignores any identity in a request body. GET /api/identity tells the page who it is acting as. With no git identity the action is refused with the command that sets one; there is no typed fallback. The CLI keeps --by as an explicit override and defaults to the same git name. Git is the only source for now.

## Alternatives rejected

- An install-time choice of identity source: a config surface nobody has asked for, and every later reader of a record would need to know which source produced the name
- The authenticated GitHub login from the gh CLI with git as fallback: stronger, but adds a subprocess dependency and behaves differently per machine
- Keep the prompt and prefill it from git: least change, but a typed name is still accepted as evidence
- Fall back to a typed name when git has none: reopens the hole in exactly the case nothing can vouch for the name

## Assumptions

- Each person approves from their own clone, so the checkout's git identity is that person; a shared machine or shared checkout breaks this
- git user.name is not authentication: it can be set to anything, so the trust is that of commit authorship, and the approval is published in a commit carrying the same name
- The MCP record_decision approved_by parameter still takes a name from the agent; this decision covers the UI and CLI only
