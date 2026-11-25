---
id: dec_wsze1b
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-25T04:30:34.791658Z'
justifies:
- scripts/check_release_tag.py::sibling_pins
- scripts/check_release_tag.py::check_pins
- packages/cli/pyproject.toml:25-33
- packages/mcp/pyproject.toml:23-26
anchor_hashes:
  packages/cli/pyproject.toml:25-33: sha256:331daf66058c1453
  packages/mcp/pyproject.toml:23-26: sha256:2c7912b6610567ea
watchers: []
context: The CLI and MCP packages required their siblings as `>=0.3.0a1,<0.4.0`. Installing
  a new CLI over an existing older core left core behind with no warning, a pairing
  no release was tested as. How tightly should the three lockstep packages require
  each other?
choice: Pin every sibling requirement, the embeddings extra included, to exactly the
  release version (`==X`). check_release_tag.py gains sibling_pins/check_pins and
  refuses a tag while any pin differs from it; test_dist_packaging derives the expected
  pins from the CLI version.
alternatives_rejected:
- 'Keep the range and rely on verify_published pinning siblings with --with: only
  protects the post-publish check, not users who upgrade one package'
- 'Raise the range floor to the current version each release (>=X,<0.4.0): still lets
  a newer core pair with an older CLI'
- 'Bump pins by hand without a gate: the next release that forgets one ships a loose
  pin'
assumptions:
- The three packages are always released together at one version, as check_tag already
  enforces
- No one needs to install a core patch without a matching CLI release
---

## Context

The CLI and MCP packages required their siblings as `>=0.3.0a1,<0.4.0`. Installing a new CLI over an existing older core left core behind with no warning, a pairing no release was tested as. How tightly should the three lockstep packages require each other?

## Choice

Pin every sibling requirement, the embeddings extra included, to exactly the release version (`==X`). check_release_tag.py gains sibling_pins/check_pins and refuses a tag while any pin differs from it; test_dist_packaging derives the expected pins from the CLI version.

## Alternatives rejected

- Keep the range and rely on verify_published pinning siblings with --with: only protects the post-publish check, not users who upgrade one package
- Raise the range floor to the current version each release (>=X,<0.4.0): still lets a newer core pair with an older CLI
- Bump pins by hand without a gate: the next release that forgets one ships a loose pin

## Assumptions

- The three packages are always released together at one version, as check_tag already enforces
- No one needs to install a core patch without a matching CLI release
