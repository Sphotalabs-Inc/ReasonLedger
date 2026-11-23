"""The agent route for judging: the user's own coding agent judges pairs.

``get_judging_task`` hands an agent the related pairs that still need a verdict, with the
rubric the configured-model judge uses; ``submit_verdicts`` validates what it sends back and
stores it in ``verdicts.yml`` exactly as ``reasonledger judge`` would. Nothing here calls a
model, and the only data handed out is decision text the agent can already read in the repo.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from reasonledger_core.reasoning.dismissals import pair_fingerprint, pair_key
from reasonledger_core.reasoning.embeddings import Embedder
from reasonledger_core.reasoning.judge import JUDGE_SYSTEM_PROMPT, pending_pairs
from reasonledger_core.reasoning.verdicts import (
    JudgeAnswer,
    StoredVerdict,
    load_verdicts,
    write_verdicts,
)

DEFAULT_BATCH = 10
MAX_BATCH = 25

_ANSWER = (
    "\nAnswer by calling submit_verdicts(verdicts, judged_by) with one entry per pair: "
    "{decision_a, decision_b, fingerprint, same_question, compatible, question, reason, "
    "severity}, copying the two ids and the fingerprint exactly as given. Judge only from the "
    "text shown. judged_by is your tool and model, for example claude-code/claude-sonnet-5. "
)
_NEXT_BATCH = (
    "Call get_judging_task again for the next batch, unless the user asked for a set number "
    "of pairs or a single pair: then stop after submitting and say what you found."
)
_ONE_PAIR = (
    "This is the one pair the user asked about: judge it, submit the verdict and stop. "
    "Tell the user in a line what you found."
)


def judging_task(
    root: Path,
    *,
    embedder: Embedder,
    limit: int = DEFAULT_BATCH,
    pair: tuple[str, str] | None = None,
) -> dict[str, Any]:
    """The next batch of pairs to judge, the rubric, and how many are left.

    ``pair`` narrows the task to those two decisions. A pair that is not waiting for a verdict
    (judged, dismissed or not related) comes back with no pairs and a ``note`` saying so.
    """
    batch_size = max(1, min(limit, MAX_BATCH))
    queue = pending_pairs(root, embedder=embedder)
    note = None
    if pair is None:
        batch = queue.pending[:batch_size]
    else:
        wanted = pair_key(*pair)
        batch = [
            c for c in queue.pending if pair_key(c.a.frontmatter.id, c.b.frontmatter.id) == wanted
        ]
        if not batch:
            note = (
                f"{pair[0]} and {pair[1]} are not waiting for a verdict: they were already "
                "judged, a person dismissed the pair, or the two are not related."
            )
    pairs = [
        {
            "decision_a": candidate.a.frontmatter.id,
            "decision_b": candidate.b.frontmatter.id,
            "fingerprint": pair_fingerprint(candidate.a, candidate.b),
            "a": {
                "context": candidate.a.frontmatter.context or "",
                "choice": candidate.a.frontmatter.choice or "",
            },
            "b": {
                "context": candidate.b.frontmatter.context or "",
                "choice": candidate.b.frontmatter.choice or "",
            },
        }
        for candidate in batch
    ]
    task: dict[str, Any] = {
        "instructions": JUDGE_SYSTEM_PROMPT
        + _ANSWER
        + (_NEXT_BATCH if pair is None else _ONE_PAIR),
        "pairs": pairs,
        "returned": len(pairs),
        "pending": len(queue.pending),
        "already_judged": queue.already_judged,
        "dismissed": queue.dismissed,
    }
    if note:
        task["note"] = note
    return task


def submit_verdicts(
    root: Path,
    answers: Sequence[Mapping[str, Any]],
    judged_by: str,
    *,
    embedder: Embedder,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Validate an agent's verdicts and store the ones that match a pair still pending.

    A pair that was already judged, dismissed, edited since the task or never shortlisted is
    rejected with a reason, never stored: a verdict is only ever scoped to the text it judged.
    """
    judged_by = judged_by.strip()
    if not judged_by:
        return {"recorded": 0, "conflicts": 0, "rejected": ["judged_by is required"]}
    pending = {
        pair_key(candidate.a.frontmatter.id, candidate.b.frontmatter.id): candidate
        for candidate in pending_pairs(root, embedder=embedder).pending
    }
    verdicts = load_verdicts(root)
    rejected: list[str] = []
    recorded = conflicts = 0
    for entry in answers:
        a_id, b_id = str(entry.get("decision_a", "")), str(entry.get("decision_b", ""))
        label = f"{a_id} <-> {b_id}"
        key = pair_key(a_id, b_id)
        candidate = pending.get(key)
        if candidate is None:
            rejected.append(f"{label}: not a pair awaiting a verdict (judged, dismissed or edited)")
            continue
        if entry.get("fingerprint") != pair_fingerprint(candidate.a, candidate.b):
            rejected.append(f"{label}: the decisions changed since the task (or no fingerprint)")
            continue
        try:
            answer = JudgeAnswer.model_validate(
                {name: entry.get(name) for name in JudgeAnswer.model_fields}
            ).linted()
        except ValidationError as exc:
            rejected.append(f"{label}: invalid answer ({exc.errors()[0]['loc']})")
            continue
        verdicts[key] = StoredVerdict(
            **answer.model_dump(),
            decision_a=candidate.a.frontmatter.id,
            decision_b=candidate.b.frontmatter.id,
            fingerprint=pair_fingerprint(candidate.a, candidate.b),
            model=judged_by,
            judged_at=now(),
        )
        del pending[key]
        recorded += 1
        conflicts += 1 if answer.is_conflict else 0
    if recorded:
        write_verdicts(root, verdicts)
    return {
        "recorded": recorded,
        "conflicts": conflicts,
        "rejected": rejected,
        "remaining": len(pending),
    }
