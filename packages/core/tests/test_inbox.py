"""Phase 5 — suggesting a home for new files, rule promotion and the inbox."""

from __future__ import annotations

from pathlib import Path

import pytest
from modules_helpers import make_repo
from reasonledger_core.modules import Manifest, Module, ModuleStatus
from reasonledger_core.modules.config import (
    ALTERNATIVE_SCORE_SHARE,
    INBOX_MAX_ITEMS,
    MEDIUM_SCORE,
    PENDING_QUEUE_CAP,
    RULE_PROMOTION_MIN_LABELS,
)
from reasonledger_core.modules.labels import LabelError
from reasonledger_core.modules.manifest import load_manifest, membership, write_manifest
from reasonledger_core.modules.models import Confidence, Tier
from reasonledger_core.modules.organize import (
    bulk_move,
    decline_placement,
    promote_rule,
    promotion_candidates,
)
from reasonledger_core.modules.suggest import (
    CoChangeIndex,
    build_cochange_index,
    suggest_placements,
)
from reasonledger_core.views.inbox import INBOX_FILES_SHOWN, collect_items, inbox_view


def _mod(module_id: str, *paths: str, status: ModuleStatus = ModuleStatus.CONFIRMED) -> Module:
    return Module(id=module_id, name=module_id.title(), paths=list(paths), status=status)


def _pages(count: int = 4) -> Module:
    return _mod("pages", *(f"app/pages/p{i}.py" for i in range(count)))


def _files(*extra: str, pages: int = 4) -> list[str]:
    return [*(f"app/pages/p{i}.py" for i in range(pages)), *extra]


@pytest.mark.phase_5
def test_files_beside_a_new_one_are_evidence_for_their_module() -> None:
    manifest = Manifest(
        modules=[_pages(), _mod("billing", "app/billing/b0.py", "app/billing/b1.py")]
    )
    files = [*_files("app/pages/zeta.py"), "app/billing/b0.py", "app/billing/b1.py"]
    groups, left = suggest_placements(manifest, files)
    assert left == [] and len(groups) == 1
    group = groups[0]
    assert (group.module, group.files) == ("pages", ["app/pages/zeta.py"])
    assert [e.kind for e in group.evidence] == ["siblings"]
    assert group.evidence[0].text == "4 of 4 files beside it are in Pages"
    assert group.confidence is Confidence.MEDIUM  # one kind of evidence, but a lopsided one
    assert MEDIUM_SCORE <= 3.0  # the weight of one full sibling majority clears the bar


@pytest.mark.phase_5
def test_a_folder_with_no_clear_majority_or_too_few_neighbours_gives_no_evidence() -> None:
    split = Manifest(modules=[_mod("a", "d/a0.py", "d/a1.py"), _mod("b", "d/b0.py", "d/b1.py")])
    assert (
        suggest_placements(split, ["d/a0.py", "d/a1.py", "d/b0.py", "d/b1.py", "d/new.py"])[0] == []
    )
    lone = Manifest(modules=[_mod("a", "d/a0.py")])
    assert suggest_placements(lone, ["d/a0.py", "d/new.py"])[1] == ["d/new.py"]  # one neighbour


@pytest.mark.phase_5
def test_a_name_shared_with_a_modules_files_is_evidence_and_generic_words_are_not() -> None:
    manifest = Manifest(
        modules=[
            _mod(
                "billing", "app/x/invoice.py", "app/y/invoice_service.py", "app/z/invoice_model.py"
            )
        ]
    )
    files = [
        "app/x/invoice.py",
        "app/y/invoice_service.py",
        "app/z/invoice_model.py",
        "other/invoice_view.py",
    ]
    groups, _ = suggest_placements(manifest, files)
    assert [(g.module, g.evidence[0].kind) for g in groups] == [("billing", "name")]
    assert groups[0].evidence[0].text == "its name shares 'invoice' with 3 files in Billing"
    generic = Manifest(modules=[_mod("a", "x/index.py", "y/index.js", "z/index.css")])
    assert (
        suggest_placements(generic, ["x/index.py", "y/index.js", "z/index.css", "q/index.html"])[0]
        == []
    )


