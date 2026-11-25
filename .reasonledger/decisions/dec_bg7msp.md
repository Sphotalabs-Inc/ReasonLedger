---
id: dec_bg7msp
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: ai
recorded_at: '2026-11-25T04:30:34.738166Z'
justifies:
- packages/cli/src/reasonledger_cli/agent_targets.py::running_launcher
- packages/cli/src/reasonledger_cli/agent_targets.py::_installed_command
- packages/cli/src/reasonledger_cli/agent_targets.py::mcp_server_entry
watchers: []
context: init wrote a bare `reasonledger` when any non-ephemeral one was on PATH and
  `uvx` otherwise. A pip user who runs the venv's binary without activating it got
  `uvx` (absent on that machine, and fetching a different version), and an older global
  install earlier on PATH silently served the new install's repo. Which command should
  the MCP config name for a persistent install?
choice: 'Use the launcher that ran init: the console script in sys.argv[0] (its `reasonledger`
  sibling when run as `rl`), or `sys.executable -m reasonledger_cli` under `python
  -m`. Write the bare name only when shutil.which resolves to that same file; otherwise
  write the absolute launcher path. Write `uvx` only when the launcher itself is in
  a uv ephemeral environment. This narrows the uvx fallback in dec_tkhnpk; installed_cli()
  from dec_jmez0j still drives the embeddings tip.'
alternatives_rejected:
- 'Always write the absolute path of the running launcher: breaks the portable bare-name
  config the MCP README documents and check_dists.sh asserts for uv tool installs'
- 'Keep the PATH-based rule and only warn when uvx is missing: still serves the wrong
  version when an older install shadows the new one'
- 'Fall back to uvx only when uvx is on PATH, else error: leaves unactivated pip venvs
  with no working config'
assumptions:
- sys.argv[0] for a console script is the script's full path, as the OS launcher passes
  it
- Editors spawn the MCP command with a PATH that may lack the user's activated venv
- .mcp.json is gitignored, so a machine-specific absolute path in it is acceptable
---

## Context

init wrote a bare `reasonledger` when any non-ephemeral one was on PATH and `uvx` otherwise. A pip user who runs the venv's binary without activating it got `uvx` (absent on that machine, and fetching a different version), and an older global install earlier on PATH silently served the new install's repo. Which command should the MCP config name for a persistent install?

## Choice

Use the launcher that ran init: the console script in sys.argv[0] (its `reasonledger` sibling when run as `rl`), or `sys.executable -m reasonledger_cli` under `python -m`. Write the bare name only when shutil.which resolves to that same file; otherwise write the absolute launcher path. Write `uvx` only when the launcher itself is in a uv ephemeral environment. This narrows the uvx fallback in dec_tkhnpk; installed_cli() from dec_jmez0j still drives the embeddings tip.

## Alternatives rejected

- Always write the absolute path of the running launcher: breaks the portable bare-name config the MCP README documents and check_dists.sh asserts for uv tool installs
- Keep the PATH-based rule and only warn when uvx is missing: still serves the wrong version when an older install shadows the new one
- Fall back to uvx only when uvx is on PATH, else error: leaves unactivated pip venvs with no working config

## Assumptions

- sys.argv[0] for a console script is the script's full path, as the OS launcher passes it
- Editors spawn the MCP command with a PATH that may lack the user's activated venv
- .mcp.json is gitignored, so a machine-specific absolute path in it is acceptable
