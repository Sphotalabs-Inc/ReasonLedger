"""`reasonledger judge` — ask the configured model which related decisions truly conflict.

The only command that calls a model about related decisions. It judges shortlisted
pairs that have no current verdict and saves each verdict to the committed
`.reasonledger/verdicts.yml` as it goes; `status`, the UI and `check-decisions`
then read those verdicts without calling anything.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reasonledger_core.consent import DataClass
from reasonledger_core.importer.config import (
    ConfigError,
    ExtractorProvider,
    load_extractor_config,
)
from reasonledger_core.importer.llm import LlmError
from reasonledger_core.models.reasoning import Relation
from reasonledger_core.reasoning import CachingEmbedder
from reasonledger_core.reasoning.conflict_config import (
    effective_conflict_config,
    resolve_conflict_embedder_with_status,
)
from reasonledger_core.reasoning.dismissals import pair_key
from reasonledger_core.reasoning.judge import (
    JudgeQueue,
    build_model_judge,
    judge_pending,
    pending_pairs,
)
from reasonledger_core.reasoning.related import Candidate
from reasonledger_core.reasoning.verdicts import VERDICTS_PATH, VerdictsError, load_verdicts

from reasonledger_cli.consent_cmd import ensure_consent

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


def add_judge_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    judge = sub.add_parser(
        "judge", help="Ask the configured model which related decisions truly conflict"
    )
    judge.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Application repo root (default: cwd)"
    )
    judge.add_argument(
        "--limit", type=int, default=None, help="Judge at most this many pairs in this run"
    )
    judge.add_argument(
        "--pair",
        nargs=2,
        metavar=("DECISION_A", "DECISION_B"),
        default=None,
        help="Judge only this pair of decisions (either order)",
    )
    judge.add_argument(
        "--dry-run",
        action="store_true",
        help="List the pairs that would be judged without calling a model",
    )


def _pair(candidate: Candidate) -> str:
    return f"{candidate.a.frontmatter.id} <-> {candidate.b.frontmatter.id}"


def _print_result(candidate: Candidate, relation: Relation | None, note: str) -> None:
    label = relation.value if relation else "failed"
    print(f"  {_pair(candidate)}: {label} — {note}", flush=True)


def _waiting(queue: JudgeQueue, pair: tuple[str, str]) -> list[Candidate]:
    """The pending candidate for this pair, if it is still waiting for a verdict."""
    wanted = pair_key(*pair)
    return [c for c in queue.pending if pair_key(c.a.frontmatter.id, c.b.frontmatter.id) == wanted]


def run_judge_cmd(
    *,
    root: Path,
    limit: int | None,
    dry_run: bool,
    pair: tuple[str, str] | None = None,
) -> int:
    if limit is not None and limit < 1:
        print("error: --limit must be at least 1", file=sys.stderr)
        return EXIT_USAGE
    if pair is not None and limit is not None:
        print(
            "error: --pair judges one pair, so it cannot be combined with --limit", file=sys.stderr
        )
        return EXIT_USAGE
    try:
        load_verdicts(root)
    except VerdictsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    embedder, status = resolve_conflict_embedder_with_status(root)
    if status.fallback_reason:
        print(f"warning: shortlist uses basic word matching because {status.fallback_reason}")
    cached = CachingEmbedder(embedder, root=root)

    queue = pending_pairs(root, embedder=cached)
    if pair is not None and not _waiting(queue, pair):
        print(
            f"error: {pair[0]} and {pair[1]} are not waiting for a verdict: they were already "
            "judged, a person dismissed the pair, or the two are not related",
            file=sys.stderr,
        )
        return EXIT_USAGE

    if dry_run:
        print(
            f"shortlisted: {queue.shortlisted}  judged: {queue.already_judged}  "
            f"dismissed: {queue.dismissed}  pending: {len(queue.pending)}"
        )
        listed = _waiting(queue, pair) if pair is not None else queue.pending[:limit]
        for candidate in listed:
            print(f"  {_pair(candidate)}  (context similarity {candidate.context_similarity:.2f})")
        return EXIT_PASS

    try:
        config = load_extractor_config(root)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if config.provider is ExtractorProvider.DISABLED:
        print(
            "error: no model is configured. Run `reasonledger config` first (the judge uses "
            "the same model as import), or ask your coding agent to call the MCP tools "
            "get_judging_task and submit_verdicts.",
            file=sys.stderr,
        )
        return EXIT_USAGE
    denied = ensure_consent(root, config, [DataClass.DECISION_TEXT], command="judge")
    if denied is not None:
        return denied
    try:
        judge = build_model_judge(config, model=effective_conflict_config(root).judge_model)
    except LlmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    print(f"judging with {judge.model}; verdicts are saved to {VERDICTS_PATH} as they arrive")
    report = judge_pending(
        root,
        judge=judge,
        embedder=cached,
        limit=limit,
        on_result=_print_result,
        only=pair_key(*pair) if pair is not None else None,
    )
    print(
        f"shortlisted: {report.shortlisted}  already judged: {report.already_judged}  "
        f"dismissed: {report.dismissed}  judged now: {report.judged} "
        f"({report.conflicts} conflicts, {report.compatible} compatible)  "
        f"failed: {len(report.failed)}"
    )
    remaining = report.pending - report.judged - len(report.failed)
    if remaining > 0:
        print(f"{remaining} pair(s) left; run `reasonledger judge` again to continue")
    if report.judged:
        print(f"commit {VERDICTS_PATH} so teammates and CI reuse these verdicts")
    return EXIT_FAIL if report.failed else EXIT_PASS
