"""Phase 3 tests for opt-in, local-only pilot metrics."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main
from reasonledger_core.decisions.format import (
    DECISIONS_DIR,
    decision_filename,
    write_decision_file,
)
from reasonledger_core.metrics import (
    METRICS_CONFIG_PATH,
    METRICS_PATH,
    MetricEvent,
    emit,
    emit_once,
    emit_once_many,
    load_metrics,
    metrics_enabled,
)
from reasonledger_core.models.decision import (
    AiTool,
    DecisionFrontmatter,
    DecisionOversight,
    DecisionRecord,
    DecisionStatus,
)
from reasonledger_core.privacy.pii_linter import lint_text
from reasonledger_core.reasoning.embeddings import DeterministicEmbedder
from reasonledger_core.views import build_ledger_view


@pytest.mark.phase_3
def test_metrics_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RL_METRICS", raising=False)

    emit(tmp_path, MetricEvent.WHY_INVOKED, match="symbol")

    assert not (tmp_path / METRICS_PATH).exists()


def _write_config(root: Path, text: str) -> None:
    path = root / METRICS_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.phase_3
def test_repo_flag_enables_metrics_without_the_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The committed flag is what makes an editor-spawned MCP server count.

    Its environment is not ours to set, so an env-var-only opt-in silently records
    nothing there — which reads as "the agent never captures" rather than "the meter
    is off".
    """
    monkeypatch.delenv("RL_METRICS", raising=False)
    _write_config(tmp_path, "metrics: true\nextractor:\n  provider: disabled\n")

    assert metrics_enabled(tmp_path) is True
    emit(tmp_path, MetricEvent.WHY_INVOKED, match="symbol")
    assert len(load_metrics(tmp_path)) == 1


@pytest.mark.phase_3
def test_metrics_stay_off_without_an_explicit_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RL_METRICS", raising=False)
    _write_config(tmp_path, "extractor:\n  provider: disabled\n")
    assert metrics_enabled(tmp_path) is False

    _write_config(tmp_path, "metrics: false\n")
    assert metrics_enabled(tmp_path) is False

    # Malformed config must not raise out of a command that merely wanted to emit.
    _write_config(tmp_path, "metrics: [ this is not: valid: yaml")
    assert metrics_enabled(tmp_path) is False
    emit(tmp_path, MetricEvent.WHY_INVOKED, match="symbol")
    assert not (tmp_path / METRICS_PATH).exists()


@pytest.mark.phase_3
def test_status_metrics_says_disabled_rather_than_printing_zeros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Zeros from a disabled meter are not data, and must not read like data."""
    monkeypatch.delenv("RL_METRICS", raising=False)

    assert main(["status", "--root", str(tmp_path), "--metrics"]) == EXIT_PASS

    output = capsys.readouterr().out
    assert "DISABLED" in output
    assert "decisions recorded" not in output


@pytest.mark.phase_3
def test_metrics_log_is_pii_free(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RL_METRICS", "1")
    emit(tmp_path, MetricEvent.WHY_INVOKED, match="symbol", email="person@example.com")

    line = (tmp_path / METRICS_PATH).read_text("utf-8")
    assert "email" not in line
    assert lint_text(line) == []


@pytest.mark.phase_3
def test_metrics_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RL_METRICS", "1")
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")

    emit(blocked, MetricEvent.WHY_INVOKED, match="symbol")


@pytest.mark.phase_3
def test_status_metrics_summarises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RL_METRICS", "1")
    for source in ("harvested", "harvested", "recorded"):
        emit(tmp_path, MetricEvent.DECISION_RECORDED, source=source)
    emit(tmp_path, MetricEvent.WHY_INVOKED, match="symbol")
    emit(tmp_path, MetricEvent.WHY_INVOKED, match="file")
    emit(tmp_path, MetricEvent.WHY_INVOKED, match="miss")
    # One event per unique pair — the surfaced count is conflicts, not view builds.
    for index in range(4):
        emit(
            tmp_path,
            MetricEvent.CONFLICT_SURFACED,
            pair=f"dec_aaa{index}::dec_bbb{index}",
            severity="high",
        )
    emit(tmp_path, MetricEvent.CONFLICT_DISMISSED, pair="dec_aaa0::dec_bbb0")

    assert main(["status", "--root", str(tmp_path), "--metrics"]) == EXIT_PASS
    output = capsys.readouterr().out
    assert "decisions recorded          3" in output
    assert "why invoked                 3   precise 1 (33%)" in output
    assert "conflicts surfaced          4   dismissed 1 (25%)" in output


@pytest.mark.phase_4
def test_surfaced_counts_pairs_not_view_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rebuilding a view must not inflate the surfaced count.

    This is the property that makes the pilot's dismissal rate readable: if 5
    conflicts viewed 20 times logged 100 surfacings, a detector dismissed 60% of
    the time would report 3% and pass the noise gate it exists to fail.
    """
    monkeypatch.setenv("RL_METRICS", "1")
    for _ in range(20):
        emit_once(
            tmp_path,
            MetricEvent.CONFLICT_SURFACED,
            pair="dec_abc123::dec_def456",
            severity="high",
        )
    surfaced = [
        event
        for event in load_metrics(tmp_path)
        if event["event"] == MetricEvent.CONFLICT_SURFACED.value
    ]
    assert len(surfaced) == 1


