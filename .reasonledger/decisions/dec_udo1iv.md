---
id: dec_udo1iv
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
proposed_by: human
recorded_at: '2026-11-09T22:58:57.657148Z'
justifies:
- packages/core/src/reasonledger_core/decisions/fingerprint.py::resolve_anchor
- packages/core/src/reasonledger_core/decisions/fingerprint.py::fingerprint_loci
- packages/core/src/reasonledger_core/reasoning/why.py::resolve_why
- packages/core/src/reasonledger_core/reasoning/ts_symbols.py::extract_ts_symbols
watchers: []
confidence: medium
context: A path:START-END locus drifts as soon as lines are added above it, and symbol
  anchoring existed only for Python, so why went wrong or file-level after ordinary
  edits in any other language. How should anchors stay correct without a parser dependency
  and without rewriting decision files on read?
choice: 'At record time store a truncated hash of the normalised lines (blank lines
  and trailing whitespace ignored) per line locus in an optional anchor_hashes map.
  At read time try the stored range, then slide a window of the same non-blank size
  over the file: exactly one match is moved, none or several is lost and falls back
  to a file-level match. Readers report moved and lost and never write. TS and JS
  get a conservative stdlib extractor that masks comments, strings, templates and
  regexes and returns no symbol whenever the text is ambiguous.'
alternatives_rejected:
- 'Add tree-sitter for per-language symbols: a new runtime dependency and grammar
  per language, ruled out by the charter'
- 'Rewrite loci to the new range on read: mutates evidence on a read path and makes
  why a writer'
- 'Store the anchored lines as text: stores source code, which AGENTS section 7 forbids'
- 'Guess a symbol when the TS span is unclear: a wrong symbol is worse than a fingerprinted
  range'
assumptions:
- Blocks over 200 non-blank lines are rarely moved intact, so they are not slid and
  only distinguish intact from changed
- The block size at record time is recovered by trying every size up to the old range
  length, since only the hash is stored
- An unterminated quote in JSX text makes the whole file yield no symbols, which is
  conservative
---

## Context

A path:START-END locus drifts as soon as lines are added above it, and symbol anchoring existed only for Python, so why went wrong or file-level after ordinary edits in any other language. How should anchors stay correct without a parser dependency and without rewriting decision files on read?

## Choice

At record time store a truncated hash of the normalised lines (blank lines and trailing whitespace ignored) per line locus in an optional anchor_hashes map. At read time try the stored range, then slide a window of the same non-blank size over the file: exactly one match is moved, none or several is lost and falls back to a file-level match. Readers report moved and lost and never write. TS and JS get a conservative stdlib extractor that masks comments, strings, templates and regexes and returns no symbol whenever the text is ambiguous.

## Alternatives rejected

- Add tree-sitter for per-language symbols: a new runtime dependency and grammar per language, ruled out by the charter
- Rewrite loci to the new range on read: mutates evidence on a read path and makes why a writer
- Store the anchored lines as text: stores source code, which AGENTS section 7 forbids
- Guess a symbol when the TS span is unclear: a wrong symbol is worse than a fingerprinted range

## Assumptions

- Blocks over 200 non-blank lines are rarely moved intact, so they are not slid and only distinguish intact from changed
- The block size at record time is recovered by trying every size up to the old range length, since only the hash is stored
- An unterminated quote in JSX text makes the whole file yield no symbols, which is conservative
