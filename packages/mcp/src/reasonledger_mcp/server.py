"""ReasonLedger MCP server — record_decision / query_decisions."""

from __future__ import annotations

import argparse
import json
import os
from importlib.metadata import version as package_version
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from reasonledger_core.models.decision import DecisionOversight, DecisionProposer

from reasonledger_mcp.hits import QUERY_LIMIT
from reasonledger_mcp.tools import (
    call_decisions_for,
    call_get_import_task,
    call_get_judging_task,
    call_get_mapping_task,
    call_get_modules,
    call_query_decisions,
    call_record_decision,
    call_submit_candidates,
    call_submit_module_map,
    call_submit_verdicts,
)

SERVER_NAME = "reasonledger"
DIST_NAME = "reasonledger-mcp"


def _repo_root() -> Path:
    raw = os.environ.get("RL_MCP_REPO_ROOT")
    return Path(raw).resolve() if raw else Path.cwd().resolve()


def create_mcp_server(*, repo_root: Path | None = None) -> FastMCP:
    root = repo_root or _repo_root()
    mcp = FastMCP(SERVER_NAME, json_response=True)
    # FastMCP takes no version, so `initialize` would report the SDK's own; agents and bug
    # reports read this one. The stdio contract test fails if the SDK moves the attribute.
    mcp._mcp_server.version = package_version(DIST_NAME)

    @mcp.tool()
    def record_decision(
        context: str,
        choice: str,
        ai_tool: str,
        alternatives_rejected: list[str] | None = None,
        assumptions: list[str] | None = None,
        confidence: str | None = None,
        model: str | None = None,
        oversight: str | None = None,
        proposed_by: str | None = None,
        approved_by: str | None = None,
        justifies: list[str] | None = None,
        body: str | None = None,
        decision_id: str | None = None,
        supersedes: str | None = None,
    ) -> str:
        """Record a governance decision as `.reasonledger/decisions/<id>.md`.

        ai_tool: free-form name of the agent, e.g. claude-code, cursor, copilot, grok, codex
            (use none for a human-made decision).
        justifies: code loci this decision explains, as path::symbol or path:START-END; a bare
            file path is saved but warned about.
        model: exact model id behind the choice, e.g. claude-sonnet-4-5 or grok-4; required
            unless ai_tool is none.
        oversight, approved_by: ignored; kept only so older rule files do not break. The record
            is always saved pending and a person gives the verdict with `reasonledger approve`.
        proposed_by: whose idea the choice was. 'human' only if the user stated or explicitly
            accepted it in chat before you acted; 'ai' if you chose or recommended it. Leave
            unset only when you cannot tell.
        supersedes: id of the ledger decision this one replaces. That record is kept and
            marked superseded; use it instead of silently contradicting a prior decision.
        """
        if oversight is not None and oversight not in {v.value for v in DecisionOversight}:
            allowed = ", ".join(v.value for v in DecisionOversight)
            raise ValueError(f"invalid oversight: {oversight!r} (allowed: {allowed})")
        if proposed_by is not None and proposed_by not in {v.value for v in DecisionProposer}:
            allowed = ", ".join(v.value for v in DecisionProposer)
            raise ValueError(f"invalid proposed_by: {proposed_by!r} (allowed: {allowed})")
        return json.dumps(
            call_record_decision(
                root,
                context=context,
                choice=choice,
                ai_tool=ai_tool,
                alternatives_rejected=alternatives_rejected,
                assumptions=assumptions,
                confidence=confidence,
                model=model,
                oversight=oversight,
                proposed_by=proposed_by,
                approved_by=approved_by,
                justifies=justifies,
                body=body,
                decision_id=decision_id,
                supersedes=supersedes,
            )
        )

    @mcp.tool()
    def query_decisions(
        query: str,
        paths: list[str] | None = None,
        semantic: bool = False,
        limit: int = QUERY_LIMIT,
        full: bool = False,
    ) -> str:
        """Query prior decisions before deciding.

        ``semantic=False`` filters by substring + path (Phase 3 behavior).
        ``semantic=True`` ranks decisions by embedding similarity (Phase 4),
        so an agent can find relevant priors even without exact keywords. It uses the
        embedder set in the repo's .reasonledger/conflict.yml; a non-empty ``warnings``
        in the result means that embedder could not start and word matching answered
        instead, so treat the ranking as weaker.

        Returns at most ``limit`` compact hits (id, context, choice, justifies, status,
        oversight, proposed_by, superseded_by), decisions in force first, plus ``total``,
        ``truncated`` and ``warnings``. ``full=true`` adds each record's markdown.
        """
        return json.dumps(
            call_query_decisions(
                root, query=query, paths=paths, semantic=semantic, limit=limit, full=full
            )
        )

    @mcp.tool()
    def decisions_for(paths: list[str], line: int | None = None) -> str:
        """Before editing a file, ask which recorded decisions cover it.

        paths: repo-relative files you are about to change. line: narrow to the code at that
        line. Returns the decisions in force (compact, with how precisely each matches: symbol,
        line or file) and how many retired or superseded ones also touch these files. Align
        with what comes back, or supersede it explicitly when you diverge.
        """
        return json.dumps(call_decisions_for(root, paths=paths, line=line))

    @mcp.tool()
    def get_import_task(limit: int = 8) -> str:
        """Get the next docs and commit messages that may contain decisions, so you can
        backfill proposals without a separate model key.

        Each doc is a repo-relative path: read that file yourself. A commit includes its
        message. Source code is not listed. Answer with submit_candidates. Use this instead
        of `reasonledger import` when no model is configured.
        """
        return json.dumps(call_get_import_task(root, limit=limit))

    @mcp.tool()
    def submit_candidates(
        candidates: list[dict[str, object]],
        extracted_by: str,
        covered: list[str] | None = None,
    ) -> str:
        """Submit extracted decisions as proposals: a list of {context, choice, source_ref,
        alternatives_rejected}.

        source_ref is "<path>#<topic>" for a path from get_import_task. covered lists every
        path from that task, including paths with no decision. Proposals wait for a person
        to confirm them. extracted_by: your tool and model.
        """
        return json.dumps(call_submit_candidates(root, candidates, extracted_by, covered))

    @mcp.tool()
    def get_mapping_task(delta: bool = False) -> str:
        """Get what you need to propose the application's module map: instructions, the answer
        format and a digest of file paths and route paths (never file contents).

        delta=False: map the whole application. delta=True: only the files no module claims yet
        (call it after adding a feature area). Answer with submit_module_map.
        """
        return json.dumps(call_get_mapping_task(root, delta=delta))

    @mcp.tool()
    def submit_module_map(
        modules: list[dict[str, object]], mapped_by: str, delta: bool = False
    ) -> str:
        """Submit module proposals: a list of {id, name, kind, description, paths}.

        The paths are checked against the real files; the result lists anything dropped so you can
        resubmit. Proposals are saved for a person to confirm. mapped_by: your tool and model.
        """
        return json.dumps(call_submit_module_map(root, modules, mapped_by, delta=delta))

    @mcp.tool()
    def get_judging_task(
        limit: int = 10, decision_a: str | None = None, decision_b: str | None = None
    ) -> str:
        """Get the next related decision pairs to judge for contradictions, with the rubric.

        limit: how many pairs to hand out (1 to 25). decision_a and decision_b: pass both ids to
        judge exactly that pair and nothing else.

        Each pair is two recorded decisions (id, context, choice). Decide whether both answer
        the same question and whether both choices can hold at once, then answer with
        submit_verdicts. Use this instead of `reasonledger judge` when no model is configured.
        """
        return json.dumps(
            call_get_judging_task(root, limit=limit, decision_a=decision_a, decision_b=decision_b)
        )

    @mcp.tool()
    def submit_verdicts(verdicts: list[dict[str, object]], judged_by: str) -> str:
        """Submit verdicts: a list of {decision_a, decision_b, same_question, compatible,
        question, reason, severity}. Verdicts are stored in .reasonledger/verdicts.yml and shown
        in the UI; a pair edited since the task is rejected. judged_by: your tool and model.
        """
        return json.dumps(call_submit_verdicts(root, verdicts, judged_by))

    @mcp.tool()
    def get_modules() -> str:
        """The module map so far (ids, kinds, status) and what no module accounts for yet."""
        return json.dumps(call_get_modules(root))

    return mcp


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog=DIST_NAME)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {package_version(DIST_NAME)}",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root where .reasonledger/decisions is written",
    )
    args = parser.parse_args(argv)
    if args.repo_root is not None:
        os.environ["RL_MCP_REPO_ROOT"] = str(args.repo_root.resolve())
    server = create_mcp_server()
    # stdio only: a network listener would need authentication and TLS before it could be offered.
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