def _write_timezone_decisions(root: Path, choices: Sequence[str]) -> None:
    """One decision per choice, all on the same question, so every pair is surfaced."""
    for index, choice in enumerate(choices):
        decision_id = f"dec_tz{index:03d}"
        write_decision_file(
            root / DECISIONS_DIR / decision_filename(decision_id),
            DecisionRecord(
                frontmatter=DecisionFrontmatter(
                    id=decision_id,
                    ai_tool=AiTool.NONE,
                    oversight=DecisionOversight.REVIEWED,
                    status=DecisionStatus.CONFIRMED,
                    context="Timestamp storage timezone policy",
                    choice=choice,
                ),
                body="",
            ),
        )


@pytest.mark.phase_4
def test_malformed_pair_is_dropped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RL_METRICS", "1")
    emit(tmp_path, MetricEvent.CONFLICT_DISMISSED, pair="not-a-pair; rm -rf /")
    assert "pair" not in load_metrics(tmp_path)[0]


@pytest.mark.phase_4
def test_reading_metrics_does_not_write_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`status --metrics` reports the pilot numbers; it must not create them.

    Building a ledger view emits CONFLICT_SURFACED, so a `--metrics` run that built
    one would inflate the surfaced count purely by being asked for it — the observer
    changing the thing observed, in the one command whose entire job is to report it
    faithfully.
    """
    monkeypatch.setenv("RL_METRICS", "1")
    # Two decisions that genuinely conflict, so a view build would have something to
    # surface — without them this test would pass against the bug it guards.
    _write_timezone_decisions(tmp_path, ["UTC", "server-local"])
    emit(tmp_path, MetricEvent.WHY_INVOKED, match="symbol")
    before = load_metrics(tmp_path)

    assert main(["status", "--root", str(tmp_path), "--metrics"]) == EXIT_PASS

    assert load_metrics(tmp_path) == before

    # And the guard is meaningful: a plain `status` *does* surface the pair.
    assert main(["status", "--root", str(tmp_path)]) == EXIT_PASS
    surfaced = [
        event
        for event in load_metrics(tmp_path)
        if event["event"] == MetricEvent.CONFLICT_SURFACED.value
    ]
    assert len(surfaced) == 1


def _count_metrics_reads(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Every read of the metrics log, recorded even when the file does not exist yet."""
    reads: list[Path] = []
    real_read_text = Path.read_text

    def counting_read_text(
        self: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        if self.name == METRICS_PATH.name:
            reads.append(self)
        return real_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    return reads


def _pairs(count: int) -> list[tuple[str, dict[str, str]]]:
    return [(f"dec_aaa{index}::dec_bbb{index}", {"severity": "high"}) for index in range(count)]


@pytest.mark.phase_4
def test_emit_once_many_reads_the_log_once_however_many_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scanning per pair made a view build quadratic: 500 decisions took 13s, not 2s."""
    monkeypatch.setenv("RL_METRICS", "1")
    reads = _count_metrics_reads(monkeypatch)

    emit_once_many(tmp_path, MetricEvent.CONFLICT_SURFACED, _pairs(50))

    assert len(reads) == 1
    assert len(load_metrics(tmp_path)) == 50


@pytest.mark.phase_4
def test_emit_once_many_writes_what_repeated_emit_once_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Batching must not change the log: same lines, same order, nothing re-emitted."""
    monkeypatch.setenv("RL_METRICS", "1")
    sequential, batched = tmp_path / "sequential", tmp_path / "batched"
    # One pair already on file, one repeated inside the batch, one for another event.
    entries = [*_pairs(3), _pairs(3)[0], ("dec_ccc0::dec_ddd0", {"severity": "low"})]
    for root in (sequential, batched):
        emit_once(root, MetricEvent.CONFLICT_SURFACED, pair=entries[1][0], severity="high")
        emit(root, MetricEvent.CONFLICT_DISMISSED, pair=entries[0][0])

    for pair, fields in entries:
        emit_once(sequential, MetricEvent.CONFLICT_SURFACED, pair=pair, **fields)
    emit_once_many(batched, MetricEvent.CONFLICT_SURFACED, entries)

    assert (batched / METRICS_PATH).read_bytes() == (sequential / METRICS_PATH).read_bytes()
    emit_once_many(batched, MetricEvent.CONFLICT_SURFACED, entries)
    assert (batched / METRICS_PATH).read_bytes() == (sequential / METRICS_PATH).read_bytes()


@pytest.mark.phase_4
def test_emit_once_many_does_nothing_when_disabled_or_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RL_METRICS", raising=False)
    emit_once_many(tmp_path, MetricEvent.CONFLICT_SURFACED, _pairs(3))
    monkeypatch.setenv("RL_METRICS", "1")
    reads = _count_metrics_reads(monkeypatch)
    emit_once_many(tmp_path, MetricEvent.CONFLICT_SURFACED, [])

    assert not (tmp_path / METRICS_PATH).exists()
    assert reads == []


@pytest.mark.phase_4
def test_view_build_reads_the_metrics_log_once_for_many_surfaced_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RL_METRICS", "1")
    _write_timezone_decisions(tmp_path, ["UTC", "server-local", "Pacific time", "Tokyo time"])
    reads = _count_metrics_reads(monkeypatch)

    build_ledger_view(tmp_path, embedder=DeterministicEmbedder())
    build_ledger_view(tmp_path, embedder=DeterministicEmbedder())

    assert len(reads) == 2, "one scan per build, however many pairs it surfaces"
    surfaced = [
        event
        for event in load_metrics(tmp_path)
        if event["event"] == MetricEvent.CONFLICT_SURFACED.value
    ]
    assert len(surfaced) == 6, "four same-question decisions make six pairs, each logged once"
