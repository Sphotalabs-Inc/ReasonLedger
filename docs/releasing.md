# ReasonLedger — Releasing

**Audience:** maintainers publishing the packages. If you are installing ReasonLedger, you want [`install.md`](install.md) instead — publishing is not a step users perform.

**Status:** the current version is `0.3.0a9`, an alpha. Publishing is done only by the **Release** workflow (`.github/workflows/release.yml`) using PyPI Trusted Publishing: no API token exists, and none belongs in this repository or in a maintainer's shell. This page is the procedure.

Publishing is **not** what makes ReasonLedger installable — [`install.md`](install.md) already documents a working `uv tool install` from a checkout, and that is the supported path today. What publishing buys is dropping the clone: `uvx reasonledger` from a machine that has never seen this repo.

---

## What gets published

Three packages, versioned in lockstep, all at `0.3.0a9`:

| Dist name | Source | Depends on |
|---|---|---|
| `reasonledger-core` | `packages/core` | — |
| `reasonledger` | `packages/cli` | `reasonledger-core>=0.3.0a1,<0.4.0`, `reasonledger-mcp>=0.3.0a1,<0.4.0` |
| `reasonledger-mcp` | `packages/mcp` | `reasonledger-core>=0.3.0a1,<0.4.0` |

**Publish in this order: `reasonledger-core`, then `reasonledger-mcp`, then `reasonledger`.** Each pins the ones before it to the same version, and an index cannot resolve a pin until its target is there. If `reasonledger` lands before `reasonledger-mcp`, it is uninstallable until the MCP server arrives.

## Before you publish

Run the full gate from the repo root, on a clean tree:

```bash
./scripts/release_gate.sh
```

It runs ruff, mypy, phases 1–5 and `check_dists.sh`, and stops at the first failure.
The gate also refuses a tracked change anywhere and an untracked file under `packages/`, because a build reads the directory, not the git index. `check_dists.sh` is the one that matters here. It builds all six artifacts, asserts the CLI wheel carries its `ui_assets/`, asserts no sdist ships a symlinked LICENSE, then installs the wheels into a fresh venv with the checkout off `PYTHONPATH` and drives the CLI end to end: `--version`, `init`, `status`, an MCP `record_decision` round trip followed by `why`, and the UI. If it passes, the artifacts are self-sufficient. In the release workflow the gate sets `DIST_DIR=dist`, so `check_dists.sh` builds into `dist/` and tests those files, and those are the files that get uploaded; locally it uses a temporary directory and discards it.

## Build

```bash
rm -rf dist
uv build --package reasonledger-core --out-dir dist
uv build --package reasonledger      --out-dir dist
uv build --package reasonledger-mcp  --out-dir dist
ls dist
```

Expect six files — a `.tar.gz` and a `.whl` for each package.

> **Use plain `uv build`, not `uv build --wheel`.** `--wheel` builds directly from the source tree; a bare `uv build` builds the sdist first and then the wheel *from that sdist*, which is the only path that exercises what an sdist can actually carry. All three packages once had a `LICENSE` symlink pointing outside their directory: `--wheel` was green, `uv build` failed, and the sdists shipped a dangling link. `check_dists.sh` now covers this.

## Publish

`release.yml` runs the gate (which builds and tests the files it uploads), then publishes core, then the MCP server, then the CLI, using PyPI Trusted Publishing: no token in the repo, and no manual `uv publish`. A tag push goes to PyPI; a manual run always goes to TestPyPI and has no way to reach PyPI.

1. One-time, on pypi.org and test.pypi.org, for each of the three projects: add a trusted publisher for this repository and workflow `release.yml`. PyPI allows one pending publisher per repository, workflow and environment, so each project has its own environment: `reasonledger-core` → `pypi-core`, `reasonledger` → `pypi`, `reasonledger-mcp` → `pypi-mcp` (TestPyPI: `testpypi-core`, `testpypi`, `testpypi-mcp`). Create the same six environments under the repository's Settings → Environments, and make the maintainer a required reviewer on the three `pypi*` ones, so a tag push waits for an approval on each publish job.
2. Rehearse: Actions → Release → Run workflow (it always uploads to TestPyPI). Then verify from that index in a scratch repo, with an **absolute** `--root` because `uvx` runs from wherever you are:

   ```bash
   uvx --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ \
       reasonledger status --root /absolute/path/to/an-app
   ```

   The `--extra-index-url` is required: TestPyPI does not mirror real dependencies like `pydantic`.
