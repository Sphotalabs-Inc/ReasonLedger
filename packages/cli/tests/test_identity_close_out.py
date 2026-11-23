"""S45 — a verdict is only a person's: shared identity default, the CI identity check, dates."""

from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_FAIL, EXIT_PASS, EXIT_USAGE, main
from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    parse_decision_markdown,
    read_decision_file,
    render_decision_markdown,
)
from reasonledger_core.harvest.deterministic import harvest_decision_from_pr
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_mcp.tools import call_record_decision
from test_import_cli import _import_fixture

LEGACY = Path(__file__).resolve().parents[3] / "fixtures" / "golden" / "decisions"


def _git(root: Path, author: str, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": author,
        "GIT_COMMITTER_NAME": author,
        "GIT_AUTHOR_EMAIL": "a@example.test",
        "GIT_COMMITTER_EMAIL": "a@example.test",
    }
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=env)


def _record(root: Path) -> str:
    result = call_record_decision(
        root,
        context="Which store?",
        choice="Use sqlite",
        alternatives_rejected=["Postgres"],
        ai_tool="claude",
        model="claude-sonnet-5-5",
        proposed_by="ai",
    )
    return str(result["decision_id"])


def _repo_with_pending(root: Path) -> str:
    _git(root, "Ada", "init", "-q", "-b", "main")
    decision_id = _record(root)
    _git(root, "Ada", "add", "-A")
    _git(root, "Ada", "commit", "-q", "-m", "record")
    return decision_id


def _approve_and_commit(root: Path, decision_id: str, *, recorded_as: str, author: str) -> None:
    assert main(["approve", decision_id, "--by", recorded_as, "--root", str(root)]) == EXIT_PASS
    _git(root, author, "commit", "-aq", "-m", "approve")


@pytest.mark.phase_3
def test_confirm_defaults_to_git_identity(tmp_path: Path, git_identity: str) -> None:
    _import_fixture(tmp_path)
    assert main(["confirm", "--all", "--root", str(tmp_path)]) == EXIT_PASS
    for path in (tmp_path / DECISIONS_DIR).glob("dec_*.md"):
        fm = read_decision_file(path).frontmatter
        assert fm.confirmed_by == git_identity and fm.approved_by == git_identity
        assert fm.approved_at is not None


@pytest.mark.phase_3
def test_no_identity_is_refused(
    tmp_path: Path, no_git_identity: None, capsys: pytest.CaptureFixture[str]
) -> None:
    _import_fixture(tmp_path)
    capsys.readouterr()
    assert main(["confirm", "--all", "--root", str(tmp_path)]) == EXIT_USAGE
    assert "--confirmed-by" in capsys.readouterr().err
    assert len(list((tmp_path / PROPOSED_DIR).glob("dec_*.md"))) == 2  # nothing promoted


@pytest.mark.phase_4
def test_check_identity_mismatch_warns(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    decision_id = _repo_with_pending(tmp_path)
    _approve_and_commit(tmp_path, decision_id, recorded_as="Grace", author="Ada")
    code = main(["check", "--decisions", "--base", "HEAD~1", "--root", str(tmp_path)])
    assert code == EXIT_PASS
    err = capsys.readouterr().err
    assert "identity" in err and "'Grace'" in err and "'Ada'" in err


@pytest.mark.phase_4
def test_check_identity_mismatch_fails_when_strict(tmp_path: Path) -> None:
    decision_id = _repo_with_pending(tmp_path)
    _approve_and_commit(tmp_path, decision_id, recorded_as="Grace", author="Ada")
    args = ["check", "--decisions", "--base", "HEAD~1", "--root", str(tmp_path)]
    assert main([*args, "--strict-identity"]) == EXIT_FAIL


@pytest.mark.phase_4
def test_check_identity_match_is_silent(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    decision_id = _repo_with_pending(tmp_path)
    _approve_and_commit(tmp_path, decision_id, recorded_as="ada", author="Ada")
    args = ["check", "--decisions", "--base", "HEAD~1", "--root", str(tmp_path)]
    assert main([*args, "--strict-identity"]) == EXIT_PASS
    assert "identity" not in capsys.readouterr().err


@pytest.mark.phase_3
def test_recorded_at_set_for_every_source(tmp_path: Path, git_identity: str) -> None:
    assert read_decision_file(
        tmp_path / DECISIONS_DIR / f"{_record(tmp_path)}.md"
    ).frontmatter.recorded_at
    assert harvest_decision_from_pr(pr_title="t", pr_body="b").frontmatter.recorded_at
    stamp = datetime(2026, 1, 2, tzinfo=UTC)
    assert (
        harvest_decision_from_pr(
            pr_title="t", pr_body="b", recorded_at=stamp
        ).frontmatter.recorded_at
        == stamp
    )
    _import_fixture(tmp_path)
    staged = list((tmp_path / PROPOSED_DIR).glob("dec_*.md"))
    assert staged and all(read_decision_file(p).frontmatter.recorded_at for p in staged)


@pytest.mark.phase_3
def test_legacy_record_round_trips() -> None:
    raw = (LEGACY / "legacy_0_2_0.md").read_text("utf-8")
    record = parse_decision_markdown(raw)
    assert record.frontmatter.recorded_at is None
    assert render_decision_markdown(record) == raw


@pytest.mark.phase_4
def test_why_shows_retired_with_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], git_identity: str
) -> None:
    result = call_record_decision(
        tmp_path,
        context="Which store?",
        choice="Use sqlite",
        alternatives_rejected=["Postgres"],
        ai_tool="claude",
        model="claude-sonnet-5-5",
        justifies=["app/store.py"],
    )
    decision_id = str(result["decision_id"])
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "store.py").write_text("x = 1\n", encoding="utf-8")
    assert main(["retire", decision_id, "--reason", "Store removed", "--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["why", "app/store.py", "--root", str(tmp_path)]) == EXIT_PASS
    assert "retired" in capsys.readouterr().out and "Store removed" in _why_json(tmp_path)


def _why_json(root: Path) -> str:
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(["why", "app/store.py", "--json", "--root", str(root)])
    return buffer.getvalue()
