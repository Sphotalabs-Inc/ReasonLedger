# reasonledger

[![CI](https://github.com/Sphotalabs-Inc/ReasonLedger/actions/workflows/ci.yml/badge.svg)](https://github.com/Sphotalabs-Inc/ReasonLedger/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/reasonledger?include_prereleases&label=PyPI)](https://pypi.org/project/reasonledger/)

**Never lose the *why* behind AI-written code.** `reasonledger` is the command-line
surface of [ReasonLedger](https://github.com/Sphotalabs-Inc/ReasonLedger): it captures the
decisions behind your codebase as reviewable records, tells you which decision justifies
a line, function, or file, and checks changes against a policy in CI.

Everything it manages lives in a `.reasonledger/` directory inside your own repo. There
is no database, no daemon, no account, and nothing runs in the background.

> **Alpha (`0.3.0a7`).** Expect rough edges.

## Watch the demo

[![Watch the ReasonLedger demo: init, review in the UI, why](https://raw.githubusercontent.com/Sphotalabs-Inc/ReasonLedger/main/docs/media/demo-poster.png)](https://github.com/user-attachments/assets/548030d1-b2ea-40ab-b61b-d131aba451e5)

[Watch the demo](https://github.com/user-attachments/assets/548030d1-b2ea-40ab-b61b-d131aba451e5) (init, review in the UI, why).

## The loop

```bash
cd /path/to/your-app
uvx reasonledger init                      # .reasonledger/, the MCP config and the agent rule
uvx reasonledger ui                        # approve what your agent recorded, on 127.0.0.1
uvx reasonledger why payments/retry.py:55  # which decision justifies this line?
```

`why` works on a file, a line, or a function:

```bash
uvx reasonledger why payments/retry.py             # the whole file
uvx reasonledger why payments/retry.py:55          # one line
uvx reasonledger why payments/retry.py::with_retry # one function
```

`init` writes the MCP config and the agent rule for Claude Code, Cursor and VS Code. Your agent
then records decisions as it works; each lands as `pending` until a person approves it in the UI
or with `reasonledger approve <id>`. To keep the command on your `PATH`:

```bash
uv tool install reasonledger
reasonledger --version
```

To work on ReasonLedger itself, use a checkout of the
[monorepo](https://github.com/Sphotalabs-Inc/ReasonLedger) (see its [`docs/install.md`](https://github.com/Sphotalabs-Inc/ReasonLedger/blob/main/docs/install.md)).

## Backfill from the docs you already have

If you would rather propose decisions from existing docs than wait for your agent, `import`
reads them with a model you configure:

```bash
reasonledger config --provider anthropic \
    --model <id> --api-key-env ANTHROPIC_API_KEY
reasonledger import --root . \
    --extracted-by anthropic/<id>          # propose decisions from your docs
reasonledger ui                            # review, confirm, reject — on localhost
```

`import` proposes; it never writes to the ledger directly. A human confirms every record
that lands — that oversight step is the evidence the product exists to produce. To try the
loop with no model account at all, replay a fixture:
`reasonledger import --fixture candidates.json --extracted-by fixture`.

## Bring your own model

Extraction uses whichever provider you configure — Anthropic, any OpenAI-compatible
endpoint, or a local model. **The API key itself is never written to disk.** Config stores
only the *name* of the environment variable that holds it, so `.reasonledger/config.yml`
is structurally incapable of leaking a secret.

An Anthropic Console API key is billed separately from a Claude Pro/Max subscription.

## `reasonledger ui`

A localhost review app, stdlib-only, bound to `127.0.0.1`. It starts when you run the
command and stops when you press Ctrl-C — it is not a service. The UI ships inside this
package; only the `.reasonledger/` data lives in your repo.

It is a per-developer, per-repo tool. There is no hosted team layer yet: teams share
decisions through git.

## Console scripts

`reasonledger` and the short alias `rl` are the same entry point.

## Extras

```bash
uv tool install "reasonledger[embeddings]"   # real embeddings for conflict detection
```

Without the extra, conflict detection uses a deterministic stub embedder — fine for tests
and demos, noisier on real prose.

---

Part of the ReasonLedger workspace: [`reasonledger-core`](https://pypi.org/project/reasonledger-core/)
(domain logic) · [`reasonledger-mcp`](https://pypi.org/project/reasonledger-mcp/) (editor-spawned MCP server).
