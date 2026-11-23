"""S58 — `init` touches only what you use, and does not mistake its own files for decisions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from reasonledger_cli.agent_targets import AGENT_RULE, RULE_BEGIN, RULE_END, detect_agents
from reasonledger_cli.check_cmd import run_check
from reasonledger_cli.init_cmd import run_init, scan_candidates
from reasonledger_cli.main import EXIT_USAGE, main
from reasonledger_core.importer.scan import RULE_ONLY_MAX_BYTES, scan_docs


def _on_path(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    """Pin which agent CLIs this test sees on PATH, whatever the machine has."""
    monkeypatch.setattr(
        "reasonledger_cli.agent_targets.agent_cli_found", lambda name: name in names
    )


def _keys(root: Path) -> set[str]:
    return {target.key for target in detect_agents(root)}


def _exists(root: Path) -> Callable[[str], bool]:
    return lambda rel: (root / rel).exists()


@pytest.mark.phase_3
def test_detection_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _on_path(monkeypatch)
    assert _keys(tmp_path) == set()
    (tmp_path / ".cursorrules").write_text("x", encoding="utf-8")
    assert _keys(tmp_path) == {"cursor"}
    (tmp_path / "AGENTS.md").write_text("x", encoding="utf-8")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "copilot-instructions.md").write_text("x", encoding="utf-8")
    assert _keys(tmp_path) == {"cursor", "claude-code", "agents-md", "vscode"}


@pytest.mark.phase_3
def test_detection_by_executable_on_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _on_path(monkeypatch, "claude")
    assert _keys(tmp_path) == {"claude-code"}
    _on_path(monkeypatch, "cursor")
    assert _keys(tmp_path) == {"cursor"}


@pytest.mark.phase_3
def test_init_writes_only_detected_agents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The rehearsal's F3: a Cursor project used with Claude Code gets those two, not four."""
    _on_path(monkeypatch, "claude")
    (tmp_path / ".cursorrules").write_text("Use tabs.\n", encoding="utf-8")
    out = run_init(root=tmp_path, scan=False)
    exists = _exists(tmp_path)
    assert exists(".cursor/mcp.json") and exists(".cursor/rules/reasonledger.mdc")
    assert exists(".mcp.json") and exists("CLAUDE.md")
    assert not exists(".vscode") and not exists(".github") and not exists("AGENTS.md")
    # Every file written or changed is printed, so nobody needs `git status`.
    for written in (".mcp.json", "CLAUDE.md", ".cursor/mcp.json", ".gitignore"):
        assert written in out
    assert "Skipped" in out
    assert "reasonledger init --agents vscode" in out
    assert "reasonledger init --agents agents-md" in out
    again = run_init(root=tmp_path, scan=False)
    assert "No changes" in again


@pytest.mark.phase_3
def test_init_with_nothing_detected_sets_up_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _on_path(monkeypatch)
    out = run_init(root=tmp_path, scan=False)
    exists = _exists(tmp_path)
    for rel in (".mcp.json", ".cursor/mcp.json", ".vscode/mcp.json", "AGENTS.md", "CLAUDE.md"):
        assert exists(rel), rel
    assert "No coding agent detected" in out
    assert "No changes" in run_init(root=tmp_path, scan=False)


