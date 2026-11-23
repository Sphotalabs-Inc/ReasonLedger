---
id: dec_o86w22
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-23T03:57:51.318009Z'
justifies:
- scripts/verify_published.py::_stop
- scripts/verify_published.py::verify
watchers: []
context: Windows verify job crashed removing its temp directory because the MCP server
  started through uvx outlived proc.kill() with that directory as its cwd. How should
  the verifier end the server?
choice: Close stdin and wait a bounded grace period for a clean exit, then kill the
  whole process tree (taskkill /T on Windows), and run the server from the work directory
  instead of the repo.
alternatives_rejected:
- 'TemporaryDirectory(ignore_cleanup_errors=True): hides the leaked server process
  instead of ending it'
- 'proc.kill() only, as before: kills the uvx launcher and leaves the real server
  alive'
- 'Retrying the directory removal in a loop: papers over a live process'
assumptions:
- The stdio MCP server exits on stdin EOF
- init writes --repo-root explicitly, so the server does not need the repo as its
  cwd
---

## Context

Windows verify job crashed removing its temp directory because the MCP server started through uvx outlived proc.kill() with that directory as its cwd. How should the verifier end the server?

## Choice

Close stdin and wait a bounded grace period for a clean exit, then kill the whole process tree (taskkill /T on Windows), and run the server from the work directory instead of the repo.

## Alternatives rejected

- TemporaryDirectory(ignore_cleanup_errors=True): hides the leaked server process instead of ending it
- proc.kill() only, as before: kills the uvx launcher and leaves the real server alive
- Retrying the directory removal in a loop: papers over a live process

## Assumptions

- The stdio MCP server exits on stdin EOF
- init writes --repo-root explicitly, so the server does not need the repo as its cwd
