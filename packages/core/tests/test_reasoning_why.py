"""Phase 4 — `rl why` reasoning-blame resolver."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions import load_decisions_from_dir, record_decision_to_path
from reasonledger_core.importer.extractor import DecisionCandidate
from reasonledger_core.importer.propose import confirm_proposed, propose_decisions
from reasonledger_core.models.decision import AiTool, DecisionOversight, RecordDecisionInput
from reasonledger_core.reasoning import MatchKind, parse_target, resolve_why
from reasonledger_core.reasoning.symbols import extract_symbols, symbol_at_line
from reasonledger_core.reasoning.why import WhyQueryError
from reasonledger_core.views import build_ledger_view

_IMPORT_TIME = datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC)

_CORPUS = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "reasoning" / "decisions"


@pytest.mark.phase_4
def test_parse_target_variants() -> None:
    assert parse_target("payments/retry.py:55") == parse_target("payments/retry.py:55")
    with_line = parse_target("payments/retry.py:55")
    assert with_line.path == "payments/retry.py"
    assert with_line.line == 55
    whole_file = parse_target("payments/retry.py")
    assert whole_file.line is None
    with pytest.raises(WhyQueryError):
        parse_target("   ")


@pytest.mark.phase_4
def test_resolve_why_matches_line_in_range() -> None:
    records = load_decisions_from_dir(_CORPUS)
    hits = resolve_why(records, parse_target("payments/retry.py:55"))
    assert [hit.record.frontmatter.id for hit in hits] == ["dec_retry01"]
    assert hits[0].match is MatchKind.LINE


@pytest.mark.phase_4
def test_resolve_why_line_outside_range_is_no_record() -> None:
    records = load_decisions_from_dir(_CORPUS)
    assert resolve_why(records, parse_target("payments/retry.py:9")) == []
    # A file with no decision at all returns cleanly (no crash).
    assert resolve_why(records, parse_target("unknown/file.py:1")) == []


@pytest.mark.phase_4
def test_resolve_why_whole_file_matches_any_locus() -> None:
    records = load_decisions_from_dir(_CORPUS)
    hits = resolve_why(records, parse_target("catalog/cache.py"))
    assert [hit.record.frontmatter.id for hit in hits] == ["dec_cache01"]


@pytest.mark.phase_4
def test_why_survives_line_shift(tmp_path: Path) -> None:
    source = "\n" * 9 + "def retry_with_backoff() -> None:\n" + "    pass\n" * 10
    path = tmp_path / "retry.py"
    path.write_text(source, encoding="utf-8")
    record_decision_to_path(
        RecordDecisionInput(
            context="Retry policy",
            choice="Back off",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            justifies=["retry.py::retry_with_backoff"],
            decision_id="dec_shift01",
        ),
        root=tmp_path,
    )

    path.write_text("\n" * 40 + source, encoding="utf-8")
    records = load_decisions_from_dir(tmp_path / ".reasonledger" / "decisions")
    hits = resolve_why(records, parse_target("retry.py:55"), root=tmp_path)

    assert [hit.record.frontmatter.id for hit in hits] == ["dec_shift01"]
    assert hits[0].match is MatchKind.SYMBOL


@pytest.mark.phase_4
def test_why_legacy_line_range_still_resolves() -> None:
    records = load_decisions_from_dir(_CORPUS)
    hits = resolve_why(records, parse_target("payments/retry.py:55"))

    assert hits[0].match is MatchKind.LINE


@pytest.mark.phase_4
def test_why_labels_file_level_fallback(tmp_path: Path) -> None:
    record_decision_to_path(
        RecordDecisionInput(
            context="Cache policy",
            choice="Use Redis",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            justifies=["catalog/cache.py"],
            decision_id="dec_file01",
        ),
        root=tmp_path,
    )
    records = load_decisions_from_dir(tmp_path / ".reasonledger" / "decisions")
    hits = resolve_why(records, parse_target("catalog/cache.py"))

    assert hits[0].match is MatchKind.FILE


@pytest.mark.phase_4
def test_parse_target_double_colon() -> None:
    target = parse_target("a/b.py::fn")
    assert target.path == "a/b.py"
    assert target.line is None
    assert target.symbol == "fn"


@pytest.mark.phase_4
def test_parse_target_windows_path_unchanged() -> None:
    target = parse_target(r"C:\x\y.py")
    assert target.path == r"C:\x\y.py"
    assert target.line is None


@pytest.mark.phase_4
def test_symbol_at_line_nested_method() -> None:
    source = "class Klass:\n    def method(self) -> None:\n        pass\n"
    assert symbol_at_line(source, 3) == "Klass.method"


@pytest.mark.phase_4
def test_extract_symbols_syntax_error_returns_empty() -> None:
    assert extract_symbols("def broken(:\n") == []


@pytest.mark.phase_4
def test_resolve_why_flags_superseded_record(tmp_path: Path) -> None:
    """A retired decision must still be returned, but labelled as superseded."""
    locus = "payments/retry.py:10-20"
    target = "payments/retry.py:15"
    original = propose_decisions(
        [
            DecisionCandidate(
                context="Retry budget",
                choice="3 attempts",
                source_ref="claude.md#retry",
                justifies=[locus],
            )
        ],
        root=tmp_path,
        extracted_by="m",
        extracted_at=_IMPORT_TIME,
    )
    original_id = original.proposed_ids[0]
    confirm_proposed(
        original_id,
        root=tmp_path,
        confirmed_by="alice",
        confirmed_at=_IMPORT_TIME,
    )

    changed = propose_decisions(
        [
            DecisionCandidate(
                context="Retry budget",
                choice="5 attempts",
                source_ref="claude.md#retry",
                justifies=[locus],
            )
        ],
        root=tmp_path,
        extracted_by="m",
        extracted_at=_IMPORT_TIME,
    )
    new_id = changed.superseded[0].proposal_id
    confirm_proposed(
        new_id,
        root=tmp_path,
        confirmed_by="alice",
        confirmed_at=_IMPORT_TIME,
    )

    records = load_decisions_from_dir(tmp_path / ".reasonledger" / "decisions")
    hits = {hit.record.frontmatter.id: hit for hit in resolve_why(records, parse_target(target))}

    assert set(hits) == {original_id, new_id}
    assert hits[original_id].superseded_by == new_id
    assert hits[new_id].superseded_by is None


@pytest.mark.phase_4
def test_orphan_detects_removed_symbol(tmp_path: Path) -> None:
    path = tmp_path / "retry.py"
    path.write_text("def retry() -> None:\n    pass\n", encoding="utf-8")
    record_decision_to_path(
        RecordDecisionInput(
            context="Retry policy",
            choice="Retry",
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            justifies=["retry.py::retry"],
            decision_id="dec_orphan1",
        ),
        root=tmp_path,
    )

    path.write_text("def replaced() -> None:\n    pass\n", encoding="utf-8")
    orphan = build_ledger_view(tmp_path).orphaned[0]

    assert orphan.reason == "missing_symbol"


@pytest.mark.phase_4
def test_why_payload_reports_matched_loci_context_and_missing_path(tmp_path: Path) -> None:
    from reasonledger_core.reasoning import why_payload

    (tmp_path / "payments").mkdir()
    (tmp_path / "payments" / "retry.py").write_text("x = 1\n", encoding="utf-8")
    records = load_decisions_from_dir(_CORPUS)

    target = parse_target("payments/retry.py:55")
    payload = why_payload(
        "payments/retry.py:55", target, resolve_why(records, target), root=tmp_path
    )
    assert payload["path_exists"] is True
    decision = payload["decisions"][0]  # type: ignore[index]
    assert decision["context"] and decision["match"] == "line"
    assert decision["matched_loci"] == [
        locus for locus in decision["justifies"] if locus.startswith("payments/retry.py")
    ]

    missing = parse_target("payments/typo.py:1")
    miss = why_payload("payments/typo.py:1", missing, [], root=tmp_path)
    assert miss["path_exists"] is False and miss["count"] == 0

    escape = parse_target("../outside.py")
    assert why_payload("../outside.py", escape, [], root=tmp_path)["path_exists"] is False
