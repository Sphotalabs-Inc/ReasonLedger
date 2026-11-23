"""Conflict gate for decision records in continuous integration.

Fails only on pairs a judge called conflicts, read from the committed
``verdicts.yml``: CI never calls a model, and a similarity hint alone is not
evidence enough to fail a build. Unjudged pairs touching new decisions warn.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename
from reasonledger_core.decisions.identity_check import identity_mismatches
from reasonledger_core.models.decision import (
    OUT_OF_FORCE,
    DecisionOversight,
    DecisionRecord,
)
from reasonledger_core.models.reasoning import Conflict, Relation, Severity
from reasonledger_core.reasoning import CachingEmbedder, relate_in_repo
from reasonledger_core.reasoning.conflict_config import resolve_conflict_embedder_with_status
from reasonledger_core.reasoning.dismissals import (
    dismissal_still_applies,
    dismissed_fingerprints,
    pair_fingerprint,
    pair_key,
)
from reasonledger_core.sync import decision_files_added_since

EXIT_PASS = 0
EXIT_FAIL = 1
_SEVERITY_RANK = {Severity.LOW: 1, Severity.MEDIUM: 2, Severity.HIGH: 3}


def _new_ids(records: list[DecisionRecord], root: Path, base: str | None) -> set[str]:
    """Return records newly added since a base, conservatively falling back to all."""
    if base is None:
        return {record.frontmatter.id for record in records}
    filenames = decision_files_added_since(root, base, DECISIONS_DIR)
    if filenames is None:
        return {record.frontmatter.id for record in records}
    return {
        record.frontmatter.id
        for record in records
        if decision_filename(record.frontmatter.id) in filenames
    }


def _is_dismissed(
    conflict: Conflict,
    by_id: dict[str, DecisionRecord],
    dismissed: dict[str, str | None],
) -> bool:
    """Whether a committed dismissal still covers this pair's current content.

    Scoped to the text that was judged, not the id pair: a decision edited into a
    genuine contradiction must fail the build again rather than inherit the silence
    of a verdict passed on its previous wording.
    """
    key = pair_key(conflict.decision_a, conflict.decision_b)
    if key not in dismissed:
        return False
    left, right = by_id.get(conflict.decision_a), by_id.get(conflict.decision_b)
    current = pair_fingerprint(left, right) if left and right else None
    return dismissal_still_applies(dismissed[key], current)


def _relevant_conflicts(
    conflicts: list[Conflict],
    records: list[DecisionRecord],
    new_ids: set[str],
    min_severity: Severity,
    dismissed: dict[str, str | None],
) -> list[Conflict]:
    statuses = {record.frontmatter.id: record.frontmatter.status for record in records}
    by_id = {record.frontmatter.id: record for record in records}
    return [
        conflict
        for conflict in conflicts
        if (conflict.decision_a in new_ids or conflict.decision_b in new_ids)
        and _SEVERITY_RANK[conflict.severity] >= _SEVERITY_RANK[min_severity]
        and statuses.get(conflict.decision_a) not in OUT_OF_FORCE
        and statuses.get(conflict.decision_b) not in OUT_OF_FORCE
        # A hint the team dismissed must not fail the build forever. The dismissal
        # is committed, so the reviewer's call travels with the repo.
        and not _is_dismissed(conflict, by_id, dismissed)
    ]


def _print_conflicts(conflicts: list[Conflict], records: list[DecisionRecord]) -> None:
    choices = {record.frontmatter.id: record.frontmatter.choice or "" for record in records}
    for conflict in conflicts:
        print(
            f"conflict: {conflict.decision_a} <-> {conflict.decision_b} ({conflict.severity.value})"
        )
        print(f"  {conflict.decision_a}: {choices[conflict.decision_a]}")
        print(f"  {conflict.decision_b}: {choices[conflict.decision_b]}")
        print(f"  {conflict.explanation}")


def run_check_decisions(
    *,
    root: Path,
    base: str | None,
    min_severity: str,
    as_json: bool,
    strict_identity: bool = False,
) -> int:
    """Fail when a new decision conflicts with a prior at the requested severity."""
    records = load_decisions_from_dir(root / DECISIONS_DIR)
    new_ids = _new_ids(records, root, base)
    embedder, embedder_status = resolve_conflict_embedder_with_status(root)
    if embedder_status.fallback_reason:
        # stderr, so `--json` output stays parseable while CI logs still show it.
        print(
            f"warning: using basic word matching because {embedder_status.fallback_reason}",
            file=sys.stderr,
        )
    pairs = relate_in_repo(root, records, embedder=CachingEmbedder(embedder, root=root))
    dismissed = dismissed_fingerprints(root)
    judged = [pair for pair in pairs if pair.relation is Relation.CONFLICT]
    relevant = _relevant_conflicts(judged, records, new_ids, Severity(min_severity), dismissed)
    by_id = {record.frontmatter.id: record for record in records}
    unjudged = [
        pair
        for pair in pairs
        if pair.relation is Relation.UNVERIFIED
        and (pair.decision_a in new_ids or pair.decision_b in new_ids)
        and not _is_dismissed(pair, by_id, dismissed)
    ]
    if unjudged:
        print(
            f"warning: {len(unjudged)} related pair(s) touching new decisions are not judged "
            "yet; run `reasonledger judge` and commit .reasonledger/verdicts.yml",
            file=sys.stderr,
        )
    pending = sorted(
        r.frontmatter.id
        for r in records
        if r.frontmatter.id in new_ids and r.frontmatter.oversight is DecisionOversight.PENDING
    )
    if pending:
        print(
            f"warning: {len(pending)} new decision(s) have no human verdict yet "
            f"({', '.join(pending)}); run `reasonledger approve <id>`",
            file=sys.stderr,
        )
    mismatches = identity_mismatches(root, base) if base else []
    for mismatch in mismatches:
        print(f"warning: identity: {mismatch.describe()}", file=sys.stderr)
    if as_json:
        print(
            json.dumps(
                {
                    "base": base,
                    "identity_mismatches": [m.describe() for m in mismatches],
                    "pending_approval": pending,
                    "new_decision_ids": sorted(new_ids),
                    "conflicts": [conflict.model_dump(mode="json") for conflict in relevant],
                    "unjudged": len(unjudged),
                },
                indent=2,
            )
        )
    else:
        _print_conflicts(relevant, records)
    failed = bool(relevant) or (strict_identity and bool(mismatches))
    return EXIT_FAIL if failed else EXIT_PASS
