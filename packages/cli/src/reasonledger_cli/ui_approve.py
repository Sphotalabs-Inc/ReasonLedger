"""Decision endpoints for `reasonledger ui` — the UI doors onto `approve`, `retire`, `supersede`.

Each door calls the same core function as its CLI command, so the UI cannot grant a verdict
the CLI would refuse (a decision that already has one stays as it is). Only `reviewed` is
offered for approval: a person reading a pending record in the browser can vouch for it,
while `modified` and `rejected` change what the ledger asserts and stay with the CLI until
the UI can edit. Who acted comes from `ui_identity`, never from the request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from reasonledger_core.decisions.format import DECISIONS_DIR, decision_filename
from reasonledger_core.decisions.lifecycle import (
    RetireError,
    retire_decision,
    supersede_decision,
)
from reasonledger_core.decisions.service import ApproveError, approve_decision
from reasonledger_core.models.decision import DecisionOversight
from reasonledger_core.privacy.pii_linter import PiiLintError

from reasonledger_cli.ui_identity import JsonResponse, NoIdentityError, acting_as


def _approve(root: Path, decision_id: str, _body: dict[str, Any]) -> JsonResponse:
    """A person's `reviewed` verdict on a pending record."""
    record = approve_decision(
        decision_id,
        root=root,
        verdict=DecisionOversight.REVIEWED,
        approved_by=acting_as(root),
        approved_at=datetime.now(UTC),
    )
    return 200, {
        "id": record.frontmatter.id,
        "oversight": record.frontmatter.oversight.value,
        "approved_by": record.frontmatter.approved_by,
    }


def _retire(root: Path, decision_id: str, body: dict[str, Any]) -> JsonResponse:
    """Take a decision out of force, with the reason it no longer applies."""
    reason = body.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return 400, {"error": "reason required"}
    record = retire_decision(
        decision_id,
        root=root,
        retired_by=acting_as(root),
        retired_at=datetime.now(UTC),
        reason=reason,
    )
    return 200, {
        "id": record.frontmatter.id,
        "status": record.frontmatter.status.value,
        "retired_by": record.frontmatter.retired_by,
    }


def _supersede(root: Path, decision_id: str, body: dict[str, Any]) -> JsonResponse:
    """A person chose the other decision of a pair: this one becomes superseded by it."""
    reason, successor = body.get("reason"), body.get("successor")
    if not isinstance(reason, str) or not reason.strip():
        return 400, {"error": "reason required"}
    if not isinstance(successor, str) or not successor.strip():
        return 400, {"error": "successor required"}
    record = supersede_decision(
        decision_id,
        successor_id=successor.strip(),
        root=root,
        decided_by=acting_as(root),
        superseded_at=datetime.now(UTC),
        reason=reason,
    )
    return 200, {
        "id": record.frontmatter.id,
        "status": record.frontmatter.status.value,
        "superseded_by": record.frontmatter.superseded_by,
        "superseded_decided_by": record.frontmatter.superseded_decided_by,
    }


_ACTIONS = {"approve": _approve, "retire": _retire, "supersede": _supersede}


def handle_decision_action(
    root: Path, decision_id: str, action: str, body: dict[str, Any]
) -> JsonResponse:
    """POST /api/decisions/<id>/<action> for a decision already in the ledger."""
    handler = _ACTIONS.get(action)
    if handler is None:
        return 404, {"error": "not found"}
    if not (root / DECISIONS_DIR / decision_filename(decision_id)).is_file():
        return 404, {"error": "unknown id"}
    try:
        return handler(root, decision_id, body)
    except (ApproveError, RetireError, PiiLintError, NoIdentityError) as exc:
        return 400, {"error": str(exc)}
