"""Proposal and conflict endpoints for `reasonledger ui`: confirm, reject, dismiss.

Who confirmed or dismissed comes from `ui_identity`, never from the request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename
from reasonledger_core.importer.propose import (
    PROPOSED_DIR,
    ImportConfirmError,
    confirm_proposed,
)
from reasonledger_core.reasoning.dismissals import (
    DismissalError,
    add_dismissal,
    pair_fingerprint,
)
from reasonledger_core.sync.repo import git_user_name

from reasonledger_cli.ui_identity import JsonResponse, NoIdentityError, acting_as


def handle_confirm(root: Path, decision_id: str) -> JsonResponse:
    """POST /api/proposals/<id>/confirm — promote a proposal into the ledger."""
    try:
        record = confirm_proposed(
            decision_id,
            root=root,
            confirmed_by=acting_as(root),
            confirmed_at=datetime.now(UTC),
        )
    except ImportConfirmError:
        return 404, {"error": "unknown id"}
    except NoIdentityError as exc:
        return 400, {"error": str(exc)}
    return 200, {"id": record.frontmatter.id, "status": record.frontmatter.status.value}


def handle_reject(root: Path, decision_id: str) -> JsonResponse:
    """POST /api/proposals/<id>/reject — delete a staged proposal."""
    path = root / PROPOSED_DIR / decision_filename(decision_id)
    if not path.is_file():
        return 404, {"error": "unknown id"}
    path.unlink()
    # No CONFLICT_DISMISSED: rejecting a proposal is not dismissing a conflict.
    # See run_reject_cmd in status_cmd.py.
    return 200, {"id": decision_id, "rejected": True}


def handle_dismiss(
    root: Path, body: dict[str, Any], decision_a: str, decision_b: str
) -> JsonResponse:
    """POST /api/dismiss — record that a judged conflict between two decisions is not real."""
    if decision_a == decision_b:
        return 400, {"error": "a decision cannot conflict with itself"}
    reason = body.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return 400, {"error": "reason required"}
    # Scope the verdict to the text it judged, exactly as `reasonledger dismiss`
    # does — a dismissal made here must not outlive an edit to either decision.
    records = load_decisions_from_dir(root / DECISIONS_DIR)
    records += load_decisions_from_dir(root / PROPOSED_DIR)
    by_id = {record.frontmatter.id: record for record in records}
    left, right = by_id.get(decision_a), by_id.get(decision_b)
    if left is None or right is None:
        return 404, {"error": "unknown id"}
    try:
        entry, _created = add_dismissal(
            root,
            decision_a=decision_a,
            decision_b=decision_b,
            reason=reason,
            dismissed_by=git_user_name(root),
            dismissed_at=datetime.now(UTC),
            fingerprint=pair_fingerprint(left, right),
        )
    except DismissalError as exc:
        return 400, {"error": str(exc)}
    return 200, {"pair": entry.pair, "reason": entry.reason}