@pytest.mark.phase_5
def test_changing_together_in_git_history_is_evidence_and_bulk_commits_are_ignored(
    tmp_path: Path,
) -> None:
    billing = {f"app/billing/b{i}.py": "x\n" for i in range(3)}
    commits = [
        ("init", billing),
        *(
            (f"feat {i}", {"app/new.py": f"{i}\n", f"app/billing/b{i}.py": f"{i}\n"})
            for i in range(3)
        ),
    ]
    commits.append(
        (
            "format everything",
            {f"bulk/f{i}.py": "x\n" for i in range(60)} | {"app/new.py": "bulk\n"},
        )
    )
    root = make_repo(tmp_path / "repo", commits)
    index = build_cochange_index(root)
    assert len(index.of("app/new.py")) == 3  # the 60-file commit says nothing about coupling
    manifest = Manifest(modules=[_mod("billing", *billing)])
    groups, _ = suggest_placements(manifest, [*billing, "app/new.py"], index)
    assert [(g.module, g.evidence[0].kind) for g in groups] == [("billing", "cochange")]
    assert groups[0].evidence[0].text == "changed with files of Billing in 3 of 3 commits"
    assert (
        suggest_placements(manifest, [*billing, "app/new.py"], CoChangeIndex())[0] == []
    )  # no history


@pytest.mark.phase_5
def test_two_kinds_of_evidence_agreeing_make_a_suggestion_high() -> None:
    manifest = Manifest(
        modules=[
            _mod(
                "billing",
                "app/billing/b0.py",
                "app/billing/b1.py",
                "x/invoice.py",
                "y/invoice_a.py",
            )
        ]
    )
    files = ["app/billing/b0.py", "app/billing/b1.py", "x/invoice.py", "y/invoice_a.py"]
    new = "app/billing/invoice_export.py"
    groups, _ = suggest_placements(manifest, [*files, new])
    group = groups[0]
    assert group.module == "billing" and group.confidence is Confidence.HIGH
    assert {e.kind for e in group.evidence} == {"siblings", "name"}
    assert group.alternative is None


@pytest.mark.phase_5
def test_a_close_runner_up_is_named_and_a_distant_one_is_not() -> None:
    assert ALTERNATIVE_SCORE_SHARE == 0.5
    manifest = Manifest(
        modules=[
            _mod("billing", "app/billing/b0.py", "app/billing/b1.py"),
            _mod("exports", "app/exp/e0.py"),
        ]
    )
    files = ["app/billing/b0.py", "app/billing/b1.py", "app/exp/e0.py"]
    new = "app/billing/n.py"
    together = [[new, "app/exp/e0.py"]] * 3
    groups, _ = suggest_placements(manifest, [*files, new], CoChangeIndex(commits={new: together}))
    # siblings 3.0 for billing, co-change 2.0 for exports: 2.0 is at least half of 3.0
    assert (groups[0].module, groups[0].alternative) == ("billing", "exports")
    stronger = Manifest(
        modules=[
            _mod(
                "billing",
                "app/billing/b0.py",
                "app/billing/b1.py",
                "x/invoice.py",
                "y/invoice_a.py",
            ),
            _mod("exports", "app/exp/e0.py"),
        ]
    )
    files = [*files, "x/invoice.py", "y/invoice_a.py"]
    far = "app/billing/invoice_n.py"
    groups, _ = suggest_placements(
        stronger, [*files, far], CoChangeIndex(commits={far: [[far, "app/exp/e0.py"]] * 3})
    )
    assert groups[0].alternative is None  # 2.0 is under half of 5.0


@pytest.mark.phase_5
def test_new_files_group_by_folder_and_a_declined_module_is_not_suggested_again() -> None:
    manifest = Manifest(modules=[_pages(), _mod("billing", "b/b0.py", "b/b1.py")])
    files = _files("app/pages/n1.py", "app/pages/n2.py", "b/n3.py", "b/b0.py", "b/b1.py")
    groups, _ = suggest_placements(manifest, files)
    assert {(g.module, tuple(g.files)) for g in groups} == {
        ("pages", ("app/pages/n1.py", "app/pages/n2.py")),
        ("billing", ("b/n3.py",)),
    }
    declined = decline_placement(manifest, ["app/pages/n1.py"], "pages")
    assert declined.declined == {"app/pages/n1.py": ["pages"]}
    groups, left = suggest_placements(declined, files)
    assert left == ["app/pages/n1.py"] and {tuple(g.files) for g in groups} == {
        ("app/pages/n2.py",),
        ("b/n3.py",),
    }
    with pytest.raises(LabelError, match="no module or bucket named 'ghost'"):
        decline_placement(manifest, ["a.py"], "ghost")


