"""Staleness watchers — Dependabot-for-decisions.

Conditions declared in a decision's ``watchers:`` frontmatter are evaluated
against customer-supplied source values. A breach flags the decision stale and
produces a PR draft that flips its status. Watcher state is fully rebuildable
from the canonical ``.md`` + the current source values (no hidden state).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from reasonledger_core.decisions.format import decision_filename, render_decision_markdown
from reasonledger_core.models.decision import DecisionRecord, DecisionStatus
from reasonledger_core.models.reasoning import (
    PullRequestDraft,
    Watcher,
    WatcherCondition,
    WatcherEvent,
    WatcherStatus,
)
from reasonledger_core.reasoning.config import WATCHER_DRIFT_MARGIN

_CONDITION_RE = re.compile(
    r"^\s*(?P<metric>[A-Za-z_][\w.]*)\s*(?P<op>>=|<=|==|!=|>|<)\s*(?P<value>-?\d+(?:\.\d+)?)\s*$"
)

_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class WatcherConditionError(ValueError):
    """Raised when a watcher condition string cannot be parsed."""


def parse_condition(raw: str) -> WatcherCondition:
    match = _CONDITION_RE.match(raw)
    if match is None:
        raise WatcherConditionError(f"unparseable watcher condition: {raw!r}")
    return WatcherCondition(
        raw=raw.strip(),
        metric=match.group("metric"),
        op=match.group("op"),
        threshold=float(match.group("value")),
    )


def _status_for(condition: WatcherCondition, value: float) -> WatcherStatus:
    holds = _OPS[condition.op](value, condition.threshold)
    if not holds:
        return WatcherStatus.STALE
    margin = abs(condition.threshold) * WATCHER_DRIFT_MARGIN
    if condition.op in {">=", ">"} and value <= condition.threshold + margin:
        return WatcherStatus.DRIFTING
    if condition.op in {"<=", "<"} and value >= condition.threshold - margin:
        return WatcherStatus.DRIFTING
    return WatcherStatus.HEALTHY


def rebuild_watchers(
    record: DecisionRecord,
    source_values: Mapping[str, float],
) -> list[Watcher]:
    """Deterministically derive watcher state from the decision + source values."""
    watchers: list[Watcher] = []
    for raw in record.frontmatter.watchers:
        condition = parse_condition(raw)
        value = source_values.get(condition.metric)
        status = WatcherStatus.HEALTHY if value is None else _status_for(condition, value)
        watchers.append(
            Watcher(
                decision_id=record.frontmatter.id,
                condition=condition.raw,
                metric=condition.metric,
                status=status,
                last_value=value,
            )
        )
    return watchers


def breached_watchers(watchers: Sequence[Watcher]) -> list[Watcher]:
    return [watcher for watcher in watchers if watcher.status == WatcherStatus.STALE]


def watcher_event(watcher: Watcher, previous: WatcherStatus) -> WatcherEvent:
    return WatcherEvent(
        decision_id=watcher.decision_id,
        condition=watcher.condition,
        value=watcher.last_value if watcher.last_value is not None else 0.0,
        transition=f"{previous.value}->{watcher.status.value}",
    )


def build_stale_pr(record: DecisionRecord, watcher: Watcher) -> PullRequestDraft:
    """Produce the PR intent that flips a breached decision to ``stale``."""
    updated = record.model_copy(deep=True)
    status_from = record.frontmatter.status.value
    updated.frontmatter.status = DecisionStatus.STALE
    decision_id = record.frontmatter.id
    return PullRequestDraft(
        decision_id=decision_id,
        title=f"chore(decisions): mark {decision_id} stale (assumption breached)",
        branch=f"reasonledger/stale/{decision_id}",
        body=(
            f"Watcher `{watcher.condition}` breached (last value "
            f"{watcher.last_value}). Marking decision `{decision_id}` stale for review."
        ),
        status_from=status_from,
        status_to=DecisionStatus.STALE.value,
        file_path=f".reasonledger/decisions/{decision_filename(decision_id)}",
        new_markdown=render_decision_markdown(updated),
    )
