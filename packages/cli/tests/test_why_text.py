"""S59.1-S59.3, S59.7 — `why` prints the why, in force first, with a caveat for coarse matches."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.models.decision import DecisionStatus
from why_helpers import HUNTER, decide, write_source


def _why(capsys: pytest.CaptureFixture[str], root: Path, *args: str) -> str:
    assert main(["why", *args, "--root", str(root)]) == EXIT_PASS
    return capsys.readouterr().out


@pytest.mark.phase_4
def test_why_text_shows_context_and_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(
        tmp_path,
        "dec_full01",
        [f"{HUNTER}:15-19"],
        rejected=["Redis: a new service", "In-process dict: lost on restart", "C", "D"],
    )
    out = _why(capsys, tmp_path, f"{HUNTER}:16")
    assert "dec_full01" in out
    assert "why: Hunter lookups hit the API on every request." in out
    assert "chose: Cache hunter lookups for sixty seconds" in out
    assert "rejected:" in out and "Redis: a new service" in out and "In-process dict" in out
    assert "\n    - C" in out and "D" not in out.split("rejected:", 1)[1].replace("Redis", "")
    assert "approved: alice" in out


@pytest.mark.phase_4
def test_why_text_says_pending_review_for_an_unapproved_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_pend01", [f"{HUNTER}:15-19"], approved_by=None)
    assert "approved: pending review" in _why(capsys, tmp_path, f"{HUNTER}:16")


@pytest.mark.phase_4
def test_why_long_fields_are_cut_with_a_pointer_to_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_long01", [f"{HUNTER}:15-19"], choice="word " * 400)
    out = _why(capsys, tmp_path, f"{HUNTER}:16")
    assert "--json" in out and len(out) < 2500


@pytest.mark.phase_4
def test_why_short_is_the_previous_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_short1", [f"{HUNTER}:15-19"])
    out = _why(capsys, tmp_path, f"{HUNTER}:16", "--short")
    assert out.splitlines() == [
        "dec_short1",
        "  choice: Cache hunter lookups for sixty seconds",
        "  oversight: reviewed",
    ]


@pytest.mark.phase_4
def test_why_orders_in_force_and_precise_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_a_old", [f"{HUNTER}:15-19"], status=DecisionStatus.RETIRED)
    decide(tmp_path, "dec_b_file", [HUNTER])
    decide(tmp_path, "dec_c_line", [f"{HUNTER}:15-19"])
    out = _why(capsys, tmp_path, f"{HUNTER}:16")
    assert out.index("dec_c_line") < out.index("dec_b_file") < out.index("dec_a_old")


@pytest.mark.phase_4
def test_why_cli_caveat_for_file_only_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_file01", [HUNTER])
    out = _why(capsys, tmp_path, f"{HUNTER}:3")
    assert "dec_file01 (file-level match)" in out
    assert "describes the file, not this line" in out


@pytest.mark.phase_4
def test_why_precise_match_has_no_file_caveat(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_line01", [f"{HUNTER}:15-19"])
    assert "describes the file" not in _why(capsys, tmp_path, f"{HUNTER}:16")


@pytest.mark.phase_4
def test_why_json_keeps_its_order_and_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_json01", [f"{HUNTER}:15-19"])
    out = _why(capsys, tmp_path, f"{HUNTER}:16", "--json")
    assert {"target", "count", "path_exists", "decisions"} <= set(json.loads(out))
