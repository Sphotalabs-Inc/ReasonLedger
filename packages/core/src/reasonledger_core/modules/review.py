"""The confirm queue: which proposals a person sees first, and how many at a time."""

from __future__ import annotations

from collections.abc import Mapping

from reasonledger_core.modules.config import PENDING_QUEUE_CAP
from reasonledger_core.modules.models import Confidence, Manifest, Module, ModuleStatus

_CONFIDENCE_ORDER = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2, None: 3}


def pending_queue(manifest: Manifest, file_counts: Mapping[str, int]) -> list[Module]:
    """Every proposed module, most trusted first, then the larger, then by id (a stable order)."""
    proposed = [m for m in manifest.capabilities if m.status is ModuleStatus.PROPOSED]
    return sorted(
        proposed, key=lambda m: (_CONFIDENCE_ORDER[m.confidence], -file_counts.get(m.id, 0), m.id)
    )


def next_up(queue: list[Module]) -> tuple[list[Module], int]:
    """The proposals to show now (at most ``PENDING_QUEUE_CAP``) and how many wait behind them."""
    return queue[:PENDING_QUEUE_CAP], max(0, len(queue) - PENDING_QUEUE_CAP)
