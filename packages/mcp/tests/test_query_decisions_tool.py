"""`query_decisions` through the real FastMCP tool function.

The server tool must be the same code path as the in-process helper, and semantic recall
must run on the embedder the repo's conflict.yml selects — never silently on the hash
default. Real models are stubbed so CI stays offline and deterministic.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from reasonledger_core.decisions import read_decision_file, write_decision_file
from reasonledger_core.models.decision import DecisionStatus
from reasonledger_core.reasoning import DeterministicEmbedder
from reasonledger_core.reasoning.cache import CACHE_DIR
from reasonledger_core.reasoning.conflict_config import ConflictConfig, write_conflict_config
from reasonledger_core.reasoning.embeddings import Embedder
from reasonledger_core.settings import Settings
from reasonledger_mcp.server import create_mcp_server
from reasonledger_mcp.tools import call_query_decisions, call_record_decision

CONCEPTS = (
    {"cache", "caching", "redis", "lookups", "faster", "speed"},
    {"api", "rest", "endpoints", "interface", "clients"},
)
PROVIDER_PATCH_TARGET = "reasonledger_core.reasoning.conflict_config.get_embedder"
CACHE_QUESTION = "make lookups faster"


class ConceptEmbedder:
    """Stand-in for a real semantic model: synonyms share a dimension, so words need no overlap."""

    model_id = "test-concept-embedder"
    dim = len(CONCEPTS)

    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.embedded.append(text)
        tokens = re.findall(r"[a-z]+", text.lower())
        vector = [float(sum(token in group for token in tokens)) for group in CONCEPTS]
        norm = math.sqrt(sum(value * value for value in vector))
        return vector if norm == 0.0 else [value / norm for value in vector]


def _query_tool(root: Path) -> Callable[..., str]:
    tool = create_mcp_server(repo_root=root)._tool_manager.get_tool("query_decisions")
    assert tool is not None
    fn: Callable[..., str] = tool.fn
    return fn


def _record(root: Path, decision_id: str, context: str, choice: str, **extra: Any) -> None:
    call_record_decision(
        root,
        context=context,
        choice=choice,
        ai_tool="claude-code",
        model="test-model",
        decision_id=decision_id,
        approved_by="alice@acme.com",
        **extra,
    )


def _seed_cache_and_api(root: Path) -> None:
    _record(root, "dec_cache01", "Which store speeds the catalog read path?", "Redis in front")
    _record(root, "dec_api001", "What interface do external clients get?", "REST endpoints")


def _select_embedders(
    monkeypatch: pytest.MonkeyPatch,
    *,
    local: Embedder | Exception,
) -> list[str]:
    """Make provider ``local`` resolve to ``local`` (or raise it); return providers requested."""
    requested: list[str] = []

    def fake_get_embedder(*, settings: Settings | None = None) -> Embedder:
        provider = (settings or Settings()).embedding_provider
        requested.append(provider)
        if provider != "local":
            return DeterministicEmbedder()
        if isinstance(local, Exception):
            raise local
        return local

    monkeypatch.setattr(PROVIDER_PATCH_TARGET, fake_get_embedder)
    return requested


@pytest.mark.phase_3
def test_server_tool_is_the_in_process_query_path(tmp_path: Path) -> None:
    _record(tmp_path, "dec_old003", "Retry policy", "Exponential", justifies=["pay/retry.py:1-9"])
    _record(tmp_path, "dec_new003", "Retry policy", "Fixed delay", justifies=["pay/retry.py:1-9"])
    old_path = tmp_path / ".reasonledger" / "decisions" / "dec_old003.md"
    new_path = tmp_path / ".reasonledger" / "decisions" / "dec_new003.md"
    old = read_decision_file(old_path)
    old.frontmatter.status = DecisionStatus.SUPERSEDED
    write_decision_file(old_path, old)
    new = read_decision_file(new_path)
    new.frontmatter.supersedes = "dec_old003"
    write_decision_file(new_path, new)

    served = json.loads(_query_tool(tmp_path)(query="retry", paths=["pay/**"]))

    assert served == call_query_decisions(tmp_path, query="retry", paths=["pay/**"])
    by_id = {d["id"]: d for d in served["decisions"]}
    assert by_id["dec_old003"]["superseded_by"] == "dec_new003"
    assert by_id["dec_new003"]["superseded_by"] is None
    assert served["warnings"] == []
    assert (served["total"], served["truncated"]) == (2, False)
    assert [d["id"] for d in served["decisions"]] == ["dec_new003", "dec_old003"]  # in force first


@pytest.mark.phase_4
def test_semantic_recall_uses_the_embedder_the_repo_configures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested = _select_embedders(monkeypatch, local=ConceptEmbedder())
    _seed_cache_and_api(tmp_path)
    query = _query_tool(tmp_path)

    default = json.loads(query(query=CACHE_QUESTION, semantic=True))
    assert default["decisions"] == []  # hash matching finds no shared word
    assert requested == ["deterministic"]

    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))
    configured = json.loads(query(query=CACHE_QUESTION, semantic=True))

    assert [d["id"] for d in configured["decisions"]] == ["dec_cache01"]
    assert configured["warnings"] == []
    assert requested == ["deterministic", "local"]


@pytest.mark.phase_4
def test_semantic_recall_says_so_when_the_configured_embedder_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _select_embedders(monkeypatch, local=ImportError("fastembed"))
    _seed_cache_and_api(tmp_path)
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))

    result = json.loads(_query_tool(tmp_path)(query="Redis read path store", semantic=True))

    assert result["ok"] is True
    assert result["decisions"][0]["id"] == "dec_cache01"  # still answers, on word matching
    assert len(result["warnings"]) == 1
    assert "basic word matching" in result["warnings"][0]
    assert "embedder is not installed" in result["warnings"][0]


@pytest.mark.phase_4
def test_semantic_recall_embeds_each_decision_once_across_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    concept = ConceptEmbedder()
    _select_embedders(monkeypatch, local=concept)
    _seed_cache_and_api(tmp_path)
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))
    query = _query_tool(tmp_path)

    query(query=CACHE_QUESTION, semantic=True)
    assert len(concept.embedded) == 3  # two decisions and the query
    query(query="which interface do clients get", semantic=True)

    assert len(concept.embedded) == 4  # only the new query: decisions came from the cache
    assert len(list((tmp_path / CACHE_DIR).glob("*.json"))) == 4


@pytest.mark.phase_4
def test_semantic_recall_honours_limit_and_reports_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Semantic mode ranks every record, then the same `limit` cap as substring mode applies."""
    _select_embedders(monkeypatch, local=ConceptEmbedder())
    _record(tmp_path, "dec_cache_a", "Which store speeds the catalog read path?", "Redis in front")
    _record(tmp_path, "dec_cache_b", "How do session lookups get faster?", "A caching layer")
    _record(tmp_path, "dec_cache_c", "Cache invalidation strategy", "Short TTL on Redis")
    _record(tmp_path, "dec_api_001", "What interface do external clients get?", "REST endpoints")
    write_conflict_config(tmp_path, ConflictConfig(embedding_provider="local"))

    result = json.loads(_query_tool(tmp_path)(query=CACHE_QUESTION, semantic=True, limit=1))

    assert (result["count"], result["total"], result["truncated"]) == (1, 3, True)
    assert result["decisions"][0]["id"].startswith("dec_cache_")
    assert result["warnings"] == []
