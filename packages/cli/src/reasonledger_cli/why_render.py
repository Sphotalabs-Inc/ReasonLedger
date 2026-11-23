"""`reasonledger why` text output: the why, not just the choice."""

from __future__ import annotations

from collections.abc import Sequence

from reasonledger_core.models.decision import OUT_OF_FORCE, DecisionOversight, DecisionStatus
from reasonledger_core.reasoning import MatchKind, Nearby, WhyHit
from reasonledger_core.reasoning.why import WhyTarget, match_rank

REJECTED_SHOWN = 3
FIELD_MAX_CHARS = 400
REJECTED_MAX_CHARS = 200
POINTER_TO_JSON = "… (cut; full text: reasonledger why {target} --json)"
MATCH_NOTES = {
    MatchKind.FILE: " (file-level match)",
    MatchKind.MOVED: " (anchor moved: found by its fingerprint at the lines you asked about)",
    MatchKind.LOST: " (anchor lost: the code it explained cannot be found; file-level match)",
}
COARSE_MATCHES = frozenset({MatchKind.FILE, MatchKind.LOST})
COARSE_CAVEAT = "  note: this decision describes the file, not this line"


def ordered_hits(hits: Sequence[WhyHit]) -> list[WhyHit]:
    """In force first, then the most precise match, then id (stable for diffs)."""
    return sorted(
        hits,
        key=lambda h: (
            h.record.frontmatter.status in OUT_OF_FORCE,
            match_rank(h.match),
            h.record.frontmatter.id,
        ),
    )


def _cut(text: str, limit: int, target: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[:limit].rstrip() + POINTER_TO_JSON.format(target=target)


def _approval(hit: WhyHit) -> str:
    fm = hit.record.frontmatter
    if fm.oversight is DecisionOversight.PENDING:
        return "pending review"
    if fm.approved_by is None:
        return fm.oversight.value
    when = f" on {fm.approved_at.date().isoformat()}" if fm.approved_at else ""
    return f"{fm.approved_by}{when}" + (
        "" if fm.oversight is DecisionOversight.REVIEWED else f" ({fm.oversight.value})"
    )


def _status_lines(hit: WhyHit) -> list[str]:
    fm = hit.record.frontmatter
    lines: list[str] = []
    if fm.status == DecisionStatus.SUPERSEDED:
        successor = (
            f" (superseded by {hit.superseded_by})" if hit.superseded_by else " (superseded)"
        )
        lines.append(f"  status: superseded{successor} — see the successor for current guidance")
        if fm.superseded_reason:
            lines.append(f"  why it was superseded: {fm.superseded_reason}")
    if fm.status == DecisionStatus.RETIRED:
        lines.append(f"  status: retired — no longer guidance ({fm.retired_reason})")
    return lines


def render_hit(hit: WhyHit, target_raw: str, *, short: bool) -> list[str]:
    fm = hit.record.frontmatter
    lines = [f"{fm.id}{MATCH_NOTES.get(hit.match, '')}"]
    if short:
        lines += [f"  choice: {fm.choice}", f"  oversight: {fm.oversight.value}"]
    else:
        lines.append(f"  why: {_cut(fm.context or '', FIELD_MAX_CHARS, target_raw)}")
        lines.append(f"  chose: {_cut(fm.choice or '', FIELD_MAX_CHARS, target_raw)}")
        rejected = fm.alternatives_rejected or []
        if rejected:
            lines.append("  rejected:")
            lines += [
                f"    - {_cut(item, REJECTED_MAX_CHARS, target_raw)}"
                for item in rejected[:REJECTED_SHOWN]
            ]
            if len(rejected) > REJECTED_SHOWN:
                lines.append(f"    … and {len(rejected) - REJECTED_SHOWN} more (--json)")
        lines.append(f"  approved: {_approval(hit)}")
    if hit.match in COARSE_MATCHES:
        lines.append(COARSE_CAVEAT)
    return [*lines, *_status_lines(hit)]


def _asked(target: WhyTarget) -> str:
    if target.line is not None:
        return f"line {target.line}"
    return f"symbol {target.symbol}" if target.symbol else "this place"


def render_miss(target: WhyTarget, nearby: Nearby | None, *, ledger_size: int) -> list[str]:
    """Two cases for a file that exists; a missing file is an error before this is reached."""
    listed = nearby.anchors if nearby else ()
    gone = nearby.out_of_force if nearby else ()
    if nearby is None or (not listed and not gone):
        size = (
            "the ledger is empty"
            if ledger_size == 0
            else f"the ledger holds {ledger_size} decision{'s' if ledger_size != 1 else ''}"
        )
        return [f"No decision names this file ({target.path}); {size}."]
    lines = [f"No decision covers {_asked(target)} of {target.path}, but this file has:"]
    for anchor in listed:
        lines.append(f"  {anchor.decision_id}  {anchor.locus}  [{anchor.status}]")
        lines.append(f"      {anchor.choice}")
        lines.append(f"      try: {anchor.command}")
    notes = []
    if nearby.more:
        notes.append(f"{nearby.more} more in force")
    for status in sorted({a.status for a in gone}):
        notes.append(f"{nearby.count_status(status)} {status}")
    if notes:
        lines.append("  " + ("and " if listed else "") + ", ".join(notes) + " (not listed)")
    return lines
