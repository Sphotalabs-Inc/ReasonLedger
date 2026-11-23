---
id: dec_queue01
ai_tool: claude-code
oversight: reviewed
justifies:
  - jobs/queue.py:1-25
context: Background job queue for outbound email delivery
choice: Redis-backed task queue
alternatives_rejected:
  - Cron polling the database
---

## Context

Background job queue for outbound email delivery

## Choice

Redis-backed task queue
