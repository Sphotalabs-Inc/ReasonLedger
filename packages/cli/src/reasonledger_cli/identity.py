"""Who a person-facing command acts as: the flag when given, else the checkout's git identity.

Every command that records a human verdict (approve, retire, confirm, modules confirm|place)
resolves the name here, so the rule is written once.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reasonledger_core.sync.repo import git_user_name

BY_HELP = "Who is acting, recorded as evidence (default: this checkout's git user.name)"


def no_identity_message(flag: str) -> str:
    return f"no {flag} given and git has no user.name for this checkout; pass {flag} <you>"


def resolve_identity(root: Path, given: str | None) -> str | None:
    """``given`` when set, else the checkout's git identity, else None."""
    return (given or "").strip() or git_user_name(root)


def acting_identity(root: Path, given: str | None, *, flag: str = "--by") -> str | None:
    """``resolve_identity``, printing why when there is neither."""
    who = resolve_identity(root, given)
    if who is None:
        print(f"error: {no_identity_message(flag)}", file=sys.stderr)
    return who
