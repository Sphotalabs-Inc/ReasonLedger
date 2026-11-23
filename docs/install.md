# ReasonLedger — Installation

**Audience:** anyone installing ReasonLedger for the first time.
**Companion:** [`product-guide.md`](product-guide.md) (day-to-day use) · [`integration.md`](integration.md) (wiring it into an app repo).

`0.3.0a6` is an alpha. The `uvx` / `uv tool install` lines fetch it from PyPI; every other command on this page was run against a clean clone before it was written down.

---

## What you are installing

ReasonLedger ships as **three Python packages**, all from this one repository:

| Package | Provides | Do you need it? |
|---|---|---|
| `reasonledger-core` | Domain logic — decision format, policy, conflicts | Always (a dependency of the other two) |
| `reasonledger` | The `reasonledger` CLI (and the `rl` alias), including the local review UI | Yes — this is the thing you run |
| `reasonledger-mcp` | The MCP server behind `reasonledger mcp`, for Cursor / Claude Code | Comes with `reasonledger`; only *live* capture uses it — the import loop works without it |

## Nothing runs in the background

No daemon, no service, no telemetry, no account, no phone-home. Every ReasonLedger process is one you start and one that exits:

- CLI commands run once and exit.
- `reasonledger mcp` is a **stdio** process spawned by your editor; it dies with the editor and never listens on a port.
- `reasonledger ui` is a foreground server on `127.0.0.1` that lives exactly as long as the terminal command.

The local tool makes **no unattended outbound calls**. The only ones that exist are `import` / `catchup` extraction (which you invoke explicitly, and which `catchup --dry-run` skips entirely) and the **Test connection** button in the UI's settings panel, on an explicit click.

---

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — used for dependency management and for running the commands
- **git**

```bash
python3 --version
python3 -m uv --version
```

Verified with Python 3.12.4 and uv 0.11.3.

## Claude Code needs to be recent

If you use Claude Code, update it **before** `init`. An old build can fail on its first run with
a model 404 that looks like a ReasonLedger fault and is not.

- No minimum Claude Code version has been established yet, so none is promised here. If your first
  run fails with a model 404, update Claude Code and try again.
- Update Claude Code with one command: `claude update`

## Install

The packages are on PyPI. Nothing needs installing to try it:

```bash
cd /path/to/your-app
uvx reasonledger init
```

To keep `reasonledger` on your `PATH` (install **once per machine**, then run it from any app repo):

```bash
uv tool install reasonledger
uv tool update-shell     # only if uv warns the tool directory is not on your PATH
reasonledger --version
```

While the only published versions are pre-releases (`0.3.0a6`), `uvx` and `uv tool install` pick them up without a flag; if yours does not, add `--prerelease allow`. ReasonLedger runs on macOS, Linux and Windows.

## Contributors: install from a checkout

Working on ReasonLedger itself, or running an unreleased commit? Install from a clone. You never have to `cd` back into it afterwards.

```bash
git clone <repository-url> ReasonLedger
cd ReasonLedger

uv build --package reasonledger-core --out-dir dist
uv build --package reasonledger      --out-dir dist
uv build --package reasonledger-mcp  --out-dir dist

uv tool install \
  --find-links dist \
  reasonledger
```

This puts two executables — `reasonledger` and `rl` — in uv's tool bin directory. The MCP server is `reasonledger mcp`, so there is no third one to install. If uv warns that it is not on your `PATH`:

```bash
uv tool update-shell
```

The install is a **self-contained snapshot**: it does not read the checkout at run time, so you can move or delete the clone afterwards. To pick up a newer version, rebuild and re-run the same command with `--force`.

**Contributors** who want the tool to track their working tree instead should install editable — then `git pull` is enough, with no rebuild:

```bash
uv tool install --editable \
  --from ./packages/cli \
  --with-editable ./packages/mcp \
  reasonledger
```

> **Do not mix the two.** `uv tool install --from ./packages/cli --with ./packages/mcp` (no `--editable`) looks like it works, but it installs `reasonledger-core` editable — because `packages/cli` declares it as a workspace source — while snapshotting the CLI. After a `git pull` the two halves are different versions, and the CLI fails on an import that core has not shipped yet. Pick one column: **all snapshot** (`--find-links dist`) or **all editable** (`--editable` + `--with-editable`).

### Optional: real embeddings for related decisions

Out of the box, shortlisting related decisions uses word matching. The `embeddings` extra adds a local embedding model (fastembed, in process — it does not use Ollama or any server). The model is downloaded on first use, so that run needs network access once.

For the editable install above, add the extra to the same command and re-run it; no `--force` is needed, it replaces the existing install:

```bash
uv tool install --editable \
  --from "./packages/cli[embeddings]" \
  --with-editable ./packages/mcp \
  reasonledger
```

Then switch a project to it (this refuses with an install hint if the extra is missing):

```bash
reasonledger conflict-config --embedding-provider local
```

Do not use `uv sync --extra embeddings` for a tool install: it installs into the checkout's own virtual environment, not the uv tool environment that the `reasonledger` on your `PATH` runs from.

