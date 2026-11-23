"""P0-4 S5: propose/confirm writer — staging, PII, idempotency, confirm."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.extractor import DecisionCandidate
from reasonledger_core.importer.propose import (
    PROPOSED_DIR,
    ImportConfirmError,
    confirm_proposed,
    propose_decisions,
)
from reasonledger_core.models.decision import DecisionSource, DecisionStatus

EXTRACTED_AT = datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC)


def _candidate(
    ref: str, *, choice: str = "UTC", context: str = "Timestamp policy"
) -> DecisionCandidate:
    return DecisionCandidate(context=context, choice=choice, source_ref=ref)


@pytest.mark.phase_3
def test_propose_writes_to_staging_not_ledger(tmp_path: Path) -> None:
    result = propose_decisions(
        [_candidate("claude.md#ts")],
        root=tmp_path,
        extracted_by="anthropic/claude-sonnet-5",
        extracted_at=EXTRACTED_AT,
    )
    assert result.created == 1
    # Never auto-written to the ledger — proposals stage separately.
    assert not (tmp_path / DECISIONS_DIR).exists()
    assert len(list((tmp_path / PROPOSED_DIR).glob("dec_*.md"))) == 1

    record = result.records[0]
    assert record.frontmatter.status == DecisionStatus.PROPOSED
    assert record.frontmatter.source == DecisionSource.DOC_IMPORT
    assert record.frontmatter.extracted_at == EXTRACTED_AT
    assert record.frontmatter.decided_at is None


@pytest.mark.phase_3
def test_propose_skips_pii(tmp_path: Path) -> None:
    result = propose_decisions(
        [_candidate("claude.md#leak", context="Contact bob@evil.example about tz")],
        root=tmp_path,
        extracted_by="m",
        extracted_at=EXTRACTED_AT,
    )
    assert result.created == 0
    assert result.skipped_pii == ["claude.md#leak"]
    assert not (tmp_path / PROPOSED_DIR).exists()


@pytest.mark.phase_3
def test_propose_is_idempotent(tmp_path: Path) -> None:
    candidates = [_candidate("claude.md#ts")]
    first = propose_decisions(
        candidates, root=tmp_path, extracted_by="m", extracted_at=EXTRACTED_AT
    )
    second = propose_decisions(
        candidates, root=tmp_path, extracted_by="m", extracted_at=EXTRACTED_AT
    )
    assert first.created == 1
    assert second.created == 0
    assert second.skipped_unchanged == 1


def _confirm_first(tmp_path: Path, candidate: DecisionCandidate) -> str:
    proposal = propose_decisions(
        [candidate], root=tmp_path, extracted_by="m", extracted_at=EXTRACTED_AT
    )
    decision_id = proposal.proposed_ids[0]
    confirm_proposed(
        decision_id,
        root=tmp_path,
        confirmed_by="alice",
        confirmed_at=datetime(2026, 7, 21, 13, 0, 0, tzinfo=UTC),
    )
    return decision_id


@pytest.mark.phase_3
def test_reimport_does_not_restage_a_confirmed_decision(tmp_path: Path) -> None:
    """Reconnecting after a gap must not resurrect work the reviewer already did."""
    candidate = _candidate("claude.md#ts")
    decision_id = _confirm_first(tmp_path, candidate)

    again = propose_decisions(
        [candidate], root=tmp_path, extracted_by="m", extracted_at=EXTRACTED_AT
    )

    assert again.created == 0
    assert again.skipped_confirmed == 1
    assert again.superseded == []
    assert not (tmp_path / PROPOSED_DIR / f"{decision_id}.md").exists()


@pytest.mark.phase_3
def test_reimport_never_puts_one_id_in_two_states(tmp_path: Path) -> None:
    """The same id in staging and the ledger is a corrupt ledger, not a duplicate."""
    candidate = _candidate("claude.md#ts")
    decision_id = _confirm_first(tmp_path, candidate)

    propose_decisions([candidate], root=tmp_path, extracted_by="m", extracted_at=EXTRACTED_AT)

    staged = {path.stem for path in (tmp_path / PROPOSED_DIR).glob("dec_*.md")}
    ledger = {record.frontmatter.id for record in load_decisions_from_dir(tmp_path / DECISIONS_DIR)}
    assert decision_id in ledger
    assert staged & ledger == set()


@pytest.mark.phase_3
def test_reimport_stages_a_changed_source_as_a_supersede(tmp_path: Path) -> None:
    """The payoff case: the doc behind a confirmed decision now says something else."""
    original_id = _confirm_first(
        tmp_path, _candidate("claude.md#ts", choice="Store timestamps in UTC")
    )

    changed = propose_decisions(
        [_candidate("claude.md#ts", choice="Store timestamps in server-local time")],
        root=tmp_path,
        extracted_by="m",
        extracted_at=EXTRACTED_AT,
    )

    assert len(changed.superseded) == 1
    supersede = changed.superseded[0]
    assert supersede.supersedes == original_id
    assert supersede.source_ref == "claude.md#ts"
    # Its own id, so the replacement and the record it replaces can coexist.
    assert supersede.proposal_id != original_id
    assert changed.created == 1
    assert (tmp_path / PROPOSED_DIR / f"{supersede.proposal_id}.md").is_file()


@pytest.mark.phase_3
def test_supersede_proposal_is_idempotent(tmp_path: Path) -> None:
    """Re-importing an unchanged-but-superseding doc must not stage a second copy."""
    _confirm_first(tmp_path, _candidate("claude.md#ts", choice="Store timestamps in UTC"))
    changed = _candidate("claude.md#ts", choice="Store timestamps in server-local time")

    first = propose_decisions([changed], root=tmp_path, extracted_by="m", extracted_at=EXTRACTED_AT)
    second = propose_decisions(
        [changed], root=tmp_path, extracted_by="m", extracted_at=EXTRACTED_AT
    )

    assert first.created == 1
    assert second.created == 0
    assert second.skipped_unchanged == 1
    assert first.superseded[0].proposal_id == second.superseded[0].proposal_id
    assert len(list((tmp_path / PROPOSED_DIR).glob("dec_*.md"))) == 1


@pytest.mark.phase_3
def test_confirming_a_supersede_retires_the_old_record(tmp_path: Path) -> None:
    """Both records survive: the ledger shows what was believed and what replaced it."""
    original_id = _confirm_first(
        tmp_path, _candidate("claude.md#ts", choice="Store timestamps in UTC")
    )
    staged = propose_decisions(
        [_candidate("claude.md#ts", choice="Store timestamps in server-local time")],
        root=tmp_path,
        extracted_by="m",
        extracted_at=EXTRACTED_AT,
    )
    new_id = staged.superseded[0].proposal_id

    confirm_proposed(
        new_id,
        root=tmp_path,
        confirmed_by="alice",
        confirmed_at=datetime(2026, 9, 1, 9, 0, 0, tzinfo=UTC),
    )

    ledger = {r.frontmatter.id: r for r in load_decisions_from_dir(tmp_path / DECISIONS_DIR)}
    assert set(ledger) == {original_id, new_id}
    assert ledger[original_id].frontmatter.status == DecisionStatus.SUPERSEDED
    assert ledger[new_id].frontmatter.status == DecisionStatus.CONFIRMED
    assert ledger[new_id].frontmatter.supersedes == original_id
    # The retired record keeps its own evidence — it is not rewritten with the new choice.
    assert ledger[original_id].frontmatter.choice == "Store timestamps in UTC"


@pytest.mark.phase_3
def test_confirming_a_supersede_of_a_missing_record_is_refused(tmp_path: Path) -> None:
    """Retiring nothing would silently drop the supersede link from the audit trail."""
    original_id = _confirm_first(
        tmp_path, _candidate("claude.md#ts", choice="Store timestamps in UTC")
    )
    staged = propose_decisions(
        [_candidate("claude.md#ts", choice="Store timestamps in server-local time")],
        root=tmp_path,
        extracted_by="m",
        extracted_at=EXTRACTED_AT,
    )
    (tmp_path / DECISIONS_DIR / f"{original_id}.md").unlink()

    with pytest.raises(ImportConfirmError, match="not in the ledger"):
        confirm_proposed(
            staged.superseded[0].proposal_id,
            root=tmp_path,
            confirmed_by="alice",
            confirmed_at=datetime(2026, 9, 1, 9, 0, 0, tzinfo=UTC),
        )


@pytest.mark.phase_3
def test_rejecting_a_supersede_leaves_the_original_confirmed(tmp_path: Path) -> None:
    """Declining the replacement must not disturb the decision already in the ledger."""
    original_id = _confirm_first(
        tmp_path, _candidate("claude.md#ts", choice="Store timestamps in UTC")
    )
    staged = propose_decisions(
        [_candidate("claude.md#ts", choice="Store timestamps in server-local time")],
        root=tmp_path,
        extracted_by="m",
        extracted_at=EXTRACTED_AT,
    )

    (tmp_path / PROPOSED_DIR / f"{staged.superseded[0].proposal_id}.md").unlink()

    ledger = load_decisions_from_dir(tmp_path / DECISIONS_DIR)
    assert [r.frontmatter.id for r in ledger] == [original_id]
    assert ledger[0].frontmatter.status == DecisionStatus.CONFIRMED


@pytest.mark.phase_3
def test_reimport_ignores_lifecycle_fields_when_comparing(tmp_path: Path) -> None:
    """`confirmed` differs from `proposed` by construction; that is not a source change."""
    candidate = _candidate("claude.md#ts")
    _confirm_first(tmp_path, candidate)

    later = propose_decisions(
        [candidate],
        root=tmp_path,
        extracted_by="a-different-model",
        extracted_at=datetime(2026, 9, 1, 9, 0, 0, tzinfo=UTC),
    )

    assert later.superseded == []
    assert later.skipped_confirmed == 1


@pytest.mark.phase_3
def test_confirm_promotes_proposal_into_ledger(tmp_path: Path) -> None:
    proposal = propose_decisions(
        [_candidate("claude.md#ts")],
        root=tmp_path,
        extracted_by="m",
        extracted_at=EXTRACTED_AT,
    )
    decision_id = proposal.proposed_ids[0]
    record = confirm_proposed(
        decision_id,
        root=tmp_path,
        confirmed_by="alice",
        confirmed_at=datetime(2026, 7, 21, 13, 0, 0, tzinfo=UTC),
    )
    assert record.frontmatter.status == DecisionStatus.CONFIRMED
    assert record.frontmatter.confirmed_by == "alice"
    # Moved out of staging into the ledger.
    assert not (tmp_path / PROPOSED_DIR / f"{decision_id}.md").exists()
    ledger = load_decisions_from_dir(tmp_path / DECISIONS_DIR)
    assert [r.frontmatter.id for r in ledger] == [decision_id]


@pytest.mark.phase_3
def test_commit_derived_records_declare_their_provenance(tmp_path: Path) -> None:
    """A commit message and a curated doc are weighed differently by a reviewer."""
    result = propose_decisions(
        [
            _candidate("docs/arch.md#ts"),
            _candidate("git:abc123def456#retries", choice="backoff"),
        ],
        root=tmp_path,
        extracted_by="m",
        extracted_at=EXTRACTED_AT,
    )
    sources = {r.frontmatter.source_ref: r.frontmatter.source for r in result.records}
    assert sources["docs/arch.md#ts"] == DecisionSource.DOC_IMPORT
    assert sources["git:abc123def456#retries"] == DecisionSource.COMMIT_IMPORT