3. Release: push the tag (`git tag v0.3.0a9 && git push origin v0.3.0a9`). **The tag is the maintainer's step.** The workflow refuses a tag that is not exactly `v` plus the version the packages declare, or that points at a commit `main` does not contain.

A version number on an index can never be reused, even after deletion, so a fix after publishing ships as the next pre-release (`0.3.0a10`).

## After the first publish

Once all three are on PyPI, the install story changes and the docs must follow:

1. [`install.md`](install.md) — move `uvx reasonledger` / `uv tool install reasonledger` from "planned" to the primary path; keep the checkout flow for contributors.
2. [`product-guide.md`](product-guide.md) — its commands still say `uv run`.
3. [`README.md`](../README.md) — the Status section.

Do not update any of these in advance. Documenting a command that does not resolve yet sends users to a failure with no way to tell whether the problem is them or the tool.

## First-release checklist

Copy into the release PR. Nothing below has been done yet.

**Blocked on a human — these cannot be automated away:**

- [ ] Claim the three names on **TestPyPI** and confirm they are free on **PyPI**. `reasonledger`, `reasonledger-core`, and `reasonledger-mcp` are all unclaimed as of this writing; if any is taken by the time you get there, the dist names change and so does every `pyproject.toml` and the `[tool.uv.sources]` block in `packages/cli` and `packages/mcp`.
- [ ] Register the trusted publishers and create the six GitHub environments (see step 1 of *Publish*). There is no API token to generate.
- [x] Release version decided: `0.3.0a9` (pre-release); `0.3.0` follows the friend test. A fix after publishing ships as `0.3.0a10`.

**Gate — all green before any upload:**

- [ ] `./scripts/release_gate.sh` (ruff, mypy, phases 1–5, `check_dists.sh`)
- [ ] Working tree clean, with no untracked file under `packages/` — `uv build` packages what is on disk, not what is committed. The gate checks both.

**Upload, by the Release workflow only (core → MCP → CLI):**

- [ ] Run the workflow manually (TestPyPI) and confirm `gate`, the three publish jobs and `verify` are green
- [ ] Push the tag; approve each `pypi*` deployment as it comes up
- [ ] Verify from PyPI: `uvx reasonledger --help` and `uv tool install reasonledger`

**Post-publish doc flip** — only after the PyPI verification above actually succeeds:

- [ ] [`install.md`](install.md) — promote `uv tool install reasonledger` above the checkout build; the "Installing from PyPI (not yet)" section becomes the primary Install section, and the current one becomes the contributor path
- [ ] [`product-guide.md`](product-guide.md) — the install pointer
- [ ] [`README.md`](../README.md) — the Status section
- [ ] This page's **Status** line

## Versioning

- Conventional Commits drive the change log; the three `pyproject.toml` versions move together.
- The release workflow runs `scripts/check_release_tag.py` on a tag push and stops unless the tag is exactly `v` plus the version all three packages declare. The upload takes its number from `pyproject.toml`, not from the tag, so this is what stops `v0.3.0a9` publishing `0.3.0a5`. It then stops unless the tagged commit is already on `main`. A TestPyPI rehearsal has no tag and skips both checks, and can only reach TestPyPI.
- The workflow's actions are pinned to commits (the comment beside each names the tag), and the three `pyproject.toml` files require `hatchling>=1.27,<2`. 1.27 is the first release whose wheels carry `License-Expression` and the `LICENSE` and `NOTICE` files (1.26.2 builds without error but its wheels carry neither, which `check_dists.sh` would catch). Bump a SHA and its comment together.
- The packages pin each other exactly (`reasonledger-core==X`, including the `[embeddings]` extra), so every version bump also bumps those pins in `packages/cli` and `packages/mcp`. A range would let `pip install -U reasonledger` keep an older core or MCP server beside the new CLI, a pairing no release was tested as. `check_release_tag.py` refuses a tag while any sibling pin differs from it, and `test_check_release_tag.py` and `test_dist_packaging.py` fail on the tree before that.
