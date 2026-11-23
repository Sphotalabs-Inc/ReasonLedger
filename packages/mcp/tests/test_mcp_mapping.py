"""Phase 5 — the agent route over MCP: an agent maps the app, submits it, and reads drift."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from reasonledger_mcp.tools import call_get_mapping_task, call_get_modules, call_submit_module_map


def _app(root: Path) -> Path:
    for folder in ("orders", "payments"):
        for index in range(4):
            path = root / "app" / folder / f"f{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x = 1\n", encoding="utf-8")
    return root


def _module(module_id: str, glob: str) -> dict[str, object]:
    return {
        "id": module_id,
        "name": module_id.title(),
        "kind": "feature",
        "description": f"{module_id} capability",
        "paths": [glob],
    }


@pytest.mark.phase_5
def test_agent_maps_submits_and_reads_back_through_the_tool_helpers(tmp_path: Path) -> None:
    root = _app(tmp_path)
    task = call_get_mapping_task(root)
    assert task["mode"] == "full" and "app/orders/" in str(task["digest"])
    bad = call_submit_module_map(root, [_module("nope", "missing/**")], "claude-code/test")
    assert bad["ok"] is False and bad["written"] is False
    good = call_submit_module_map(root, [_module("orders", "app/orders/**")], "claude-code/test")
    assert good["ok"] is True and good["modules"] == ["orders"]
    view = call_get_modules(root)
    # the agent left payments out, so its files wait in the shared bucket
    assert [m["id"] for m in view["modules"]] == ["orders", "shared"]
    assert good["buckets"] == {"shared": 4} and view["drift"]["unplaced"] == 0  # type: ignore[index]
    for index in range(4):
        (root / "app" / "billing").mkdir(exist_ok=True)
        (root / "app" / "billing" / f"f{index}.py").write_text("x = 1\n", encoding="utf-8")
    assert call_get_modules(root)["drift"]["unplaced"] == 4  # type: ignore[index]
    delta = call_get_mapping_task(root, delta=True)
    assert delta["mode"] == "delta" and len(delta["unplaced_files"]) == 4  # type: ignore[arg-type]
    assert [m["id"] for m in delta["existing_modules"]] == ["orders"]  # type: ignore[index, union-attr]


@pytest.mark.phase_5
@pytest.mark.asyncio
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="the MCP client's stdio reader raises BrokenResourceError while closing on Windows "
    "after every call has succeeded; test_mcp_contract's stdio test covers the same server",
)
async def test_the_server_offers_the_three_mapping_tools(tmp_path: Path) -> None:
    root = _app(tmp_path)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "reasonledger_mcp.server", "--repo-root", str(root)],
        env={"RL_MCP_REPO_ROOT": str(root)},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        names = {t.name for t in (await session.list_tools()).tools}
        assert {"get_mapping_task", "submit_module_map", "get_modules"} <= names
        assert {"get_judging_task", "submit_verdicts"} <= names
        assert {"get_import_task", "submit_candidates"} <= names
        result = await session.call_tool("get_mapping_task", {"delta": False})
        payload = json.loads(result.content[0].text)  # type: ignore[union-attr]
        assert payload["mode"] == "full"
        sent = await session.call_tool(
            "submit_module_map",
            {"modules": [_module("payments", "app/payments/**")], "mapped_by": "test/agent"},
        )
        assert json.loads(sent.content[0].text)["ok"] is True  # type: ignore[union-attr]
