"""The related-decision judge: a model decides which shortlisted pairs truly conflict.

Similarity finds pairs that share a topic; only a reader can tell whether two answers
contradict each other. The judge is that reader. It runs only when a person asks
(`reasonledger judge`, or "Check for conflicts" in the UI), never as a side effect of
`status`, of loading the UI or of CI, and every verdict is written to the committed
``verdicts.yml`` so it is paid for once.

The model sees each decision's id, context and choice — the fields the pair
fingerprint covers, so a verdict is invalidated exactly when its inputs change.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.config import ExtractorConfig
from reasonledger_core.importer.llm import (
    HttpPost,
    StructuredClient,
    StructuredTask,
    build_structured_client,
    call_with_retry,
)
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.models.reasoning import ConflictVerdict, Relation
from reasonledger_core.reasoning.conflict_config import effective_conflict_config
from reasonledger_core.reasoning.dismissals import (
    dismissal_still_applies,
    dismissed_fingerprints,
    pair_fingerprint,
    pair_key,
)
from reasonledger_core.reasoning.embeddings import Embedder
from reasonledger_core.reasoning.related import Candidate, shortlist
from reasonledger_core.reasoning.verdicts import (
    JudgeAnswer,
    StoredVerdict,
    load_verdicts,
    stored_verdict_source,
    write_verdicts,
)

JUDGE_SYSTEM_PROMPT = """\
You check pairs of engineering decisions recorded in one codebase for contradictions.
Each decision has a context (the open question it answered) and a choice (what was picked).

Answer two questions about the pair:
1. same_question: do both decisions answer the same open question about the same part of
   the system? Sharing a topic, a component or vocabulary is not enough. Decisions about
   different layers (for example a language toolchain and a domain state machine), or
   where one decision implements, refines or depends on the other, answer different
   questions.
2. compatible: can both choices be in force at the same time without one making the
   other wrong?

Flag a conflict (same_question true, compatible false) only when you can name the single
question both answer and say why both answers cannot hold.

question: the question both decisions answer, in one short sentence; if they answer
different questions, the topic they share.
reason: one or two sentences a reviewer can check against the two decisions.
severity: high when following one decision would break or undo the other, medium when
they pull the codebase in different directions, low otherwise and for compatible pairs.
Never include names, email addresses or other personal data.
"""

JUDGE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "same_question": {"type": "boolean"},
        "compatible": {"type": "boolean"},
        "question": {"type": "string"},
        "reason": {"type": "string"},
        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["same_question", "compatible", "question", "reason", "severity"],
    "additionalProperties": False,
}

JUDGE_TASK = StructuredTask(
    system=JUDGE_SYSTEM_PROMPT,
    schema=JUDGE_SCHEMA,
    name="judge_decision_pair",
    schema_name="decision_pair_verdict",
    description="Judge whether two recorded decisions conflict.",
)


def build_judge_prompt(a: DecisionRecord, b: DecisionRecord) -> str:
    def block(label: str, record: DecisionRecord) -> str:
        fm = record.frontmatter
        return f"Decision {label} ({fm.id})\nContext: {fm.context or ''}\nChoice: {fm.choice or ''}"

    return f"{block('A', a)}\n\n{block('B', b)}"


def _correction(error: str) -> str:
    return f"Your previous response was invalid: {error}. Respond with schema-valid JSON only."


class ModelJudge:
    """Judges one pair per model call; also usable as a ``ConflictClassifier``."""

    def __init__(self, client: StructuredClient) -> None:
        self._client = client
        self.model = client.model

    def judge(self, a: DecisionRecord, b: DecisionRecord) -> JudgeAnswer:
        """Raises ``LlmError`` (or its ``InvalidResponse``) when no valid answer comes back."""
        messages: list[dict[str, object]] = [{"role": "user", "content": build_judge_prompt(a, b)}]
        answer = call_with_retry(
            self._client, messages, JudgeAnswer.model_validate, correction=_correction
        )
        return answer.linted()

    def classify(
        self,
        a: DecisionRecord,
        b: DecisionRecord,
        *,
        context_similarity: float,
        choice_similarity: float,
    ) -> ConflictVerdict:
        return self.judge(a, b).to_verdict(score=context_similarity)


def build_model_judge(
    config: ExtractorConfig,
    *,
    model: str | None = None,
    api_key: str | None = None,
    http_post: HttpPost | None = None,
) -> ModelJudge:
    """A judge on the importer's provider; ``model`` overrides its configured model."""
    return ModelJudge(
        build_structured_client(
            config, JUDGE_TASK, api_key=api_key, http_post=http_post, model=model
        )
    )


class JudgeReport(BaseModel):
    shortlisted: int
    already_judged: int
    pending: int
    dismissed: int = 0
    judged: int = 0
    conflicts: int = 0
    compatible: int = 0
    failed: list[str] = []


