# reasonledger-core

Framework-free domain logic for [ReasonLedger](https://github.com/Sphotalabs-Inc/ReasonLedger) —
the audit-critical heart shared by the CLI and the MCP server.

This is a library. Most people want [`reasonledger`](https://pypi.org/project/reasonledger/)
(the CLI) instead; install this directly only if you are building your own surface on top
of the same domain model.

## What's in it

| Area | What it does |
|---|---|
| `decisions` | The Decision record format — frontmatter parse/write, round-trip, on-disk layout |
| `importer` | Bring-your-own-model extraction, propose-and-confirm staging, connection probe |
| `reasoning` | `why` resolution, conflict detection, staleness watchers, pluggable embeddings |
| `views` | `build_ledger_view` — a read-only projection of a repo's `.reasonledger/` state |
| `policy` | Policy evaluation for CI gates |
| `privacy` | The PII linter |
| `provenance` | AI-authorship signals read from commit metadata |

No web framework, no ORM session, and no I/O beyond the files it is pointed at — so the
same implementation backs every surface rather than being reimplemented per app.

## Design properties worth knowing

- **Secrets are structurally excluded.** `ExtractorConfig` has no field capable of holding
  a raw API key — only the *name* of the environment variable that supplies one.
- **Views never write.** `build_ledger_view` re-evaluates watcher conditions on read; it
  cannot modify a decision file.
- **Deterministic by default.** Embeddings resolve to a deterministic stub unless the
  local model is enabled, so tests and CI need no network and no model. Embeddings never use the
  network.

## Requirements

Python 3.12+.

```bash
# --pre: every release is a pre-release for now, and pip skips those unless told otherwise
pip install --pre reasonledger-core
pip install --pre "reasonledger-core[embeddings]"   # real embeddings via fastembed
```
