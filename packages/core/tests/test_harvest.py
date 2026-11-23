"""Phase 3 PR-harvest deterministic + LLM fixture replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_core.decisions import (
    load_decisions_from_dir,
    parse_decision_markdown,
    render_decision_markdown,
)
from reasonledger_core.decisions.ids import harvest_decision_id
from reasonledger_core.harvest import (
    PrHarvestInput,
    harvest_decision_from_pr,
    harvest_from_fixture,
    harvest_pull_requests,
    replay_llm_harvest,
)

HARVEST = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "harvest"


def _three_pr_fixture() -> list[PrHarvestInput]:
    return [
        PrHarvestInput(
            source_key="acme/payments#101",
            pr_title="Use exponential backoff for payment retries",
            pr_body=(
                "## Decision: payment retry policy\n\n"
                "Choice: Exponential backoff with jitter\n"
                "Justifies: payments/retry.py:40-72\n"
            ),
            diff_text="+++ b/payments/retry.py\n",
        ),
        PrHarvestInput(
            source_key="acme/payments#102",
            pr_title="Add idempotency keys to checkout",
            pr_body="Choice: UUID v4 keys stored in Redis\n",
            diff_text="+++ b/checkout/idempotency.py\n",
        ),
        PrHarvestInput(
            source_key="acme/payments#103",
            pr_title="Fail open on metrics sink outage",
            pr_body="Choice: Drop metrics locally when sink is down\n",
            diff_text="+++ b/observability/metrics.py\n",
        ),
    ]


@pytest.mark.phase_3
def test_harvest_batch_idempotent(tmp_path: Path) -> None:
    prs = _three_pr_fixture()
    first = harvest_pull_requests(prs, root=tmp_path)
    assert first.created == 3
    assert first.updated == 0
    assert first.skipped_unchanged == 0
    assert first.skipped_pii == []

    decisions_dir = tmp_path / ".reasonledger" / "decisions"
    paths = sorted(decisions_dir.glob("dec_*.md"))
    after_first = sorted(path.read_text("utf-8") for path in paths)

    second = harvest_pull_requests(prs, root=tmp_path)
    assert second.created == 0
    assert second.updated == 0
    assert second.skipped_unchanged == 3
    assert second.skipped_pii == []

    after_second = sorted(path.read_text("utf-8") for path in paths)
    assert after_second == after_first
    assert len(load_decisions_from_dir(decisions_dir)) == 3


@pytest.mark.phase_3
def test_harvest_deterministic_id() -> None:
    source_key = "acme/widget#42"
    first = harvest_decision_id(source_key)
    second = harvest_decision_id(source_key)
    assert first == second
    assert first.startswith("dec_")

    record = harvest_decision_from_pr(
        pr_title="Widget cache TTL",
        pr_body="Choice: 5 minute TTL\n",
        source_key=source_key,
    )
    assert record.frontmatter.id == first


@pytest.mark.phase_3
def test_harvest_updates_on_change(tmp_path: Path) -> None:
    source_key = "acme/payments#101"
    pr = PrHarvestInput(
        source_key=source_key,
        pr_title="Use exponential backoff for payment retries",
        pr_body="Choice: Fixed interval retries\n",
    )
    first = harvest_pull_requests([pr], root=tmp_path)
    assert first.created == 1
    decision_id = harvest_decision_id(source_key)
    path = tmp_path / ".reasonledger" / "decisions" / f"{decision_id}.md"
    assert path.is_file()

    updated_pr = PrHarvestInput(
        source_key=source_key,
        pr_title="Use exponential backoff for payment retries",
        pr_body="Choice: Exponential backoff with jitter\n",
    )
    second = harvest_pull_requests([updated_pr], root=tmp_path)
    assert second.created == 0
    assert second.updated == 1
    assert second.skipped_unchanged == 0

    record = parse_decision_markdown(path.read_text("utf-8"))
    assert record.frontmatter.id == decision_id
    assert record.frontmatter.choice == "Exponential backoff with jitter"


@pytest.mark.phase_3
def test_harvest_pii_skipped(tmp_path: Path) -> None:
    clean = PrHarvestInput(
        source_key="acme/payments#200",
        pr_title="Safe retry policy",
        pr_body="Choice: Exponential backoff\n",
    )
    dirty = PrHarvestInput(
        source_key="acme/payments#201",
        pr_title="Leaky PR body",
        pr_body="Choice: Contact bob@evil.example for rollout\n",
    )
    result = harvest_pull_requests([clean, dirty], root=tmp_path)
    assert result.created == 1
    assert result.skipped_pii == ["acme/payments#201"]
    assert result.updated == 0
    assert result.skipped_unchanged == 0

    decisions_dir = tmp_path / ".reasonledger" / "decisions"
    assert len(list(decisions_dir.glob("dec_*.md"))) == 1
    assert not (decisions_dir / f"{harvest_decision_id('acme/payments#201')}.md").exists()


@pytest.mark.phase_3
def test_harvest_populates_justifies(tmp_path: Path) -> None:
    pr = PrHarvestInput(
        source_key="acme/api#55",
        pr_title="Add pagination helper",
        pr_body="Choice: Cursor-based pagination\n",
        diff_text=(
            "diff --git a/api/pagination.py b/api/pagination.py\n"
            "+++ b/api/pagination.py\n"
            "+++ b/api/helpers.py\n"
        ),
    )
    result = harvest_pull_requests([pr], root=tmp_path)
    assert result.created == 1

    decision_id = harvest_decision_id("acme/api#55")
    path = tmp_path / ".reasonledger" / "decisions" / f"{decision_id}.md"
    record = parse_decision_markdown(path.read_text("utf-8"))
    assert sorted(record.frontmatter.justifies) == ["api/helpers.py", "api/pagination.py"]


@pytest.mark.phase_3
def test_deterministic_pr_harvest_matches_golden() -> None:
    payload = json.loads((HARVEST / "pr_deterministic.json").read_text("utf-8"))
    expected = json.loads((HARVEST / "pr_deterministic_expected.json").read_text("utf-8"))[
        "expected"
    ]
    record = harvest_from_fixture(payload)
    assert record.frontmatter.id == expected["id"]
    assert record.frontmatter.ai_tool == expected["ai_tool"]
    assert record.frontmatter.model == expected["model"]
    assert record.frontmatter.choice == expected["choice"]
    assert record.frontmatter.justifies == expected["justifies"]
    assert record.frontmatter.alternatives_rejected == expected["alternatives_rejected"]
    assert record.frontmatter.oversight.value == expected["oversight"]
    # Round-trip proposed markdown
    again = parse_decision_markdown(render_decision_markdown(record))
    assert again.frontmatter.id == record.frontmatter.id


@pytest.mark.phase_3
def test_llm_harvest_replays_fixture_only() -> None:
    record = replay_llm_harvest(HARVEST / "llm_replay.json")
    assert record.frontmatter.id == "dec_llm001"
    assert record.frontmatter.ai_tool == "cursor"
    assert record.frontmatter.choice is not None
    assert "SameSite=Lax" in record.frontmatter.choice
