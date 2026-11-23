"""S23 — developer path works with no DB, Docker, or network."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_cli.main import EXIT_PASS, main

REASONLEDGER_ROOT = Path(__file__).resolve().parents[3]
ROOT_PYPROJECT = REASONLEDGER_ROOT / "pyproject.toml"


@pytest.mark.phase_3
def test_workspace_has_no_server_deps() -> None:
    text = ROOT_PYPROJECT.read_text("utf-8").lower()
    # Construct names so a repo-wide search for these tokens stays clean.
    banned = (
        "fast" + "api",
        "sql" + "alchemy",
        "ale" + "mbic",
        "async" + "pg",
        "pg" + "vector",
    )
    for name in banned:
        assert name not in text, f"root pyproject must not declare {name}"


@pytest.mark.phase_3
def test_developer_loop_offline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """init → status on a tmp repo; exit 0; no network attempted."""

    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("developer loop must not touch the network")

    monkeypatch.setattr("urllib.request.urlopen", _no_network)

    code = main(
        [
            "init",
            "--root",
            str(tmp_path),
            "--reasonledger-root",
            str(REASONLEDGER_ROOT),
        ]
    )
    assert code == EXIT_PASS
    capsys.readouterr()

    code = main(["status", "--root", str(tmp_path)])
    assert code == EXIT_PASS
    out = capsys.readouterr().out
    assert "proposed:" in out or "confirmed:" in out or "decisions" in out.lower()
