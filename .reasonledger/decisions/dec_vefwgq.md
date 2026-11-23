---
id: dec_vefwgq
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-22T06:08:56.248846Z'
justifies:
- scripts/check_dists.sh:20
- .github/workflows/release.yml:73-76
- tests/test_release_workflow.py::test_the_gate_uploads_the_files_it_tested_rather_than_building_again
anchor_hashes:
  scripts/check_dists.sh:20: sha256:c4c35a43ec425114
  .github/workflows/release.yml:73-76: sha256:0644e46aaf08e2eb
watchers: []
context: release_gate.sh and check_dists.sh built and tested the three packages in
  a temporary directory, then the workflow built them again into dist/ and uploaded
  that second build, so the files that reached PyPI were never the files that had
  been installed and exercised. How should the tested artifacts and the uploaded artifacts
  be made the same?
choice: check_dists.sh takes an optional DIST_DIR and builds into it instead of its
  temporary directory, leaving the files there. The release workflow sets DIST_DIR
  to dist/ on the gate step, drops its separate build step, and uploads that directory,
  so the wheels and sdists installed and driven by the script are byte for byte the
  ones published. Locally DIST_DIR is unset and nothing is left behind.
alternatives_rejected:
- 'Keep the second build and assert the two builds are identical: it depends on the
  build being reproducible and still tests files other than the ones uploaded'
- 'Run the dist assertions again on dist/ in a separate step: it duplicates the legal-file,
  ui_assets and install checks in two places that can drift'
- 'Download the uploaded artifact in a separate job and run check_dists.sh on it:
  it adds a job and an artifact round trip without testing anything the shared directory
  does not'
assumptions:
- The gate job runs in a fresh checkout, so dist/ starts empty and check_dists.sh
  finds exactly three sdists and three wheels
---

## Context

release_gate.sh and check_dists.sh built and tested the three packages in a temporary directory, then the workflow built them again into dist/ and uploaded that second build, so the files that reached PyPI were never the files that had been installed and exercised. How should the tested artifacts and the uploaded artifacts be made the same?

## Choice

check_dists.sh takes an optional DIST_DIR and builds into it instead of its temporary directory, leaving the files there. The release workflow sets DIST_DIR to dist/ on the gate step, drops its separate build step, and uploads that directory, so the wheels and sdists installed and driven by the script are byte for byte the ones published. Locally DIST_DIR is unset and nothing is left behind.

## Alternatives rejected

- Keep the second build and assert the two builds are identical: it depends on the build being reproducible and still tests files other than the ones uploaded
- Run the dist assertions again on dist/ in a separate step: it duplicates the legal-file, ui_assets and install checks in two places that can drift
- Download the uploaded artifact in a separate job and run check_dists.sh on it: it adds a job and an artifact round trip without testing anything the shared directory does not

## Assumptions

- The gate job runs in a fresh checkout, so dist/ starts empty and check_dists.sh finds exactly three sdists and three wheels
