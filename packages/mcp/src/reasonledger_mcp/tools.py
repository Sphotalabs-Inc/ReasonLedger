"""ReasonLedger MCP helpers for in-process tool calls (tests / thin wrappers)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reasonledger_core.decisions import (
    load_decisions_from_dir,
    query_decisions,
    record_decision_to_path,
    render_decision_markdown,
    superseded_by_map,
)
from reasonledger_core.decisions.format import DECISIONS_DIR, DecisionIdError
from reasonledger_core.decisions.lifecycle import RetireError
from reasonledger_core.models.decision import (
    AiTool,
    DecisionProposer,
    DecisionRecord,
    QueryDecisionsInput,
    RecordDecisionInput,
)
from reasonledger_core.privacy.pii_linter import PiiLintError
from reasonledger_core.reasoning.retrieval import semantic_recall
from reasonledger_core.reasoning.symbols import supports, symbol_at_line
from reasonledger_core.reasoning.why import WhyHit, WhyTarget, match_rank, resolve_why
from reasonledger_core.repo_files import read_repo_text

from reasonledger_mcp.hits import QUERY_LIMIT, compact_hit, in_force, in_force_first


def _anchor_symbols(repo_root: Path, loci: list[str]) -> list[str]:
    """Upgrade supported ``path:line`` loci when the source still names a symbol."""
    anchored: list[str] = []
    for locus in loci:
        path, separator, line_text = locus.rpartition(":")
        if not separator or not line_text.isdigit() or not supports(path):
            anchored.append(locus)
            continue
        source = read_repo_text(repo_root, path)
        if source is None:
            anchored.append(locus)
            continue
        symbol = symbol_at_line(source, int(line_text), path)
        anchored.append(f"{path}::{symbol}" if symbol is not None else locus)
    return anchored


_LINE_LOCUS = re.compile(r":\d+(-\d+)?$")


def _bare_path_warnings(loci: list[str]) -> list[str]:
    """Name loci that point at a whole file: they match every decision touching it."""
    return [
        f"justifies {locus!r} is a bare file path; use {locus}::symbol_name or {locus}:START-END "
        "so `reasonledger why` returns this decision only for the code it explains"
        for locus in loci
        if "::" not in locus and not _LINE_LOCUS.search(locus)
    ]


def _proposer_name(record: DecisionRecord) -> str | None:
    proposer = record.frontmatter.proposed_by
    return proposer.value if proposer else None


def _proposed_by_warnings(proposed_by: DecisionProposer | None) -> list[str]:
    if proposed_by is not None:
        return []
    return [
        "proposed_by is not set: pass 'human' if the user stated or explicitly accepted this "
        "choice in chat, or 'ai' if you chose it, so the ledger shows whose idea it was"
    ]


def _verdict_warnings(kwargs: dict[str, Any]) -> list[str]:
    """A verdict is a person's to give; say so when an agent tries to write one."""
    ignored = [name for name in ("approved_by", "oversight") if kwargs.get(name)]
    if not ignored:
        return []
    return [
        f"{' and '.join(ignored)} ignored: a record written through MCP is always pending. "
        "A person gives the verdict with `reasonledger approve <id>` or in `reasonledger ui`."
    ]


def call_record_decision(repo_root: Path, **kwargs: Any) -> dict[str, Any]:
    proposed_by_raw = kwargs.get("proposed_by")
    proposed_by = DecisionProposer(proposed_by_raw) if proposed_by_raw else None
    justifies = _anchor_symbols(repo_root, list(kwargs.get("justifies") or []))
    inp = RecordDecisionInput(
        context=str(kwargs["context"]),
        choice=str(kwargs["choice"]),
        alternatives_rejected=list(kwargs.get("alternatives_rejected") or []),
        assumptions=list(kwargs.get("assumptions") or []),
        confidence=kwargs.get("confidence"),
        ai_tool=kwargs.get("ai_tool", AiTool.NONE),
        model=kwargs.get("model"),
        proposed_by=proposed_by,
        justifies=justifies,
        body=kwargs.get("body"),
        decision_id=kwargs.get("decision_id"),
        supersedes=kwargs.get("supersedes"),
    )
    try:
        record, path = record_decision_to_path(inp, root=repo_root, recorded_at=datetime.now(UTC))
    except (PiiLintError, RetireError, DecisionIdError) as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "path": path.relative_to(repo_root).as_posix(),
        "decision_id": record.frontmatter.id,
        "markdown": render_decision_markdown(record),
        "warnings": _verdict_warnings(kwargs)
        + _bare_path_warnings(justifies)
        + _proposed_by_warnings(proposed_by),
    }


def call_query_decisions(
    repo_root: Path,
    *,
    query: str,
    paths: list[str] | None = None,
    semantic: bool = False,
    limit: int = QUERY_LIMIT,
    full: bool = False,
) -> dict[str, Any]:
    """Matches in force first, capped at ``limit``; ``total`` counts them before the cap.

    Semantic mode ranks with the embedder the repo's conflict.yml selects. If that backend
    cannot start, recall still answers on the hash embedder and ``warnings`` says so, so a
    weaker ranking is never mistaken for the configured one.
    """
    records = load_decisions_from_dir(repo_root / DECISIONS_DIR)
    warnings: list[str] = []
    if semantic:
        hits, embedder_status = semantic_recall(
            repo_root, records, query, top_k=max(len(records), 1)
        )
        if embedder_status.fallback_reason:
            warnings.append(
                "semantic recall is using basic word matching because "
                f"{embedder_status.fallback_reason}"
            )
    else:
        hits = query_decisions(records, QueryDecisionsInput(query=query, paths=list(paths or [])))
    ranked = in_force_first(hits)
    shown = ranked[: max(limit, 0)]
    superseded_map = superseded_by_map(records)
    return {
        "ok": True,
        "semantic": semantic,
        "total": len(ranked),
        "count": len(shown),
        "truncated": len(shown) < len(ranked),
        "warnings": warnings,
        "decisions": [
            compact_hit(r, superseded_map.get(r.frontmatter.id), full=full) for r in shown
        ],
    }


