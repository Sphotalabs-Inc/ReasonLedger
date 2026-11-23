"""Phase 5 — a person confirms, renames, merges and rejects modules."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from modules_helpers import tree
from reasonledger_core.modules import Manifest, Module, ModuleKind, ModuleStatus, merge_proposals
from reasonledger_core.modules.buckets import new_bucket
from reasonledger_core.modules.config import PENDING_QUEUE_CAP, REJECT_REAPPEAR_JACCARD
from reasonledger_core.modules.editing import (
    ModuleEditError,
    confirm_modules,
    high_confidence_ids,
    merge_modules,
    reject_module,
    rename_module,
)
from reasonledger_core.modules.models import Confidence, Suggestion, Tier
from reasonledger_core.modules.review import next_up, pending_queue

AT = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)


def _mod(
    module_id: str,
    *paths: str,
    status: ModuleStatus = ModuleStatus.PROPOSED,
    confidence: Confidence | None = None,
    tier: Tier | None = None,
    kind: ModuleKind = ModuleKind.FEATURE,
) -> Module:
    return Module(
        id=module_id,
        name=module_id.replace("-", " ").title(),
        paths=list(paths) or [f"{module_id}/**"],
        status=status,
        confidence=confidence,
        tier=tier,
        kind=kind,
    )


def _by_id(manifest: Manifest) -> dict[str, Module]:
    return {m.id: m for m in manifest.modules}


@pytest.mark.phase_5
def test_confirming_records_who_and_when_and_is_harmless_to_repeat() -> None:
    done = _mod("kept", status=ModuleStatus.CONFIRMED)
    manifest = Manifest(modules=[_mod("a"), _mod("b"), done])
    updated, changed = confirm_modules(manifest, ["a", "kept"], by=" alice ", at=AT)
    assert changed == ["a"]  # kept was already confirmed
    confirmed = _by_id(updated)["a"]
    assert confirmed.status is ModuleStatus.CONFIRMED
    assert (confirmed.confirmed_by, confirmed.confirmed_at) == ("alice", AT)
    assert _by_id(updated)["kept"] == done and _by_id(updated)["b"].status is ModuleStatus.PROPOSED


@pytest.mark.phase_5
def test_confirming_an_unknown_module_or_without_a_name_changes_nothing() -> None:
    manifest = Manifest(modules=[_mod("a")])
    with pytest.raises(ModuleEditError, match="no module named 'ghost'"):
        confirm_modules(manifest, ["a", "ghost"], by="me", at=AT)
    with pytest.raises(ModuleEditError, match="did you mean a"):
        confirm_modules(manifest, ["aa"], by="me", at=AT)
    with pytest.raises(ModuleEditError, match="--by"):
        confirm_modules(manifest, ["a"], by="  ", at=AT)
    assert manifest.modules[0].status is ModuleStatus.PROPOSED  # the input is never mutated


@pytest.mark.phase_5
def test_bulk_confirm_selects_only_proposed_high_confidence_modules() -> None:
    manifest = Manifest(
        modules=[
            _mod("sure", confidence=Confidence.HIGH),
            _mod("maybe", confidence=Confidence.MEDIUM),
            _mod("unknown"),
            _mod("done", status=ModuleStatus.CONFIRMED, confidence=Confidence.HIGH),
            new_bucket("tooling"),
        ]
    )
    assert high_confidence_ids(manifest) == ["sure"]


@pytest.mark.phase_5
def test_the_queue_is_ordered_by_trust_then_size_and_capped() -> None:
    modules = [_mod(f"m{i}", confidence=Confidence.LOW) for i in range(PENDING_QUEUE_CAP + 2)]
    modules += [
        _mod("high-small", confidence=Confidence.HIGH),
        _mod("high-big", confidence=Confidence.HIGH),
        _mod("medium", confidence=Confidence.MEDIUM),
        _mod("done", status=ModuleStatus.CONFIRMED, confidence=Confidence.HIGH),
    ]
    queue = pending_queue(Manifest(modules=modules), {"high-big": 9, "high-small": 2})
    assert [m.id for m in queue][:3] == ["high-big", "high-small", "medium"]
    assert "done" not in {m.id for m in queue}  # only proposals wait
    shown, waiting = next_up(queue)
    assert len(shown) == PENDING_QUEUE_CAP == 5
    assert waiting == len(queue) - PENDING_QUEUE_CAP


@pytest.mark.phase_5
def test_a_rename_changes_the_id_and_everything_that_points_at_it() -> None:
    manifest = Manifest(
        modules=[_mod("templates"), _mod("other")],
        labels={"a.py": "templates", "b.py": "other"},
        suggestions=[Suggestion(module="templates", paths=["c.py"])],
    )
    updated, new_id = rename_module(manifest, "templates", " Data extraction ")
    assert new_id == "data-extraction"
    assert _by_id(updated)["data-extraction"].name == "Data extraction"
    assert updated.labels == {"a.py": "data-extraction", "b.py": "other"}
    assert updated.suggestions[0].module == "data-extraction"
    assert "templates" not in _by_id(updated)
    same, kept_id = rename_module(manifest, "templates", "Templates")  # a name change alone
    assert kept_id == "templates" and _by_id(same)["templates"].name == "Templates"


@pytest.mark.phase_5
def test_a_rename_refuses_a_taken_id_a_bucket_and_an_empty_name() -> None:
    manifest = Manifest(modules=[_mod("a"), _mod("b"), new_bucket("shared-backend")])
    with pytest.raises(ModuleEditError, match="already a module"):
        rename_module(manifest, "a", "B")
    with pytest.raises(ModuleEditError, match="already a module or a bucket"):
        rename_module(manifest, "a", "Tooling")  # a bucket id is reserved
    with pytest.raises(ModuleEditError, match="is a bucket"):
        rename_module(manifest, "shared-backend", "Helpers")
    with pytest.raises(ModuleEditError, match="new name"):
        rename_module(manifest, "a", "  ")


@pytest.mark.phase_5
def test_a_merge_unites_the_paths_and_moves_labels_and_suggestions() -> None:
    manifest = Manifest(
        modules=[
            Module(
                id="keep",
                name="Keep",
                description="",
                paths=["k/**", "x.py"],
                tier=Tier.BACKEND,
                confidence=Confidence.HIGH,
                evidence=["model:m", "specs"],
            ),
            Module(
                id="gone",
                name="Gone",
                description="what it does",
                paths=["g/**", "x.py"],
                tier=Tier.FRONTEND,
                confidence=Confidence.LOW,
                evidence=["specs", "layout"],
            ),
        ],
        labels={"l.py": "gone"},
        suggestions=[Suggestion(module="gone", paths=["s.py"])],
    )
    merged = _by_id(merge_modules(manifest, "keep", "gone"))
    assert set(merged) == {"keep"}
    kept = merged["keep"]
    assert kept.paths == ["g/**", "k/**", "x.py"]
    assert kept.name == "Keep" and kept.description == "what it does"  # fills a blank description
    assert kept.tier is None  # a backend and a frontend module do not make a tier
    assert kept.confidence is Confidence.LOW  # the more cautious of the two
    assert kept.evidence == ["model:m", "specs", "layout"]
    after = merge_modules(manifest, "keep", "gone")
    assert after.labels == {"l.py": "keep"} and after.suggestions[0].module == "keep"


@pytest.mark.phase_5
def test_a_merge_refuses_what_would_lose_a_confirmation_or_is_not_a_module_pair() -> None:
    confirmed = _mod("sure", status=ModuleStatus.CONFIRMED)
    manifest = Manifest(modules=[confirmed, _mod("maybe"), new_bucket("tooling")])
    with pytest.raises(ModuleEditError, match="the other way round"):
        merge_modules(manifest, "maybe", "sure")
    assert "maybe" not in _by_id(merge_modules(manifest, "sure", "maybe"))  # the safe direction
    with pytest.raises(ModuleEditError, match="itself"):
        merge_modules(manifest, "sure", "sure")
    with pytest.raises(ModuleEditError, match="is a bucket"):
        merge_modules(manifest, "sure", "tooling")


@pytest.mark.phase_5
def test_a_rejected_proposal_is_remembered_and_a_confirmed_module_cannot_be_rejected() -> None:
    manifest = Manifest(modules=[_mod("noise"), _mod("real", status=ModuleStatus.CONFIRMED)])
    updated = reject_module(manifest, "noise", " generated code ")
    assert "noise" not in _by_id(updated)
    assert [(r.paths, r.reason) for r in updated.rejected] == [(["noise/**"], "generated code")]
    with pytest.raises(ModuleEditError, match="is confirmed"):
        reject_module(manifest, "real")


@pytest.mark.phase_5
def test_a_rejection_holds_while_a_new_map_covers_about_the_same_files() -> None:
    files = list(tree("app/pages", 10))
    manifest = reject_module(Manifest(modules=[_mod("pages", "app/pages/**")]), "pages")
    assert REJECT_REAPPEAR_JACCARD == 0.7
    same = _mod("pages-again", "app/pages/**")
    most = _mod("pages-most", *files[:8])  # 8 of 10 files: Jaccard 0.8, still the same module
    half = _mod("pages-half", *files[:5])  # 5 of 10 files: Jaccard 0.5, a different proposal
    other = _mod("billing", "app/billing/**")
    merged = merge_proposals(manifest, [same, most, half, other], [*files, "app/billing/f0.py"])
    assert [m.id for m in merged.modules] == ["pages-half", "billing"]
    # without a file list only an identical path set stays down
    blind = merge_proposals(manifest, [same, most])
    assert [m.id for m in blind.modules] == ["pages-most"]
