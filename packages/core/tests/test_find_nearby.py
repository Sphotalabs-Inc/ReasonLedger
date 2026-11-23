"""Phase 4 — find_nearby: what `why` knows about a file when the asked place has no decision."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.decisions import load_decisions_from_dir, record_decision_to_path
from reasonledger_core.models.decision import AiTool, DecisionOversight, RecordDecisionInput
from reasonledger_core.reasoning.why_nearby import (
    NEARBY_CHOICE_CHARS,
    NEARBY_LIMIT,
    Nearby,
    find_nearby,
    first_line,
    nearby_payload,
)

SOURCE = "src/cache.py"


def _decide(
    root: Path, decision_id: str, justifies: list[str], choice: str = "Use a cache"
) -> None:
    record_decision_to_path(
        RecordDecisionInput(
            context="Why a cache?",
            choice=choice,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            approved_by="alice",
            justifies=justifies,
            alternatives_rejected=["None"],
            decision_id=decision_id,
        ),
        root=root,
    )


def _nearby(root: Path, line: int | None) -> Nearby:
    return find_nearby(
        load_decisions_from_dir(root / ".reasonledger" / "decisions"), SOURCE, line, root=root
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    body = "".join(f"x{n} = {n}\n" for n in range(1, 41))
    (tmp_path / SOURCE).write_text(
        body + "\n\ndef lookup() -> int:\n    return 1\n", encoding="utf-8"
    )
    return tmp_path


@pytest.mark.phase_4
def test_nearest_line_anchor_comes_first(repo: Path) -> None:
    _decide(repo, "dec_far", [f"{SOURCE}:30-31"])
    _decide(repo, "dec_near", [f"{SOURCE}:10-12"])
    nearby = _nearby(repo, 1)
    assert [a.decision_id for a in nearby.anchors] == ["dec_near", "dec_far"]
    assert [a.distance for a in nearby.anchors] == [9, 29]
    assert nearby.anchors[0].command == "reasonledger why src/cache.py:10"


@pytest.mark.phase_4
def test_a_symbol_anchor_is_placed_by_its_span(repo: Path) -> None:
    _decide(repo, "dec_sym", [f"{SOURCE}::lookup"])
    _decide(repo, "dec_line", [f"{SOURCE}:5-6"])
    nearby = _nearby(repo, 43)  # asked inside lookup's span: distance 0
    assert nearby.anchors[0].decision_id == "dec_sym" and nearby.anchors[0].distance == 0
    assert nearby.anchors[0].command == "reasonledger why src/cache.py::lookup"


@pytest.mark.phase_4
def test_with_no_asked_line_distance_is_unknown_and_order_is_by_id(repo: Path) -> None:
    _decide(repo, "dec_b", [f"{SOURCE}:10-12"])
    _decide(repo, "dec_a", [f"{SOURCE}:20-22"])
    nearby = _nearby(repo, None)
    assert [a.decision_id for a in nearby.anchors] == ["dec_a", "dec_b"]
    assert all(a.distance is None for a in nearby.anchors)


@pytest.mark.phase_4
def test_a_whole_file_anchor_is_listed(repo: Path) -> None:
    _decide(repo, "dec_file", [SOURCE])
    assert _nearby(repo, 1).anchors[0].command == "reasonledger why src/cache.py"


@pytest.mark.phase_4
def test_the_cap_and_the_overflow_count(repo: Path) -> None:
    for index in range(NEARBY_LIMIT + 2):
        _decide(repo, f"dec_{index}", [f"{SOURCE}:{10 + index}-{10 + index}"])
    nearby = _nearby(repo, 1)
    assert len(nearby.anchors) == NEARBY_LIMIT and nearby.more == 2


@pytest.mark.phase_4
def test_anchors_in_other_files_are_ignored(repo: Path) -> None:
    _decide(repo, "dec_else", ["src/other.py:1-5"])
    nearby = _nearby(repo, 1)
    assert nearby.anchors == () and nearby.out_of_force == () and nearby.more == 0


@pytest.mark.phase_4
def test_payload_lists_in_force_then_out_of_force_with_status(repo: Path) -> None:
    from reasonledger_core.decisions import read_decision_file, write_decision_file
    from reasonledger_core.models.decision import DecisionStatus

    _decide(repo, "dec_live", [f"{SOURCE}:10-12"])
    _decide(repo, "dec_gone", [f"{SOURCE}:11-12"])
    path = repo / ".reasonledger" / "decisions" / "dec_gone.md"
    record = read_decision_file(path)
    record.frontmatter.status = DecisionStatus.RETIRED
    write_decision_file(path, record)
    nearby = _nearby(repo, 1)
    assert nearby.count_status("retired") == 1
    assert [(e["id"], e["status"]) for e in nearby_payload(nearby)] == [
        ("dec_live", "active"),
        ("dec_gone", "retired"),
    ]


@pytest.mark.phase_4
def test_first_line_takes_the_first_sentence_line_and_truncates() -> None:
    assert first_line("\n  First line\nsecond") == "First line"
    cut = first_line("x" * 500)
    assert len(cut) == NEARBY_CHOICE_CHARS and cut.endswith("…")
