"""Tooling: deploy, scripts and maintenance code, gathered into one platform-side module."""

from __future__ import annotations

from collections.abc import Sequence

from reasonledger_core.modules.config import MIN_MODULE_FILES, TOOLING_MODULE_ID
from reasonledger_core.modules.files import is_support, is_tooling
from reasonledger_core.modules.models import Candidate, SignalKind


def tooling_candidates(files: Sequence[str]) -> list[Candidate]:
    """One candidate holding every tooling file; it folds into ``platform`` when there is one."""
    members = frozenset(p for p in files if is_tooling(p) and not is_support(p))
    if len(members) < MIN_MODULE_FILES:
        return []
    return [
        Candidate(
            name=TOOLING_MODULE_ID.title(),
            id_hint=TOOLING_MODULE_ID,
            signal=SignalKind.TOOLING,
            files=members,
            description="Build, deploy and maintenance code",
        )
    ]
