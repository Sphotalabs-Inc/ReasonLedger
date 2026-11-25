---
id: dec_mue8jk
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-25T05:38:36.064437Z'
justifies:
- packages/mcp/pyproject.toml:26-28
- packages/mcp/tests/test_mcp_packaging.py::test_intel_macs_are_held_to_a_cryptography_with_a_wheel
anchor_hashes:
  packages/mcp/pyproject.toml:26-28: sha256:b76de914c055f5df
watchers: []
context: reasonledger-mcp depends on mcp, which requires pyjwt[crypto] and so cryptography.
  cryptography 49 and later ship no Intel macOS wheel, so on an Intel Mac pip and
  uv build it from source and the install fails unless Rust 1.83 or newer is present.
  How should the package make a plain install work there?
choice: Declare `cryptography<49; sys_platform == 'darwin' and platform_machine ==
  'x86_64'` in reasonledger-mcp, the package that brings mcp in. Only Intel Macs are
  held back, to 48.x which still ships the wheel; every other platform resolves the
  current release. A packaging test checks the marker applies on Intel macOS only
  and that the bound admits 48.0.1 and excludes 49.0.0.
alternatives_rejected:
- 'Document that Intel Mac users need Rust 1.83+: most testers would hit a long build
  error first and leave'
- 'Cap cryptography below 49 on every platform: holds all users on an older release
  for one platform''s sake'
- 'Drop the dependency on mcp and implement the stdio protocol ourselves: a large
  rewrite of a working server for a packaging problem'
assumptions:
- The stdio MCP server does not use the parts of mcp that need features from cryptography
  49+
- Lift the cap once cryptography ships an Intel macOS wheel again or Intel Macs stop
  mattering
---

## Context

reasonledger-mcp depends on mcp, which requires pyjwt[crypto] and so cryptography. cryptography 49 and later ship no Intel macOS wheel, so on an Intel Mac pip and uv build it from source and the install fails unless Rust 1.83 or newer is present. How should the package make a plain install work there?

## Choice

Declare `cryptography<49; sys_platform == 'darwin' and platform_machine == 'x86_64'` in reasonledger-mcp, the package that brings mcp in. Only Intel Macs are held back, to 48.x which still ships the wheel; every other platform resolves the current release. A packaging test checks the marker applies on Intel macOS only and that the bound admits 48.0.1 and excludes 49.0.0.

## Alternatives rejected

- Document that Intel Mac users need Rust 1.83+: most testers would hit a long build error first and leave
- Cap cryptography below 49 on every platform: holds all users on an older release for one platform's sake
- Drop the dependency on mcp and implement the stdio protocol ourselves: a large rewrite of a working server for a packaging problem

## Assumptions

- The stdio MCP server does not use the parts of mcp that need features from cryptography 49+
- Lift the cap once cryptography ships an Intel macOS wheel again or Intel Macs stop mattering
