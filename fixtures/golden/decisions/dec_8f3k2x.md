---
id: dec_8f3k2x
ai_tool: claude-code
model: claude-opus-4-8
oversight: reviewed
approved_by: alice@acme.com
justifies:
  - payments/retry.py:40-72
confidence: high
context: Choose retry backoff for payment webhooks
choice: Exponential backoff with jitter
alternatives_rejected:
  - Fixed interval retries
assumptions:
  - Webhook provider is at-least-once
---

## Context

Choose retry backoff for payment webhooks

## Choice

Exponential backoff with jitter

## Alternatives rejected

- Fixed interval retries

## Assumptions

- Webhook provider is at-least-once
