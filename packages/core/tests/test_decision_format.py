"""Phase 3 decision format round-trip and query tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.decisions import (
    load_decisions_from_dir,
    parse_decision_markdown,
    query_decisions,
    record_decision_to_path,
    render_decision_markdown,
    superseded_by_map,
)
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    QueryDecisionsInput,
    RecordDecisionInput,
)

GOLDEN = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "decisions" / "dec_8f3k2x.md"


@pytest.mark.phase_3
def test_decision_markdown_round_trip_golden() -> None:
    raw = GOLDEN.read_text("utf-8")
    record = parse_decision_markdown(raw)
    assert record.frontmatter.id == "dec_8f3k2x"
    assert record.frontmatter.ai_tool == AiTool.CLAUDE_CODE
    assert record.frontmatter.oversight == DecisionOversight.REVIEWED
    rerendered = render_decision_markdown(record)
    again = parse_decision_markdown(rerendered)
    assert again == record


@pytest.mark.phase_3
def test_a_topics_line_from_before_topics_were_removed_is_ignored_then_dropped() -> None:
    older = """---
id: dec_old001
ai_tool: claude-code
model: claude-sonnet-5-5
oversight: pending
status: active
topics:
- promo-codes
context: Old question
choice: Old answer
---
"""

    record = parse_decision_markdown(older)

    assert record.frontmatter.id == "dec_old001" and "topics" not in record.frontmatter.model_dump()
    assert "topics" not in render_decision_markdown(record)


@pytest.mark.phase_3
def test_record_decision_write_round_trip(tmp_path: Path) -> None:
    inp = RecordDecisionInput(
        context="Retry policy",
        choice="Exponential backoff",
        alternatives_rejected=["Fixed delay"],
        assumptions=["At-least-once delivery"],
        confidence="high",
        ai_tool=AiTool.CURSOR,
        model="composer",
        oversight=DecisionOversight.REVIEWED,
        approved_by="alice@acme.com",
        justifies=["payments/retry.py:40-72"],
        decision_id="dec_test01",
    )
    record, path = record_decision_to_path(inp, root=tmp_path)
    assert path.exists()
    assert record.frontmatter.id == "dec_test01"
    loaded = load_decisions_from_dir(tmp_path / ".reasonledger" / "decisions")
    assert len(loaded) == 1
    assert loaded[0] == record


@pytest.mark.phase_3
def test_query_decisions_by_text_and_path() -> None:
    record = parse_decision_markdown(GOLDEN.read_text("utf-8"))
    hits = query_decisions([record], QueryDecisionsInput(query="backoff"))
    assert len(hits) == 1
    by_path = query_decisions(
        [record],
        QueryDecisionsInput(query="", paths=["payments/**"]),
    )
    assert len(by_path) == 1
    miss = query_decisions([record], QueryDecisionsInput(query="unrelated-xyz"))
    assert miss == []


def _bare_record(decision_id: str, *, supersedes: str | None = None) -> DecisionRecord:
    return DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            supersedes=supersedes,
        )
    )


@pytest.mark.phase_3
def test_superseded_by_map() -> None:
    assert superseded_by_map([]) == {}

    old = _bare_record("dec_old01")
    new = _bare_record("dec_new01", supersedes="dec_old01")
    unrelated = _bare_record("dec_other1")
    assert superseded_by_map([old, new, unrelated]) == {"dec_old01": "dec_new01"}
