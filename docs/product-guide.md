# ReasonLedger — Product Guide

**Never lose the *why* behind AI-written code.** ReasonLedger captures the reasoning behind decisions your team (and your AI tools) make — the choice, the alternatives you rejected, the assumptions you made — as plain markdown files that live *in your repo*. Ask `why is this line here?` months later and get a real answer instead of a shrug.

This guide is for developers using ReasonLedger day-to-day. To install it first, see [`install.md`](install.md). For wiring it into an app repo, see [`integration.md`](integration.md). For the engineering internals, see [`../AGENTS.md`](../AGENTS.md).

---

## The core idea

A **Decision record** is one markdown file: a YAML header (id, choice, oversight, what code it justifies) plus a short prose body. Nothing more exotic than that — no database, no server required to read them.

```
.reasonledger/
  decisions/     confirmed decisions — the ledger
  proposed/      candidates awaiting your review
  policy.yml     optional CI policy rules
  config.yml     which model extracts decisions from docs (no secrets)
  state.yml      the catch-up watermark (last scanned commit)
```

Every decision moves through the same lifecycle:

```
proposed  →  confirmed            (a human reviewed it)
active    →  stale                (a watcher's assumption broke)
confirmed →  superseded           (the doc behind it changed, and you confirmed the replacement)
```

A **superseded** record is retired, never deleted — the trail has to show what was believed before and when it changed. A decision can also go **orphaned**: it names a file that is no longer in the repo, so the decision may still be sound but its pointer isn't.

Two decisions can also be flagged as **conflicting** — a similarity *hint*, not a verdict, always worth a human look before you act on it. When a hint is wrong, `reasonledger dismiss <id-a> <id-b> --reason "..."` records that judgement in `.reasonledger/dismissed.yml`. Commit it and the hint stops nagging **everyone** on the team, and stops failing the CI gate. One person triages a false positive once.

If most hints on your repo turn out wrong, that's a tuning problem, not something to dismiss one-by-one forever — `reasonledger conflict-config` adjusts the gate and the embedder per repo.

## Two ways decisions get captured

**1. Live, while you code.** Wire the MCP server into Cursor / Claude Code (see `integration.md`). Your agent calls `record_decision` after a real choice and `query_decisions` before making one — decisions accrue as you work, with zero extra steps.

**2. Import from what you've already written.** Most repos already have decisions buried in `claude.md`, `.cursorrules`, or a `docs/*.md` file — just not in a reviewable, queryable form. `reasonledger import` reads those docs, proposes decision records, and — the useful part — checks new proposals against each other and your existing ledger for **contradictions**. This is often how the first real value shows up: two docs quietly disagreeing about the same thing.

Either way, nothing is written to the ledger without a human confirming it first.

## Working as a team

Decision records are files in your repo. Commit them and your teammates have them — reviewed in the
PR that introduces them, distributed by `git clone`, with full history. `reasonledger status --since
main` shows what changed while you were away. There is no server and nothing to sync.

## Quickstart

Install once ([`install.md`](install.md)), then work from the app repo — `--root` defaults to the
current directory, so none of these need a path:

```bash
cd /path/to/your-app

# 1. Scaffold .reasonledger/
reasonledger init

# 2. (Optional — only needed for `import`) pick a model, see below
reasonledger config --provider anthropic --model claude-sonnet-5 \
  --api-key-env ANTHROPIC_API_KEY

# 3. Pull decisions out of your existing docs
reasonledger import --extracted-by anthropic/claude-sonnet-5

# 4. Review what it found
reasonledger ui
#   or, without a browser:
reasonledger status

# 5. Ask why, later, on any file
reasonledger why src/payments/retry.py:42
```