Choose the embedder **before** running `reasonledger judge`. A different embedder shortlists different pairs, so verdicts spent on pairs it later drops are wasted.

### Or: no install at all

`uv run` from inside the checkout still works and is what CI uses:

```bash
cd /path/to/ReasonLedger
uv sync --all-packages --dev
uv run reasonledger status --root /absolute/path/to/your-app
```

To invoke the checkout's environment *without* leaving your app repo, use `--project` — **never `--directory`** (see [the cwd trap](#the-cwd-trap-directory-vs-project)):

```bash
cd /path/to/your-app
uv run --project /absolute/path/to/ReasonLedger reasonledger status
```

## Verify

```bash
reasonledger --help
rl --help
reasonledger mcp --help
```

`reasonledger --help` lists every command. `rl` is a shorter alias for the same CLI.

`which reasonledger` should point at uv's tool bin directory. If it points anywhere else — a pyenv shim, a `pip install -e` in a global environment — that older install will shadow this one. Remove it first; see [Troubleshooting](#troubleshooting).

## First run — no API key required

This walks the whole loop against a recorded fixture, so it needs no model, no API account, and no network. **Every command runs from inside your app repo with no `--root`** — the default root is the current directory.

```bash
cd /path/to/your-app

# 1. Scaffold .reasonledger/
reasonledger init

# 2. Propose decisions from a recorded fixture instead of a live model
reasonledger import \
  --extracted-by fixture/demo \
  --fixture /absolute/path/to/ReasonLedger/fixtures/golden/import/extractor_replay.json

# 3. See what it staged (nothing is in the ledger yet)
reasonledger status

# 4. Confirm — this is the human-oversight step the ledger exists to record
reasonledger confirm --all --confirmed-by you@example.com

# 5. Ask why, on a file the decision justifies
reasonledger why backend/app/date_utils.py
```