def ledger_records(root: Path) -> list[DecisionRecord]:
    """Proposals plus ledger records — the set every related-decision surface compares."""
    return load_decisions_from_dir(root / PROPOSED_DIR) + load_decisions_from_dir(
        root / DECISIONS_DIR
    )


@dataclass(frozen=True)
class JudgeQueue:
    """The shortlist, split by what is left to do about each pair."""

    pending: list[Candidate]
    already_judged: int
    dismissed: int

    @property
    def shortlisted(self) -> int:
        return len(self.pending) + self.already_judged + self.dismissed


def _dismissal_applies(dismissed: Mapping[str, str | None], candidate: Candidate) -> bool:
    """A person's "not a conflict" still covers this pair as it reads now."""
    key = pair_key(candidate.a.frontmatter.id, candidate.b.frontmatter.id)
    return key in dismissed and dismissal_still_applies(
        dismissed[key], pair_fingerprint(candidate.a, candidate.b)
    )


def pending_pairs(root: Path, *, embedder: Embedder) -> JudgeQueue:
    """Shortlisted pairs still needing a verdict, and how many need none.

    A pair needs none when a verdict is stored or a person dismissed it: a dismissal
    outranks a model, so asking the model would only spend a call on a settled question.
    A dismissal covers the decisions as they read then, so a pair edited since is judged.
    """
    cfg = effective_conflict_config(root)
    candidates = shortlist(
        sorted(ledger_records(root), key=lambda record: record.frontmatter.id),
        embedder=embedder,
        k=cfg.shortlist_k,
        min_context_similarity=cfg.context_similarity_gate,
    )
    lookup = stored_verdict_source(load_verdicts(root))
    dismissed = dismissed_fingerprints(root)
    pending: list[Candidate] = []
    already_judged = 0
    dismissed_count = 0
    for candidate in candidates:
        if lookup(candidate) is not None:
            already_judged += 1
        elif _dismissal_applies(dismissed, candidate):
            dismissed_count += 1
        else:
            pending.append(candidate)
    return JudgeQueue(pending, already_judged, dismissed_count)


def judge_pending(
    root: Path,
    *,
    judge: ModelJudge,
    embedder: Embedder,
    limit: int | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    on_result: Callable[[Candidate, Relation | None, str], None] | None = None,
    only: str | None = None,
    before_each: Callable[[Candidate], bool] = lambda _candidate: True,
) -> JudgeReport:
    """Judge pairs that have no verdict and no dismissal, saving after each one.

    Saving per pair means an interrupted run (a slow local model, a dropped
    connection) keeps everything judged so far. A failed pair is reported and left
    unjudged, never recorded as compatible. ``only`` narrows the run to one pending pair
    by its ``pair_key``; ``before_each`` is handed each pair before it is sent and stops the
    run by answering False, so a caller can show what is being compared and end a run
    between calls without losing what it has saved.
    """
    queue = pending_pairs(root, embedder=embedder)
    report = JudgeReport(
        shortlisted=queue.shortlisted,
        already_judged=queue.already_judged,
        dismissed=queue.dismissed,
        pending=len(queue.pending),
    )
    verdicts = load_verdicts(root)
    chosen = [
        candidate
        for candidate in queue.pending
        if only is None or pair_key(candidate.a.frontmatter.id, candidate.b.frontmatter.id) == only
    ]
    for candidate in chosen[:limit] if limit is not None else chosen:
        if not before_each(candidate):
            break
        a, b = candidate.a, candidate.b
        try:
            answer = judge.judge(a, b)
        except Exception as exc:  # any provider failure skips this pair, never the run
            report.failed.append(f"{a.frontmatter.id} <-> {b.frontmatter.id}: {exc}")
            if on_result:
                on_result(candidate, None, str(exc))
            continue
        verdicts[pair_key(a.frontmatter.id, b.frontmatter.id)] = StoredVerdict(
            **answer.model_dump(),
            decision_a=a.frontmatter.id,
            decision_b=b.frontmatter.id,
            fingerprint=pair_fingerprint(a, b),
            model=judge.model,
            judged_at=now(),
        )
        write_verdicts(root, verdicts)
        relation = Relation.CONFLICT if answer.is_conflict else Relation.COMPATIBLE
        report.judged += 1
        if answer.is_conflict:
            report.conflicts += 1
        else:
            report.compatible += 1
        if on_result:
            on_result(candidate, relation, answer.question if answer.is_conflict else answer.reason)
    return report


def agreement(predictions: list[tuple[bool, bool]]) -> tuple[float, float, float]:
    """Precision, recall and false-positive rate of (predicted, labelled) conflict pairs."""
    tp = sum(1 for predicted, label in predictions if predicted and label)
    fp = sum(1 for predicted, label in predictions if predicted and not label)
    fn = sum(1 for predicted, label in predictions if not predicted and label)
    tn = sum(1 for predicted, label in predictions if not predicted and not label)
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    false_positive_rate = fp / (fp + tn) if (fp + tn) else 0.0
    return precision, recall, false_positive_rate
