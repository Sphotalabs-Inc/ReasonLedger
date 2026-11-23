---
id: dec_jmez0j
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-13T20:42:06.981803Z'
justifies:
- packages/cli/src/reasonledger_cli/agent_targets.py::installed_cli
- packages/cli/src/reasonledger_cli/agent_targets.py::_is_ephemeral
watchers: []
context: init must write an MCP command the agent can start later. Under `uvx reasonledger
  init`, PATH holds a throwaway environment's bin, so `which reasonledger` succeeds
  for an executable the agent will not have. How does init decide that reasonledger
  is installed?
choice: installed_cli() accepts the PATH hit only when its path has no uv ephemeral-environment
  segment (environments-vN or archive-vN) and is not inside UV_CACHE_DIR; otherwise
  init writes `uvx reasonledger mcp`.
alternatives_rejected:
- 'Spawn a fresh login shell and run command -v: slow, shell-specific and not portable
  to Windows'
- 'Compare against sys.prefix of the running process: misses an installed tool that
  is also what is running, and false-positives when a venv is on PATH'
- 'Always write uvx: slower agent start and a network dependency on every start for
  people who did install it'
assumptions:
- uv keeps uvx environments under a cache directory segment named environments-vN
  or archive-vN
---

## Context

init must write an MCP command the agent can start later. Under `uvx reasonledger init`, PATH holds a throwaway environment's bin, so `which reasonledger` succeeds for an executable the agent will not have. How does init decide that reasonledger is installed?

## Choice

installed_cli() accepts the PATH hit only when its path has no uv ephemeral-environment segment (environments-vN or archive-vN) and is not inside UV_CACHE_DIR; otherwise init writes `uvx reasonledger mcp`.

## Alternatives rejected

- Spawn a fresh login shell and run command -v: slow, shell-specific and not portable to Windows
- Compare against sys.prefix of the running process: misses an installed tool that is also what is running, and false-positives when a venv is on PATH
- Always write uvx: slower agent start and a network dependency on every start for people who did install it

## Assumptions

- uv keeps uvx environments under a cache directory segment named environments-vN or archive-vN
