"""Deterministic PR-harvest — extract proposed decisions without an LLM."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from reasonledger_core.decisions.ids import generate_decision_id, harvest_decision_id
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    normalize_ai_tool,
)

_DECISION_HEADING = re.compile(
    r"^##\s+Decision\s*:\s*(?P<title>.+)$",
    re.MULTILINE | re.IGNORECASE,
)
_CHOICE = re.compile(r"(?im)^(?:choice|chose|we chose)\s*:\s*(?P<value>.+)$")
_ALT = re.compile(r"(?im)^(?:alternatives?(?: rejected)?|rejected)\s*:\s*(?P<value>.+)$")
_ASSUMPTION = re.compile(r"(?im)^(?:assumptions?)\s*:\s*(?P<value>.+)$")
_JUSTIFIES = re.compile(r"(?im)^(?:justifies|files?)\s*:\s*(?P<value>.+)$")
_AI_TOOL = re.compile(r"(?im)^(?:ai[_ -]?tool)\s*:\s*(?P<value>[\w-]+)$")
_MODEL = re.compile(r"(?im)^(?:model)\s*:\s*(?P<value>.+)$")
_PATH_IN_DIFF = re.compile(r"(?m)^\+\+\+\s+b/(?P<path>\S+)$")


def harvest_decision_from_pr(
    *,
    pr_title: str,
    pr_body: str,
    diff_text: str = "",
    decision_id: str | None = None,
    source_key: str | None = None,
    recorded_at: datetime | None = None,
) -> DecisionRecord:
    """Build a proposed decision from PR metadata (deterministic rules)."""
    resolved_id = decision_id
    if resolved_id is None and source_key is not None:
        resolved_id = harvest_decision_id(source_key)
    if resolved_id is None:
        resolved_id = generate_decision_id()
    body = pr_body or ""
    choice_match = _CHOICE.search(body)
    choice = choice_match.group("value").strip() if choice_match else pr_title.strip()
    heading = _DECISION_HEADING.search(body)
    context = heading.group("title").strip() if heading else pr_title.strip()

    alternatives = _split_list(_ALT.search(body))
    assumptions = _split_list(_ASSUMPTION.search(body))
    justifies = _split_list(_JUSTIFIES.search(body))
    if not justifies and diff_text:
        justifies = sorted({m.group("path") for m in _PATH_IN_DIFF.finditer(diff_text)})

    tool_match = _AI_TOOL.search(body)
    ai_tool = normalize_ai_tool(tool_match.group("value")) if tool_match else AiTool.NONE

    model_match = _MODEL.search(body)
    model = model_match.group("value").strip() if model_match else None

    prose_parts = [f"## Context\n\n{context}", f"## Choice\n\n{choice}"]
    if alternatives:
        prose_parts.append(
            "## Alternatives rejected\n\n" + "\n".join(f"- {a}" for a in alternatives)
        )
    if assumptions:
        prose_parts.append("## Assumptions\n\n" + "\n".join(f"- {a}" for a in assumptions))
    if body.strip():
        prose_parts.append("## Source PR body\n\n" + body.strip())

    frontmatter = DecisionFrontmatter(
        id=resolved_id,
        ai_tool=ai_tool,
        model=model,
        oversight=DecisionOversight.PENDING,
        approved_by=None,
        recorded_at=recorded_at or datetime.now(UTC),
        justifies=justifies,
        confidence="harvested",
        context=context,
        choice=choice,
        alternatives_rejected=alternatives,
        assumptions=assumptions,
    )
    return DecisionRecord(frontmatter=frontmatter, body="\n\n".join(prose_parts))


def harvest_from_fixture(payload: dict[str, Any]) -> DecisionRecord:
    return harvest_decision_from_pr(
        pr_title=str(payload.get("title", "")),
        pr_body=str(payload.get("body", "")),
        diff_text=str(payload.get("diff", "")),
        decision_id=payload.get("decision_id"),
    )


def _split_list(match: re.Match[str] | None) -> list[str]:
    if match is None:
        return []
    raw = match.group("value").strip()
    if not raw:
        return []
    if "," in raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [raw]
