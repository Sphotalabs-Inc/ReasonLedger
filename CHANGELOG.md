# Changelog

Versions move in lockstep across `reasonledger-core`, `reasonledger` and `reasonledger-mcp`.

## 0.3.0a9 — pre-release

### Fixed

- Installing on an Intel Mac no longer needs a Rust compiler. `mcp` pulls in `cryptography`, whose
  releases from 49 on ship no Intel macOS wheel, so pip and uv built it from source and failed
  without Rust 1.83 or newer. `reasonledger-mcp` now keeps Intel Macs on `cryptography<49`, which
  has the wheel; every other platform is unchanged.
- The hint shown when the local embedder is missing names this release
  (`pip install 'reasonledger[embeddings]==0.3.0a9'`). Without a version, pip skips pre-releases
  and found nothing to install.

### Added

- A "Help test the alpha" section in the README, and bug-report and feedback forms for GitHub
  issues that ask for the version, OS, install method and coding agent.

## 0.3.0a8 — pre-release

### Fixed

- `init` writes an MCP command that starts the install which ran it. A pip install run from its
  venv without activating it used to get `uvx reasonledger mcp`, which fails where uv is absent and
  otherwise fetches a different version; an older `reasonledger` earlier on `PATH` used to serve the
  new install's repo. The bare `reasonledger` is still written when `PATH` finds this same install,
  the absolute path of the launcher otherwise, and `uvx` only from a `uvx` run.
- The three packages require each other at exactly the release version, the `[embeddings]` extra
  included. A range let `pip install -U reasonledger` keep an older core or MCP server beside the
  new CLI. The release tag check refuses a tag while any sibling pin differs from it.
- The welcome, the `init` embeddings tip and the local-embedder hint link to the install docs on
  GitHub instead of `docs/install.md`, which is not in the wheels.
- The MCP server's `initialize` reply reports the `reasonledger-mcp` version instead of the `mcp`
  SDK's.

## 0.3.0a7 — pre-release

### Changed

- The GitHub Actions workflows run on the Node 24 releases of `actions/checkout`,
  `astral-sh/setup-uv`, `actions/upload-artifact` and `actions/download-artifact`, each pinned by
  commit SHA, and Dependabot keeps those pins current weekly. This clears the Node.js 20
  deprecation warning in CI and Release.
- `why` is now described everywhere as answering for "a line, function, or file", which is what it
  accepts (`why <file>`, `why <file>:<line>`, `why <file>::<function>`): the CLI help, the bare
  command's welcome, the README and the docs. The README and user manual show all three forms.
- The PyPI READMEs carry CI and PyPI badges, a "Watch the demo" poster linking to the demo video, and
  absolute links only.
- Bare `reasonledger` (and `rl`) now prints a short getting-started guide and exits 0 instead of
  an argparse "arguments are required" error. In a folder that already has `.reasonledger/` it
  leads with `reasonledger status`; otherwise with `reasonledger init`.
- `reasonledger --help` lists the commands in groups (everyday, review, setup, advanced).
- A mistyped command suggests the closest real one (`reasonledger intt` -> "Did you mean `init`?")
  and points to `reasonledger --help`. It still exits 2, and other usage errors are unchanged.

## 0.3.0a6 — pre-release

First release cut from the public repository. It carries the `0.3.0a5` changes below unchanged;
the number moves because `0.3.0a5` was rehearsed before the repository was published and a version
can never be reused on an index.

## 0.3.0a5 — pre-release

### Security

- The secret linter now recognises Anthropic, OpenAI project, GitHub (classic and fine-grained),
  Slack, Stripe and Google keys, JWTs and PEM private-key headers. A phone number now needs
  separators or parentheses, so Unix timestamps and counts no longer read as one, and an SSH remote
  such as `git@host` is no longer taken for an email. A secret with no recognisable shape still passes.
- `reasonledger ui` refuses any request whose `Host` is not the address it printed, which closes a
  DNS-rebinding route to the session token. Open the UI at the `127.0.0.1` URL it prints, not `localhost`.
- `reasonledger-core` no longer reads a `.env` file from the current directory, and the settings
  nothing used (`RL_FIXTURES_ROOT`, `RL_BACKFILL_MONTHS`, `RL_CRITICAL_PATH_GLOBS`, the OIDC, GitHub App
  and attestation keys, `RL_CONFLICT_ENDPOINT_URL`) are gone. `RL_EMBEDDING_PROVIDER` remains.

