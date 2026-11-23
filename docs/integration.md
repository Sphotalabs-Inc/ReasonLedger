# ReasonLedger — Integration guide

**Decision memory for AI-assisted codebases — never lose the why behind a line of code.**

**Audience:** Engineers and coding agents (Cursor, Claude Code, Copilot) integrating ReasonLedger into an application repository.  

Hand this file to an agent with: *“Follow `docs/integration.md` to wire ReasonLedger into this app.”*

---

## What you are integrating

ReasonLedger captures **Decision records** about AI-assisted code:

1. Agents **query** prior Decision records before choosing.
2. Agents **record** Decision records as markdown under `.reasonledger/decisions/`.
3. Optional **CI policy gate** blocks/warns PRs that violate `.reasonledger/policy.yml`.

Decision records live **in the application git repo** (portable).

### MCP is a stdio process, not a service — and it is optional

`reasonledger mcp` (the `reasonledger-mcp` server) is **spawned by your editor** over stdin/stdout, and it exits when the editor does. It never listens on a port, never runs unattended, and there is nothing to start or monitor. "Is the MCP server running?" — only while your editor is, and only because your editor launched it.

It is also **optional**. It buys you *live* capture: the agent calling `record_decision` / `query_decisions` mid-session. The entire `import → review → confirm → why` loop (§B) works with no MCP server at all.


---

## Quickstart from a clean clone (3 commands)

From the ReasonLedger repo root (offline, deterministic):

```bash
uv sync --all-packages --dev
uv run reasonledger init --root fixtures/sandbox/ts-app --reasonledger-root "$PWD"
uv run reasonledger why src/payments/retry.ts:4 --root fixtures/sandbox/ts-app
```

The fixture TypeScript app under `fixtures/sandbox/ts-app/` ships with a seeded Decision record (`dec_retry01`) so `why` returns a real answer immediately. Re-running `init` is safe — it never overwrites existing Decision records or a customized policy.

Expected `why` output (human-readable):

```text
dec_retry01
  choice: Exponential backoff with jitter
  oversight: reviewed
```

---

## TypeScript application repo

Provenance and `why` are **language-agnostic** (git metadata + `justifies` loci). TypeScript is the default quickstart because it matches the largest Cursor user base.

### 1. Scaffold the app repo

```bash
cd /absolute/path/to/your-ts-app
reasonledger init
```

Creates `.reasonledger/decisions/` (with `.gitkeep`), a `.reasonledger/policy.yml` stub, and prints MCP + Cursor rule snippets. Idempotent — safe to re-run.

### 2. Wire MCP (Cursor)

