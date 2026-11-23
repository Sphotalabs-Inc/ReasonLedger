"""S13: LedgerView — lifecycle projection, display-only staleness, conflict hints."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    decision_filename,
    read_decision_file,
    write_decision_file,
)
from reasonledger_core.importer.extractor import DecisionCandidate
from reasonledger_core.importer.propose import propose_decisions
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionProposer,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.models.reasoning import Relation, Severity
from reasonledger_core.reasoning.conflict_config import ConflictConfig, write_conflict_config
from reasonledger_core.reasoning.dismissals import add_dismissal
from reasonledger_core.views import build_ledger_view

EXTRACTED_AT = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)


def _stage_proposal(root: Path, ref: str, context: str, choice: str) -> None:
    propose_decisions(
        [DecisionCandidate(context=context, choice=choice, source_ref=ref)],
        root=root,
        extracted_by="test/extractor",
        extracted_at=EXTRACTED_AT,
    )


def _write_ledger_record(
    root: Path,
    decision_id: str,
    *,
    status: DecisionStatus,
    context: str,
    choice: str,
    watchers: list[str] | None = None,
    justifies: list[str] | None = None,
) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.NONE,
            oversight=DecisionOversight.REVIEWED,
            status=status,
            context=context,
            choice=choice,
            watchers=watchers or [],
            justifies=justifies or [],
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


@pytest.mark.phase_3
def test_ledger_view_projects_lifecycle(tmp_path: Path) -> None:
    _stage_proposal(tmp_path, "docs/a.md#bundler", "Frontend bundler tooling", "vite")
    _stage_proposal(tmp_path, "docs/b.md#pagination", "API pagination style", "cursor pagination")
    _write_ledger_record(
        tmp_path,
        "dec_active1",
        status=DecisionStatus.ACTIVE,
        context="Queue technology selection",
        choice="sqs",
    )
    _write_ledger_record(
        tmp_path,
        "dec_conf1",
        status=DecisionStatus.CONFIRMED,
        context="Email provider integration",
        choice="resend",
    )
    _write_ledger_record(
        tmp_path,
        "dec_stale1",
        status=DecisionStatus.STALE,
        context="Cache layer topology",
        choice="redis cluster",
    )

    view = build_ledger_view(tmp_path)
    # Exact equality on purpose: adding a counts key is a view-schema change that
    # every consumer (status, UI, --json) sees, so it should fail here first.
    assert view.counts == {
        "proposed": 2,
        "confirmed": 1,
        "active": 1,
        "superseded": 0,
        "retired": 0,
        "stale": 1,
        "orphaned": 0,
        "moved_anchors": 0,
        "lost_anchors": 0,
        "conflicts": 0,
        "related": 0,
        "pending_approval": 0,
        "agreed": 0,
        "recommended": 0,
        "unverified": 0,
        "dismissed": 0,
        "reopened": 0,
    }
    assert [p.id for p in view.proposals] == sorted(p.id for p in view.proposals)
    assert [d.id for d in view.decisions] == ["dec_active1", "dec_conf1", "dec_stale1"]
    assert [d.id for d in view.stale] == ["dec_stale1"]
    assert view.proposals[0].extracted_by == "test/extractor"


@pytest.mark.phase_3
def test_view_counts_and_carries_who_proposed_each_decision(tmp_path: Path) -> None:
    for decision_id, proposer in [
        ("dec_h1", DecisionProposer.HUMAN),
        ("dec_h2", DecisionProposer.HUMAN),
        ("dec_a1", DecisionProposer.AI),
        ("dec_legacy", None),
    ]:
        record = DecisionRecord(
            frontmatter=DecisionFrontmatter(
                id=decision_id,
                ai_tool=AiTool.NONE,
                oversight=DecisionOversight.REVIEWED,
                proposed_by=proposer,
                context=f"context {decision_id}",
                choice=f"choice {decision_id}",
            ),
            body="",
        )
        write_decision_file(tmp_path / DECISIONS_DIR / decision_filename(decision_id), record)

    view = build_ledger_view(tmp_path)

    assert (view.counts["agreed"], view.counts["recommended"]) == (2, 1)
    assert {d.id: d.proposed_by for d in view.decisions} == {
        "dec_a1": "ai",
        "dec_h1": "human",
        "dec_h2": "human",
        "dec_legacy": None,
    }


@pytest.mark.phase_3
def test_ledger_view_empty_repo(tmp_path: Path) -> None:
    view = build_ledger_view(tmp_path)
    assert view.proposals == []
    assert view.decisions == []
    assert view.stale == []
    assert view.watchers == []
    assert view.conflicts == []
    assert view.counts["proposed"] == 0


@pytest.mark.phase_4
def test_ledger_view_watch_values_stale_is_display_only(tmp_path: Path) -> None:
    _write_ledger_record(
        tmp_path,
        "dec_queue1",
        status=DecisionStatus.ACTIVE,
        context="Queue depth assumption",
        choice="single consumer",
        watchers=["queue_depth < 100"],
    )

    # No values -> watcher unknown, nothing stale.
    baseline = build_ledger_view(tmp_path)
    assert baseline.stale == []
    assert baseline.watchers[0].status == "unknown"

    # Breached value -> display-stale, but the file on disk is untouched.
    view = build_ledger_view(tmp_path, watch_values={"queue_depth": 150.0})
    assert [d.id for d in view.stale] == ["dec_queue1"]
    watcher = view.watchers[0]
    assert watcher.status == "stale"
    assert watcher.last_value == 150.0

    on_disk = read_decision_file(tmp_path / DECISIONS_DIR / decision_filename("dec_queue1"))
    assert on_disk.frontmatter.status == DecisionStatus.ACTIVE


@pytest.mark.phase_4
def test_ledger_view_conflicts_hint(tmp_path: Path) -> None:
    _write_ledger_record(
        tmp_path,
        "dec_tzutc",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="UTC",
    )
    _write_ledger_record(
        tmp_path,
        "dec_tzlocal",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="server-local",
    )
    view = build_ledger_view(tmp_path)
    # Similar context alone is not a conflict: nobody has judged the pair yet.
    assert view.counts["conflicts"] == 0
    assert view.counts["related"] == 1
    assert view.counts["unverified"] == 1
    pair = view.related[0]
    assert pair.relation is Relation.UNVERIFIED
    assert {pair.decision_a, pair.decision_b} == {"dec_tzutc", "dec_tzlocal"}


@pytest.mark.phase_4
def test_dismissed_conflict_disappears_from_the_view(tmp_path: Path) -> None:
    """A hint the reviewer judged wrong must stop nagging on every status call."""
    _write_ledger_record(
        tmp_path,
        "dec_tzutc",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="UTC",
    )
    _write_ledger_record(
        tmp_path,
        "dec_tzlocal",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="server-local",
    )
    assert build_ledger_view(tmp_path).counts["related"] == 1

    add_dismissal(
        tmp_path,
        decision_a="dec_tzutc",
        decision_b="dec_tzlocal",
        reason="different subsystems; storage policy is scoped per service",
    )

    view = build_ledger_view(tmp_path)
    assert view.related == []
    assert view.counts["related"] == 0
    # Still counted, so a reviewer can see suppression is happening.
    assert view.counts["dismissed"] == 1


@pytest.mark.phase_4
def test_dismissal_reopens_when_a_decision_is_edited(tmp_path: Path) -> None:
    """A verdict covers the text it judged, not the id pair forever.

    Regression: editing a decision into a genuine contradiction used to stay
    permanently suppressed by the dismissal recorded against its old wording.
    """
    from reasonledger_core.decisions import load_decisions_from_dir
    from reasonledger_core.decisions.format import DECISIONS_DIR
    from reasonledger_core.models.reasoning import ConflictStatus
    from reasonledger_core.reasoning.dismissals import pair_fingerprint

    _write_ledger_record(
        tmp_path,
        "dec_tzutc",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="UTC",
    )
    _write_ledger_record(
        tmp_path,
        "dec_tzlocal",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="server-local",
    )
    by_id = {
        record.frontmatter.id: record
        for record in load_decisions_from_dir(tmp_path / DECISIONS_DIR)
    }
    add_dismissal(
        tmp_path,
        decision_a="dec_tzutc",
        decision_b="dec_tzlocal",
        reason="different subsystems; storage policy is scoped per service",
        fingerprint=pair_fingerprint(by_id["dec_tzutc"], by_id["dec_tzlocal"]),
    )
    assert build_ledger_view(tmp_path).counts["related"] == 0

    # The dismissed decision is rewritten onto a directly opposing choice.
    _write_ledger_record(
        tmp_path,
        "dec_tzlocal",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="store every timestamp in the requesting user's local zone",
    )

    view = build_ledger_view(tmp_path)
    assert view.counts["related"] == 1
    assert view.counts["dismissed"] == 0
    assert view.counts["reopened"] == 1
    assert view.related[0].status is ConflictStatus.REOPENED
    # The UI payload carries the same marker, so both surfaces agree.
    assert view.related_with_details[0].status is ConflictStatus.REOPENED


@pytest.mark.phase_4
def test_cached_view_matches_uncached(tmp_path: Path) -> None:
    from reasonledger_core.views import build_ledger_view_cached
    from reasonledger_core.views.cache import clear_view_cache

    clear_view_cache()
    _write_ledger_record(
        tmp_path,
        "dec_cache1",
        status=DecisionStatus.CONFIRMED,
        context="Cache store selection",
        choice="Redis",
    )
    uncached = build_ledger_view(tmp_path).model_dump(exclude={"generated_at"})
    cached = build_ledger_view_cached(tmp_path).model_dump(exclude={"generated_at"})
    assert cached == uncached


@pytest.mark.phase_4
def test_cache_invalidates_on_new_decision(tmp_path: Path) -> None:
    from reasonledger_core.views import build_ledger_view_cached
    from reasonledger_core.views.cache import clear_view_cache

    clear_view_cache()
    _write_ledger_record(
        tmp_path,
        "dec_cache_a",
        status=DecisionStatus.CONFIRMED,
        context="First",
        choice="A",
    )
    first = build_ledger_view_cached(tmp_path)
    assert first.counts["confirmed"] == 1
    _write_ledger_record(
        tmp_path,
        "dec_cache_b",
        status=DecisionStatus.CONFIRMED,
        context="Second",
        choice="B",
    )
    second = build_ledger_view_cached(tmp_path)
    assert second.counts["confirmed"] == 2
    assert {d.id for d in second.decisions} == {"dec_cache_a", "dec_cache_b"}


@pytest.mark.phase_4
def test_cache_invalidates_on_conflict_config_change(tmp_path: Path) -> None:
    """A retuned gate only touches .reasonledger/conflict.yml — no decision file
    changes — so the fingerprint has to notice that file too, exactly like the
    dismissed.yml case above.
    """
    from reasonledger_core.views import build_ledger_view_cached
    from reasonledger_core.views.cache import clear_view_cache

    clear_view_cache()
    _write_ledger_record(
        tmp_path,
        "dec_retry_pay",
        status=DecisionStatus.CONFIRMED,
        context="Retry policy for flaky network calls to the payments API",
        choice="Exponential backoff with jitter",
    )
    _write_ledger_record(
        tmp_path,
        "dec_retry_bill",
        status=DecisionStatus.CONFIRMED,
        context="Retry strategy for flaky network calls to the billing API",
        choice="Fixed delay retry, three attempts",
    )
    first = build_ledger_view_cached(tmp_path)
    assert first.counts["related"] == 1

    # DeterministicEmbedder rates this pair's context similarity at ~0.8; a gate
    # above that suppresses it without touching either decision file.
    write_conflict_config(tmp_path, ConflictConfig(context_similarity_gate=0.9))

    second = build_ledger_view_cached(tmp_path)
    assert second.counts["related"] == 0
    assert second.related == []


@pytest.mark.phase_4
def test_cache_invalidates_on_dismissal(tmp_path: Path) -> None:
    """A dismissal only touches dismissed.yml — no decisions/proposed .md file changes.

    The fingerprint has to notice that file too, or a cached view keeps showing a
    conflict the reviewer already dismissed until an unrelated ledger edit happens
    to invalidate the cache — which is exactly the gap the UI's Dismiss button
    would have silently hit.
    """
    from reasonledger_core.views import build_ledger_view_cached
    from reasonledger_core.views.cache import clear_view_cache

    clear_view_cache()
    _write_ledger_record(
        tmp_path,
        "dec_tzutc",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="UTC",
    )
    _write_ledger_record(
        tmp_path,
        "dec_tzlocal",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="server-local",
    )
    first = build_ledger_view_cached(tmp_path)
    assert first.counts["related"] == 1

    add_dismissal(
        tmp_path,
        decision_a="dec_tzutc",
        decision_b="dec_tzlocal",
        reason="different subsystems; storage policy is scoped per service",
    )

    second = build_ledger_view_cached(tmp_path)
    assert second.counts["related"] == 0
    assert second.related == []


@pytest.mark.phase_4
def test_view_budget_500_decisions(tmp_path: Path) -> None:
    import time

    from reasonledger_core.reasoning.embeddings import DeterministicEmbedder

    for i in range(500):
        _write_ledger_record(
            tmp_path,
            f"dec_bud{i:04d}",
            status=DecisionStatus.CONFIRMED,
            context=f"Decision context number {i} about storage choice",
            choice=f"option-{i % 7}",
        )
    start = time.perf_counter()
    view = build_ledger_view(tmp_path, embedder=DeterministicEmbedder())
    elapsed = time.perf_counter() - start
    assert view.counts["confirmed"] == 500
    assert elapsed < 2.0, f"build_ledger_view took {elapsed:.2f}s"


def _two_timezone_records(root: Path) -> None:
    for decision_id, choice in (("dec_tzutc", "UTC"), ("dec_tzlocal", "server-local")):
        _write_ledger_record(
            root,
            decision_id,
            status=DecisionStatus.CONFIRMED,
            context="Timestamp storage timezone policy",
            choice=choice,
        )


@pytest.mark.phase_4
def test_view_reports_embedder_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A degraded run must say so on the view every surface renders from."""
    _two_timezone_records(tmp_path)
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))

    def _missing(**_: object) -> object:
        raise ImportError("No module named 'fastembed'")

    monkeypatch.setattr("reasonledger_core.reasoning.conflict_config.get_embedder", _missing)
    view = build_ledger_view(tmp_path)
    assert view.embedder is not None
    assert view.embedder.requested == "local"
    assert view.embedder.fallback_reason is not None
    assert view.counts["related"] == 1  # still detects, on the fallback embedder


