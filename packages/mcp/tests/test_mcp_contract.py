"""Phase 3 MCP contract — tool I/O and vendor-neutral clients over stdio + HTTP."""

from __future__ import annotations

import json
from importlib.metadata import version as package_version
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from reasonledger_core.decisions import (
    parse_decision_markdown,
    read_decision_file,
    write_decision_file,
)
from reasonledger_core.models.decision import DecisionStatus
from reasonledger_mcp.server import DIST_NAME, SERVER_NAME, create_mcp_server, main
from reasonledger_mcp.tools import call_query_decisions, call_record_decision

CLIENTS = ("claude-code", "cursor", "copilot")


@pytest.mark.phase_3
@pytest.mark.parametrize("client_name", CLIENTS)
def test_record_decision_round_trip_per_vendor_client(tmp_path: Path, client_name: str) -> None:
    result = call_record_decision(
        tmp_path,
        context=f"Decision from {client_name}",
        choice="Use feature flag",
        alternatives_rejected=["Hard-code"],
        assumptions=["Flag service available"],
        confidence="high",
        ai_tool=client_name if client_name != "claude-code" else "claude-code",
        model="test-model",
        oversight="reviewed",
        approved_by="alice@acme.com",
        justifies=["flags/toggle.py:1-10"],
        decision_id=f"dec_{client_name[:6]}",
    )
    assert result["ok"] is True
    record = parse_decision_markdown(result["markdown"])
    path = tmp_path / result["path"]
    assert path.is_file()
    assert parse_decision_markdown(path.read_text("utf-8")) == record


@pytest.mark.phase_3
@pytest.mark.parametrize(
    ("sent", "stored"),
    [("claude", "claude-code"), ("Grok", "grok"), ("Open Hands", "open-hands"), ("codex", "codex")],
)
def test_record_decision_keeps_free_form_ai_tool(tmp_path: Path, sent: str, stored: str) -> None:
    result = call_record_decision(
        tmp_path, context="c", choice="x", ai_tool=sent, model="grok-4", decision_id="dec_free01"
    )
    record = parse_decision_markdown(result["markdown"])
    assert record.frontmatter.ai_tool == stored
    assert record.frontmatter.model == "grok-4"


@pytest.mark.phase_3
@pytest.mark.parametrize("model", [None, "", "   "])
def test_record_decision_requires_model_unless_human(tmp_path: Path, model: str | None) -> None:
    with pytest.raises(ValueError, match="model is required"):
        call_record_decision(tmp_path, context="c", choice="x", ai_tool="cursor", model=model)
    result = call_record_decision(tmp_path, context="c", choice="x", ai_tool="none", model=model)
    assert result["ok"] is True


@pytest.mark.phase_3
def test_record_decision_warns_on_bare_file_paths_but_saves(tmp_path: Path) -> None:
    result = call_record_decision(
        tmp_path,
        context="c",
        choice="x",
        ai_tool="none",
        proposed_by="human",
        justifies=["app/radio.py", "app/radio.py:10-20", "app/radio.py::read_radio"],
    )
    assert result["ok"] is True
    assert len(result["warnings"]) == 1
    assert "app/radio.py::symbol_name" in result["warnings"][0]
    assert (
        call_record_decision(
            tmp_path, context="c2", choice="x2", ai_tool="none", proposed_by="human"
        )["warnings"]
        == []
    )


@pytest.mark.phase_3
@pytest.mark.parametrize("proposer", ["human", "ai"])
def test_record_decision_stores_who_proposed_it_and_query_returns_it(
    tmp_path: Path, proposer: str
) -> None:
    result = call_record_decision(
        tmp_path,
        context="c",
        choice="x",
        ai_tool="none",
        proposed_by=proposer,
        decision_id="dec_prop01",
    )
    assert parse_decision_markdown(result["markdown"]).frontmatter.proposed_by == proposer
    assert result["warnings"] == []
    hits = call_query_decisions(tmp_path, query="x")["decisions"]
    assert [h["proposed_by"] for h in hits] == [proposer]


@pytest.mark.phase_3
def test_record_decision_warns_when_proposed_by_is_missing_but_saves(tmp_path: Path) -> None:
    result = call_record_decision(tmp_path, context="c", choice="x", ai_tool="none")
    assert result["ok"] is True
    assert parse_decision_markdown(result["markdown"]).frontmatter.proposed_by is None
    assert any("proposed_by" in w for w in result["warnings"])
    hits = call_query_decisions(tmp_path, query="x")["decisions"]
    assert [h["proposed_by"] for h in hits] == [None]


@pytest.mark.phase_3
def test_server_rejects_an_unknown_proposed_by(tmp_path: Path) -> None:
    tool = create_mcp_server(repo_root=tmp_path)._tool_manager.get_tool("record_decision")
    assert tool is not None
    with pytest.raises(ValueError, match="invalid proposed_by"):
        tool.fn(context="c", choice="x", ai_tool="none", proposed_by="robot")


