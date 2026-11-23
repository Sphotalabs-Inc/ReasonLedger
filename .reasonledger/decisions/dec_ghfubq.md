---
id: dec_ghfubq
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-13T06:03:46.536783Z'
justifies:
- packages/core/src/reasonledger_core/decisions/format.py::decision_filename
- packages/core/src/reasonledger_core/decisions/format.py::DecisionIdError
- packages/core/src/reasonledger_core/decisions/service.py::record_decision_to_path
- packages/mcp/src/reasonledger_mcp/tools.py::call_record_decision
watchers: []
context: A decision id from an MCP caller became a file name unchecked, so a crafted
  id could write or overwrite a Markdown file outside .reasonledger/decisions. Where
  should ids be validated, and what should a clash do?
choice: decision_filename, the one place an id becomes a path, accepts only dec_ followed
  by lowercase letters, digits or underscore and raises DecisionIdError otherwise.
  record_decision_to_path refuses to write over an existing file with the same error,
  and the MCP tool returns both as ok:false. The pattern is not put on DecisionFrontmatter.id,
  so in-memory records and the labelled conflict corpus keep short ids.
alternatives_rejected:
- 'Pydantic pattern on DecisionFrontmatter.id and RecordDecisionInput.decision_id:
  breaks the golden conflict corpus and many fixtures that use ids like x, and raises
  ValidationError past the tool''s error handling'
- 'Resolve the path and check it stays inside the decisions folder only: still permits
  overwriting any existing record and odd names inside the folder'
assumptions:
- Real ids are generated as dec_ plus six alphanumerics, or dec_ plus a hash, so the
  pattern admits every id the product creates
---

## Context

A decision id from an MCP caller became a file name unchecked, so a crafted id could write or overwrite a Markdown file outside .reasonledger/decisions. Where should ids be validated, and what should a clash do?

## Choice

decision_filename, the one place an id becomes a path, accepts only dec_ followed by lowercase letters, digits or underscore and raises DecisionIdError otherwise. record_decision_to_path refuses to write over an existing file with the same error, and the MCP tool returns both as ok:false. The pattern is not put on DecisionFrontmatter.id, so in-memory records and the labelled conflict corpus keep short ids.

## Alternatives rejected

- Pydantic pattern on DecisionFrontmatter.id and RecordDecisionInput.decision_id: breaks the golden conflict corpus and many fixtures that use ids like x, and raises ValidationError past the tool's error handling
- Resolve the path and check it stays inside the decisions folder only: still permits overwriting any existing record and odd names inside the folder

## Assumptions

- Real ids are generated as dec_ plus six alphanumerics, or dec_ plus a hash, so the pattern admits every id the product creates
