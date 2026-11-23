---
id: dec_rqb1gc
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-13T21:29:08.691000Z'
justifies:
- packages/cli/src/reasonledger_cli/why_cmd.py::run_why
- packages/cli/src/reasonledger_cli/why_render.py::render_miss
watchers: []
context: '`why` on a path that is not a file in the repo printed the generic miss
  line and exited 0, so a typo read as "nothing recorded yet". The spec said "the
  error as today" and the CLI had no distinct error. What should the CLI do?'
choice: 'The CLI prints `error: no file at <path> in this repo (use a path relative
  to the repo root)` to stderr and exits 2, matching the UI''s no-file error. `--json`
  is unchanged (exit 0, path_exists false, nearby empty). The rest of dec_7uht0r (shared
  find_nearby, additive nearby key, near metric) stands.'
alternatives_rejected:
- 'Keep the generic miss line and append a note about the missing file: still exits
  0 and still reads as a miss, the trust bug S59 targets'
- 'Exit 2 for --json as well: breaks the rule that existing json shape and exit codes
  do not change for consumers'
assumptions: []
supersedes: dec_7uht0r
---

## Context

`why` on a path that is not a file in the repo printed the generic miss line and exited 0, so a typo read as "nothing recorded yet". The spec said "the error as today" and the CLI had no distinct error. What should the CLI do?

## Choice

The CLI prints `error: no file at <path> in this repo (use a path relative to the repo root)` to stderr and exits 2, matching the UI's no-file error. `--json` is unchanged (exit 0, path_exists false, nearby empty). The rest of dec_7uht0r (shared find_nearby, additive nearby key, near metric) stands.

## Alternatives rejected

- Keep the generic miss line and append a note about the missing file: still exits 0 and still reads as a miss, the trust bug S59 targets
- Exit 2 for --json as well: breaks the rule that existing json shape and exit codes do not change for consumers
