"""Phase 5 — decision membership and the module map view."""

from __future__ import annotations

from pathlib import Path

import pytest
from modules_helpers import tree, write_files
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename, write_decision_file
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionProposer,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.models.reasoning import Conflict, Severity
from reasonledger_core.modules import Manifest, Module, ModuleKind, ModuleStatus, write_manifest
from reasonledger_core.modules.buckets import new_bucket
from reasonledger_core.modules.config import MAX_MODULES_PER_DECISION
from reasonledger_core.modules.digest import labelable_files, source_files
from reasonledger_core.modules.labels import label_files
from reasonledger_core.modules.manifest import load_manifest
from reasonledger_core.modules.models import Tier
from reasonledger_core.modules.placement import place_decisions
from reasonledger_core.views.map_view import load_map, module_page, overview


def _module(
    module_id: str, glob: str, kind: ModuleKind = ModuleKind.FEATURE, tier: Tier | None = None
) -> Module:
    return Module(
        id=module_id,
        name=module_id.title(),
        paths=[glob],
        kind=kind,
        tier=tier,
        status=ModuleStatus.CONFIRMED if kind is ModuleKind.FOUNDATION else ModuleStatus.PROPOSED,
    )


def _decision(
    root: Path,
    decision_id: str,
    *loci: str,
    status: DecisionStatus = DecisionStatus.ACTIVE,
    oversight: DecisionOversight = DecisionOversight.REVIEWED,
) -> None:
    record = DecisionRecord(
        frontmatter=DecisionFrontmatter(
            id=decision_id,
            ai_tool=AiTool.CLAUDE_CODE,
            model="test-model",
            oversight=oversight,
            status=status,
            proposed_by=DecisionProposer.AI,
            justifies=list(loci),
            context=f"question for {decision_id}",
            choice=f"choice for {decision_id}",
        ),
        body="",
    )
    write_decision_file(root / DECISIONS_DIR / decision_filename(decision_id), record)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write_files(
        tmp_path,
        {
            **tree("backend/app/promo", 3),
            **tree("frontend/src/promo", 3, ".js"),
            **tree("backend/app/dates", 3),
            **tree("backend/app/credits", 3),
            **tree("backend/app/alpha", 3),
            **tree("backend/app/beta", 3),
            **tree("backend/app/zero", 3),
            "backend/app/utils.py": "",
            "backend/app/stray.py": "",
        },
    )
    write_manifest(
        tmp_path,
        Manifest(
            modules=[
                _module("promo-codes", "backend/app/promo/**", tier=Tier.BACKEND),
                _module("promo-codes-ui", "frontend/src/promo/**", tier=Tier.FRONTEND),
                _module("dates", "backend/app/dates/**", ModuleKind.FOUNDATION, Tier.BACKEND),
                _module("credits", "backend/app/credits/**", tier=Tier.BACKEND),
                _module("alpha", "backend/app/alpha/**", tier=Tier.BACKEND),
                _module("beta", "backend/app/beta/**", tier=Tier.BACKEND),
                _module("zero", "backend/app/zero/**", tier=Tier.BACKEND),
                new_bucket("shared-backend", ["backend/app/utils.py"]),
            ]
        ),
    )
    _decision(tmp_path, "dec_shared", "backend/app/promo/f0.py:1-10", "frontend/src/promo/f0.js")
    _decision(tmp_path, "dec_dates", "backend/app/dates/f0.py::parse")
    _decision(
        tmp_path,
        "dec_wide",
        *(f"backend/app/{m}/f0.py" for m in ("promo", "credits", "dates", "alpha", "beta")),
    )
    _decision(tmp_path, "dec_loose")
    _decision(tmp_path, "dec_docs", "docs/notes.md")
    _decision(
        tmp_path,
        "dec_pending",
        "backend/app/credits/f0.py",
        oversight=DecisionOversight.PENDING,
    )
    _decision(
        tmp_path,
        "dec_old",
        "backend/app/credits/f1.py",
        "backend/app/credits/gone.py",
        status=DecisionStatus.SUPERSEDED,
    )
    return tmp_path


@pytest.mark.phase_5
def test_a_decision_belongs_to_every_module_its_anchors_fall_in(repo: Path) -> None:
    data = load_map(repo)
    shared = data.placements["dec_shared"]
    assert shared.modules == ["promo-codes", "promo-codes-ui"] and shared.shared
    assert shared.anchors["promo-codes"] == ["backend/app/promo/f0.py:1-10"]  # the locus, kept
    assert not data.placements["dec_dates"].shared  # usage does not spread a decision
    assert data.placements["dec_loose"].unplaced
    docs = data.placements["dec_docs"]
    assert docs.unplaced and docs.outside == ["docs/notes.md"]
    wide = data.placements["dec_wide"]
    assert len(wide.modules) == MAX_MODULES_PER_DECISION + 1 and wide.cross_cutting
    assert not shared.cross_cutting
    again = place_decisions(list(data.records.values()), data.manifest, data.root)
    assert again["dec_shared"] == shared  # deterministic


@pytest.mark.phase_5
def test_tiles_count_a_shared_decision_in_each_module_but_the_total_once(repo: Path) -> None:
    view = overview(load_map(repo))
    tiles = {t.id: t for t in [*view.features, *view.foundations, *view.buckets]}
    assert (tiles["promo-codes"].decisions, tiles["promo-codes"].shared) == (1, 1)
    assert (tiles["promo-codes-ui"].decisions, tiles["promo-codes-ui"].shared) == (1, 1)
    # live decisions: shared, dates, wide, loose, docs, pending (the superseded one is not counted)
    assert view.decisions == 6
    assert sum(t.decisions for t in tiles.values()) != view.decisions  # tiles do not sum
    assert tiles["promo-codes"].tier == "backend" and tiles["promo-codes-ui"].tier == "frontend"


