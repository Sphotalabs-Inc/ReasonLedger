"""Ledger composition counts shared by `status --stats` and the UI summary strip."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionProposer,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.modules import Manifest, Module, write_manifest
from reasonledger_core.modules.buckets import new_bucket
from reasonledger_core.modules.config import SHARED_BUCKET_ID
from reasonledger_core.views import build_ledger_view, build_stats
from reasonledger_core.views.map_view import load_map, overview


def _decision(
    root: Path,
    decision_id: str,
    locus: str,
    *,
    oversight: DecisionOversight = DecisionOversight.PENDING,
    proposed_by: DecisionProposer | None = None,
    status: DecisionStatus = DecisionStatus.ACTIVE,
) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=oversight,
            status=status,
            proposed_by=proposed_by,
            justifies=[locus],
            context=f"question for {decision_id}",
            choice=f"choice for {decision_id}",
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for folder in ("orders", "billing", "search", "misc"):
        path = tmp_path / "app" / folder / "f0.py"
        path.parent.mkdir(parents=True)
        path.write_text("x = 1\n", encoding="utf-8")
    _decision(
        tmp_path,
        "dec_a",
        "app/orders/f0.py:1-1",
        oversight=DecisionOversight.REVIEWED,
        proposed_by=DecisionProposer.HUMAN,
    )
    _decision(tmp_path, "dec_b", "app/orders/f0.py:1-1", proposed_by=DecisionProposer.AI)
    _decision(tmp_path, "dec_c", "app/billing/f0.py:1-1")
    _decision(
        tmp_path,
        "dec_d",
        "app/billing/f0.py:1-1",
        oversight=DecisionOversight.MODIFIED,
        proposed_by=DecisionProposer.AI,
    )
    _decision(
        tmp_path,
        "dec_gone",
        "app/search/f0.py:1-1",
        proposed_by=DecisionProposer.AI,
        status=DecisionStatus.RETIRED,
    )
    return tmp_path


def _map(root: Path) -> None:
    write_manifest(
        root,
        Manifest(
            modules=[
                Module(id="billing", name="Billing", paths=["app/billing/**"]),
                Module(id="orders", name="Orders", paths=["app/orders/**"]),
                Module(id="search", name="Search", paths=["app/search/**"]),
                new_bucket(SHARED_BUCKET_ID, ["app/misc/**"]),
            ]
        ),
    )


@pytest.mark.phase_5
def test_counts_cover_decisions_in_force_only(repo: Path) -> None:
    view = build_ledger_view(repo)
    stats = build_stats(view.decisions, None)

    assert stats.in_force == 4
    assert (stats.judged, stats.pending) == (2, 2)
    assert (stats.proposed_human, stats.proposed_ai, stats.proposed_unset) == (1, 2, 1)
    # The backlog is the same number `status` already reports, not a second definition.
    assert stats.pending == view.counts["pending_approval"]


@pytest.mark.phase_5
def test_without_a_map_modules_are_absent_not_zero(repo: Path) -> None:
    stats = build_stats(build_ledger_view(repo).decisions, overview(load_map(repo)))

    assert stats.mapped is False
    assert stats.modules == [] and stats.modules_without_decisions == 0


@pytest.mark.phase_5
def test_modules_rank_by_decisions_and_name_the_ones_with_none(repo: Path) -> None:
    _map(repo)
    stats = build_stats(build_ledger_view(repo).decisions, overview(load_map(repo)))

    assert stats.mapped is True
    # Ties break on id; the bucket is not a module; the retired decision leaves Search at zero.
    assert [(m.id, m.decisions, m.pending) for m in stats.modules] == [
        ("billing", 2, 1),
        ("orders", 2, 1),
        ("search", 0, 0),
    ]
    assert stats.modules_without_decisions == 1
    assert stats.modules[0].coverage == pytest.approx(1.0)
