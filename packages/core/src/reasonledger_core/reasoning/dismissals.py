"""Dismissed conflict pairs — the human verdict on a similarity hint.

Conflict detection produces *hints*, not verdicts. A hint the reviewer has judged
wrong must stop being reported, or it nags on every ``status`` call until the
reviewer stops reading conflicts altogether — which is how a noisy detector
destroys the feature it belongs to.

The file is **committable on purpose**. A teammate's dismissal is shared the same way a
decision is: reviewed in the PR that introduces it and distributed by clone. One person
triages a false positive once, and nobody on the team sees it again.

Dismissals are also the pilot's ground truth for conflict quality: the rate at
which surfaced hints get dismissed is what the 5-pair smoke test cannot measure.

**A dismissal is scoped to the content it judged.** The reviewer's verdict was
"these two decisions, as they read today, do not contradict each other" — not "this
pair of ids may never conflict again". So each entry carries a fingerprint of the
classifier's inputs, and a dismissal stops applying once either decision's
``context`` or ``choice`` changes. Without that, editing a decision into a genuine
contradiction would be silently suppressed by an old dismissal — the worst failure
available to a tool that claims to be evidence-grade.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.privacy.pii_linter import lint_text

DISMISSED_PATH = Path(".reasonledger/dismissed.yml")
DISMISSED_VERSION = "1"

_FINGERPRINT_LENGTH = 32
_FIELD_SEPARATOR = "\x1f"
_RECORD_SEPARATOR = "\x1e"


class DismissalError(ValueError):
    """Raised when the dismissal file is malformed or an entry is invalid."""


class Dismissal(BaseModel):
    """One reviewer verdict that a surfaced conflict is not a real conflict."""

    pair: str = Field(description="Unordered pair key, e.g. dec_aaa::dec_bbb")
    reason: str = Field(description="Why this hint is wrong — required, and reviewable")
    dismissed_by: str | None = None
    dismissed_at: datetime | None = None
    fingerprint: str | None = Field(
        default=None,
        description=(
            "Content fingerprint of the two decisions when dismissed. Absent on entries "
            "written before fingerprinting existed; those keep suppressing unconditionally."
        ),
    )


def pair_key(decision_a: str, decision_b: str) -> str:
    """Order-independent key for a conflict pair.

    Conflict ordering is an implementation detail of the detector; a dismissal must
    survive the pair being reported the other way round.
    """
    return "::".join(sorted((decision_a, decision_b)))


def pair_fingerprint(a: DecisionRecord, b: DecisionRecord) -> str:
    """Fingerprint the two decisions' *classifier inputs*, order-independently.

    Deliberately narrow: only ``context`` and ``choice`` are read by
    ``conflicts.classify_pair``, so fixing a typo in a decision body must not
    resurrect a settled dismissal, while changing what was actually decided must.
    """
    parts = sorted(
        _FIELD_SEPARATOR.join(
            (
                record.frontmatter.id,
                record.frontmatter.context or "",
                record.frontmatter.choice or "",
            )
        )
        for record in (a, b)
    )
    digest = hashlib.sha256(_RECORD_SEPARATOR.join(parts).encode("utf-8")).hexdigest()
    return digest[:_FINGERPRINT_LENGTH]


def dismissal_still_applies(stored: str | None, current: str | None) -> bool:
    """Whether a recorded dismissal still covers the pair's current content.

    Both unknown cases resolve to "keep suppressing". A legacy entry predates
    fingerprinting, and an uncomputable fingerprint means a decision is missing —
    neither is evidence that the reviewer's judgement went stale, and re-surfacing
    on a guess is exactly the nagging the dismissal file exists to prevent.
    """
    if stored is None or current is None:
        return True
    return stored == current


def load_dismissals(root: Path) -> list[Dismissal]:
    """Read dismissals, or return [] when absent. Raises only on malformed content."""
    path = root / DISMISSED_PATH
    if not path.is_file():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DismissalError(f"cannot read {DISMISSED_PATH}: {exc}") from exc
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise DismissalError(f"{DISMISSED_PATH} must be a mapping")
    entries = raw.get("dismissed") or []
    if not isinstance(entries, list):
        raise DismissalError(f"{DISMISSED_PATH}: 'dismissed' must be a list")
    try:
        return [Dismissal.model_validate(entry) for entry in entries]
    except Exception as exc:
        raise DismissalError(f"{DISMISSED_PATH}: invalid entry: {exc}") from exc


def dismissed_fingerprints(root: Path) -> dict[str, str | None]:
    """Pair key -> the content fingerprint it was dismissed against (None = legacy).

    Read by every view build and every CI gate run, so a malformed file must not
    take down `status`. `reasonledger dismiss` surfaces the parse error instead.
    """
    try:
        return {entry.pair: entry.fingerprint for entry in load_dismissals(root)}
    except DismissalError:
        return {}


def dismissed_keys(root: Path) -> set[str]:
    """Pair keys the team has dismissed, ignoring content drift. Never raises.

    Callers that can resolve both decisions should prefer `dismissed_fingerprints`
    so an edited decision stops being suppressed by a stale verdict.
    """
    return set(dismissed_fingerprints(root))


def write_dismissals(root: Path, entries: list[Dismissal]) -> Path:
    """Write the dismissal file, sorted by pair for a stable diff."""
    path = root / DISMISSED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": DISMISSED_VERSION,
        "dismissed": [
            entry.model_dump(mode="json", exclude_none=True)
            for entry in sorted(entries, key=lambda item: item.pair)
        ],
    }
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def add_dismissal(
    root: Path,
    *,
    decision_a: str,
    decision_b: str,
    reason: str,
    dismissed_by: str | None = None,
    dismissed_at: datetime | None = None,
    fingerprint: str | None = None,
) -> tuple[Dismissal, bool]:
    """Record a dismissal. Returns (entry, recorded).

    Re-dismissing the same pair *on unchanged content* is a no-op. Re-dismissing it
    after either decision's context/choice moved replaces the entry: the reviewer is
    passing a fresh judgement on different text, and that judgement — not the stale
    one — is what should be committed and shared. Without this, a re-opened conflict
    could never be settled again.

    The reason is PII-linted like any other free text a human types into the
    ledger — a dismissal is committed and shared, so it is exactly as exposed as
    a decision body.
    """
    text = reason.strip()
    if not text:
        raise DismissalError("a dismissal needs a reason — an unexplained one cannot be reviewed")
    findings = lint_text(text, allow_emails={dismissed_by} if dismissed_by else None)
    if findings:
        rules = ", ".join(sorted({finding.rule_id for finding in findings}))
        raise DismissalError(f"dismissal reason contains disallowed PII ({rules})")

    key = pair_key(decision_a, decision_b)
    entries = load_dismissals(root)
    entry = Dismissal(
        pair=key,
        reason=text,
        dismissed_by=dismissed_by,
        dismissed_at=dismissed_at,
        fingerprint=fingerprint,
    )
    existing = next((item for item in entries if item.pair == key), None)
    if existing is not None:
        if dismissal_still_applies(existing.fingerprint, fingerprint):
            return existing, False
        entries = [entry if item.pair == key else item for item in entries]
        write_dismissals(root, entries)
        return entry, True

    entries.append(entry)
    write_dismissals(root, entries)
    return entry, True