- Consent now matches what is sent: a model call that includes repository text says so, screens it
  for PII and secrets first, and `--preview` shows exactly what would be sent. Paths read from a
  repository must stay inside it (a symlink out of the checkout is refused), and model endpoints
  must be HTTPS and are never followed through a redirect.

### Release

- The release workflow refuses a tag that disagrees with the package versions or is not on `main`,
  publishes in dependency order (core, MCP, CLI) and uploads the exact files the gate tested.
- `scripts/verify_published.py` ends the MCP server and everything `uvx` started for it before its
  temporary directory is removed (Windows could not delete a directory a live process was in), and
  re-reads the index on each retry instead of a cached miss.

### Removed from `reasonledger-core`

- The coverage rollups and the audit report (`reasonledger_core.coverage`, `reasonledger_core.audit`,
  `CoverageMetrics`, `compute_coverage_metrics`) with their models, tests and goldens. They computed
  org-level figures that no command or MCP tool used.

### Licence and legal files

- Every package carries `NOTICE` beside `LICENSE` and names SphotaLabs Inc. as author. The repository
  gains `TRADEMARKS.md`, `CONTRIBUTING.md` (DCO sign-off, no CLA) and `SECURITY.md`.

### Windows

- The CLI writes UTF-8 to stdout and stderr, so a legacy code page no longer garbles `—` or raises
  `UnicodeEncodeError`.

### Packaging

- The logo no longer carries an embedded content-credentials manifest, which shrinks it by 44%.
- The core and MCP READMEs match what is published and what `init` writes (`pip install --pre`, the
  `reasonledger mcp` command), the user manual and runbook describe `init`'s agent detection, and the
  release checklist globs name the version.

### MCP

- `get_judging_task` takes optional `decision_a` and `decision_b`: naming both returns only that
  pair and tells the agent to stop. A pair that is not waiting for a verdict comes back empty with a
  note saying why. Batch instructions now continue only unless the user asked for a set number of
  pairs or one pair.
- `submit_candidates` returns a one-line `summary` (sources read, proposals staged or none found,
  how many remain), and `get_import_task` returns `total` and `done`. The agent is told to relay the
  summary, so a batch with no decisions is no longer silent.

### CLI

- `reasonledger judge --pair A B` judges one pair with the configured model (works with `--dry-run`).
- The `judge` and `import` errors for a repo with no model now point to the agent route.
- `init` tells Cursor users that Cursor reads `.cursor/mcp.json` only from the folder it has open.

### Local UI

- Settings says a model is optional and that the default is your coding agent's own model.
- The Map banner has an "Open Edit map" button for unplaced files and proposed modules.
- Confirm no longer asks "Confirm <id> as <name>?"; it confirms, then says who it was recorded as.
- A judged pair leads with "Verdict: Compatible." or "Verdict: Conflict.", then the reason, then
  "Judged by <tool/model> on <date>". Each unchecked pair shows an exact prompt for your agent, and
  the Check for conflicts card explains the every-pair, few-pairs and one-pair prompts.

## 0.3.0a4 — pre-release

### Open-core boundary

- **Removed from `reasonledger-core`:** the attestation log, evidence packs and GRC connectors, with
  their models and tests. They are the commercial tier and are no longer published. Nothing on the
  developer path used them; `reasonledger check --policy` is unchanged.
- `reasonledger_core` no longer exports `AttestationLog`, `verify_chain` or `verify_checkpoint`, and
  the `cryptography` dependency is gone.

## 0.3.0a3 — pre-release (TestPyPI only)

### MCP

- `get_import_task` and `submit_candidates`: your coding agent can propose decisions from the docs
  and commit messages it can already read, so backfill needs no API key and no local model. The
  proposals are staged like any other import; a person confirms each one.

### Local UI

- The setup step offers the agent route for importing, next to the configured-model route.

## 0.3.0a2 — pre-release (TestPyPI only)

- `cryptography` 50 is now the minimum, and the lock file takes the patched releases for the open
  dependency advisories. No behaviour change.

## 0.3.0a1 — pre-release (TestPyPI only)

A pre-release because the decision record format gained fields and a published version number
can never be reused.

### CLI