Use the JSON snippet printed by `init`, or see [section A](#a-cursor--claude-code--mcp-primary-path) below. Point `--repo-root` at your TypeScript app, not the ReasonLedger checkout.

### 3. Record Decision records with `justifies` loci

When an agent records a decision, include TypeScript paths:

```json
"justifies": ["src/payments/retry.ts:3-6"]
```

Commit `.reasonledger/decisions/*.md` with the PR.

### 4. Ask why at a line

```bash
cd /absolute/path/to/your-ts-app
reasonledger why src/payments/retry.ts:4
reasonledger why src/payments/retry.ts:4 --json
```

On a miss: exit `0` with `no decision justifies this line yet`.

Validate against the bundled fixture, from the ReasonLedger checkout:

```bash
uv run reasonledger why src/payments/retry.ts:4 --root fixtures/sandbox/ts-app
```

---

## Prerequisites

Full setup instructions are in [`install.md`](install.md); the short version:

- ReasonLedger installed **once per machine** as a uv tool, so `reasonledger` (and its `mcp` subcommand) is on your `PATH` from any repo.
- Target **application** repo path (the repo Cursor/Claude is editing — not necessarily the ReasonLedger repo).

**ReasonLedger is a developer tool, not a runtime dependency of your app.** Do not add it to
`requirements.txt`, `package.json`, or your production image. The only thing an application repo
commits is `.reasonledger/` — plain text decisions, policy, and config. The CLI, the UI assets, and
the MCP server all live in the tool install on each developer's machine.

Working from a checkout instead:

```bash
# From the ReasonLedger repo root
uv sync --all-packages --dev
```

---

## A. Cursor / Claude Code — MCP (optional; for live capture)

### 1. Check the server starts against the *application* repo

```bash
reasonledger mcp --repo-root /absolute/path/to/your-app
```

Stdio is the default transport (what Cursor expects). Running this by hand only proves it launches — it will sit waiting on stdin. **In normal use you never run this yourself:** the editor spawns it from the config below and it exits with the editor. Ctrl+C to stop it here.

### 2. Cursor MCP config

Add a server entry (Cursor **Settings → MCP**, or project `.cursor/mcp.json`):

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

| Flag / env | Meaning |
|---|---|
| `--repo-root` / `RL_MCP_REPO_ROOT` | Where `.reasonledger/decisions/` is written |

Running from a checkout instead of a [tool install](install.md#install)? Wrap the command in `uv run --project /absolute/path/to/ReasonLedger` — **not `--directory`**, which moves the working directory into the checkout and repoints every relative path with it.

Restart Cursor / reload MCP after saving.

### 2b. VS Code (Copilot agent mode)

`reasonledger init` writes `.vscode/mcp.json`. VS Code's root key is `servers`, not
`mcpServers`, and the entry names its transport:

```json
{
  "servers": {
    "reasonledger": {
      "type": "stdio",
      "command": "reasonledger",
      "args": ["mcp", "--repo-root", "/absolute/path/to/your-app"]
    }
  }
}
```

The file is git-ignored (it holds an absolute path). The rule goes to
`.github/copilot-instructions.md`. When `reasonledger` is not on your `PATH`, `init` writes
the `uvx reasonledger mcp` form instead, so nothing else needs installing.

### 3. Tools the agent must use

#### `query_decisions`

Call **before** a non-trivial design choice.

| Argument | Type | Notes |
|---|---|---|
| `query` | string | Natural language or keywords |
| `paths` | string[]? | Optional path filters, e.g. `["payments/**"]`. Ignored when `semantic` is `true` |
| `semantic` | bool? | `true` = rank by embedding similarity, so a paraphrase finds the record; default is substring match |
| `limit` | int? | Most hits to return (default 10) |
| `full` | bool? | `true` adds each record's `markdown`; default is compact |

**Output:** `total` (matches before the limit), `truncated`, `warnings`, and `decisions`: each with `id`, `context`, `choice`, `justifies`, `status`, `oversight`, `proposed_by`, `superseded_by` (plus `retired_reason` when retired, `superseded_reason` when a person chose its successor). Decisions in force come before retired and superseded ones.

**Which embedder answers `semantic: true`.** The same one `reasonledger status` uses: `embedding_provider` in the app repo's `.reasonledger/conflict.yml`, which `reasonledger init` sets to `local` (the bge model) whenever the embeddings extra is installed, else the `RL_EMBEDDING_PROVIDER` environment variable, else the deterministic hash embedder. You do not need to put anything in the MCP config's `env`. The MCP server must run in an environment that has the extra (install `reasonledger[embeddings]`, since `reasonledger mcp` runs from it; see `reasonledger init`'s note).

If the configured embedder cannot start (extra missing, model download blocked), the call still answers on basic word matching and says so in `warnings`; an empty `warnings` means the configured embedder ran. Word matching is much weaker on paraphrases, so treat a warning as a reason to fix the install, not to trust the ranking. Decision vectors are cached in the gitignored `.reasonledger/cache/embeddings/`, so a decision is embedded once, not on every call; the first semantic call after a fresh clone is the slow one.

#### `decisions_for`

Call **before editing a file**: it returns the decisions that cover it.

| Argument | Type | Notes |
|---|---|---|
| `paths` | string[] | Repo-relative files about to change. A path outside the repo is refused |
| `line` | int? | Narrow to the code at this line |

**Output:** the decisions in force (compact, as above) each with `match` — `symbol`, `line`, `moved`, `file` or `lost` — and `out_of_force`, how many retired or superseded decisions also touch these files. No file contents are returned.

#### `record_decision`

Call **after** a meaningful choice is made (and before or with the PR).

| Argument | Required | Notes |
|---|---|---|
| `context` | yes | What problem was being decided |
| `choice` | yes | What was selected |
| `ai_tool` | yes | Free-form agent name, stored lowercase-hyphenated (`claude-code`, `cursor`, `copilot`, `grok`, `codex`, …); `claude` is an alias for `claude-code`; `none` for a human-made decision |
| `alternatives_rejected` | no | List of strings |
| `assumptions` | no | Free-text assumptions |
| `watchers` | no | Machine conditions, e.g. `postgres_version >= 15` (frontmatter) |
| `confidence` | no | e.g. `high` |
| `model` | yes unless `ai_tool` is `none` | Exact model id, e.g. `claude-sonnet-4-5` or `grok-4` |
| `oversight` | no | **Ignored.** A record written through MCP is always `pending`; a person gives the verdict with `reasonledger approve <id> [--as modified\|rejected]` or in the UI. Kept in the signature for one release so older rule files still work; passing it adds a warning |
| `proposed_by` | no, but warned if missing | `human` (the user stated or explicitly accepted the choice before it was made) \| `ai` (the agent chose or recommended it). Shown in the UI as **agreed** / **recommended**. Independent of `oversight`, which records whether a person reviewed the record afterwards |
| `approved_by` | no | **Ignored**, like `oversight`. The approver is the git `user.name` of the person who runs `approve` |
| `justifies` | no | Code loci, e.g. `["payments/retry.py::retry", "payments/retry.py:40-72"]` — needed for `why`; bare file paths are saved with a warning |
| `body` | no | Optional markdown body |
| `decision_id` | no | Stable id; auto-generated if omitted |

**Output:** writes `.reasonledger/decisions/<id>.md` in the app repo. Commit it with the change.

PII in the decision text is **rejected** by the linter (emails/phones/SSNs/keys in prose).

### 4. Suggested Cursor / agent rule

`reasonledger init` already writes this rule for you (see below); you only need the text to
adapt it for another agent:

```markdown
# ReasonLedger

Before editing a file, call MCP `decisions_for` with its path: it returns the decisions that
cover that code, so you change it knowing why it is the way it is.

When making a non-trivial architectural or behavioral choice:
1. Call MCP `query_decisions` with a short description (use `semantic: true` when available).
2. Prefer aligning with prior Decision records; if diverging, explain why in the new record
   and pass the old record's id as `supersedes` when the new one replaces it.
3. After deciding, call `record_decision` with `ai_tool` set to the active tool (e.g.
   `claude-code`, `cursor`, `copilot`), `model` set to the exact model id, and `justifies`
   loci as `path::symbol` or `path:START-END`.
   Never pass `oversight` or `approved_by`: the record is saved `pending` and a person gives
   the verdict with `reasonledger approve` or in `reasonledger ui`.
   Set `proposed_by`: `human` only if the user stated or explicitly accepted the choice in
   chat before you acted, `ai` if you chose or recommended it. Never claim `human` to be safe.
4. Commit `.reasonledger/decisions/*.md` in the same PR as the code change.
5. Do not put secrets, customer PII, or source code dumps into decision bodies.
```

Where `init` puts it: Claude Code → `CLAUDE.md`, Cursor → `.cursor/rules/reasonledger.mdc`,
VS Code → `.github/copilot-instructions.md`, any other agent that reads it → `AGENTS.md`. In a
shared file it is the block between `<!-- reasonledger:begin -->` and `<!-- reasonledger:end -->`.

### 5. Verify locally

```bash
# After the agent records a decision
ls your-app/.reasonledger/decisions/

# Which decision justifies a line?
cd /absolute/path/to/your-app
reasonledger why payments/retry.py:55
```

---

## B. CLI — onboarding, `why`, and policy gate

### `reasonledger init`

Scaffold Decision record layout in an application repo (one-command onboarding):

```bash
cd /path/to/your-app
reasonledger init
```

Creates `.reasonledger/decisions/` (`.gitkeep`) and a `.reasonledger/policy.yml` stub when missing. Prints MCP config and a Cursor rule. **Idempotent** — never overwrites existing Decision records or an existing policy file.

### `reasonledger why`

```bash
reasonledger why path/to/file.py:42
reasonledger why path/to/file.py:42 --json
```

Human-readable output includes decision id, `choice`, and `oversight`. Clean message (exit 0) when nothing justifies the locus — `no decision justifies this line yet`.

### `reasonledger check`

Evaluates `.reasonledger/policy.yml` against a JSON change context (used by CI).

```bash
reasonledger check \
  --policy .reasonledger/policy.yml \
  --change /path/to/change-context.json \
  --json
```

Exit codes: `0` pass/warn, `1` fail, `2` usage/parse error.

### Import existing decisions

Bring your own model to extract decisions from docs already in the repo (`claude.md`, `docs/**`, etc.). Import **proposes** records only — nothing lands in the ledger until a human confirms.

**1. Configure the extractor** (non-secret settings only; API key stays in env):

```bash
reasonledger config \
  --provider anthropic \
  --model claude-sonnet-5 \
  --api-key-env ANTHROPIC_API_KEY
```

Optional connection check:

```bash
export ANTHROPIC_API_KEY=...   # never commit this
reasonledger config --test
```

**2. Run import** (offline demo with a recorded fixture — no live model in CI):

```bash
reasonledger import \
  --extracted-by anthropic/claude-sonnet-5 \
  --fixture /path/to/ReasonLedger/fixtures/golden/import/extractor_replay_conflict.json
```

With a configured provider (omit `--fixture`), import calls your endpoint and prints a **conflict-first** report, then a proposal summary. Staged files appear under `.reasonledger/proposed/`; review and confirm before they move to `.reasonledger/decisions/`.

**`.reasonledger/config.yml` shape** (committable — no secrets):

```yaml
extractor:
  provider: anthropic          # anthropic | openai_compatible | local | disabled
  model: claude-sonnet-5
  base_url: https://api.anthropic.com   # optional for anthropic; required for others; https unless localhost
  api_key_env: ANTHROPIC_API_KEY        # env-var name only — value resolved at runtime
```

Example policy and PR contexts: `fixtures/sandbox/pr-workflows/` in this repo.  
Composite Action: `.github/actions/reasonledger-check/`.

---

## C. Policy file (application repo)

Create `.reasonledger/policy.yml` in the **app** repo. Example shape (see sandbox fixtures for a full sample):

```yaml
version: "1"
rules:
  - id: critical-path-needs-review
    when:
      paths: ["payments/**", "auth/**"]
      provenance: ai_assisted
    require:
      oversight: reviewed
    on_violation: fail
```

Keys under `when` are `provenance` (`ai_assisted`, `likely_ai`, `human` or `unknown`) and `paths`; keys under `require` are `oversight` (one of `reviewed`, `modified`, `merged_unreviewed`, `n/a`), `approver: codeowner` and `approver_not: author`. **Any other key is an error, not ignored**: `reasonledger check` exits `2` and names the rule, the key and the keys allowed there, so a condition you meant can never be silently dropped.

Wire CI to build a change-context JSON from the PR and invoke `reasonledger check` (or the composite action).

---

## E. Agent checklist (copy into a task)

- [ ] MCP server configured with `--repo-root` = application repo  
- [ ] Agent can list tools `record_decision` and `query_decisions`  
- [ ] Project rule instructs query-before / record-after  
- [ ] At least one Decision record committed under `.reasonledger/decisions/`  
- [ ] `justifies` paths match real files so `reasonledger why` works  
- [ ] (Optional) `.reasonledger/policy.yml` + CI check  

---

## F. Troubleshooting

| Symptom | Fix |
|---|---|
| MCP tools missing | Reload MCP; confirm `uv` on PATH; paths are absolute |
| `query_decisions` returns a `warnings` entry about word matching | The configured embedder could not start: install the embeddings extra into the environment `reasonledger mcp` runs in (`uv tool install --force "reasonledger[embeddings]"`), then reload MCP |
| Decisions written in wrong place | `--repo-root` must be the **app**, not ReasonLedger |
| `record_decision` returns PII error | Remove emails/phones/keys from context/body; use `approved_by` only for approver |

---

## G. What not to do

- Do not store source code or prompts in decision bodies.  
- Do not commit `.env` secrets.  
- Do not call live customer LLM endpoints from CI — use fixtures/stubs.  
- Do not treat the deterministic embedder as production semantic quality — install the embeddings extra (or plug a customer endpoint) and check that `query_decisions` returns no `warnings`.

---

*Integration guide for ReasonLedger. Keep in sync with `packages/mcp` tool signatures when they change.*
