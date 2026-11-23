"""`reasonledger ui` — "Check for conflicts", with a stand-in judge: no model, no network."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from reasonledger_cli import ui_judge
from reasonledger_cli.ui_judge import JudgeSession
from reasonledger_core.importer.config import ExtractorConfig, ExtractorProvider
from reasonledger_core.importer.llm import LlmError
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.models.reasoning import Severity
from reasonledger_core.reasoning.verdicts import JudgeAnswer, load_verdicts
from test_ui_server import _UiServer, _write_confirmed

ON_MACHINE = ExtractorConfig(
    provider=ExtractorProvider.OPENAI_COMPATIBLE, base_url="http://localhost:11434/v1", model="m"
)
OFF_MACHINE = ExtractorConfig(
    provider=ExtractorProvider.OPENAI_COMPATIBLE, base_url="https://judge.test/v1", model="m"
)
WAIT_SECONDS = 10.0


@pytest.fixture
def ui(tmp_path: Path) -> Iterator[_UiServer]:
    server = _UiServer(tmp_path)
    yield server
    server.close()


class _Judge:
    """Says every pair clashes; can fail, hold a call open, or ask the session to stop."""

    model = "stand-in"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False
        self.gate: threading.Event | None = None
        self.stop: JudgeSession | None = None

    def judge(self, a: DecisionRecord, b: DecisionRecord) -> JudgeAnswer:
        self.calls += 1
        if self.gate is not None:
            self.gate.wait(WAIT_SECONDS)
        if self.stop is not None:
            # Stop answers at once, naming the pair still in flight, before the call returns.
            stopping = self.stop.post("stop", {})[1]
            assert stopping["state"] == "stopping"
            assert stopping["current"] == [a.frontmatter.id, b.frontmatter.id]
        if self.fail:
            raise LlmError("model unreachable")
        return JudgeAnswer(
            same_question=True,
            compatible=False,
            question="Which timezone are timestamps stored in?",
            reason="The two choices cannot both hold.",
            severity=Severity.HIGH,
        )


def _three_pairs(root: Path) -> None:
    for decision_id, choice in (
        ("dec_tz1", "UTC"),
        ("dec_tz2", "server-local"),
        ("dec_tz3", "IST"),
    ):
        _write_confirmed(
            root, decision_id, context="Timestamp storage timezone policy", choice=choice
        )


def _session(
    root: Path, monkeypatch: pytest.MonkeyPatch, config: ExtractorConfig = ON_MACHINE
) -> tuple[JudgeSession, _Judge]:
    monkeypatch.setattr(ui_judge, "load_extractor_config", lambda _root: config)
    judge = _Judge()
    return JudgeSession(root, build_judge=lambda _config, _model: judge), judge  # type: ignore[arg-type,return-value]


def _finished(session: JudgeSession) -> dict[str, object]:
    session.wait(WAIT_SECONDS)
    return session.get()[1]


@pytest.mark.phase_4
def test_a_check_judges_every_pending_pair_and_saves_the_verdicts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _three_pairs(tmp_path)
    session, judge = _session(tmp_path, monkeypatch)
    assert session.get() == (200, {**session.get()[1], "state": "idle", "total": 0})

    status, started = session.post("start", {})
    assert (status, started["state"], started["model"]) == (200, "running", "stand-in")
    done = _finished(session)
    assert (done["state"], done["total"], done["checked"]) == ("finished", 3, 3)
    assert (done["conflicts"], done["compatible"], done["failed"]) == (3, 0, 0)
    assert len(load_verdicts(tmp_path)) == 3

    # Nothing is left, so a second run sends nothing.
    session.post("start", {})
    assert (_finished(session)["total"], judge.calls) == (0, 3)


@pytest.mark.phase_4
def test_one_pair_can_be_checked_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _three_pairs(tmp_path)
    session, judge = _session(tmp_path, monkeypatch)
    for bad in ("dec_tz1", ["dec_tz1"], ["dec_tz1", 2]):
        assert session.post("start", {"pair": bad})[0] == 400

    assert session.post("start", {"pair": ["dec_tz2", "dec_tz1"]})[0] == 200
    done = _finished(session)
    assert (done["state"], done["total"], done["checked"], judge.calls) == ("finished", 1, 1, 1)
    assert len(load_verdicts(tmp_path)) == 1


@pytest.mark.phase_4
def test_stop_ends_the_run_after_the_pair_in_flight_and_keeps_what_was_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _three_pairs(tmp_path)
    session, judge = _session(tmp_path, monkeypatch)
    judge.stop = session

    session.post("start", {})
    done = _finished(session)
    assert (done["state"], done["total"], done["checked"]) == ("stopped", 3, 1)
    assert done["current"] is None
    assert len(load_verdicts(tmp_path)) == 1
    assert session.post("nope", {})[0] == 404


@pytest.mark.phase_4
def test_only_one_check_runs_at_a_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _three_pairs(tmp_path)
    session, judge = _session(tmp_path, monkeypatch)
    judge.gate = threading.Event()

    assert session.post("start", {})[0] == 200
    status, refused = session.post("start", {})
    assert status == 409 and "already running" in refused["error"]
    judge.gate.set()
    assert _finished(session)["state"] == "finished"


@pytest.mark.phase_4
def test_a_pair_the_model_fails_on_is_counted_and_never_stored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _three_pairs(tmp_path)
    session, judge = _session(tmp_path, monkeypatch)
    judge.fail = True

    session.post("start", {"pair": ["dec_tz1", "dec_tz2"]})
    done = _finished(session)
    assert (done["state"], done["checked"], done["failed"]) == ("finished", 1, 1)
    assert load_verdicts(tmp_path) == {}


@pytest.mark.phase_4
def test_nothing_is_sent_off_the_machine_without_consent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _three_pairs(tmp_path)
    session, judge = _session(tmp_path, monkeypatch, OFF_MACHINE)

    status, refused = session.post("start", {})
    assert (status, refused["need"]) == (409, "consent")
    assert "judge.test" in refused["error"]
    assert (session.get()[1]["state"], judge.calls) == ("idle", 0)


@pytest.mark.phase_4
def test_the_server_refuses_to_check_with_no_model_and_says_what_is_needed(
    tmp_path: Path, ui: _UiServer
) -> None:
    _three_pairs(tmp_path)
    status, raw = ui.request("POST", "/api/judge/start", body=b"{}")
    assert (status, json.loads(raw)["need"]) == (409, "model")
    status, raw = ui.request("GET", "/api/judge")
    assert (status, json.loads(raw)["state"]) == (200, "idle")
    assert ui.request("POST", "/api/judge/start", body=b"{}", token="wrong")[0] == 403
