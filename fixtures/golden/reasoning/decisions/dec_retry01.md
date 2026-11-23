---
id: dec_retry01
ai_tool: claude-code
model: claude-opus-4-8
oversight: reviewed
justifies:
  - payments/retry.py:40-72
context: Retry backoff strategy for payment webhook delivery
choice: Exponential backoff with jitter
alternatives_rejected:
  - Fixed interval retries
assumptions:
  - Webhook provider is at-least-once
---

## Context

Retry backoff strategy for payment webhook delivery

## Choice

Exponential backoff with jitter