- `reasonledger mcp` runs the MCP server, so `uv tool install reasonledger` is the whole install (S57).
- `init` sets up only the agents the repo uses (`--agents all` for every one), writes `policy.yml`
  only with `--policy`, and its own rule files no longer count as decision candidates (S58).
- `why` prints the context, the choice, the rejected alternatives and who approved it; `--short`
  keeps the old three lines. A miss in a file that has decisions elsewhere lists them instead of
  saying nothing is recorded; `--json` gains an additive `nearby` list; the `why_invoked` metric
  records `match: near` (S59).

### Local UI

- Check related decisions for conflicts from the Review tab or one pair at a time from Ask: the same
  run as `reasonledger judge`, in the background, with progress and Stop. It starts only on a click.

### Decision record format (additions only; a 0.2.0 file loads and round-trips unchanged)

- `retired` status with `retired_by`, `retired_at`, `retired_reason` (S45).
- `superseded_by`, `superseded_decided_by`, `superseded_at`, `superseded_reason`, written on a
  decision when a person chooses another existing decision to stand in its place
  (`reasonledger supersede <id> --successor <id> --reason`, or Keep on a conflict in the UI).
  The decision that stands is not rewritten.
- `recorded_at` on every new record whatever its source, `approved_at` on `approve` and
  `confirm` (S45). Old files are not rewritten; views derive a missing `recorded_at` from git
  and label it.
- Optional `anchor_hashes`: a truncated hash of the lines each `path:START-END` locus pointed at,
  so `why` finds the code after it moves. It is a hash, never source (S52).

### Security

- **Decision ids are validated.** An id must look like `dec_` then lowercase letters, digits or `_`;
  anything else (such as `../../x`) is refused, and `record_decision` never overwrites an existing
  record.
- **A replacement takes effect when a person approves it.** `record_decision` with `supersedes`
  used to take the old decision out of force at once, while the replacement was still pending. The
  old decision now stays in force until `approve`; a rejected replacement changes nothing.
- **No remote embeddings.** The `remote` embedding provider, which could send decision text to a
  configured URL without consent, is removed. Embeddings are local (`deterministic` or `local`).
- **MCP is stdio only.** `--transport streamable-http`, `--host` and `--port` are removed: there was
  no authentication or TLS in front of that listener.
- **Data-handling wording narrowed.** The PII linter is documented as a pattern check for common
  accidents, not a guarantee that free text or imported docs hold no personal data or secrets.

### Changed behaviour

- `pip install reasonledger` now also installs `reasonledger-mcp`, so `reasonledger init` works without
  `uv` or a second install.
- **MCP `record_decision` can no longer grant a verdict.** `approved_by` and `oversight` stay in
  the signature for one release so existing rule files keep working, but they are ignored and the
  result carries a warning: every record is saved `pending` and a person gives the verdict with
  `reasonledger approve` or in `reasonledger ui` (S45).
- `confirm --confirmed-by` and `modules confirm|place --by` default to the checkout's git
  `user.name`, like `approve` and `retire` (S45).
- `check --decisions --base <ref>` warns when a verdict's recorded name differs from the author of
  the commit that added it; `--strict-identity` makes that fail (S45).
- **`query_decisions` result shape** (S50): at most `limit` hits (default 10), each compact (`id`,
  `context`, `choice`, `justifies`, `status`, `oversight`, `proposed_by`, `superseded_by`;
  `retired_reason` when retired), decisions in force first, plus `total` and `truncated`. Pass
  `full: true` for each record's `markdown`. The `top_k` parameter is replaced by `limit`.
- **Strict policy parsing** (S49): an unknown key in `policy.yml` is an error naming the rule, the
  key and the keys allowed there, and `reasonledger check` exits `2` instead of ignoring it. A
  policy that used `ai_assisted: true` under `when` was silently matching more than intended.
- `why` reports `moved` and `lost` anchors; `status` and the UI list them beside orphaned ones.

### Added

- `reasonledger init` writes each agent's MCP config and rule — Claude Code, Cursor, VS Code
  (Copilot) and `AGENTS.md` readers — instead of printing the rule. `--agents` and `--no-rules`
  select; a second run changes nothing (S46).
- MCP `decisions_for(paths, line)`: the decisions in force that cover a file, before editing it (S51).
- TypeScript and JavaScript symbol anchors, with no new dependency (S52).
- `reasonledger --version` and `reasonledger-mcp --version`.
- CI runs the full suite on macOS and Windows (S53).