Running from a ReasonLedger checkout rather than an installed tool? Prefix each command with
`uv run --project /path/to/ReasonLedger`. Do **not** use `uv run --directory` — it moves the working
directory into the checkout, and every command above then reads the wrong repo. See
[`install.md`](install.md#the-cwd-trap-directory-vs-project).

## What's running on my machine

**Nothing, unless you started it.** There is no daemon, no service, no telemetry, no account.

| Surface | What it is | Lifetime |
|---|---|---|
| `reasonledger` CLI | One-shot commands | Exits per invocation |
| `reasonledger mcp` | A **stdio** MCP server | Spawned by your editor, dies with it — never listens on a port |
| `reasonledger ui` | A localhost HTTP server | Only while the terminal command runs |

**Is the MCP server running?** No. It is not a service. Your editor spawns it over stdin/stdout per the snippet `reasonledger init` prints, and it exits when the editor does. It is also *optional* — the whole `import → review → confirm → why` loop works with no MCP server at all.

**Does the UI live in my repo?** No. The HTML/CSS/JS ship inside the installed `reasonledger` package. `reasonledger ui --root <app>` starts an ephemeral server that only *reads* that app's `.reasonledger/` files. The only thing ever written into your repo is `.reasonledger/` itself.

**Is the UI centralized?** No. It is per-developer, per-repo, and ephemeral: bound to `127.0.0.1` only, stdlib-only, no database, no Docker, no account, with a fresh session token each run, and it never phones home.

The local plane makes **no unattended outbound calls**. The only ones that exist are `import`/`catchup` extraction — which you invoke explicitly, and which `catchup --dry-run` skips entirely — and the **Test connection** button in the UI, on an explicit click.

## Reviewing proposals

Two interfaces read the exact same files — pick whichever fits the moment:

- **`reasonledger ui`** — opens a browser tab on `127.0.0.1` (no Docker, no database). See proposals, decisions, stale and orphaned items, and conflict hints; **Confirm** / **Reject** each proposal with a click, **Dismiss** a conflict pair with a reason; a **Refresh** button re-reads the files without reloading the page. A **Model settings** panel shows which model `import` will use, lets you change it, and warns when the API-key environment variable it names isn't set in the shell you started the server from. A **Conflict settings** panel does the same for the gate and embedder `status`/`ui` use to flag conflicts — the same setting `reasonledger conflict-config` changes from a terminal. It's a page bound to your machine only — a per-session token protects it, so nothing else on your network can call it.
- **`reasonledger status [--json]`** — the same view as text, for a terminal or a script. Add `--html out.html` to export a single, self-contained, read-only snapshot (no server, safe to attach to a PR or a compliance folder).
- **`reasonledger reject <id>`** — drop a proposal from the terminal without opening the UI.
- **`reasonledger confirm <id> | --all`** — promote reviewed proposals into `.reasonledger/decisions/`. Requires `--confirmed-by <you>` — that's the human-oversight evidence recorded on the file.

Confirming and rejecting only ever touch `.reasonledger/proposed/` and `.reasonledger/decisions/` — your application code is never modified.

## Choosing a model, and where it's saved

`import` needs a model to turn prose into structured decisions. **Bring your own** — nothing is hardcoded:

| Provider | Where it runs | Needs |
|---|---|---|
| `anthropic` | Anthropic's API | a Console API key (**separate from a Claude Pro/Max subscription** — different billing) |
| `openai_compatible` | OpenAI, Azure, or any compatible gateway | an API key + endpoint |
| `local` | Ollama / vLLM on your machine | nothing leaves your machine |

Set it once:

```bash
reasonledger config --provider anthropic --model claude-sonnet-5 \
  --api-key-env ANTHROPIC_API_KEY
```

This writes `.reasonledger/config.yml` — provider, model, base URL. **The API key itself is never written there.** Only the *name* of the environment variable holding it is saved; the actual value is read from your shell environment at the moment a command runs. That file is safe to commit — grep it and you'll never find a secret in it, only a variable name like `ANTHROPIC_API_KEY`.

No key, no problem: you (or your coding agent) can extract candidates yourselves and feed them in offline via `reasonledger import --fixture candidates.json` — see `integration.md` §Option B. No API account required.

## Watchers and staleness

A decision can name a condition it depends on — `queue_depth < 100`. When you check status with current values (`--watch-values values.json`), a breached condition shows the decision as **stale** in the view. This is display-only: the underlying file is never rewritten just because you looked. Nothing runs in the background; staleness is recomputed fresh every time you check.

## Policy gate (CI)

`.reasonledger/policy.yml` can require oversight on sensitive paths — e.g. "AI-assisted changes to `payments/**` need a reviewed decision." `reasonledger check` evaluates it against a change and exits non-zero on violation, so you can wire it into CI. See `integration.md` §C for the file format.

## Command reference

| Command | Does |
|---|---|
| `reasonledger init` | Scaffold `.reasonledger/` in an app repo |
| `reasonledger config [--test]` | Set (and test) the BYOM extractor provider |
| `reasonledger import` | Extract proposed decisions from existing docs; reports conflicts first |
| `reasonledger catchup [--dry-run]` | What changed since the last sync — scans only the delta |
| `reasonledger status [--json\|--html]` | Show proposals / decisions / stale / orphaned / conflicts |
| `reasonledger ui` | Interactive browser review (confirm / reject / refresh / why) |
| `reasonledger confirm <id>\|--all` | Promote proposals into the ledger |
| `reasonledger reject <id>` | Drop a proposal |
| `reasonledger dismiss <a> <b> --reason "..."` | Mark a conflict hint as wrong (committed, team-shared) |
| `reasonledger conflict-config [--show]` | Tune the conflict-detection gate/embedder for this repo |
| `reasonledger why <path[:line]>` | Which decision(s) justify this code, even after the code moved (labelled *moved* or *lost*) |
| `reasonledger approve <id>` / `retire <id> --reason ...` | A person's verdict, or taking a decision out of force; recorded under your git `user.name` |
| `reasonledger check` | Evaluate policy against a change (CI) |

## Installing

See [`install.md`](install.md) — `uvx reasonledger init` from PyPI, prerequisites, verification and MCP wiring; the checkout flow is there too, for contributors.

---

*For MCP wiring, TypeScript quickstarts, and the sandbox fixtures referenced above, see [`integration.md`](integration.md).*
