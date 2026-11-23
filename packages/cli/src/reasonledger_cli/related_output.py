"""One wording for related decisions across `import`, `catchup` and `judge` output."""

from __future__ import annotations

from reasonledger_core.models.reasoning import Conflict, Relation

JUDGE_HINT = (
    "run `reasonledger judge`, or ask your coding agent to call get_judging_task, "
    "to check them for conflicts"
)


def print_related_summary(pairs: list[Conflict]) -> None:
    """Judged conflicts in full; the rest of the shortlist as a count."""
    conflicts = [pair for pair in pairs if pair.relation is Relation.CONFLICT]
    unjudged = sum(1 for pair in pairs if pair.relation is Relation.UNVERIFIED)
    related = len(pairs) - len(conflicts)
    if conflicts:
        print("conflicts (judged: same question, answers clash):")
        for conflict in conflicts:
            print(
                f"  {conflict.decision_a} <-> {conflict.decision_b} "
                f"({conflict.severity.value}): {conflict.explanation}"
            )
    if not related:
        print("related decisions: none")
        return
    note = f" — {unjudged} not judged yet; {JUDGE_HINT}" if unjudged else ""
    print(f"related decisions: {related}{note}")