def _precision(hit: WhyHit) -> tuple[int, str]:
    return match_rank(hit.match), hit.record.frontmatter.id


def call_decisions_for(
    repo_root: Path, *, paths: list[str], line: int | None = None
) -> dict[str, Any]:
    """The decisions in force that cover ``paths`` (and ``line``), before an agent edits them.

    Uses the same matcher as `reasonledger why`. Only decision text comes back, never file
    contents, and a path outside the repo root refuses the whole call.
    """
    root = repo_root.resolve()
    relative: list[str] = []
    for raw in paths:
        resolved = (root / raw).resolve()
        if not resolved.is_relative_to(root):
            return {"ok": False, "error": f"{raw!r} is outside the repository"}
        relative.append(resolved.relative_to(root).as_posix())
    records = load_decisions_from_dir(root / DECISIONS_DIR)
    superseded_map = superseded_by_map(records)
    best: dict[str, WhyHit] = {}
    out_of_force: set[str] = set()
    for path in relative:
        for hit in resolve_why(records, WhyTarget(path=path, line=line), root=root):
            ident = hit.record.frontmatter.id
            if not in_force(hit.record):
                out_of_force.add(ident)
            elif ident not in best or _precision(hit) < _precision(best[ident]):
                best[ident] = hit
    ordered = sorted(best.values(), key=_precision)
    return {
        "ok": True,
        "paths": relative,
        "decisions": [
            {
                **compact_hit(h.record, superseded_map.get(h.record.frontmatter.id)),
                "match": h.match.value,
            }
            for h in ordered
        ],
        "out_of_force": len(out_of_force),
    }


def dumps_tool_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


def call_get_import_task(repo_root: Path, *, limit: int = 8) -> dict[str, Any]:
    """Documents and commit messages still unseen, for the agent to extract proposals from."""
    from reasonledger_core.importer.agent_route import import_task

    return import_task(repo_root, limit=limit)


def call_submit_candidates(
    repo_root: Path,
    candidates: list[dict[str, Any]],
    extracted_by: str,
    covered: list[str] | None = None,
) -> dict[str, Any]:
    """Validate an agent's extractions and stage them as proposals for a person to confirm."""
    from reasonledger_core.importer.agent_route import submit_candidates

    return submit_candidates(repo_root, candidates, extracted_by, covered)


def call_get_mapping_task(repo_root: Path, *, delta: bool = False) -> dict[str, Any]:
    """The digest (or the drift delta) an agent maps the application from; never file contents."""
    from reasonledger_core.modules.agent_route import mapping_task

    return mapping_task(repo_root, delta=delta)


def call_submit_module_map(
    repo_root: Path, modules: list[dict[str, Any]], mapped_by: str, *, delta: bool = False
) -> dict[str, Any]:
    """Validate an agent's module proposals and write them as proposals for a person to confirm."""
    from reasonledger_core.modules.agent_route import submit_map

    return submit_map(repo_root, modules, mapped_by, delta=delta)


def call_get_modules(repo_root: Path) -> dict[str, Any]:
    """The module map (ids, kinds, status) and what in the code no module accounts for yet."""
    from reasonledger_core.modules.agent_route import modules_view

    return modules_view(repo_root)


def _conflict_embedder(repo_root: Path) -> Any:
    from reasonledger_core.reasoning import CachingEmbedder
    from reasonledger_core.reasoning.conflict_config import resolve_conflict_embedder_with_status

    embedder, _status = resolve_conflict_embedder_with_status(repo_root)
    return CachingEmbedder(embedder, root=repo_root)


def call_get_judging_task(
    repo_root: Path,
    *,
    limit: int = 10,
    decision_a: str | None = None,
    decision_b: str | None = None,
) -> dict[str, Any]:
    """The next batch of related pairs for the agent to judge, or one named pair.

    Decision text only. Naming both ``decision_a`` and ``decision_b`` narrows the task to that
    pair; naming only one is an error, since a pair needs both sides.
    """
    from reasonledger_core.reasoning.agent_judge import judging_task

    if (decision_a is None) != (decision_b is None):
        return {"ok": False, "error": "name both decision_a and decision_b, or neither"}
    pair = (decision_a, decision_b) if decision_a and decision_b else None
    return judging_task(repo_root, embedder=_conflict_embedder(repo_root), limit=limit, pair=pair)


def call_submit_verdicts(
    repo_root: Path, verdicts: list[dict[str, Any]], judged_by: str
) -> dict[str, Any]:
    """Validate an agent's verdicts and store them beside the model-judged ones."""
    from reasonledger_core.reasoning.agent_judge import submit_verdicts

    return submit_verdicts(repo_root, verdicts, judged_by, embedder=_conflict_embedder(repo_root))
