"""S59.4-S59.6 — a miss never reads as "nothing here" when the file has decisions elsewhere."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.metrics import load_metrics
from reasonledger_core.models.decision import DecisionStatus
from why_helpers import HUNTER, HUNTER_LOCUS, decide, write_source

NEARBY_CAP = 5


def _run(capsys: pytest.CaptureFixture[str], root: Path, *args: str) -> str:
    assert main(["why", *args, "--root", str(root)]) == EXIT_PASS
    return capsys.readouterr().out


@pytest.mark.phase_4
def test_why_line_miss_lists_other_anchors_in_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The rehearsal's F4, verbatim: a decision at 15-19, asked at line 1."""
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_hunt01", [HUNTER_LOCUS])
    out = _run(capsys, tmp_path, f"{HUNTER}:1")
    assert "No decision covers line 1" in out
    assert "dec_hunt01" in out and "15-19" in out
    assert "Cache hunter lookups for sixty seconds" in out
    assert f"reasonledger why {HUNTER}:15" in out
    assert "no decision is recorded for this file" not in out.lower()
    assert "no decision justifies this line yet" not in out


@pytest.mark.phase_4
def test_why_line_miss_lists_symbol_anchors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "src" / "cache.py"
    source.parent.mkdir()
    source.write_text("X = 1\n\n\ndef lookup() -> int:\n    return 2\n", encoding="utf-8")
    decide(tmp_path, "dec_sym001", ["src/cache.py::lookup"])
    out = _run(capsys, tmp_path, "src/cache.py:1")
    assert "No decision covers line 1" in out
    assert "dec_sym001" in out and "src/cache.py::lookup" in out
    assert "reasonledger why src/cache.py::lookup" in out


@pytest.mark.phase_4
def test_why_nearby_is_nearest_first_and_capped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER, lines=100)
    for index, start in enumerate((90, 40, 60, 20, 80, 30, 70)):
        decide(tmp_path, f"dec_n{index:02d}", [f"{HUNTER}:{start}-{start + 1}"])
    out = _run(capsys, tmp_path, f"{HUNTER}:1")
    listed = [line for line in out.splitlines() if "dec_n" in line]
    assert len(listed) == NEARBY_CAP
    starts = [int(line.split(f"{HUNTER}:")[1].split("-")[0]) for line in listed]
    assert starts == [20, 30, 40, 60, 70]
    assert "2 more" in out


@pytest.mark.phase_4
def test_why_file_without_decisions_says_so_and_counts_the_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    write_source(tmp_path, "other/file.ts")
    decide(tmp_path, "dec_else01", ["other/file.ts:1-3"])
    decide(tmp_path, "dec_else02", ["other/file.ts:4-5"])
    out = _run(capsys, tmp_path, f"{HUNTER}:1")
    assert "No decision names this file" in out and "2 decisions" in out
    assert "dec_else01" not in out


@pytest.mark.phase_4
def test_why_empty_ledger_is_told_apart_from_an_uncovered_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    out = _run(capsys, tmp_path, f"{HUNTER}:1")
    assert "No decision names this file" in out and "ledger is empty" in out


@pytest.mark.phase_4
def test_why_nearby_counts_retired_without_listing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_live01", [HUNTER_LOCUS])
    decide(tmp_path, "dec_dead01", [f"{HUNTER}:25-27"], status=DecisionStatus.RETIRED)
    out = _run(capsys, tmp_path, f"{HUNTER}:1")
    assert "dec_live01" in out and "dec_dead01" not in out
    assert "and 1 retired" in out


@pytest.mark.phase_4
def test_why_only_retired_anchors_still_does_not_say_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_dead01", [HUNTER_LOCUS], status=DecisionStatus.RETIRED)
    out = _run(capsys, tmp_path, f"{HUNTER}:1")
    assert "No decision covers line 1" in out and "1 retired" in out


@pytest.mark.phase_4
def test_why_json_nearby_is_additive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_hunt01", [HUNTER_LOCUS])
    miss = json.loads(_run(capsys, tmp_path, f"{HUNTER}:1", "--json"))
    assert miss["count"] == 0 and miss["decisions"] == [] and miss["path_exists"] is True
    entry = miss["nearby"][0]
    assert entry["id"] == "dec_hunt01" and entry["locus"] == HUNTER_LOCUS
    assert entry["status"] == "active" and entry["choice"].startswith("Cache hunter")
    assert entry["command"] == f"reasonledger why {HUNTER}:15"

    hit = json.loads(_run(capsys, tmp_path, f"{HUNTER}:16", "--json"))
    assert hit["nearby"] == [] and hit["count"] == 1
    assert set(hit) == {"target", "count", "path_exists", "decisions", "nearby"}


@pytest.mark.phase_4
def test_why_json_nearby_is_empty_when_the_file_has_no_decisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_source(tmp_path, HUNTER)
    assert json.loads(_run(capsys, tmp_path, f"{HUNTER}:1", "--json"))["nearby"] == []


@pytest.mark.phase_4
def test_why_missing_file_is_an_error_not_a_miss(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    decide(tmp_path, "dec_hunt01", [HUNTER_LOCUS])
    assert main(["why", f"{HUNTER}:1", "--root", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "no file at" in captured.err and "No decision covers" not in captured.out


@pytest.mark.phase_4
def test_why_near_miss_is_a_separate_metric(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RL_METRICS", "1")
    write_source(tmp_path, HUNTER)
    decide(tmp_path, "dec_hunt01", [HUNTER_LOCUS])
    _run(capsys, tmp_path, f"{HUNTER}:1")  # near
    _run(capsys, tmp_path, f"{HUNTER}:16")  # hit
    write_source(tmp_path, "bare/file.ts")
    _run(capsys, tmp_path, "bare/file.ts:1")  # miss
    matches = [e["match"] for e in load_metrics(tmp_path) if e["event"] == "why_invoked"]
    assert matches == ["near", "line", "miss"]