def _labelled(count: int = 3, **extra: str) -> Manifest:
    paths = [f"app/pages/p{i}.py" for i in range(count)]
    return Manifest(
        modules=[_mod("pages"), _mod("billing", "app/billing/**")],
        labels={**dict.fromkeys(paths, "pages"), **extra},
    )


@pytest.mark.phase_5
def test_hand_placed_files_in_one_folder_offer_a_rule_when_nothing_else_there_has_a_home() -> None:
    files = [f"app/pages/p{i}.py" for i in range(3)] + ["app/pages/new.py", "app/billing/b0.py"]
    found = promotion_candidates(_labelled(), files)
    assert RULE_PROMOTION_MIN_LABELS == 3
    assert [(c.pattern, c.target, c.extra_files) for c in found] == [("app/pages/**", "pages", 1)]
    assert promotion_candidates(_labelled(2), files) == []  # two is not a pattern yet
    blocked = [*files, "app/pages/mine.py"]
    manifest = _labelled().model_copy(
        update={"labels": {**_labelled().labels, "app/pages/mine.py": "billing"}}
    )
    assert promotion_candidates(manifest, blocked) == []  # a rule would take billing's file
    already = _labelled().model_copy(
        update={"labels": {**_labelled().labels, "app/pages/**": "pages"}}
    )
    assert promotion_candidates(already, files) == []


@pytest.mark.phase_5
def test_promoting_replaces_one_by_one_labels_with_the_rule_and_later_files_follow() -> None:
    files = [f"app/pages/p{i}.py" for i in range(3)] + ["app/pages/new.py"]
    manifest = _labelled()
    manifest = manifest.model_copy(
        update={"labels": {**manifest.labels, "app/billing/b0.py": "billing"}}
    )
    promoted, covered = promote_rule(
        manifest, [*files, "app/billing/b0.py"], "app/pages/**", "pages"
    )
    assert covered == 4
    assert promoted.labels == {
        "app/billing/b0.py": "billing",
        "app/pages/**": "pages",
    }  # the others left alone
    owner = membership(promoted)
    assert (
        owner.module_of("app/pages/new.py") == "pages"
        and owner.module_of("app/pages/p0.py") == "pages"
    )


@pytest.mark.phase_5
def test_a_bulk_move_is_one_edit_and_skips_files_already_there() -> None:
    manifest = Manifest(modules=[_mod("pages", "app/pages/**"), _mod("billing", "app/billing/**")])
    files = ["app/pages/a.py", "app/billing/b.py", "other/x.py", "other/y.py"]
    moved, count = bulk_move(
        manifest,
        files,
        [(["other/x.py"], "pages"), (["other/y.py"], "billing"), (["app/pages/a.py"], "pages")],
    )
    assert count == 2 and moved.labels == {"other/x.py": "pages", "other/y.py": "billing"}
    with pytest.raises(ValueError, match="already there"):
        bulk_move(manifest, files, [(["app/pages/a.py"], "pages")])
    with pytest.raises(LabelError, match="no module or bucket named 'ghost'"):
        bulk_move(manifest, files, [(["other/x.py"], "ghost")])


@pytest.mark.phase_5
def test_declined_placements_are_written_sorted_and_survive_a_reload(tmp_path: Path) -> None:
    manifest = Manifest(modules=[_mod("pages"), _mod("billing")])
    manifest = decline_placement(
        decline_placement(manifest, ["z.py", "a.py"], "pages"), ["a.py"], "billing"
    )
    write_manifest(tmp_path, manifest)
    text = (tmp_path / ".reasonledger" / "modules.yml").read_text("utf-8")
    assert text.index("a.py:") < text.index("z.py:")
    assert load_manifest(tmp_path).declined == {"a.py": ["billing", "pages"], "z.py": ["pages"]}
    write_manifest(tmp_path, manifest.model_copy(update={"declined": {}}))
    assert "declined" not in (tmp_path / ".reasonledger" / "modules.yml").read_text(
        encoding="utf-8"
    )