> **The fixture only fires on a repo that has the document it was recorded against.** `extractor_replay.json` is keyed to `claude.md`, so on a repo without one, step 2 reports `created: 0` and step 3 shows nothing — correctly, but confusingly. To see the demo end to end on a scratch repo, give it something to match first:
>
> ```bash
> printf '# Notes\n\nWe store all timestamps in UTC.\n' > claude.md
> ```
>
> On a real repo, drop the `--fixture` flag and [configure a model](#configure-a-model-optional--only-for-live-import) instead.

Step 3 prints the staged proposal and step 5 answers with the decision's `choice` and `oversight`. `init` is idempotent — re-running it never overwrites existing decisions or a customized policy.

To review proposals in a browser instead of a terminal:

```bash
reasonledger ui
```

It prints a `http://127.0.0.1:<port>` URL and serves that repo's ledger until you press Ctrl+C.

## The cwd trap: `--directory` vs `--project`

`--root` defaults to the current directory on **every** subcommand, so a tool-installed `reasonledger` needs no path arguments at all. That default is also the trap, if you reach for `uv run --directory`:

```bash
cd /path/to/your-app
# WRONG — --directory moves cwd into the checkout, so this reads
# ReasonLedger's own ledger and reports 0 of everything
uv run --directory /path/to/ReasonLedger reasonledger status
```

**`--project` selects the environment without moving the working directory.** Use it, or install the tool and skip the wrapper entirely:

```bash
uv run --project /path/to/ReasonLedger reasonledger status   # right
reasonledger status                                          # better
```

The same trap applies to output paths under `--directory`: `status --html ledger.html` writes into the checkout, not your repo.

## Configure a model (optional — only for live `import`)

`import` and `catchup` need a model to turn prose into structured decisions. Bring your own:

```bash
cd /path/to/your-app
reasonledger config --provider anthropic --model claude-sonnet-5 \
  --api-key-env ANTHROPIC_API_KEY
```

Then check it reaches the provider:

```bash
export ANTHROPIC_API_KEY=...      # never commit this
reasonledger config --test
```

You can do the same from the **Model settings** panel in `reasonledger ui`, which also tells you when the named variable is missing from the environment the server was started in.

**About the key:** `.reasonledger/config.yml` stores the provider, model, base URL, and the *name* of an environment variable — never the key itself. There is no code path in ReasonLedger that writes a key to disk, and the UI refuses a request that tries to send one.

**About consent:** a model on this machine (a `localhost` base URL) needs no permission. A model anywhere else, including Anthropic, gets nothing until you allow each kind of data for this repo: the first command that needs it shows what it would send and asks `[y/N]`, `reasonledger consent --preview repo_text` shows one message exactly as it would be sent, and `reasonledger consent` (or **Settings → Data sent to your model**) shows and changes your choices. Any base URL that is not on this machine must use `https`. Where a command can't ask (CI), it refuses and names the grant command. The record lives in your user config directory, never in the repo.

**About billing:** an Anthropic **Console API key is separate from a Claude Pro/Max subscription** — different product, separate billing. A subscription does not give you API access.

**Or skip models entirely:** `reasonledger import --fixture candidates.json` accepts decision candidates you (or your coding agent) extracted yourself. No API account required. See [`integration.md`](integration.md) §B.

## Wire up MCP (optional)

Only needed for *live* capture — your agent calling `record_decision` / `query_decisions` mid-session. The entire `import → review → confirm → why` loop above works with no MCP server at all.

`reasonledger init` writes the MCP config for the agents your repo already uses — Claude Code (`.mcp.json`), Cursor (`.cursor/mcp.json`), VS Code (`.vscode/mcp.json`) — detected from their files or their CLI on `PATH`, and prints every file it wrote. With none detected it sets up all four; `--agents all` forces all four, `--agents cursor,vscode` picks. It lists the agents it skipped with the command that adds each. It writes `policy.yml` only for `reasonledger init --policy`. It writes the config in your app repo for you, filled in with that repo's absolute path (it never overwrites an existing file, and adds each to `.gitignore` because the path is machine-specific). It also writes each agent's rule, so there is nothing to paste. Cursor reads `.cursor/mcp.json` only from the folder you open, so open the app repo itself (`cursor /path/to/repo`), not a parent folder, then check Settings > MCP shows `reasonledger` switched on. Keep the absolute `--repo-root` path `init` writes; a relative `.` follows whatever folder Cursor opened. For another editor, the entry is the one below. With the tool installed, `reasonledger` is on `PATH` and needs no wrapper; without it, `init` writes `uvx reasonledger mcp …` instead:

```json
{
  "mcpServers": {
    "reasonledger": {
      "command": "reasonledger",
      "args": ["mcp", "--repo-root", "/absolute/path/to/your-app"]
    }
  }
}
```

Working from a checkout instead? Run `reasonledger init --reasonledger-root /absolute/path/to/ReasonLedger` and the snippet wraps the command in `uv run --project` — which, unlike `--directory`, leaves the working directory alone.

`--repo-root` is the **app** repo — where decisions get written — not the ReasonLedger checkout. Restart the editor after saving. This is a **stdio** server: the editor spawns it, it talks over stdin/stdout, and it exits with the editor. It never opens a port.

See [`integration.md`](integration.md) §A for the tool signatures and a suggested agent rule.

## What lands in your app repo

Exactly one directory, all of it plain text and committable:

```
.reasonledger/
  decisions/     confirmed decisions — the ledger
  proposed/      candidates awaiting your review
  policy.yml     optional CI policy rules
  config.yml     provider + model + env-var *name* (never a key)
  state.yml      the catch-up watermark (last scanned commit)
```

No `node_modules`, no build step, no server files, nothing outside `.reasonledger/`. **None of it holds a secret.** The UI's HTML/CSS/JS ship inside the installed `reasonledger` package, not in your repo — `reasonledger ui` only *reads* the files above.

**ReasonLedger is a developer tool, not a runtime dependency.** An app repo commits `.reasonledger/` and nothing else — never add `reasonledger` to `requirements.txt`, `package.json`, or a production image. Each developer installs the CLI once on their own machine; the repo carries only the decisions.

## Installing from PyPI

[Install](#install) is the PyPI path: `uvx reasonledger init`, or `uv tool install reasonledger`. The checkout flow under [Contributors](#contributors-install-from-a-checkout) gives the same executables from a clone. Publishing is a maintainer step — see [`releasing.md`](releasing.md).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ModuleNotFoundError: reasonledger_core.*` | An older `pip install -e` is shadowing the tool install — see [Removing an older install](#removing-an-older-install) |
| `status` reports 0 of everything | Either you are not in the app repo, or `uv run --directory` moved cwd into the checkout — use `--project`, or the tool install |
| An output file "written" but missing | Same cause; `--html` paths resolve against the checkout under `--directory` |
| `import` reports `created: 0` | Nothing to extract from — with `--fixture`, the repo must contain the document the fixture was recorded against |
| `error: extraction is disabled` | No provider configured — run `reasonledger config`, or pass `--fixture` |
| `provider requires an API key` | `api_key_env` names a variable that isn't exported in *this* shell |
| MCP tools missing in the editor | Reload MCP; `reasonledger` must be on the editor's `PATH` (or the config must use `uvx reasonledger mcp`); `--repo-root` must be absolute |
| The install stops while building `cryptography` (a Rust error) | Your Python or platform has no prebuilt wheel, often because uv picked the newest Python. Install with a supported one: `uv tool install --python 3.12 reasonledger` |
| Decisions written to the wrong repo | `--repo-root` must be the app, not the ReasonLedger checkout |

### Removing an older install

If `which reasonledger` points at a pyenv shim or a system Python rather than uv's tool bin, an earlier `pip install -e` is winning. A half-updated one of those is the usual source of `ModuleNotFoundError` on a module that plainly exists in the checkout: the CLI is editable and current, while `reasonledger-core` is a frozen copy from an older build.

```bash
which -a reasonledger
python3 -m pip uninstall reasonledger reasonledger-core reasonledger-mcp
```

Run the uninstall against **the interpreter the shim resolves to** — with pyenv, that is `~/.pyenv/versions/<version>/bin/python`, not whatever `python3` means in the current shell. Then re-run the [tool install](#install) and confirm `which reasonledger` has moved.

---

*Next: [`product-guide.md`](product-guide.md) for the day-to-day loop, or [`integration.md`](integration.md) to wire this into an app repo.*