@pytest.mark.phase_4
def test_view_reports_healthy_embedder(tmp_path: Path) -> None:
    _two_timezone_records(tmp_path)
    view = build_ledger_view(tmp_path)
    assert view.embedder is not None
    assert view.embedder.fallback_reason is None


@pytest.mark.phase_4
def test_superseded_record_drops_out_of_the_view_conflicts(tmp_path: Path) -> None:
    _two_timezone_records(tmp_path)
    _write_ledger_record(
        tmp_path,
        "dec_tzlocal",
        status=DecisionStatus.SUPERSEDED,
        context="Timestamp storage timezone policy",
        choice="server-local",
    )
    view = build_ledger_view(tmp_path)
    assert view.counts["conflicts"] == 0


def _commit_verdict(root: Path, a: str, b: str, *, conflict: bool) -> None:
    """Write a verdict the way `reasonledger judge` does, fingerprinted on current text."""
    from reasonledger_core.decisions import load_decisions_from_dir
    from reasonledger_core.decisions.format import DECISIONS_DIR
    from reasonledger_core.reasoning.dismissals import pair_fingerprint, pair_key
    from reasonledger_core.reasoning.verdicts import (
        StoredVerdict,
        load_verdicts,
        write_verdicts,
    )

    by_id = {r.frontmatter.id: r for r in load_decisions_from_dir(root / DECISIONS_DIR)}
    verdicts = load_verdicts(root)
    verdicts[pair_key(a, b)] = StoredVerdict(
        same_question=True,
        compatible=not conflict,
        question="Which timezone are timestamps stored in?",
        reason="One stores UTC, the other server-local time.",
        severity=Severity.HIGH if conflict else Severity.LOW,
        decision_a=a,
        decision_b=b,
        fingerprint=pair_fingerprint(by_id[a], by_id[b]),
        model="test-judge",
        judged_at=EXTRACTED_AT,
    )
    write_verdicts(root, verdicts)


