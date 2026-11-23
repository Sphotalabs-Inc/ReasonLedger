---
id: dec_retry01
ai_tool: cursor
oversight: reviewed
justifies:
  - src/payments/retry.ts:3-6
context: Retry backoff strategy for payment webhook delivery
choice: Exponential backoff with jitter
---

## Choice

Exponential backoff with jitter
