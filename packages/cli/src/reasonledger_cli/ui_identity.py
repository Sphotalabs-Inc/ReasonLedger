"""Who the local UI records an action as: the checkout's git identity, never the browser's word.

A name typed into a page is a name anyone can type. The server reads ``user.name`` from the
repository it serves and ignores any identity in a request, so an approval made here carries
the same name as the commit that will publish it. There is deliberately no typed fallback:
with no git identity the action is refused and the person is told how to set one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reasonledger_core.sync.repo import git_user_name

JsonResponse = tuple[int, dict[str, Any]]

IDENTITY_SOURCE = "git"
NO_IDENTITY = (
    "git has no user.name for this checkout, so there is nobody to record this as. "
    'Run `git config user.name "Your Name"` and try again.'
)


class NoIdentityError(ValueError):
    """The checkout has no git identity to act as."""

    def __init__(self) -> None:
        super().__init__(NO_IDENTITY)


def acting_as(root: Path) -> str:
    """The git identity for ``root``; raises NoIdentityError when there is none."""
    name = git_user_name(root)
    if name is None:
        raise NoIdentityError
    return name


def handle_get_identity(root: Path) -> JsonResponse:
    """GET /api/identity — the name actions will be recorded under, or how to set one."""
    name = git_user_name(root)
    return 200, {"name": name, "source": IDENTITY_SOURCE, "hint": None if name else NO_IDENTITY}