@pytest.mark.phase_4
def test_judged_conflict_is_a_conflict(tmp_path: Path) -> None:
    _two_timezone_records(tmp_path)
    _commit_verdict(tmp_path, "dec_tzutc", "dec_tzlocal", conflict=True)
    view = build_ledger_view(tmp_path)
    assert view.counts["conflicts"] == 1
    assert view.counts["related"] == 0
    assert view.conflicts[0].severity is Severity.HIGH
    assert "Which timezone" in view.conflicts[0].explanation
    assert view.conflicts_with_details[0].relation is Relation.CONFLICT


@pytest.mark.phase_4
def test_judged_compatible_stays_related(tmp_path: Path) -> None:
    _two_timezone_records(tmp_path)
    _commit_verdict(tmp_path, "dec_tzutc", "dec_tzlocal", conflict=False)
    view = build_ledger_view(tmp_path)
    assert view.counts["conflicts"] == 0
    assert view.counts["unverified"] == 0
    assert view.related[0].relation is Relation.COMPATIBLE


@pytest.mark.phase_4
def test_verdict_lapses_when_a_decision_is_edited(tmp_path: Path) -> None:
    """An old "compatible" must never cover a decision rewritten since it was judged."""
    _two_timezone_records(tmp_path)
    _commit_verdict(tmp_path, "dec_tzutc", "dec_tzlocal", conflict=False)
    _write_ledger_record(
        tmp_path,
        "dec_tzlocal",
        status=DecisionStatus.CONFIRMED,
        context="Timestamp storage timezone policy",
        choice="store every timestamp in the requesting user's local zone",
    )
    view = build_ledger_view(tmp_path)
    assert view.related[0].relation is Relation.UNVERIFIED


