# reasonledger-mcp

The [Model Context Protocol](https://modelcontextprotocol.io) server for
[ReasonLedger](https://github.com/Sphotalabs-Inc/ReasonLedger). It lets a coding agent record
the decision it just made — and recall the decisions already made — without leaving the
session.

## It is not a service

`reasonledger-mcp` speaks **stdio**. Your editor spawns it, and it exits when the editor
does. It never listens on a port and never runs unattended. Nothing about installing it
puts a process on your machine.

It is also **optional**. The whole `import → review → confirm → why` loop works with no
MCP server at all; this package is for *live* capture, where the agent writes the decision
as it makes it rather than having it reconstructed from docs later.

## Tools

| Tool | What it does |
|---|---|
| `record_decision` | Writes a Decision record to `.reasonledger/decisions/<id>.md`, checked for common PII and API-key patterns before it lands (a safety net, not a guarantee: keep secrets and personal data out of decision text) |
| `query_decisions` | Retrieves prior decisions; `semantic=true` gives pre-decision recall rather than keyword match. At most `limit` (default 10) compact hits, in force first; `full=true` adds the markdown |
| `decisions_for` | The decisions in force that cover the files you are about to edit |
| `get_import_task`, `submit_candidates` | Backfill: your agent reads the docs and commit messages and proposes decisions, which a person confirms |
| `get_judging_task`, `submit_verdicts` | Conflict checks: your agent judges related pairs of decisions |
| `get_mapping_task`, `get_modules`, `submit_module_map` | Module map: your agent names the modules of your app |

All of them operate on the repo root given by `--repo-root` (or the `RL_MCP_REPO_ROOT`
environment variable), defaulting to the directory the editor spawned the server in.

## Wiring it up

`reasonledger init` writes this config (and the agent's rule) for Claude Code, Cursor and
VS Code, filled in with your actual paths. The shape is:

```json
{
  "mcpServers": {
    "reasonledger": {
      "command": "reasonledger",
      "args": ["mcp", "--repo-root", "/path/to/your-app"]
    }
  }
}
```

If `reasonledger` is not on your `PATH`, `init` writes `uvx` as the command and
`["reasonledger", "mcp", "--repo-root", …]` as the arguments instead. `reasonledger mcp` runs the
same server as the `reasonledger-mcp` executable. `uv tool install reasonledger` installs only
`reasonledger` and `rl`, not `reasonledger-mcp`, so the config uses the `mcp` subcommand.

The server speaks `stdio` only: your editor starts it and it never opens a network port.

## Requirements

Python 3.12+. Depends on [`reasonledger-core`](https://pypi.org/project/reasonledger-core/)
for the decision format, PII linter, and retrieval.

Most people want [`reasonledger`](https://pypi.org/project/reasonledger/) (the CLI) as well
— that is where `init`, `import`, `ui`, and `why` live.
