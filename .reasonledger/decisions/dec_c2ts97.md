---
id: dec_c2ts97
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-17T05:25:14.566808Z'
justifies:
- packages/core/src/reasonledger_core/__init__.py:1-25
- packages/cli/tests/test_open_core_boundary.py::test_core_wheel_has_no_org_rollup_modules
- .github/workflows/ci.yml:33-65
anchor_hashes:
  packages/core/src/reasonledger_core/__init__.py:1-25: sha256:cf7a8b446f77c3d6
  .github/workflows/ci.yml:33-65: sha256:b3c5eb9fff5cd269
watchers: []
confidence: high
context: After the open-core split, reasonledger-core still shipped org-level coverage
  rollups (coverage/, models/coverage.py) and an audit report with an "Organization:"
  heading (audit/). No CLI command or MCP tool called them; they were exported from
  the package root and exercised only by Phase 1 tests. Spec 16 S55.5 had kept them
  in core. Should they stay in the first published release?
choice: Remove coverage/, audit/ and models/coverage.py with their four test files
  and two golden folders, drop CoverageMetrics and compute_coverage_metrics from the
  package root, and drop the two modules from the CI phase 1 and 2 coverage flags.
  Provenance, oversight, ingest, paths and policy stay, since check --policy and the
  Phase 1 suite still use them. A wheel test now pins that the removed modules are
  absent, and spec 16 S55.5 and spec 01 carry a dated amendment.
alternatives_rejected:
- 'Keep them as the free half of a future hosted dashboard: they are org-shaped code
  with no caller, published under Apache-2.0 for good, and a future team product can
  reimplement them from the records'
- 'Move them to a CLI command such as reasonledger report so they are reachable: that
  adds a feature and a public surface the developer-first release does not need'
- 'Leave them and mark them experimental: dead code in a published wheel still counts
  as API for anyone who imports it, and the charter says to delete what is unused'
assumptions:
- No external user depends on these functions, since only TestPyPI pre-releases carried
  them
- 'ingest, oversight, provenance, paths and harvest are a separate question: they
  are also unreachable from the CLI and MCP but are the Phase 1 provenance scan that
  spec 00 lists as free'
---

## Context

After the open-core split, reasonledger-core still shipped org-level coverage rollups (coverage/, models/coverage.py) and an audit report with an "Organization:" heading (audit/). No CLI command or MCP tool called them; they were exported from the package root and exercised only by Phase 1 tests. Spec 16 S55.5 had kept them in core. Should they stay in the first published release?

## Choice

Remove coverage/, audit/ and models/coverage.py with their four test files and two golden folders, drop CoverageMetrics and compute_coverage_metrics from the package root, and drop the two modules from the CI phase 1 and 2 coverage flags. Provenance, oversight, ingest, paths and policy stay, since check --policy and the Phase 1 suite still use them. A wheel test now pins that the removed modules are absent, and spec 16 S55.5 and spec 01 carry a dated amendment.

## Alternatives rejected

- Keep them as the free half of a future hosted dashboard: they are org-shaped code with no caller, published under Apache-2.0 for good, and a future team product can reimplement them from the records
- Move them to a CLI command such as reasonledger report so they are reachable: that adds a feature and a public surface the developer-first release does not need
- Leave them and mark them experimental: dead code in a published wheel still counts as API for anyone who imports it, and the charter says to delete what is unused

## Assumptions

- No external user depends on these functions, since only TestPyPI pre-releases carried them
- ingest, oversight, provenance, paths and harvest are a separate question: they are also unreachable from the CLI and MCP but are the Phase 1 provenance scan that spec 00 lists as free
