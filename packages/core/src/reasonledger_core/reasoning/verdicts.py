"""Judged related pairs — what a model concluded, reused until either decision changes.

The file is **committable on purpose**, beside ``dismissed.yml``: a verdict costs a
model call, so one developer pays for it and teammates and CI reuse it by clone.
That is also what keeps ``check-decisions`` deterministic: CI never calls a model,
it reads the verdicts already committed.

A verdict is scoped to the text it judged, with the same fingerprint dismissals use
(each decision's id, context and choice). Edit either decision and the pair is
unjudged again, so an old "compatible" can never hide a new contradiction.

Model output is linted for PII before it is written; a flagged sentence is replaced
rather than committed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.models.reasoning import Conflict, ConflictVerdict, Severity
from reasonledger_core.privacy.pii_linter import lint_text
from reasonledger_core.reasoning.conflict_config import effective_conflict_config
from reasonledger_core.reasoning.dismissals import pair_fingerprint, pair_key
from reasonledger_core.reasoning.embeddings import Embedder
from reasonledger_core.reasoning.related import Candidate, VerdictSource, relate_decisions

VERDICTS_PATH = Path(".reasonledger/verdicts.yml")
VERDICTS_VERSION = "1"
PII_WITHHELD = "(withheld: the model's wording failed the PII lint)"


class VerdictsError(ValueError):
    """Raised when the verdict file is malformed."""


class JudgeAnswer(BaseModel):
    """A judge's answer about one pair, as the model returns it."""

    same_question: bool
    compatible: bool
    question: str
    reason: str
    severity: Severity

    @property
    def is_conflict(self) -> bool:
        return self.same_question and not self.compatible

    def to_verdict(self, *, score: float) -> ConflictVerdict:
        explanation = f"{self.question} — {self.reason}" if self.is_conflict else self.reason
        return ConflictVerdict(
            is_conflict=self.is_conflict,
            severity=self.severity if self.is_conflict else Severity.LOW,
            explanation=explanation,
            score=round(score, 6),
        )

    def linted(self) -> JudgeAnswer:
        """The same answer with any sentence that trips the PII linter withheld."""
        return self.model_copy(
            update={
                "question": PII_WITHHELD if lint_text(self.question) else self.question,
                "reason": PII_WITHHELD if lint_text(self.reason) else self.reason,
            }
        )


class StoredVerdict(JudgeAnswer):
    """A judged pair as committed to ``verdicts.yml``."""

    decision_a: str
    decision_b: str
    fingerprint: str
    model: str
    judged_at: datetime


def load_verdicts(root: Path) -> dict[str, StoredVerdict]:
    """Verdicts keyed by ``pair_key``; empty when the file is absent."""
    path = root / VERDICTS_PATH
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise VerdictsError(f"cannot read {VERDICTS_PATH}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("verdicts", []), list):
        raise VerdictsError(f"{VERDICTS_PATH} must be a mapping with a `verdicts` list")
    try:
        entries = [StoredVerdict.model_validate(item) for item in raw.get("verdicts", [])]
    except ValidationError as exc:
        raise VerdictsError(f"invalid entry in {VERDICTS_PATH}: {exc}") from exc
    return {pair_key(entry.decision_a, entry.decision_b): entry for entry in entries}


def effective_verdicts(root: Path) -> dict[str, StoredVerdict]:
    """Verdicts for read-only surfaces. Never raises.

    A malformed file must not break `status` or the UI; its pairs read as unjudged,
    and `reasonledger judge` (the write path) surfaces the parse error.
    """
    try:
        return load_verdicts(root)
    except VerdictsError:
        return {}


def write_verdicts(root: Path, verdicts: Mapping[str, StoredVerdict]) -> Path:
    """Write every verdict, sorted by pair for a stable diff."""
    path = root / VERDICTS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": VERDICTS_VERSION,
        "verdicts": [verdicts[key].model_dump(mode="json") for key in sorted(verdicts)],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), "utf-8")
    return path


def stored_verdict_source(verdicts: Mapping[str, StoredVerdict]) -> VerdictSource:
    """Look up a candidate's verdict, ignoring one judged on different text."""

    def verdict(candidate: Candidate) -> ConflictVerdict | None:
        a_id, b_id = candidate.a.frontmatter.id, candidate.b.frontmatter.id
        stored = verdicts.get(pair_key(a_id, b_id))
        if stored is None or stored.fingerprint != pair_fingerprint(candidate.a, candidate.b):
            return None
        return stored.to_verdict(score=candidate.context_similarity).model_copy(
            update={"judged_by": stored.model, "judged_at": stored.judged_at}
        )

    return verdict


def relate_in_repo(
    root: Path,
    records: Sequence[DecisionRecord],
    *,
    embedder: Embedder,
    verdicts: VerdictSource | None = None,
) -> list[Conflict]:
    """Related pairs under this repo's shortlist settings and committed verdicts.

    The one entry point `status`, the UI, `import` and `check-decisions` share, so
    they cannot disagree about which pairs exist or what is known about them.
    ``verdicts`` replaces the committed file (tests, replayed fixtures).
    """
    cfg = effective_conflict_config(root)
    return relate_decisions(
        records,
        verdicts=verdicts or stored_verdict_source(effective_verdicts(root)),
        embedder=embedder,
        k=cfg.shortlist_k,
        min_context_similarity=cfg.context_similarity_gate,
    )
