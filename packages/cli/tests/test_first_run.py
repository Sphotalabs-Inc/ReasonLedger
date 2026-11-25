"""A first-time user's first contact: the bare command, the command list and a mistyped command."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
from reasonledger_cli.first_run import LEDGER_DIR
from reasonledger_cli.main import main
from reasonledger_cli.parser import COMMAND_GROUPS, build_parser


def _lines(text: str) -> list[str]:
    """Output split on any newline, so a Windows text stream's \\r\\n reads the same."""
    return text.replace("\r\n", "\n").splitlines()


@pytest.mark.phase_3
def test_bare_command_prints_the_first_run_loop_with_init_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main([]) == 0

    out = _lines(capsys.readouterr().out)
    assert len(out) <= 15
    steps = [line.split()[1] for line in out if line.startswith("  reasonledger ")]
    assert steps == ["init", "ui", "why"]
    assert any("--help" in line and "docs/install.md" in line for line in out)


@pytest.mark.phase_3
def test_bare_command_in_a_repo_with_a_ledger_leads_with_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / LEDGER_DIR).mkdir()
    monkeypatch.chdir(tmp_path)

    assert main([]) == 0

    out = _lines(capsys.readouterr().out)
    assert len(out) <= 15
    steps = [line.split()[1] for line in out if line.startswith("  reasonledger ")]
    assert steps == ["status", "ui", "why"]
    assert any("already has" in line for line in out)


@pytest.mark.phase_3
def test_a_mistyped_command_suggests_the_closest_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["intt"])

    assert raised.value.code == 2
    err = _lines(capsys.readouterr().err)
    assert any("Did you mean `init`?" in line for line in err)
    assert any("reasonledger --help" in line for line in err)


@pytest.mark.phase_3
def test_a_command_with_no_close_match_only_points_to_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["zzzzzz"])

    assert raised.value.code == 2
    err = "\n".join(_lines(capsys.readouterr().err))
    assert "Did you mean" not in err
    assert "reasonledger --help" in err


@pytest.mark.phase_3
@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["why"], "required: target"),
        (["approve", "dec_x", "--as", "bogus"], "invalid choice"),
    ],
)
def test_other_usage_errors_keep_argparses_message_and_exit_code(
    argv: list[str], expected: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(argv)

    assert raised.value.code == 2
    err = "\n".join(_lines(capsys.readouterr().err))
    assert expected in err
    assert "unknown command" not in err


@pytest.mark.phase_3
def test_help_groups_every_command_exactly_once() -> None:
    parser = build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    grouped = [
        name
        for line in COMMAND_GROUPS.splitlines()
        if line.startswith("  ")
        for name in line.split(None, 1)[1].split(", ")
    ]

    assert sorted(grouped) == sorted(sub.choices)


@pytest.mark.phase_3
def test_help_still_exits_zero_and_lists_the_groups(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--help"])

    assert raised.value.code == 0
    out = "\n".join(_lines(capsys.readouterr().out))
    assert "command groups:" in out
    assert "everyday" in out
