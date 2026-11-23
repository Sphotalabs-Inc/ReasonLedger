"""Shared extraction prompts and JSON schema (deterministic, no network)."""

from __future__ import annotations

from reasonledger_core.importer.scan import ImportSource

EXTRACTION_TOOL_NAME = "extract_decisions"

CANDIDATES_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "context": {"type": "string"},
                    "choice": {"type": "string"},
                    "source_ref": {"type": "string"},
                    "alternatives_rejected": {"type": "array", "items": {"type": "string"}},
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                    "justifies": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string"},
                },
                "required": ["context", "choice", "source_ref"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["decisions"],
    "additionalProperties": False,
}

EXTRACTION_SYSTEM_PROMPT = """\
You extract genuine engineering decisions from project prose — documentation, or a
commit message explaining why a change was made.

A decision is a choice made among alternatives — not a fact, tutorial, or TODO.

Rules:
- Extract only real decisions (context + chosen option + rejected alternatives when stated).
- Set a unique source_ref per decision as "<source-path>#<slug-of-heading-or-topic>"
  (path from the prompt; a source starting "git:" is a commit, which has no headings).
- justifies: file paths only when the source names them — never invent line numbers or loci.
- Include no PII (names, emails, tokens, internal URLs with credentials).
- decisions: [] is valid when the source contains no decisions. A commit that only
  describes what changed, without saying why, contains no decision.
"""


def build_user_prompt(source: ImportSource) -> str:
    """Build the user message for a single source extraction."""
    return f"Document path: {source.path}\n\n{source.text}"
