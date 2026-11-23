# ReasonLedger — User Manual

**Never lose the why behind a line of AI-written code.** Your coding agent records each real
design choice as a small markdown file in your repo. You review it. Months later you point at
a line and ask why it is there.

This manual gets you from nothing to a working loop in about ten minutes. Deeper references:
[`install.md`](install.md) · [`product-guide.md`](product-guide.md) ·
[`integration.md`](integration.md).

---

## 1. What it does

- **Records decisions.** While coding, your agent writes down what was being decided, what it
  chose, what it rejected, and which code the choice explains.
- **Keeps them in git.** One markdown file per decision in `.reasonledger/decisions/`. No
  database, no server, no account. `cat` and `git log` work.
- **Waits for you.** A decision an agent records is `pending` until a person approves it.
- **Answers "why".** `reasonledger why path/to/file.py:42` returns the decision behind that line.
- **Flags contradictions.** Two decisions that answer the same question differently can be
  surfaced as a conflict (optional, §5.2).

Nothing runs in the background and nothing leaves your machine unless you configure a model
and allow it (§7). Your application code is never modified.

---

## 2. Install (once per machine)

You need Python 3.12+, [uv](https://docs.astral.sh/uv/) and git. There is nothing to install
first: `uvx` fetches ReasonLedger from PyPI the first time you run it (§3). To keep it on your
`PATH` instead:

```bash
uv tool install reasonledger
```

This puts `reasonledger` and `rl` (a shorter alias) on your `PATH`; the MCP server is `reasonledger mcp`. Check
with `reasonledger --version`. If the command is not found, run `uv tool update-shell` and open
a new terminal. Working on ReasonLedger itself, or installing from a checkout? See the
contributors section of [`install.md`](install.md). It runs on macOS, Linux and Windows.

---

## 3. Set up your repo

```bash
cd /path/to/your-app
uvx reasonledger init        # or just `reasonledger init` if you installed it
```

`init` creates `.reasonledger/` and, for each agent, writes the MCP config **and** the rule
that tells the agent to use it. There is nothing to paste:

| Agent | MCP config | Rule |
|---|---|---|
| Claude Code | `.mcp.json` | `CLAUDE.md` |
| Cursor | `.cursor/mcp.json` | `.cursor/rules/reasonledger.mdc` |
| VS Code (Copilot agent mode) | `.vscode/mcp.json` | `.github/copilot-instructions.md` |
| Any agent that reads it | — | `AGENTS.md` |

The MCP configs hold a path specific to your machine, so they are git-ignored and never
overwritten if you already have one (`init` prints the entry to merge instead). The rule files
are meant to be committed. In a file you share (`CLAUDE.md`, `AGENTS.md`,
`copilot-instructions.md`) the rule sits between `<!-- reasonledger:begin -->` and
`<!-- reasonledger:end -->`; `init` replaces that block in place and never touches a line
outside it. Running `init` again changes nothing.

`--agents claude-code,cursor,vscode` names the agents (default: the ones `init` finds in the repo or
on your `PATH`, or all four when it finds none; `--agents all` forces all four), and `--no-rules` writes
only the MCP configs. Agents that keep their config in your home directory (Codex, Windsurf)
are not written to; `init` prints where theirs goes.

Then **restart your agent** so it picks up the MCP server. Claude Code asks you to approve the
project server the first time.

---

## 4. The loop

### 4.1 Your agent records a decision

Work as usual. Before editing a file the agent calls `decisions_for` with its path, to see the
decisions that already cover it. When it chooses between real alternatives, it calls
`query_decisions` to see whether this was already decided (at most 10 compact hits, decisions
in force first; `limit` and `full` change that), then records the choice:

```
record_decision(
  context="How should failed payment webhook deliveries be retried?",
  choice="Exponential backoff with full jitter, capped at 30 seconds",
  alternatives_rejected=[
    "Fixed delay: synchronised retries hammer a recovering endpoint",
    "Linear backoff: too slow to back off under sustained failure"
  ],
  justifies=["src/payments/retry.ts:1-6"],
  ai_tool="claude-code",
  model="claude-sonnet-5",
  proposed_by="ai"
)
```

That writes `.reasonledger/decisions/dec_dhzm4x.md` (the id is generated):

```markdown
---
id: dec_dhzm4x
ai_tool: claude-code
model: claude-sonnet-5
oversight: pending
status: active
proposed_by: ai
justifies:
- src/payments/retry.ts:1-6
context: How should failed payment webhook deliveries be retried?
choice: Exponential backoff with full jitter, capped at 30 seconds
alternatives_rejected:
- 'Fixed delay: synchronised retries hammer a recovering endpoint'
- 'Linear backoff: too slow to back off under sustained failure'
---
```

Three fields are worth knowing:

| Field | Meaning |
|---|---|
| `justifies` | The code this decision explains: `path:START-END` or `path::function_name`. This is what `why` matches against. |
| `oversight` | `pending` until a person looks; then `reviewed`, `modified` or `rejected`. An agent cannot set it: a record written through MCP is always `pending`, whatever the agent passes. |
| `proposed_by` | `ai` if the agent chose it, `human` if you stated or accepted the choice before the agent acted. |

### 4.2 You review it

```bash
reasonledger status                          # lists what is waiting for a verdict
reasonledger approve dec_dhzm4x              # add --as modified or --as rejected if that is the honest verdict
```

Or run `reasonledger ui`, press **Review** on the decision and approve from the dialog, which
shows the whole record first (§6). Commit the decision file in the same PR as the code it explains.

**Who you are.** Nothing asks for your name. An approval is recorded under the `user.name` git
has for this checkout, the same name your commit of the decision file carries, along with the
time. The browser cannot send a different name; with no `user.name` set the UI refuses and tells
you to run `git config user.name "Your Name"`. On the command line `--by <name>` overrides it.

### 4.3 When a decision stops applying

An approved decision is not approved forever. Two ways take one out of force, and both keep the
record and its original approval as history:

```bash
reasonledger retire dec_dhzm4x --reason "The cache layer was removed"   # nothing replaces it
```

- **Retire** (the command above, or **Retire** on the card in the UI): status becomes `retired`,
  with who, when and the reason you must give.
- **Supersede**: have the agent record the replacement with `supersedes: dec_dhzm4x`. The old
  record becomes `superseded` and points at its successor.
- **Choose between two that clash**: when both decisions already exist, run
  `reasonledger supersede dec_dhzm4x --successor dec_9k2m1p --reason "Covers both cases"`, or
  click **Keep** on the one that stands in the conflict on the Review tab. The other becomes
  `superseded` with who chose, when and the reason; the one that stands is not changed.

Retired and superseded decisions stay visible, labelled, and drop out of conflicts, coverage and
the waiting list.

### 4.4 Ask why

```bash
reasonledger why src/payments/retry.ts:4
```

```text
dec_dhzm4x
  choice: Exponential backoff with full jitter, capped at 30 seconds
  oversight: reviewed
```

Add `--json` for scripting. If nothing explains the line yet, `why` says so and exits `0`, so
it is safe to run speculatively.

**Anchors survive edits.** When a decision is recorded, ReasonLedger stores a short hash of the
lines it pointed at (never the code itself). Insert 20 lines above them and `why` on the new
line still finds the decision, labelled *anchor moved*. If the code was rewritten, or two
identical copies exist, the decision still matches the file and is labelled *anchor lost*.
`reasonledger status` and the UI list moved and lost anchors beside orphaned ones. Reading
never rewrites a decision file. Symbols (`path::name`) work for Python, TypeScript and
JavaScript; other languages use fingerprinted line ranges.

---

## 5. Optional extras

Each of these is independent. Skip them on a first try.

### 5.1 Backfill decisions from docs you already have

Most repos have decisions buried in `CLAUDE.md`, `.cursorrules` or `docs/*.md`. `import`
reads them with a model you choose and stages **proposals**; nothing reaches the ledger until
you confirm.

```bash
reasonledger config --provider anthropic --model claude-sonnet-5 --api-key-env ANTHROPIC_API_KEY
reasonledger import --extracted-by anthropic/claude-sonnet-5
reasonledger status
reasonledger confirm --all --confirmed-by sam
```

Only the *name* of the environment variable is stored, never the key. A local model (Ollama or
similar) works too and keeps everything on your machine. Later, `reasonledger catchup` imports
only what changed since the last run (`--dry-run` shows the delta without calling a model).

### 5.2 Check for contradictions

Similar wording is not a contradiction, so this takes two steps:

1. **Related.** Each decision is compared with its nearest neighbours by context. `status` and
   the UI list these pairs as *related, not judged yet*.
2. **Judged.** A model decides whether each related pair answers the same question with
   answers that cannot both hold. Only those are called **conflicts**.

```bash
reasonledger judge --dry-run     # how many pairs would be judged; no model call
reasonledger judge               # verdicts land in .reasonledger/verdicts.yml
```

No model configured? Ask your coding agent to call the MCP tool `get_judging_task` and answer
with `submit_verdicts`; the result lands in the same file. Commit `verdicts.yml` so teammates
and CI reuse it.

If a flagged pair is a false alarm, dismiss it once for the whole team:

```bash
reasonledger dismiss dec_abc123 dec_def456 --reason "different subsystems, coincidental wording"
```

Editing either decision re-opens the pair, so a dismissal cannot hide a contradiction that
appears later. To fail a pull request on a judged conflict, add
`reasonledger check --decisions --base origin/main` to CI.

### 5.3 Map decisions to modules

```bash
reasonledger map --scan          # no model, nothing sent
```

This proposes a module map from the structure of your repo into `.reasonledger/modules.yml`. Once you
confirm modules, the UI shows which decisions cover each module and which modules have none.
Your agent can build a better map with the MCP tools `get_mapping_task` and
`submit_module_map`.

---

## 6. The review UI

```bash
reasonledger ui      # serves on 127.0.0.1 until you press Ctrl+C
```

| Tab | Shows | Fills in when |
|---|---|---|
| **Review** | A getting-started checklist, then proposals and decisions waiting for you | Your agent records a decision, or you `import` |
| **Map** | Your modules and the decisions that cover them | A map exists (§5.3) |
| **Organize** | A workbench to move files between modules and place decisions | A map exists (§5.3) |
| **Settings** | The model for `import` and `judge`, and what may be sent to it | Any time; the default is no model |

An empty tab means nothing has been recorded yet, not that something is broken.

---

## 7. What leaves your machine

By default, nothing: no model is configured, and capture, review and `why` need none. A local
model never leaves your machine. A model elsewhere gets nothing until you allow each kind of
data, per repo:

| Kind | Sent by | What it is |
|---|---|---|
| `decision_text` | `judge` | The context and choice of your decisions |
| `paths` | `map` | File and route paths; never file contents |
| `repo_text` | `import`, `catchup` | Your docs, and your commit messages with their bodies; never diffs or authors |

The first time a command needs a kind you have not allowed, it shows what it would send and
asks. In CI it refuses instead. Manage this with `reasonledger consent` or in **Settings**. The
choice is stored in your user config, not in the repo. `reasonledger consent --preview repo_text`
prints how many docs and commit messages would go, which are held back, and one message exactly
as it is sent.

A choice is tied to the address it was given for: its scheme, host and port. Pointing the repo at
another provider, or the same host on another port, asks again. (Choices recorded by earlier
versions named only a host and are asked for once more.) A base URL must use `https` unless the
model is on this machine (`localhost`, `127.0.0.1`, `::1`), must not carry a user name, password
or query string, and a provider that answers with a redirect is refused rather than followed, so
your API key only ever goes to the address you configured.

Embeddings are always computed on your machine; decision text is never sent anywhere to embed it.

**What is and is not checked.** Decision text is free text that people and agents write, and
`repo_text` is your docs and commit messages as they are. ReasonLedger checks both for common
patterns only (email addresses, phone numbers, US SSNs, card-like numbers, private-key headers
and a few API key shapes such as `sk-`, `AKIA` and `ghp_`). A decision record that matches is
refused. A doc or commit message that matches is held back whole before anything goes to a model
elsewhere: `import` and `catchup` list it by path and pattern, never the match, and `catchup`
leaves its watermark where it was so the next run reads it again once you fix it. That catches
accidents, not everything: a secret or personal detail in another shape passes. Keep such details
out of decision text and out of the docs you import, and treat what you allow in the table above
as including whatever those fields contain. A doc that is a symlink to a file outside the repo is
never read.

If your coding agent does the judging or mapping over MCP, ReasonLedger itself sends nothing;
the agent sees only what it can already see in your repo.

---

## 8. Commands you will use

| Command | Does |
|---|---|
| `reasonledger init` | Set up `.reasonledger/` and the MCP config in a repo |
| `reasonledger ui` | Review in the browser |
| `reasonledger status` | What is waiting, stale, related or in conflict |
| `reasonledger approve <id>` | Give a pending decision a verdict, as your git identity |
| `reasonledger retire <id> --reason <why>` | Take a decision that no longer applies out of force |
| `reasonledger supersede <id> --successor <id> --reason <why>` | Settle two decisions that clash: the first is kept as history and points at the one that stands |
| `reasonledger why <path[:line]>` | Which decision explains this code |
| `reasonledger import` / `catchup` | Propose decisions from docs and commits |
| `reasonledger confirm` / `reject` | Accept or drop a proposal |
| `reasonledger judge` / `dismiss` | Judge related pairs; mark a false alarm |
| `reasonledger map --scan` | Propose the module map without a model |
| `reasonledger consent` | Show or change what may be sent to a model |

`reasonledger <command> --help` lists every flag. The policy gate (`check --policy`), the
HTML snapshot and the rest are in [`product-guide.md`](product-guide.md).

---

## 9. If you are trying this for someone

For your own trial:

The most useful test is on your own repo, during real work:

1. Do §2 and §3, then work with your agent for a session or two.
2. Review what it recorded (§4.2).
3. A few days later, run `why` on a line the agent wrote.

What the author most wants to know:

- Did the agent record decisions without being reminded? Were they real decisions or noise?
- Was reviewing them a chore?
- Did `why` point at the right decision? Did you reach for it again unprompted?
- Where did you get stuck, and what would make you stop using it?