@pytest.mark.phase_4
def test_cache_invalidates_on_new_verdict(tmp_path: Path) -> None:
    from reasonledger_core.views import build_ledger_view_cached
    from reasonledger_core.views.cache import clear_view_cache

    clear_view_cache()
    _two_timezone_records(tmp_path)
    assert build_ledger_view_cached(tmp_path).counts["conflicts"] == 0
    _commit_verdict(tmp_path, "dec_tzutc", "dec_tzlocal", conflict=True)
    assert build_ledger_view_cached(tmp_path).counts["conflicts"] == 1


@pytest.mark.phase_3
def test_orphans_list_only_decisions_in_force_and_name_nearby_replacements(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "new.py").write_text("def build():\n    return 1\n")
    kwargs = {"context": "Where do totals live?", "choice": "In one module"}
    _write_ledger_record(
        tmp_path,
        "dec_gone",
        status=DecisionStatus.CONFIRMED,
        justifies=["src/old.py::build"],
        **kwargs,
    )
    _write_ledger_record(
        tmp_path,
        "dec_retired",
        status=DecisionStatus.RETIRED,
        justifies=["src/old.py::build"],
        **kwargs,
    )
    _write_ledger_record(
        tmp_path,
        "dec_next",
        status=DecisionStatus.ACTIVE,
        justifies=["src/new.py::build"],
        **kwargs,
    )
    view = build_ledger_view(tmp_path)
    assert [(o.decision_id, o.candidates) for o in view.orphaned] == [("dec_gone", ["dec_next"])]
    assert view.counts["orphaned"] == 1


@pytest.mark.phase_3
def test_symbols_the_extractor_skips_are_not_reported_missing(tmp_path: Path) -> None:
    (tmp_path / "ui.js").write_text("(function (g) {\n  function pie() {}\n})(window);\n")
    (tmp_path / "cfg.py").write_text("TARGETS = {}\n# def commented_out(): pass\n")
    (tmp_path / "note.js").write_text("// function ghost() {}\nconst s = 'function ghost() {}';\n")
    _write_ledger_record(
        tmp_path,
        "dec_nested",
        status=DecisionStatus.ACTIVE,
        context="c",
        choice="d",
        justifies=[
            "ui.js::pie",
            "cfg.py::TARGETS",
            "ui.js::gone",
            "cfg.py::OTHER",
            "cfg.py::commented_out",
            "note.js::ghost",
        ],
    )
    reported = {o.locus for o in build_ledger_view(tmp_path).orphaned}
    assert reported == {"ui.js::gone", "cfg.py::OTHER", "cfg.py::commented_out", "note.js::ghost"}