@pytest.mark.phase_5
def test_the_inbox_orders_by_confidence_then_kind_and_includes_every_kind() -> None:
    manifest = Manifest(
        modules=[
            _pages(),
            _mod("proposed-one", "q/**", status=ModuleStatus.PROPOSED).model_copy(
                update={"confidence": Confidence.HIGH}
            ),
        ],
        labels={f"app/pages/l{i}.py": "pages" for i in range(3)},
    )
    manifest = manifest.model_copy(update={"modules": [*manifest.modules[:1], manifest.modules[1]]})
    files = [
        *_files("app/pages/zeta.py", "app/pages/l0.py", "app/pages/l1.py", "app/pages/l2.py"),
        "q/a.py",
        "svc/export_a.py",
        "svc/export_b.py",
        "svc/export_c.py",
    ]
    items, left = collect_items(manifest, files)
    kinds = [i.kind for i in items]
    assert set(kinds) == {"place", "rule", "new-module", "proposal"} and left == 0
    assert items[0].kind == "rule"  # what the person just did comes first
    rest = [i.confidence for i in items[1:]]
    assert rest == sorted(rest, key=("high", "medium", "low").index)

    new = next(i for i in items if i.kind == "new-module")
    assert new.name == "Export" and new.file_count == 3 and new.target is None
    proposal = next(i for i in items if i.kind == "proposal")
    assert (proposal.target, proposal.confidence, proposal.files) == ("proposed-one", "high", [])


@pytest.mark.phase_5
def test_inbox_keys_are_stable_skips_hide_items_and_long_lists_are_cut() -> None:
    manifest = Manifest(modules=[_pages(), _mod("billing", "b/b0.py", "b/b1.py")])
    many = [f"app/pages/new{i:02d}.py" for i in range(INBOX_FILES_SHOWN + 5)]
    files = [*_files(*many), "b/b0.py", "b/b1.py", "b/n.py"]
    first = inbox_view(manifest, files)
    again = inbox_view(manifest, files)
    assert [i.key for i in first.items] == [i.key for i in again.items]  # same input, same keys
    big = next(i for i in first.items if i.target == "pages")
    assert big.file_count == INBOX_FILES_SHOWN + 5 and len(big.files) == INBOX_FILES_SHOWN
    other = inbox_view(manifest, [*files, "app/pages/one_more.py"])
    assert (
        next(i for i in other.items if i.target == "pages").key != big.key
    )  # a changed group is a new item
    hidden = inbox_view(manifest, files, skipped=[big.key])
    assert big.key not in {i.key for i in hidden.items} and hidden.total == first.total - 1
    assert (PENDING_QUEUE_CAP, INBOX_MAX_ITEMS) == (5, 50)
    assert first.history is False


@pytest.mark.phase_5
def test_a_file_is_never_suggested_across_the_frontend_and_backend() -> None:
    backend = _mod(
        "labels",
        "backend/app/label.py",
        "backend/app/label_service.py",
        "backend/app/label_routes.py",
    )
    backend = backend.model_copy(update={"tier": Tier.BACKEND})
    frontend = _mod("labels-ui", "frontend/src/label_a.js", "frontend/src/label_b.js").model_copy(
        update={"tier": Tier.FRONTEND}
    )
    files = [
        *backend.paths,
        *frontend.paths,
        "frontend/src/ui/label_new.js",
        "backend/app/label_extra.py",
    ]
    manifest = Manifest(modules=[backend, frontend])
    groups, left = suggest_placements(manifest, files)
    by_file = {f: g.module for g in groups for f in g.files}
    # the name word 'label' is shared with both modules, but each file keeps to its own side
    assert by_file == {
        "frontend/src/ui/label_new.js": "labels-ui",
        "backend/app/label_extra.py": "labels",
    }
    assert left == []
    only_backend = Manifest(modules=[backend])
    assert (
        suggest_placements(
            only_backend, [*backend.paths, "frontend/src/ui/label_new.js", "frontend/src/x.js"]
        )[0]
        == []
    )


@pytest.mark.phase_5
def test_the_inbox_shows_only_the_next_few_proposals_and_counts_the_rest() -> None:
    modules = [
        _mod(f"m{i}", f"d{i}/a.py", f"d{i}/b.py", status=ModuleStatus.PROPOSED) for i in range(8)
    ]
    files = [p for m in modules for p in m.paths]
    view = inbox_view(Manifest(modules=modules), files)
    assert view.counts == {"proposal": PENDING_QUEUE_CAP} and view.total == PENDING_QUEUE_CAP
    assert view.proposals_waiting == 3
