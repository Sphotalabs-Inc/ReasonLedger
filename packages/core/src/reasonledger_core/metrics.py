"""Opt-in local pilot metrics. Metrics never leave the local machine."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from enum import StrEnum
from pathlib import Path

import yaml

METRICS_PATH = Path(".reasonledger/metrics.jsonl")
METRICS_CONFIG_PATH = Path(".reasonledger/config.yml")
METRICS_ENV_VAR = "RL_METRICS"
type MetricValue = str | int
_ALLOWED_VALUES = {
    "source": frozenset({"recorded", "harvested", "doc-import", "commit-import"}),
    "match": frozenset({"symbol", "line", "moved", "file", "lost", "near", "miss"}),
    "severity": frozenset({"low", "medium", "high"}),
}
# `pair` cannot be an enumerated allow-list, so it is shape-constrained instead:
# two decision ids and nothing else. Decision ids are generated hashes, never
# user text, so this stays inside the "no free text in metrics" rule.
_PAIR_RE = re.compile(r"^dec_[a-z0-9]+::dec_[a-z0-9]+$")


class MetricEvent(StrEnum):
    DECISION_RECORDED = "decision_recorded"
    WHY_INVOKED = "why_invoked"
    CONFLICT_SURFACED = "conflict_surfaced"
    CONFLICT_DISMISSED = "conflict_dismissed"


def metrics_enabled_in_repo(root: Path) -> bool:
    """Whether ``.reasonledger/config.yml`` opts this repo into local metrics.

    Never raises and never propagates a parse error: a malformed config must not take
    down the command a developer was actually running.
    """
    path = root / METRICS_CONFIG_PATH
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    return isinstance(data, dict) and data.get("metrics") is True


def metrics_enabled(root: Path | None = None) -> bool:
    """Whether this process may write local pilot metrics.

    Two ways in, because one was not enough. The env var alone required
    ``RL_METRICS=1`` to be set in *every* process that emits — the developer's shell for
    `why`/`status`, and separately the environment an editor spawns the MCP server in.
    Miss the second and `record_decision` silently records nothing, which reads as "the
    agent never captures anything" rather than "the meter is off". The repo-level flag is
    committed, shared with the team, and independent of how a process was launched.

    Metrics stay opt-in either way: absent config and unset env means off, and nothing
    written here ever leaves the machine.
    """
    if os.environ.get(METRICS_ENV_VAR) == "1":
        return True
    return root is not None and metrics_enabled_in_repo(root)


def _payload(event: MetricEvent, fields: Mapping[str, MetricValue]) -> dict[str, MetricValue]:
    """The allow-listed subset of ``fields``; everything else is dropped, never logged."""
    payload: dict[str, MetricValue] = {"event": event.value}
    for key, value in fields.items():
        allowed_value = key in _ALLOWED_VALUES and value in _ALLOWED_VALUES[key]
        is_count = key == "count" and isinstance(value, int) and not isinstance(value, bool)
        is_pair = key == "pair" and isinstance(value, str) and bool(_PAIR_RE.match(value))
        if allowed_value or is_count or is_pair:
            payload[key] = value
    return payload


def _append(root: Path, payloads: list[dict[str, MetricValue]]) -> None:
    """Append every payload in one write, so a batch costs one open and stays line-atomic."""
    chunk = "".join(json.dumps(payload, sort_keys=True) + "\n" for payload in payloads)
    try:
        path = root / METRICS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(chunk)
    except OSError:
        return


def emit(root: Path, event: MetricEvent, **fields: MetricValue) -> None:
    """Append one allow-listed event, or silently no-op when disabled or unwritable."""
    if not metrics_enabled(root):
        return
    _append(root, [_payload(event, fields)])


def load_metrics(root: Path) -> list[dict[str, MetricValue]]:
    """Read valid local metric events; corrupt lines are ignored."""
    try:
        lines = (root / METRICS_PATH).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, MetricValue]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("event"), str):
            events.append(
                {
                    key: value
                    for key, value in payload.items()
                    if key in {"event", "count", "pair"} or key in _ALLOWED_VALUES
                }
            )
    return events


def emit_once(root: Path, event: MetricEvent, *, pair: str, **fields: MetricValue) -> None:
    """Emit an event at most once per pair, ever.

    Some events describe a *thing* rather than an *action*: a surfaced conflict is
    the same conflict whether the view is built once or fifty times. Counting it per
    build inflates the denominator of the dismissal rate without bound, which would
    make a noisy detector look quiet — the exact failure the pilot exists to catch.
    """
    emit_once_many(root, event, [(pair, fields)])


def emit_once_many(
    root: Path, event: MetricEvent, entries: Iterable[tuple[str, Mapping[str, MetricValue]]]
) -> None:
    """`emit_once` for many ``(pair, fields)`` entries, reading the log once.

    The log is the source of truth for "already emitted", so a one-off scan per call
    was the original design. Called once per surfaced pair from a view build, that scan
    re-parsed the whole file every time and made a build quadratic in its own output
    (500 decisions took 13s). Reading it once and tracking what this batch adds keeps
    the log authoritative across processes while making a build linear. The scan is
    skipped altogether when there is nothing to emit.
    """
    pending = list(entries)
    if not pending or not metrics_enabled(root):
        return
    seen = {
        existing.get("pair") for existing in load_metrics(root) if existing["event"] == event.value
    }
    payloads: list[dict[str, MetricValue]] = []
    for pair, fields in pending:
        if pair in seen:
            continue
        seen.add(pair)
        payloads.append(_payload(event, {**fields, "pair": pair}))
    if payloads:
        _append(root, payloads)


def metric_counts(events: list[dict[str, MetricValue]]) -> Counter[str]:
    """Aggregate event counts, respecting a conflict event's optional count."""
    counts: Counter[str] = Counter()
    for event in events:
        name = event["event"]
        if not isinstance(name, str):
            continue
        raw_count = event.get("count", 1)
        count = raw_count if isinstance(raw_count, int) and not isinstance(raw_count, bool) else 1
        counts[name] += count
    return counts
