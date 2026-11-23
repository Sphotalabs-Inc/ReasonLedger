---
id: dec_8ahl3q
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: superseded
proposed_by: human
justifies:
- packages/core/src/reasonledger_core/reasoning/topics.py::classify_pending
- packages/core/src/reasonledger_core/reasoning/topics.py::effective_topics
- packages/core/src/reasonledger_core/reasoning/topics.py::topic_descriptions
- packages/core/src/reasonledger_core/views/ledger.py::build_ledger_view
- packages/cli/src/reasonledger_cli/topics_cmd.py::run_topics_cmd
- packages/cli/src/reasonledger_cli/ui_assets/browse.js::groupDecisions
watchers: []
context: The Find-a-decision card grouped by the directory of each decision's code
  anchors, which in a layered codebase sorts by layer (routes, services, models) rather
  than the business function a reader wants. How should decisions be grouped by function,
  and where should that grouping live?
choice: Add an optional topics list to decision frontmatter, which always wins. For
  decisions without one, a new explicit reasonledger topics command has the configured
  model pick from a fixed list (specs/modules names with their title and purpose,
  plus a taxonomy list in topics.yml, plus topics already in use), capped at two,
  and commits the answers to .reasonledger/topics.yml under a context-and-choice fingerprint.
  The view and UI only read that file and group by topic, falling back to folder for
  unfiled decisions; unlisted suggestions are reported, never stored.
alternatives_rejected:
- 'Cluster decisions by embedding similarity: group names are unstable and unnamed,
  so a reader cannot tell what a cluster is or trust it between runs'
- 'Let the model invent topics freely: near-duplicates (promo, promo-codes) and drift;
  a fixed list with reported suggestions keeps a person in charge of the vocabulary'
- 'Classify inside the view or UI on load: hidden model calls and cost on a read-only
  surface, the same reason judging stays an explicit command'
- 'Store topics only in frontmatter: every existing record would need editing, and
  an imported record''s text is not ours to rewrite; a separate fingerprinted file
  leaves records untouched'
- 'Ask the model for up to three topics: llama3.2 always filled all three with generic
  ones such as platform and offers, so the cap is two with a prefer-one prompt'
assumptions:
- A repo's specs/modules (or its topics.yml taxonomy) is a good enough function vocabulary;
  without one the command refuses and says where to get a list
- A local 8B model with per-topic descriptions files well enough to review; a 3B model
  did not, so the command takes a --model override
- Context and choice are the only fields that decide a decision's function, so editing
  them is what re-files it
superseded_by: dec_gtll6j
superseded_decided_by: iharpreet
superseded_at: '2026-11-13T05:14:34.325769Z'
superseded_reason: Topics were removed once module membership landed; decisions now
  belong to modules by their code anchors.
---

## Context

The Find-a-decision card grouped by the directory of each decision's code anchors, which in a layered codebase sorts by layer (routes, services, models) rather than the business function a reader wants. How should decisions be grouped by function, and where should that grouping live?

## Choice

Add an optional topics list to decision frontmatter, which always wins. For decisions without one, a new explicit reasonledger topics command has the configured model pick from a fixed list (specs/modules names with their title and purpose, plus a taxonomy list in topics.yml, plus topics already in use), capped at two, and commits the answers to .reasonledger/topics.yml under a context-and-choice fingerprint. The view and UI only read that file and group by topic, falling back to folder for unfiled decisions; unlisted suggestions are reported, never stored.

## Alternatives rejected

- Cluster decisions by embedding similarity: group names are unstable and unnamed, so a reader cannot tell what a cluster is or trust it between runs
- Let the model invent topics freely: near-duplicates (promo, promo-codes) and drift; a fixed list with reported suggestions keeps a person in charge of the vocabulary
- Classify inside the view or UI on load: hidden model calls and cost on a read-only surface, the same reason judging stays an explicit command
- Store topics only in frontmatter: every existing record would need editing, and an imported record's text is not ours to rewrite; a separate fingerprinted file leaves records untouched
- Ask the model for up to three topics: llama3.2 always filled all three with generic ones such as platform and offers, so the cap is two with a prefer-one prompt

## Assumptions

- A repo's specs/modules (or its topics.yml taxonomy) is a good enough function vocabulary; without one the command refuses and says where to get a list
- A local 8B model with per-topic descriptions files well enough to review; a 3B model did not, so the command takes a --model override
- Context and choice are the only fields that decide a decision's function, so editing them is what re-files it