@pytest.mark.phase_5
def test_a_cross_cutting_decision_is_listed_apart_and_under_a_foundation_only(repo: Path) -> None:
    view = overview(load_map(repo))
    assert [d.id for d in view.cross_cutting] == ["dec_wide"]
    tiles = {t.id: t for t in [*view.features, *view.foundations]}
    assert tiles["dates"].decisions == 2  # its own decision and the cross-cutting one
    assert tiles["credits"].cross_cutting == 1 and tiles["alpha"].decisions == 0
    page = module_page(load_map(repo), "alpha")
    assert page is not None and page.decisions == [] and page.tile.cross_cutting == 1
    dates = module_page(load_map(repo), "dates")
    assert dates is not None and {d.id for d in dates.decisions} == {"dec_dates", "dec_wide"}


@pytest.mark.phase_5
def test_unplaced_decisions_files_and_the_zero_decision_module_stay_visible(repo: Path) -> None:
    view = overview(load_map(repo))
    assert {d.id for d in view.unplaced_decisions} == {"dec_loose", "dec_docs"}
    assert view.unplaced_files == 1  # backend/app/stray.py belongs to no module or bucket
    zero = next(t for t in view.features if t.id == "zero")
    assert (zero.decisions, zero.coverage, zero.files) == (0, 0.0, 3)
    assert [t.id for t in view.buckets] == ["shared-backend"]
    assert view.pending_proposals == 6  # every capability but the foundation is still proposed


@pytest.mark.phase_5
def test_coverage_counts_anchored_files_of_live_decisions_only(repo: Path) -> None:
    view = overview(load_map(repo))
    credits = next(t for t in view.features if t.id == "credits")
    # dec_pending anchors f0.py; dec_wide anchors f0.py too; the superseded f1.py does not count
    assert credits.coverage == pytest.approx(1 / 3, abs=0.001)
    assert credits.decisions == 1 and credits.pending == 1


@pytest.mark.phase_5
def test_a_module_page_lists_its_decisions_shares_neighbours_orphans_and_conflicts(
    repo: Path,
) -> None:
    conflict = Conflict(
        decision_a="dec_shared",
        decision_b="dec_wide",
        severity=Severity.HIGH,
        explanation="they disagree",
        score=0.9,
    )
    data = load_map(repo, [conflict])
    page = module_page(data, "promo-codes")
    assert page is not None
    assert [d.id for d in page.decisions] == ["dec_shared"]  # dec_wide is cross-cutting
    assert [m.id for m in page.decisions[0].modules] == ["promo-codes", "promo-codes-ui"]
    assert [(n.id, n.shared) for n in page.neighbours] == [("promo-codes-ui", 1)]
    assert page.conflicts == []  # only one side is on this page
    assert page.files == sorted(f"backend/app/promo/f{i}.py" for i in range(3))
    credits = module_page(data, "credits")
    assert credits is not None
    old = next(d for d in credits.decisions if d.id == "dec_old")
    assert old.superseded and [o.locus for o in credits.orphaned] == ["backend/app/credits/gone.py"]
    assert module_page(data, "no-such-module") is None


@pytest.mark.phase_5
def test_without_a_module_map_the_overview_says_so(tmp_path: Path) -> None:
    view = overview(load_map(tmp_path))
    assert view.empty and view.features == [] and view.decisions == 0


@pytest.mark.phase_5
def test_a_decision_with_no_module_says_what_a_person_can_do_about_it(repo: Path) -> None:
    write_files(repo, {"spec/01-plan.md": "# plan\n", "backend/app/tests/test_x.py": ""})
    _decision(repo, "dec_spec", "spec/01-plan.md:1-1")

    unplaced = {d.id: d for d in overview(load_map(repo)).unplaced_decisions}

    # A live anchor in a folder nothing owns: the folder can be claimed, the decision not placed.
    assert (unplaced["dec_spec"].claimable, unplaced["dec_spec"].placeable) == (["spec/**"], False)
    # No anchor, or one at a file that is gone: nothing to claim, so a person places it.
    assert (unplaced["dec_loose"].claimable, unplaced["dec_loose"].placeable) == ([], True)
    assert (unplaced["dec_docs"].claimable, unplaced["dec_docs"].placeable) == ([], True)


@pytest.mark.phase_5
def test_a_label_on_a_support_folder_brings_its_files_into_the_map(repo: Path) -> None:
    write_files(repo, {"spec/01-plan.md": "# plan\n", "backend/app/promo/tests/test_x.py": ""})
    _decision(repo, "dec_spec", "spec/01-plan.md:1-1")
    assert "spec/01-plan.md" not in source_files(repo)  # a scan never models specs
    manifest = load_manifest(repo)
    specs = Module(id="specs", name="Specs", paths=[], status=ModuleStatus.CONFIRMED)
    labelled, matched = label_files(
        manifest.model_copy(update={"modules": [*manifest.modules, specs]}),
        ["spec/**"],
        "specs",
        labelable_files(repo, ["spec/**"]),
    )
    write_manifest(repo, labelled)

    view = overview(load_map(repo))

    assert matched == ["spec/01-plan.md"]
    assert "dec_spec" not in {d.id for d in view.unplaced_decisions}
    tile = next(t for t in view.features if t.id == "specs")
    assert (tile.files, tile.decisions, tile.coverage) == (1, 1, 1.0)
    # Only a label that names the support folder opts it in: promo's glob leaves its tests out.
    assert "backend/app/promo/tests/test_x.py" not in source_files(repo)
