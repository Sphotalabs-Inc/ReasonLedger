# ReasonLedger

[![CI](https://github.com/Sphotalabs-Inc/ReasonLedger/actions/workflows/ci.yml/badge.svg)](https://github.com/Sphotalabs-Inc/ReasonLedger/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/reasonledger?include_prereleases&label=PyPI)](https://pypi.org/project/reasonledger/)

Your AI coding agent records *why* it made each choice, you approve it once, and
`reasonledger why` tells you which decision justifies a line, function, or file. The records are
plain files in your own repository. This is an alpha (`0.3.0a9`).

A short demo of the loop (init, review in the UI, why):

https://github.com/user-attachments/assets/548030d1-b2ea-40ab-b61b-d131aba451e5

```bash
cd /path/to/your-app
uvx reasonledger init                         # .reasonledger/, the MCP config and the agent rule
uvx reasonledger ui                           # approve what your agent recorded, on 127.0.0.1
uvx reasonledger why src/jobs/queue.py:55     # which decision justifies this line?
```

`why` takes a file, a line, or a function:

```bash
uvx reasonledger why src/jobs/queue.py            # the whole file
uvx reasonledger why src/jobs/queue.py:55         # one line
uvx reasonledger why src/jobs/queue.py::enqueue   # one function
```

A decision is one Markdown file in `.reasonledger/decisions/` (an excerpt of a real one from this
repository, `dec_4qveld`):

```markdown
---
id: dec_4qveld
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: reviewed
approved_by: iharpreet
justifies:
- packages/core/src/reasonledger_core/reasoning/judge.py::pending_pairs
context: reasonledger judge sent every shortlisted pair that lacked a model verdict to the model,
  including pairs a person had already dismissed. Should the judge skip dismissed pairs, and how
  should it treat a dismissal that has gone stale?
choice: pending_pairs now returns a JudgeQueue that splits the shortlist into pending, already
  judged and dismissed. …
alternatives_rejected:
- 'Add an --include-dismissed flag: a speculative parameter, since editing either decision
  already re-opens a pair for judging'
---
```

and what `why` answers for the code it justifies (also real, each line shortened here):

```text
$ reasonledger why packages/core/src/reasonledger_core/reasoning/judge.py::pending_pairs
dec_4qveld
  why: reasonledger judge sent every shortlisted pair that lacked a model verdict to the model, …
  chose: pending_pairs now returns a JudgeQueue that splits the shortlist into pending, …
  rejected:
    - Judge dismissed pairs anyway to catch a model disagreement: a person's verdict outranks …
    - Add an --include-dismissed flag: a speculative parameter, since editing either …
    - Skip any pair that has a dismissal entry regardless of fingerprint: contradicts …
    … and 1 more (--json)
  approved: iharpreet on 2026-11-12
```

The install, the first-run walk-through and what `init` writes are in
[`docs/install.md`](docs/install.md) and [`docs/user-manual.md`](docs/user-manual.md).

## Help test the alpha

We are looking for developers to run the whole loop on a repository they really work on and tell
us where it breaks or confuses them.

1. In that repository, run `uvx reasonledger init`, then restart your coding agent (Claude Code,
   Cursor or VS Code) so it picks up the MCP server and the rule.
2. Work as usual. When your agent makes a real choice between alternatives, it records it.
3. Run `uvx reasonledger ui` to review and approve what it recorded.
4. Run `uvx reasonledger why <file>:<line>` on code it changed.

Most useful to hear about: an install that fails, an agent that records nothing (or records
noise), a `why` that names the wrong decision, and anything in the UI you had to guess at.
[Open an issue](https://github.com/Sphotalabs-Inc/ReasonLedger/issues/new/choose) with the output of `reasonledger --version`, your OS and your agent.
Please do not paste source code or secrets into an issue.

## Start here

| Role | Read |
|---|---|
| **New to ReasonLedger — start here** | [`docs/user-manual.md`](docs/user-manual.md) |
| **Installing it for the first time** | [`docs/install.md`](docs/install.md) |
| **Developer using ReasonLedger day-to-day** | [`docs/product-guide.md`](docs/product-guide.md) |
| **Engineer or agent integrating Cursor / CI** | [`docs/integration.md`](docs/integration.md) |
| **Engineering “how”** | [`AGENTS.md`](AGENTS.md) |

## Orientation

| Need | Read |
|---|---|
| Build order & test discipline | [`AGENTS.md`](AGENTS.md) §8–9 |
| Publishing the packages (maintainers) | [`docs/releasing.md`](docs/releasing.md) |

## Local plane

`reasonledger ui` is one developer reviewing their own proposals — a foreground command on
`127.0.0.1`, stdlib-only, no database, no account. Installed by [`docs/install.md`](docs/install.md).
Nothing runs in the background unless you start it. No daemon, no telemetry.

## Status

Early, and local-first. The core loop works end to end: your coding agent records decisions over
MCP, you review and approve them in `reasonledger ui`, and `reasonledger why` tells you which
decision justifies a line, function, or file. Also built:

- conflict detection between related decisions, judged by your own coding agent over MCP or by a
  model you configure;
- a module map of your app and which decisions cover each module (`reasonledger map --scan` needs
  no model);
- importing decisions from your docs and commit history, and `catchup` to import only what changed;
- a consent step: nothing goes to a model that is off your machine until you allow that kind of
  data, per repo (`reasonledger consent`).

Not yet: a hosted team layer; teams share decisions through git. The suite runs on macOS,
Linux and Windows in CI. All five phase suites pass.

Install from PyPI — nothing to clone, and `uvx` needs no install at all. See
[`docs/install.md`](docs/install.md); the first screen above is the whole loop.

Working on ReasonLedger itself? The checkout flow is in the contributors section of
[`docs/install.md`](docs/install.md).

```bash
# Python (from repo root)
python3 -m uv sync --all-packages --dev
python3 -m uv run pytest -m "phase_1 or phase_2 or phase_3 or phase_4 or phase_5"

# MCP server (stdio) — query_decisions supports semantic=true for pre-decision recall
uv run reasonledger mcp --repo-root .

# Reasoning-blame: which decision(s) justify a line, function, or file
uv run reasonledger why packages/core/src/reasonledger_core/decisions/service.py:40

# What changed since the last sync? (--dry-run costs nothing and needs no model)
uv run reasonledger catchup --root /absolute/path/to/your-app --dry-run

# Policy CI gate (local)
uv run reasonledger check \
  --policy fixtures/sandbox/pr-workflows/policy.yml \
  --change fixtures/sandbox/pr-workflows/pr-compliant.json
```

## Licence

ReasonLedger's local tool (the CLI, the MCP server and the review UI) is Apache-2.0 and will stay
open source. The decision records it writes into your repository are yours; the licence covers the
tool, not your records.

[`LICENSE`](LICENSE) · [`NOTICE`](NOTICE) · [`TRADEMARKS.md`](TRADEMARKS.md) ·
[`CONTRIBUTING.md`](CONTRIBUTING.md) · [`SECURITY.md`](SECURITY.md)

## Building with an AI agent

1. Read `AGENTS.md` and the pages under `docs/`.
2. For integrating into another app, follow [`docs/integration.md`](docs/integration.md).
3. Respect the phase gate: prior phase suites must stay green.

> Provenance detection reads **declared** AI assistance. Inline completions (Cursor tab, Copilot ghost
> text) leave no trace in commit metadata, so a change made that way classifies as `human`.