@pytest.mark.phase_3
def test_init_agents_all_forces_all_four(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _on_path(monkeypatch)
    (tmp_path / ".cursorrules").write_text("x", encoding="utf-8")
    run_init(root=tmp_path, scan=False, agents="all")
    assert (tmp_path / ".vscode" / "mcp.json").is_file() and (tmp_path / "CLAUDE.md").is_file()


@pytest.mark.phase_3
def test_init_does_not_write_policy_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _on_path(monkeypatch)
    run_init(root=tmp_path, scan=False)
    assert not (tmp_path / ".reasonledger" / "policy.yml").exists()
    run_init(root=tmp_path, scan=False, policy=True)
    assert (tmp_path / ".reasonledger" / "policy.yml").is_file()


@pytest.mark.phase_3
def test_init_policy_flag_never_overwrites(tmp_path: Path) -> None:
    policy = tmp_path / ".reasonledger" / "policy.yml"
    policy.parent.mkdir()
    policy.write_text('version: "1"\nmine: true\n', encoding="utf-8")
    run_init(root=tmp_path, scan=False, policy=True, agents="agents-md")
    assert policy.read_text("utf-8") == 'version: "1"\nmine: true\n'


@pytest.mark.phase_3
def test_check_policy_without_a_file_names_the_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    change = tmp_path / "change.json"
    change.write_text("{}", encoding="utf-8")
    code = main(["check", "--policy", str(tmp_path / "missing.yml"), "--change", str(change)])
    assert code == EXIT_USAGE
    assert "reasonledger init --policy" in capsys.readouterr().err
    assert run_check  # imported for the contract: the same function backs the CLI


@pytest.mark.phase_3
def test_rule_files_are_not_candidates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After `init` in a repo with no docs, the report must not count its own rule files."""
    _on_path(monkeypatch)
    out = run_init(root=tmp_path, scan=True)
    assert scan_candidates(root=tmp_path).doc_count == 0
    assert "No decision candidates found" in out
    assert scan_docs(tmp_path) == []


@pytest.mark.phase_3
def test_a_file_with_prose_and_the_rule_counts_once(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text(
        "# Notes\n\nWe store timestamps in UTC.\n\n" + RULE_BEGIN + "\nrule\n" + RULE_END + "\n",
        encoding="utf-8",
    )
    assert scan_candidates(root=tmp_path).doc_count == 1


@pytest.mark.phase_3
def test_import_skips_the_rule_block(tmp_path: Path) -> None:
    prose = "We store timestamps in UTC.\n"
    (tmp_path / "CLAUDE.md").write_text(
        f"{prose}\n{RULE_BEGIN}\nCall record_decision before editing.\n{RULE_END}\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text(
        f"{RULE_BEGIN}\nCall record_decision.\n{RULE_END}\n", encoding="utf-8"
    )
    sources = scan_docs(tmp_path)
    assert [s.path for s in sources] == ["CLAUDE.md"]
    assert "record_decision" not in sources[0].text and prose.strip() in sources[0].text


@pytest.mark.phase_3
def test_the_rule_block_fits_under_the_read_threshold() -> None:
    """Counting reads only small files; a rule that outgrew the limit would be counted."""
    assert len(RULE_BEGIN) + len(AGENT_RULE) + len(RULE_END) < RULE_ONLY_MAX_BYTES


@pytest.mark.phase_3
def test_embeddings_hint_is_one_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _on_path(monkeypatch)
    monkeypatch.setattr("reasonledger_cli.init_cmd.local_embedder_available", lambda: False)
    out = run_init(root=tmp_path, scan=False)
    hint = [line for line in out.splitlines() if line.startswith("Optional real embeddings")]
    assert len(hint) == 1 and "(" not in hint[0]


@pytest.mark.phase_3
def test_init_prints_why_each_agent_was_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A surprising choice must be explainable without reading code (S58.2)."""
    _on_path(monkeypatch, "claude")
    (tmp_path / ".cursorrules").write_text("x", encoding="utf-8")
    out = run_init(root=tmp_path, scan=False)
    assert "Claude Code (found `claude` on PATH)" in out
    assert "Cursor (found .cursorrules)" in out


@pytest.mark.phase_3
def test_the_default_path_does_not_depend_on_the_machine(tmp_path: Path) -> None:
    """The suite's conftest pins PATH: a real `claude` here must not change what init writes."""
    run_init(root=tmp_path, scan=False)
    assert (tmp_path / "CLAUDE.md").is_file() and (tmp_path / ".vscode" / "mcp.json").is_file()
