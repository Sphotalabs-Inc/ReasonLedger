---
id: dec_jxy5na
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-13T20:33:19.737052Z'
justifies:
- scripts/verify_published.py::index_env
- scripts/verify_published.py::mcp_exchange
- .github/workflows/release.yml:107-130
anchor_hashes:
  .github/workflows/release.yml:107-130: sha256:2c67237a6f4d1edf
watchers: []
context: The release workflow needs a post-publish check on Linux, macOS and Windows
  runners that have only uv installed. What should the check be written in, and how
  does it point at TestPyPI versus PyPI?
choice: One stdlib-only Python script run with `uv run --no-project python`, which
  sets UV_INDEX_URL, UV_EXTRA_INDEX_URL and UV_INDEX_STRATEGY in the environment so
  every uvx call, including the MCP command init wrote, inherits the index. Its decision
  logic is plain functions unit-tested without network.
alternatives_rejected:
- 'A bash script: the Windows runner path and quoting differ and the logic could not
  be unit-tested here'
- 'Per-OS workflow steps with inline YAML shell: three copies to drift, untestable'
- 'Index flags on each uvx command line: the MCP command written by init would not
  inherit them on TestPyPI'
assumptions: []
---

## Context

The release workflow needs a post-publish check on Linux, macOS and Windows runners that have only uv installed. What should the check be written in, and how does it point at TestPyPI versus PyPI?

## Choice

One stdlib-only Python script run with `uv run --no-project python`, which sets UV_INDEX_URL, UV_EXTRA_INDEX_URL and UV_INDEX_STRATEGY in the environment so every uvx call, including the MCP command init wrote, inherits the index. Its decision logic is plain functions unit-tested without network.

## Alternatives rejected

- A bash script: the Windows runner path and quoting differ and the logic could not be unit-tested here
- Per-OS workflow steps with inline YAML shell: three copies to drift, untestable
- Index flags on each uvx command line: the MCP command written by init would not inherit them on TestPyPI
