# AGENTS.md — ReasonLedger Engineering Charter

Canonical rules for any agent or human contributing to this repo. `README.md` and `docs/` describe **what** the product does; this file governs **how** to change it.

Every client is pointed here rather than given its own copy: `.cursor/rules/index.mdc` references it, and `CLAUDE.md` imports it (Claude Code reads `CLAUDE.md`, not `AGENTS.md`). Edit this file; the others are thin pointers.

## 0. Prime directives

- **When in doubt, ASK.** Never guess on product scope, security, data handling, schema, or architecture. A clarifying question is always cheaper than a wrong build. If the docs are silent or ambiguous, stop and ask.
- **Do not invent scope.** Build what the task asks; anything beyond it, ask first.
- **Respect the phase gate.** Don't start phase N+1 until phase N's acceptance suite *and* all prior suites are green.
- **These records are evidence of who decided what: correctness and security outrank speed.** No shortcuts on the paths that carry trust (policy, the PII linter, approval).

## 1. Stack (pinned — do not substitute without asking)

- **Developer path:** Python 3.12 · Pydantic v2 · `uv` · `ruff` (lint+format) · `mypy` (strict) · `pytest` + `pytest-cov`.
- **Local UI:** stdlib HTTP server + static assets inside the CLI package (no Node runtime required).
- **Hosted and commercial features** live outside this repository and are never added here.
- **Shared:** Conventional Commits. No new runtime dependency without justification (§7).

## 2. Repository structure (canonical)

```
packages/
  core/       Framework-free domain logic: provenance, oversight, policy,
              decision format, PII linter. The audit-critical heart.
  cli/        `reasonledger` CLI (e.g. `check`, `ui`) — depends on core
  mcp/        MCP server (Phase 3) — depends on core
fixtures/     recorded GitHub data, golden artifacts, decision corpus
tests/        cross-package integration + e2e; unit tests live beside their package
docs/         install, usage, integration and release documentation
```

- **Domain logic lives in `packages/core`, framework-free**, so cli and mcp share one implementation. Never duplicate domain logic into an app.
- **Apps stay thin:** the CLI, MCP server and local UI keep orchestration separate from domain logic in `core`.

## 3. Code quality

- **No dead code.** No commented-out blocks, unused exports, speculative abstractions, or "just in case" parameters. Delete it — git remembers.
- **DRY / single source of truth.** Shared logic → `core` or a shared util; shared types → one definition. No copy-paste.
- **Small units.** Soft file limit **300 lines**, hard **400** — split before exceeding. Functions do one thing, prefer <50 lines, keep complexity low.
- **Efficient.** No work that grows per item inside a loop (a file read or subprocess per record); cache what is expensive and key the cache on what it depends on.
- **Self-documenting names**; comments explain *why*, not *what*; match surrounding style.

## 4. No hard-coding

- No magic numbers/strings — named constants or config.
- All config via a **single typed settings module** (typed settings from the environment, in `core`). No secrets, URLs, thresholds, or paths inline.
- Output-affecting thresholds (confidence, similarity) are **named, documented, test-pinned** config.

## 5. Local UI

- **One design-token source:** CSS variables in `style.css`. No hard-coded colors or inline style values in the assets.
- Hand-written HTML, CSS and JS served by the stdlib server; no Node toolchain and no bundler. Every dynamic string goes through `escapeHtml`, and live panels reach the server only through `RLApi` (`api.js`), never a hand-written `fetch`.
- Accessibility: semantic HTML, keyboard nav, ARIA where needed. No a11y regressions.

## 6. Records and logging

- Business logic stays in `core`; the UI server only routes, checks the session token, Origin and Host, and calls `core`.
- **Append-only invariants** (e.g. a decision id is never overwritten) enforced in code, not by convention.
- Structured logging; **never log secrets, tokens, or PII** (PII discipline is a product feature).

## 7. Security (first-class — it's the product's domain)

- **Least privilege:** read-only unless a command must write. The tool asks for no GitHub token or scope.
- **Secrets** via the environment only, never committed; config stores the *name* of the variable, never its value.
- **Data minimization:** store metadata + evidence pointers; **never store, export or send source code** — enforced by a test. A local, loopback-only viewer MAY read working-tree files on request; that content is never persisted, cached, exported or included in a model prompt.
- Treat all external input as untrusted and validate it: change JSON, model output, files read from the repository, and every HTTP request to the local UI.
- Dependency hygiene: minimal, pinned, vetted; audit in CI. Hashing uses the standard library; never roll your own crypto.
- Anything touching auth, signing, scopes, or data handling that's unclear → **ASK** (§0).

