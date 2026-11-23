"""The CLI must not die, or garble, on text a legacy Windows code page cannot encode."""

from __future__ import annotations

import io
import sys

import pytest
from reasonledger_cli.main import _use_utf8_output


@pytest.mark.phase_3
def test_main_switches_output_to_utf8_and_replaces_what_cannot_be_encoded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = io.TextIOWrapper(io.BytesIO(), encoding="cp437", errors="strict")
    monkeypatch.setattr(sys, "stdout", legacy)
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(io.BytesIO(), encoding="cp437"))

    _use_utf8_output()
    print("decision — memory → ledger")
    legacy.flush()

    assert legacy.buffer.getvalue().decode("utf-8") == "decision — memory → ledger\n"  # type: ignore[attr-defined]


@pytest.mark.phase_3
def test_a_stream_without_reconfigure_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    class Plain:
        def write(self, text: str) -> int:
            return len(text)

    monkeypatch.setattr(sys, "stdout", Plain())
    monkeypatch.setattr(sys, "stderr", Plain())
    _use_utf8_output()
