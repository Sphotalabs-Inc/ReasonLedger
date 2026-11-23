---
id: dec_auth01
ai_tool: cursor
model: composer
oversight: reviewed
justifies:
  - auth/session.py:10-40
context: User authentication session token strategy
choice: Stateless JWT access tokens
alternatives_rejected:
  - Server-side session store
---

## Context

User authentication session token strategy

## Choice

Stateless JWT access tokens