## 8. Testing

- Each phase has an acceptance suite tagged `phase-N`; a phase is done only when it + all prior suites are green.
- **Test alongside code**, not after. `core` is TDD-friendly and gets the highest coverage.
- **Determinism:** no live network or live LLM in CI — recorded GitHub fixtures, stubbed/replayed inference, checked-in golden/snapshot artifacts.
- Coverage: **≥80% overall; 100% + property tests** on policy evaluation and the PII linter.

## 9. Workflow

- Phase order; small, focused commits (Conventional Commits, e.g. `feat(core): add co-author trailer detector`).
- Before "done": `ruff`, `mypy` and the relevant `phase-N` tests pass locally.
- Update `docs/` when behavior intentionally changes; regenerate goldens deliberately.
- No new dependency, top-level directory, or service without checking this file or asking.

## 10. Decision capture — we dogfood this product (MANDATORY)

ReasonLedger exists because the reasoning behind AI-assisted code evaporates when the
session ends. Capture does not happen unless something makes it happen, so in this repo
it is a rule, not a habit. This section is that rule.

### Before editing and before deciding

Before editing a file, call MCP `decisions_for` with its path: it returns the decisions in force that
cover that code. Then, before a choice:

Call MCP `query_decisions` (`semantic: true`) with a short description of what you are
about to decide. If a prior decision covers it, follow it or supersede it explicitly (pass its id as
`supersedes` to `record_decision`) — do not silently contradict it.

### After deciding — the trigger is narrow and the bar is real

Call MCP `record_decision` when, and only when, **you chose between two or more viable
alternatives and the choice changed the code or the constraints on it.**

Record: picking a data structure, algorithm, dependency, protocol, schema shape, error
strategy, or boundary. Widening or narrowing a public contract. Accepting a tradeoff
you'd have to re-argue in six months.

Do **not** record: renames, formatting, mechanical refactors, test-only edits, doc
typos, dependency version bumps, or carrying out an explicit instruction where you
exercised no judgement. A thin ledger of real decisions beats a fat one of noise —
noise is what killed a decade of ADR adoption.

### Field discipline — these three rules exist because violating them is measurable

1. **`context` and `choice` must say different things.** `context` is the question that
   was open; `choice` is what was picked. If they read the same, the record carries no
   information — a record where `context == choice == the commit subject` is strictly
   less useful than `git log`. Conflict detection also degrades: it reads exactly these two fields, so
   when they are identical the detector collapses into a similarity band-pass filter.
2. **`justifies` must carry line or symbol loci, not bare file paths.** Use
   `path/to/file.py:120-168` or `path/to/file.py::function_name`. Bare file paths match
   at the coarsest tier, and a file touched by six decisions returns six low-precision
   hits from `rl why`.
3. **`alternatives_rejected` must be non-empty.** If nothing was rejected, there was no
   decision — see the trigger above.

Always set `model` to the exact model id. Do not pass `oversight` or `approved_by`: a record written through MCP is always `pending`, and the server ignores both (with a warning). Only a person at a checkout closes it, with `reasonledger approve <id>` or in `reasonledger ui`, under their git identity. Never claim `reviewed` for a human who has not looked.

Set `proposed_by` on every record: `human` only when the user stated or explicitly accepted the choice in chat before you acted, `ai` when you chose or recommended it. It is a separate claim from `oversight` — an AI-recommended choice a person later approves is `proposed_by: ai`, `oversight: reviewed`. If unsure, say `ai`; the UI shows `human` as "agreed", and wrongly claiming it is the same kind of false evidence as claiming `reviewed`.
Never put a name, email, or any PII in free-text fields; the PII linter will reject the
record and it is committed and shared like any other file.

### Public records explain public code only

This ledger is published with the repository, so a record must explain code that is in it,
and its text must make sense to a reader who has only this repository. Do not name other
repositories or projects, customers, testers or pilots, internal documents or their sections,
or plans for work that lives elsewhere; describe what was observed instead ("on an
application with separate frontend and backend folders"). A decision about work outside this
repository is recorded where that work lives, not here. Read a record as a stranger would
before committing it.

### Verify

`reasonledger why <file>:<line>` should return the decision you just recorded. If it
returns nothing, your `justifies` loci are wrong — fix them rather than moving on.
