---
id: dec_4q4uig
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-22T05:06:26.499678Z'
justifies:
- scripts/check_release_tag.py::check_tag
- scripts/check_release_tag.py::package_versions
- .github/workflows/release.yml:36-43
- tests/test_check_release_tag.py::test_the_workflow_runs_the_check_on_tag_pushes_before_building
anchor_hashes:
  .github/workflows/release.yml:36-43: sha256:1f1b209f42735e6b
watchers: []
context: The release workflow publishes the version in pyproject.toml, not the one
  in the pushed tag, so a tag such as v0.3.0a6 on a tree still at 0.3.0a5 would upload
  0.3.0a5 and only fail afterwards in the verify job. Where should the tag-versus-version
  check live, and how strict should it be?
choice: A stdlib-only script, scripts/check_release_tag.py, whose pure check_tag function
  takes the tag and the three declared versions. The gate job runs it first on tag
  pushes only, passing $GITHUB_REF_NAME. It requires the tag to be exactly v plus
  one version shared by core, cli and mcp, with plain string equality and no PEP 440
  normalisation, and a phase_3 test pins both the logic and the workflow wiring.
alternatives_rejected:
- 'Inline bash in the workflow step comparing the tag with a grep of pyproject.toml:
  untestable offline and fragile to quoting in TOML'
- 'Comparing under PEP 440 normalisation so v0.3.0-alpha5 would match 0.3.0a5: the
  verify job and the docs use the literal string, so a looser match would let a tag
  through that verify then rejects'
- 'Having the publish jobs read the tag and override the version at build time: it
  would publish a version no commit declares, which breaks the lockstep range pinned
  by test_dist_packaging'
- 'Relying on the verify job alone: it only fails after the wrong version is already
  on PyPI, where a number cannot be reused'
assumptions:
- Tags are always v plus the literal version string the packages declare
- The three packages stay in lockstep, as docs/releasing.md requires
---

## Context

The release workflow publishes the version in pyproject.toml, not the one in the pushed tag, so a tag such as v0.3.0a6 on a tree still at 0.3.0a5 would upload 0.3.0a5 and only fail afterwards in the verify job. Where should the tag-versus-version check live, and how strict should it be?

## Choice

A stdlib-only script, scripts/check_release_tag.py, whose pure check_tag function takes the tag and the three declared versions. The gate job runs it first on tag pushes only, passing $GITHUB_REF_NAME. It requires the tag to be exactly v plus one version shared by core, cli and mcp, with plain string equality and no PEP 440 normalisation, and a phase_3 test pins both the logic and the workflow wiring.

## Alternatives rejected

- Inline bash in the workflow step comparing the tag with a grep of pyproject.toml: untestable offline and fragile to quoting in TOML
- Comparing under PEP 440 normalisation so v0.3.0-alpha5 would match 0.3.0a5: the verify job and the docs use the literal string, so a looser match would let a tag through that verify then rejects
- Having the publish jobs read the tag and override the version at build time: it would publish a version no commit declares, which breaks the lockstep range pinned by test_dist_packaging
- Relying on the verify job alone: it only fails after the wrong version is already on PyPI, where a number cannot be reused

## Assumptions

- Tags are always v plus the literal version string the packages declare
- The three packages stay in lockstep, as docs/releasing.md requires
