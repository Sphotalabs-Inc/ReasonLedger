---
id: dec_2rayr9
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-22T06:08:56.165161Z'
justifies:
- .github/workflows/release.yml:37
- .github/workflows/release.yml:61-67
- tests/test_release_workflow.py::test_a_manual_run_cannot_choose_pypi
- tests/test_release_workflow.py::test_a_tag_must_be_on_main_before_anything_is_tested_or_built
anchor_hashes:
  .github/workflows/release.yml:37: sha256:cad6a871fdcebc83
  .github/workflows/release.yml:61-67: sha256:1d71b50943920715
watchers: []
context: The release workflow let a manual run pick `pypi` from any branch and accepted
  a tag on any commit, so the only barrier to publishing unreviewed code was an optional
  GitHub environment reviewer. How should the ways to reach PyPI be limited, in code
  the repo can test rather than in settings it cannot see?
choice: 'A manual run takes no inputs and always targets TestPyPI: INDEX and every
  publish job''s environment are derived from the event, so only a tag push resolves
  to the pypi, pypi-core or pypi-mcp environments. On a tag push the gate job fetches
  full history and refuses the run unless the tagged commit is an ancestor of origin/main.
  Required reviewers on the three pypi* environments stay a documented one-time setting,
  as a second barrier rather than the only one. tests/test_release_workflow.py reads
  the parsed workflow to pin all of it.'
alternatives_rejected:
- 'Keep the pypi option on manual runs and add a branch check: it leaves a second
  route to PyPI that the documented procedure never uses, and a check on it can be
  edited away in the same dispatch'
- 'Rely on required reviewers on the pypi* environments alone: that is repository
  configuration, not versioned, tested or visible in review, and the three pypi* environments
  did not exist when this was decided'
- 'Constrain the PyPI trusted publisher to the main branch: a publisher binds repository,
  workflow and environment, not a ref, so it cannot express this'
assumptions:
- Releases are cut by pushing a v* tag for a commit that is already on main
- A hotfix goes out the same way, as the next pre-release from main
---

## Context

The release workflow let a manual run pick `pypi` from any branch and accepted a tag on any commit, so the only barrier to publishing unreviewed code was an optional GitHub environment reviewer. How should the ways to reach PyPI be limited, in code the repo can test rather than in settings it cannot see?

## Choice

A manual run takes no inputs and always targets TestPyPI: INDEX and every publish job's environment are derived from the event, so only a tag push resolves to the pypi, pypi-core or pypi-mcp environments. On a tag push the gate job fetches full history and refuses the run unless the tagged commit is an ancestor of origin/main. Required reviewers on the three pypi* environments stay a documented one-time setting, as a second barrier rather than the only one. tests/test_release_workflow.py reads the parsed workflow to pin all of it.

## Alternatives rejected

- Keep the pypi option on manual runs and add a branch check: it leaves a second route to PyPI that the documented procedure never uses, and a check on it can be edited away in the same dispatch
- Rely on required reviewers on the pypi* environments alone: that is repository configuration, not versioned, tested or visible in review, and the three pypi* environments did not exist when this was decided
- Constrain the PyPI trusted publisher to the main branch: a publisher binds repository, workflow and environment, not a ref, so it cannot express this

## Assumptions

- Releases are cut by pushing a v* tag for a commit that is already on main
- A hotfix goes out the same way, as the next pre-release from main
