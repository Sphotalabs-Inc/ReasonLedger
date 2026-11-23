"""P0-4 S1: Decision provenance/import schema — round-trip and invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions.format import (
    parse_decision_markdown,
    render_decision_markdown,
)
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionSource,
    DecisionStatus,
)

GOLDEN = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "decisions" / "dec_8f3k2x.md"


def _imported_record() -> DecisionRecord:
    fm = DecisionFrontmatter(
        id="dec_import01",
        ai_tool=AiTool.NONE,
        oversight=DecisionOversight.REVIEWED,
        status=DecisionStatus.PROPOSED,
        context="Extracted from claude.md architecture section",
        choice="Store timestamps as UTC",
        source=DecisionSource.DOC_IMPORT,
        source_ref="claude.md#architecture",
        extracted_by="anthropic/claude-sonnet-5",
        extracted_at=datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC),
        justifies=["backend/app/date_utils.py"],
    )
    return DecisionRecord(frontmatter=fm, body="Imported decision body.")


@pytest.mark.phase_3
def test_import_provenance_round_trip() -> None:
    record = _imported_record()
    parsed = parse_decision_markdown(render_decision_markdown(record))
    assert parsed == record
    assert parsed.frontmatter.source == DecisionSource.DOC_IMPORT
    assert parsed.frontmatter.source_ref == "claude.md#architecture"
    assert parsed.frontmatter.extracted_by == "anthropic/claude-sonnet-5"
    assert parsed.frontmatter.extracted_at == datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC)
    assert parsed.frontmatter.status == DecisionStatus.PROPOSED


@pytest.mark.phase_3
def test_decided_at_not_defaulted_to_now() -> None:
    # A decision found today in an old doc must NOT claim it was decided today.
    fm = DecisionFrontmatter(
        id="dec_import02",
        ai_tool=AiTool.NONE,
        oversight=DecisionOversight.REVIEWED,
        source=DecisionSource.DOC_IMPORT,
    )
    assert fm.decided_at is None
    assert fm.confirmed_by is None
    assert fm.confirmed_at is None


@pytest.mark.phase_3
def test_status_supports_proposed_and_confirmed() -> None:
    assert DecisionStatus("proposed") is DecisionStatus.PROPOSED
    assert DecisionStatus("confirmed") is DecisionStatus.CONFIRMED


@pytest.mark.phase_3
def test_existing_golden_has_no_provenance_fields() -> None:
    # Backward compat: pre-import records parse; provenance fields default None
    # and stay absent on re-render (exclude_none).
    record = parse_decision_markdown(GOLDEN.read_text("utf-8"))
    assert record.frontmatter.source is None
    assert record.frontmatter.extracted_at is None
    assert record.frontmatter.decided_at is None
    assert parse_decision_markdown(render_decision_markdown(record)) == record
