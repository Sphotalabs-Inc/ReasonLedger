"""S27 — `init` candidate scan report."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_cli.init_cmd import run_init
from reasonledger_cli.main import EXIT_PASS, main

REASONLEDGER_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.phase_3
def test_init_reports_candidate_count_offline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("a.md", "b.md", "c.md"):
        (tmp_path / name).write_text(f"# {name}\n", encoding="utf-8")

    code = main(
        [
            "init",
            "--root",
            str(tmp_path),
            "--reasonledger-root",
            str(REASONLEDGER_ROOT),
        ]
    )
    assert code == EXIT_PASS
    out = capsys.readouterr().out
    assert "3 decision candidates" in out
    assert "Traceback" not in out


@pytest.mark.phase_3
def test_init_no_scan_flag_skips_report(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("# doc\n", encoding="utf-8")
    out = run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=False)
    assert "decision candidates" not in out


@pytest.mark.phase_3
def test_init_zero_candidates_omits_import_commands(tmp_path: Path) -> None:
    out = run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=True)
    assert "No decision candidates found" in out
    assert "reasonledger import" not in out


@pytest.mark.phase_3
def test_init_still_idempotent_with_scan(tmp_path: Path) -> None:
    first = run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=True)
    second = run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=True)
    # Scaffolding actions differ on re-run; candidate report line must stay stable.
    assert "decision candidates" in first or "No decision candidates found" in first
    assert ("decision candidates" in first) == ("decision candidates" in second)
    assert not (tmp_path / ".reasonledger" / "policy.yml").exists()  # S58: only `init --policy`


_LOCAL_AVAILABLE = "reasonledger_cli.init_cmd.local_embedder_available"


@pytest.mark.phase_4
def test_init_starts_new_repo_on_local_embedder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reasonledger_core.reasoning.conflict_config import load_conflict_config

    monkeypatch.setattr(_LOCAL_AVAILABLE, lambda: True)
    out = run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=False)
    assert load_conflict_config(tmp_path).embedding_provider == "local"
    assert "conflict.yml (local embedding model)" in out
    assert "basic word matching" not in out


@pytest.mark.phase_4
def test_init_without_extra_writes_nothing_and_says_how(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reasonledger_core.reasoning.conflict_config import CONFLICT_CONFIG_PATH

    monkeypatch.setattr(_LOCAL_AVAILABLE, lambda: False)
    out = run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=False)
    assert not (tmp_path / CONFLICT_CONFIG_PATH).exists()
    assert "Optional real embeddings" in out


@pytest.mark.phase_4
def test_init_keeps_an_existing_conflict_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from reasonledger_core.reasoning.conflict_config import (
        ConflictConfig,
        load_conflict_config,
        write_conflict_config,
    )

    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="deterministic"))
    monkeypatch.setattr(_LOCAL_AVAILABLE, lambda: True)
    run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=False)
    assert load_conflict_config(tmp_path).embedding_provider == "deterministic"


@pytest.mark.phase_3
def test_init_writes_cursor_mcp_config_for_this_repo_and_ignores_it(tmp_path: Path) -> None:
    import json

    run_init(agents="all", root=tmp_path, scan=False)

    config = json.loads((tmp_path / ".cursor" / "mcp.json").read_text("utf-8"))
    entry = config["mcpServers"]["reasonledger"]
    assert entry["args"][-2:] == ["--repo-root", str(tmp_path.resolve())]
    assert ".cursor/mcp.json" in (tmp_path / ".gitignore").read_text("utf-8").splitlines()


@pytest.mark.phase_3
def test_init_never_overwrites_an_existing_cursor_mcp_config(tmp_path: Path) -> None:
    existing = tmp_path / ".cursor" / "mcp.json"
    existing.parent.mkdir()
    existing.write_text('{"mcpServers": {"mine": {}}}\n', encoding="utf-8")

    run_init(agents="all", root=tmp_path, scan=False)

    assert existing.read_text("utf-8") == '{"mcpServers": {"mine": {}}}\n'


@pytest.mark.phase_3
def test_init_writes_claude_code_mcp_config_and_ignores_it(tmp_path: Path) -> None:
    import json

    run_init(agents="all", root=tmp_path, scan=False)

    config = json.loads((tmp_path / ".mcp.json").read_text("utf-8"))
    assert config["mcpServers"]["reasonledger"]["args"][-2:] == [
        "--repo-root",
        str(tmp_path.resolve()),
    ]
    assert ".mcp.json" in (tmp_path / ".gitignore").read_text("utf-8").splitlines()


@pytest.mark.phase_3
def test_init_keeps_an_existing_claude_code_mcp_config(tmp_path: Path) -> None:
    existing = tmp_path / ".mcp.json"
    existing.write_text('{"mcpServers": {"mine": {}}}\n', encoding="utf-8")

    run_init(agents="all", root=tmp_path, scan=False)

    assert existing.read_text("utf-8") == '{"mcpServers": {"mine": {}}}\n'


@pytest.mark.phase_3
def test_init_ends_by_pointing_at_the_ui_and_says_when_each_tab_fills_in(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")

    out = run_init(agents="all", root=tmp_path, scan=True)

    assert "nothing was sent anywhere" in out
    tail = out[out.rindex("Next:") :]
    assert "reasonledger ui" in tail and "What shows up when" in tail
    assert "Restart" in out and "Paste into" not in out
    assert "# ReasonLedger" not in out  # the rule is written, not printed


# --- S46: every supported agent gets its MCP config and its rule, with nothing to paste ---

import json  # noqa: E402

from reasonledger_cli.agent_targets import (  # noqa: E402
    AGENT_RULE,
    RULE_BEGIN,
    RULE_END,
    TARGETS,
)

SHARED_RULE_FILES = [t for t in TARGETS if not t.owns_rule_file]


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".reasonledger/cache" not in str(p)
    }


@pytest.mark.phase_3
@pytest.mark.parametrize("target", TARGETS, ids=[t.key for t in TARGETS])
def test_init_writes_rule_and_config_per_agent(tmp_path: Path, target) -> None:  # type: ignore[no-untyped-def]
    run_init(agents="all", root=tmp_path, scan=False)
    rule = (tmp_path / target.rule_path).read_text("utf-8")
    assert "decisions_for" in rule and "approved_by" in rule  # told never to pass it
    assert "Never pass `oversight` or `approved_by`" in rule
    if target.mcp_path:
        config = json.loads((tmp_path / target.mcp_path).read_text("utf-8"))
        assert "reasonledger" in config[target.mcp_root_key]
        assert target.mcp_path in (tmp_path / ".gitignore").read_text("utf-8").splitlines()
    assert target.rule_path not in (tmp_path / ".gitignore").read_text("utf-8").splitlines()


@pytest.mark.phase_3
def test_init_vscode_config_uses_servers_key(tmp_path: Path) -> None:
    run_init(agents="all", root=tmp_path, scan=False)
    config = json.loads((tmp_path / ".vscode" / "mcp.json").read_text("utf-8"))
    assert "mcpServers" not in config
    assert config["servers"]["reasonledger"]["type"] == "stdio"


@pytest.mark.phase_3
def test_init_marked_block_appended_then_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    above, below = "# My project\n\nMy own rules.\n", "\n## Footer\nkeep me\n"
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(above, encoding="utf-8")
    run_init(agents="all", root=tmp_path, scan=False)
    first = claude.read_text("utf-8")
    assert first.startswith(above) and RULE_BEGIN in first and first.rstrip().endswith(RULE_END)

    claude.write_text(first + below, encoding="utf-8")
    monkeypatch.setattr("reasonledger_cli.agent_targets.AGENT_RULE", AGENT_RULE + "6. New step.\n")
    run_init(agents="all", root=tmp_path, scan=False)
    second = claude.read_text("utf-8")
    assert second.startswith(above) and second.endswith(below)
    assert "6. New step." in second and second.count(RULE_BEGIN) == 1


@pytest.mark.phase_3
def test_init_second_run_is_byte_identical(tmp_path: Path) -> None:
    run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=False)
    before = _tree(tmp_path)
    out = run_init(agents="all", root=tmp_path, reasonledger_root=REASONLEDGER_ROOT, scan=False)
    assert _tree(tmp_path) == before
    assert "No changes" in out and "  + " not in out


@pytest.mark.phase_3
def test_init_agents_flag_limits_targets(tmp_path: Path) -> None:
    assert main(["init", "--root", str(tmp_path), "--no-scan", "--agents", "cursor"]) == EXIT_PASS
    assert (tmp_path / ".cursor" / "mcp.json").is_file()
    assert (tmp_path / ".cursor" / "rules" / "reasonledger.mdc").is_file()
    for absent in (".mcp.json", "CLAUDE.md", ".vscode", "AGENTS.md", ".github"):
        assert not (tmp_path / absent).exists()
    assert main(["init", "--root", str(tmp_path), "--agents", "emacs"]) == 2


@pytest.mark.phase_3
def test_init_no_rules(tmp_path: Path) -> None:
    run_init(agents="all", root=tmp_path, scan=False, rules=False)
    assert (tmp_path / ".mcp.json").is_file()
    assert not (tmp_path / "CLAUDE.md").exists() and not (tmp_path / ".cursor/rules").exists()


@pytest.mark.phase_3
def test_init_existing_mcp_config_untouched(tmp_path: Path) -> None:
    existing = tmp_path / ".vscode" / "mcp.json"
    existing.parent.mkdir()
    existing.write_text('{"servers": {"mine": {}}}\n', encoding="utf-8")
    out = run_init(agents="all", root=tmp_path, scan=False)
    assert existing.read_text("utf-8") == '{"servers": {"mine": {}}}\n'
    assert ".vscode/mcp.json exists; add this entry yourself" in out


@pytest.mark.phase_3
def test_init_falls_back_to_uvx_when_the_server_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    run_init(agents="all", root=tmp_path, scan=False)
    entry = json.loads((tmp_path / ".mcp.json").read_text("utf-8"))["mcpServers"]["reasonledger"]
    assert entry["command"] == "uvx" and entry["args"][:2] == ["reasonledger", "mcp"]