@pytest.mark.phase_3
def test_server_tool_shares_the_record_path_with_in_process_calls(tmp_path: Path) -> None:
    (tmp_path / "mod.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    server = create_mcp_server(repo_root=tmp_path)
    tool = server._tool_manager.get_tool("record_decision")
    assert tool is not None
    payload = json.loads(
        tool.fn(context="c", choice="x", ai_tool="claude", model="m", justifies=["mod.py:1"])
    )
    record = parse_decision_markdown(payload["markdown"])
    assert record.frontmatter.ai_tool == "claude-code"
    assert record.frontmatter.oversight.value == "pending"
    assert record.frontmatter.justifies == ["mod.py::alpha"]


@pytest.mark.phase_3
def test_query_decisions_returns_fixtures(tmp_path: Path) -> None:
    call_record_decision(
        tmp_path,
        context="Backoff",
        choice="Jittered exponential",
        ai_tool="cursor",
        model="test-model",
        justifies=["payments/retry.py:40-72"],
        decision_id="dec_qtest1",
        approved_by="alice@acme.com",
    )
    found = call_query_decisions(tmp_path, query="exponential", paths=["payments/**"])
    assert found["ok"] is True
    assert found["count"] == 1
    assert found["decisions"][0]["id"] == "dec_qtest1"
    assert found["decisions"][0]["superseded_by"] is None


@pytest.mark.phase_3
def test_query_decisions_flags_superseded_record(tmp_path: Path) -> None:
    old = call_record_decision(
        tmp_path,
        context="Retry policy",
        choice="Exponential backoff",
        ai_tool="cursor",
        model="test-model",
        justifies=["payments/retry.py:40-72"],
        decision_id="dec_old002",
        approved_by="alice@acme.com",
    )
    new = call_record_decision(
        tmp_path,
        context="Retry policy",
        choice="Fixed delay",
        ai_tool="cursor",
        model="test-model",
        justifies=["payments/retry.py:40-72"],
        decision_id="dec_new002",
        approved_by="alice@acme.com",
    )
    old_path, new_path = tmp_path / old["path"], tmp_path / new["path"]
    old_record = read_decision_file(old_path)
    old_record.frontmatter.status = DecisionStatus.SUPERSEDED
    write_decision_file(old_path, old_record)
    new_record = read_decision_file(new_path)
    new_record.frontmatter.supersedes = "dec_old002"
    write_decision_file(new_path, new_record)

    found = call_query_decisions(tmp_path, query="retry", paths=["payments/**"])
    by_id = {d["id"]: d for d in found["decisions"]}
    assert by_id["dec_old002"]["status"] == "superseded"
    assert by_id["dec_old002"]["superseded_by"] == "dec_new002"
    assert by_id["dec_new002"]["superseded_by"] is None


@pytest.mark.phase_4
def test_record_decision_anchors_python_line_to_symbol(tmp_path: Path) -> None:
    source = tmp_path / "payments" / "retry.py"
    source.parent.mkdir()
    source.write_text("def retry() -> None:\n    pass\n", encoding="utf-8")

    result = call_record_decision(
        tmp_path,
        context="Backoff",
        choice="Jittered exponential",
        ai_tool="cursor",
        model="test-model",
        justifies=["payments/retry.py:2"],
        decision_id="dec_anchor1",
        approved_by="alice@acme.com",
    )

    record = parse_decision_markdown(result["markdown"])
    assert record.frontmatter.justifies == ["payments/retry.py::retry"]


@pytest.mark.phase_4
def test_query_decisions_semantic_mode_ranks_relevant(tmp_path: Path) -> None:
    call_record_decision(
        tmp_path,
        context="Caching layer for the product catalog service",
        choice="Redis shared cache store",
        ai_tool="cursor",
        model="test-model",
        justifies=["catalog/cache.py:5-30"],
        decision_id="dec_cache01",
        approved_by="alice@acme.com",
    )
    call_record_decision(
        tmp_path,
        context="Public API interface style for external clients",
        choice="REST JSON endpoints",
        ai_tool="cursor",
        model="test-model",
        justifies=["api/routes.py:1-50"],
        decision_id="dec_api01",
        approved_by="alice@acme.com",
    )
    found = call_query_decisions(
        tmp_path,
        query="how should we cache the catalog with redis",
        semantic=True,
    )
    assert found["ok"] is True
    assert found["semantic"] is True
    assert found["count"] >= 1
    assert found["decisions"][0]["id"] == "dec_cache01"


@pytest.mark.phase_3
@pytest.mark.asyncio
async def test_mcp_stdio_list_and_call_tools(tmp_path: Path) -> None:
    import sys

    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "reasonledger_mcp.server", "--repo-root", str(tmp_path)],
        env={"RL_MCP_REPO_ROOT": str(tmp_path)},
    )
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        assert init.serverInfo.name == SERVER_NAME
        assert init.serverInfo.version == package_version(DIST_NAME)
        tools = await session.list_tools()
        names = {t.name for t in tools.tools}
        assert "record_decision" in names
        assert "query_decisions" in names
        # Validate tool schemas expose required properties
        record_tool = next(t for t in tools.tools if t.name == "record_decision")
        schema = record_tool.inputSchema
        assert "properties" in schema
        assert "context" in schema["properties"]
        assert "choice" in schema["properties"]

        call = await session.call_tool(
            "record_decision",
            {
                "context": "stdio capture",
                "choice": "Adopt MCP",
                "ai_tool": "claude-code",
                "model": "test-model",
                "decision_id": "dec_stdio1",
                "approved_by": "alice@acme.com",
                "justifies": ["mcp/server.py:1-5"],
            },
        )
        text = call.content[0].text  # type: ignore[union-attr]
        payload = json.loads(text)
        assert payload["ok"] is True
        assert (tmp_path / ".reasonledger" / "decisions" / "dec_stdio1.md").is_file()

        found = await session.call_tool("query_decisions", {"query": "Adopt MCP"})
        queried = json.loads(found.content[0].text)  # type: ignore[union-attr]
        assert queried["count"] == 1
        assert queried["decisions"][0]["superseded_by"] is None
        assert queried["warnings"] == []


@pytest.mark.phase_3
@pytest.mark.parametrize("flag", ["--transport", "--host", "--port"])
def test_the_server_offers_no_network_transport(flag: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([flag, "streamable-http"])

    assert exit_info.value.code == 2
