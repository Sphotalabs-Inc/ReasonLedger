---
id: dec_legacy02
ai_tool: claude-code
model: claude-sonnet-4-5
oversight: reviewed
status: active
approved_by: iharpreet
justifies:
- app/store.py::open_store
watchers: []
confidence: high
context: Which store backs the cache?
choice: Use sqlite
alternatives_rejected:
- Postgres
assumptions:
- Single writer
---

## Context

Which store backs the cache?

## Choice

Use sqlite
