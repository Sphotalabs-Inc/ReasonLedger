"""Phase 5 — suggesting a home for a decision with no working anchor."""

from __future__ import annotations

from pathlib import Path

import pytest
from modules_helpers import git, make_repo, tree, write_files
from reasonledger_core.modules import Manifest, Module
from reasonledger_core.modules.decision_suggest import suggest_homes
from reasonledger_core.modules.digest import source_files
from reasonledger_core.modules.suggest import build_cochange_index
from reasonledger_core.views.organize_files import load_records
from test_map_view import _decision

MANIFEST = Manifest(
    modules=[
        Module(id="pages", name="Pages", paths=["app/pages/**"]),
        Module(id="billing", name="Billing", paths=["app/billing/**"]),
    ]
)


def _repo(root: Path) -> Path:
    return make_repo(root, [("init", {**tree("app/pages", 4), **tree("app/billing", 4)})])


def _record_in_a_commit(root: Path, decision_id: str, *loci: str, changed: dict[str, str]) -> None:
    _decision(root, decision_id, *loci)
    write_files(root, changed)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", f"record {decision_id}")


def _suggest(root: Path, decision_id: str):  # type: ignore[no-untyped-def]
    record = next(r for r in load_records(root) if r.frontmatter.id == decision_id)
    return suggest_homes(record, MANIFEST, source_files(root), root, build_cochange_index(root))


@pytest.mark.phase_5
def test_two_kinds_of_evidence_agreeing_make_a_high_confidence_suggestion(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _record_in_a_commit(
        root,
        "dec_dead",
        "app/pages/gone.py:1-9",
        changed={
            "app/pages/f0.py": "# a\n",
            "app/pages/f1.py": "# b\n",
            "app/billing/f0.py": "# c\n",
        },
    )

    first, second = _suggest(root, "dec_dead")

    assert (first.module, first.confidence, first.kinds) == ("pages", "high", 2)
    assert "recorded in a commit that also changed 2 of 3 files in pages" in first.evidence[0]
    assert "its anchor in app/pages is gone" in first.evidence[1]
    assert (second.module, second.confidence) == ("billing", "low")


@pytest.mark.phase_5
def test_one_kind_over_half_is_medium_and_the_commit_that_added_the_file_is_the_one_read(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    _record_in_a_commit(root, "dec_loose", changed={"app/billing/f0.py": "# edit\n"})
    write_files(root, {"app/pages/f2.py": "# later\n", "app/pages/f3.py": "# later\n"})
    _decision(root, "dec_loose")  # touched again in a later commit that changed pages instead
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "approve dec_loose, tidy pages")

    (only,) = _suggest(root, "dec_loose")

    assert (only.module, only.confidence, only.kinds) == ("billing", "medium", 1)


@pytest.mark.phase_5
def test_nothing_points_anywhere_without_history_or_a_dead_anchor(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _decision(root, "dec_loose")  # written but never committed, and anchored to nothing

    assert _suggest(root, "dec_loose") == []
