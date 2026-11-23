---
id: dec_g2ov5e
ai_tool: cursor
model: grok-4.7
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-15T05:58:33.398433Z'
justifies:
- packages/core/pyproject.toml:24
- packages/core/src/reasonledger_core/attestation/checkpoint.py::generate_signing_keypair
anchor_hashes:
  packages/core/pyproject.toml:24: sha256:dc6b1801198c3834
watchers: []
confidence: high
context: Dependabot's cryptography alerts need 50.0.0 or newer, but reasonledger-core
  publishes cryptography>=42.0,<45, and fastembed 0.8.0 requires pillow<13. What range
  should the published package require?
choice: Require cryptography>=50,<51 and lock 50.0.2. Lock the other alerted packages
  at or above their patched floors, including fastembed 0.9.1 so pillow 13.0.0 resolves.
alternatives_rejected:
- Keep cryptography>=42.0,<45 and only bump packages that pin allows. The cryptography
  alerts stay open.
- Require cryptography>=50 with no upper bound. That drops the exclusive ceiling this
  dependency already uses.
- Stay on cryptography 48.0.1, the last release with an Intel macOS wheel. It is still
  below the 50.0.0 floor.
- Leave fastembed at 0.8.0. That release requires pillow<13, so the Pillow alerts
  cannot clear.
assumptions:
- Ed25519 PEM sign and verify in checkpoint.py stays compatible on cryptography 50.
- cryptography 50 publishes no Intel macOS wheel, so that platform builds from source
  and needs rustc 1.83 or newer.
---

## Context

Dependabot's cryptography alerts need 50.0.0 or newer, but reasonledger-core publishes cryptography>=42.0,<45, and fastembed 0.8.0 requires pillow<13. What range should the published package require?

## Choice

Require cryptography>=50,<51 and lock 50.0.2. Lock the other alerted packages at or above their patched floors, including fastembed 0.9.1 so pillow 13.0.0 resolves.

## Alternatives rejected

- Keep cryptography>=42.0,<45 and only bump packages that pin allows. The cryptography alerts stay open.
- Require cryptography>=50 with no upper bound. That drops the exclusive ceiling this dependency already uses.
- Stay on cryptography 48.0.1, the last release with an Intel macOS wheel. It is still below the 50.0.0 floor.
- Leave fastembed at 0.8.0. That release requires pillow<13, so the Pillow alerts cannot clear.

## Assumptions

- Ed25519 PEM sign and verify in checkpoint.py stays compatible on cryptography 50.
- cryptography 50 publishes no Intel macOS wheel, so that platform builds from source and needs rustc 1.83 or newer.
