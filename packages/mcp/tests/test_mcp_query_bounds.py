"""S50 — query_decisions never floods an agent's context."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions.lifecycle import retire_decision
from reasonledger_mcp.hits import QUERY_LIMIT
from reasonledger_mcp.tools import call_query_decisions, call_record_decision


def _record(root: Path, decision_id: str, choice: str = "Use a cache") -> None:
    call_record_decision(
        root,
        context="Which cache backs the catalog?",
        choice=choice,
        alternatives_rejected=["none"],
        ai_tool="claude",
        model="m",
        justifies=["catalog/cache.py:1-9"],
        decision_id=decision_id,
    )


@pytest.mark.phase_3
def test_query_default_limit_and_total(tmp_path: Path) -> None:
    for n in range(QUERY_LIMIT + 3):
        _record(tmp_path, f"dec_c{n:03d}")
    found = call_query_decisions(tmp_path, query="cache")
    assert (found["count"], found["total"], found["truncated"]) == (
        QUERY_LIMIT,
        QUERY_LIMIT + 3,
        True,
    )
    small = call_query_decisions(tmp_path, query="cache", limit=2)
    assert small["count"] == 2 and small["total"] == QUERY_LIMIT + 3
    semantic = call_query_decisions(tmp_path, query="cache catalog", semantic=True, limit=3)
    assert semantic["count"] == 3 and semantic["truncated"] is True


@pytest.mark.phase_3
def test_query_compact_by_default(tmp_path: Path) -> None:
    _record(tmp_path, "dec_one001")
    hit = call_query_decisions(tmp_path, query="cache")["decisions"][0]
    assert "markdown" not in hit
    assert set(hit) == {
        "id",
        "context",
        "choice",
        "justifies",
        "status",
        "oversight",
        "proposed_by",
        "superseded_by",
    }


@pytest.mark.phase_3
def test_query_full_includes_markdown(tmp_path: Path) -> None:
    _record(tmp_path, "dec_one001")
    hit = call_query_decisions(tmp_path, query="cache", full=True)["decisions"][0]
    assert hit["markdown"].startswith("---")


@pytest.mark.phase_4
def test_query_in_force_first(tmp_path: Path) -> None:
    _record(tmp_path, "dec_aaa001")  # sorts first, but is retired below
    _record(tmp_path, "dec_zzz001")
    retire_decision(
        "dec_aaa001", root=tmp_path, retired_by="p", retired_at=datetime.now(UTC), reason="gone"
    )
    for semantic in (False, True):
        hits = call_query_decisions(tmp_path, query="cache catalog", semantic=semantic)["decisions"]
        assert [h["id"] for h in hits] == ["dec_zzz001", "dec_aaa001"]
        assert hits[1]["retired_reason"] == "gone"
