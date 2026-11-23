"""S56 — a page must not tell a reader to run a command the real parser rejects.

Every `reasonledger <subcommand> …` (or `rl …`) written in the three reader-facing docs is
fed to `build_parser()`. Docs MUST NOT state how many commands exist, so the count is never
the thing that is checked — only that what is written parses.
"""

from __future__ import annotations

import argparse
import re
import shlex
from pathlib import Path

import pytest
from reasonledger_cli.parser import build_parser

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "packages" / "cli" / "README.md",
    REPO_ROOT / "docs" / "user-manual.md",
)
PLACEHOLDER_ARG = "placeholder"
FENCE = re.compile(r"^```(?P<lang>\w*)")
SHELL_FENCES = {"", "bash", "sh", "shell", "console"}
INLINE_CODE = re.compile(r"`([^`\n]+)`")
BRACKETED = re.compile(r"\[[^\]]*\]")
ANGLED = re.compile(r"<[^>]+>")
COMMAND = re.compile(r"(?:^|\s)(?:reasonledger|rl)\s+(?P<rest>[a-z-].*)$")
PRESENTATION_ONLY = {"--help", "-h", "--version"}


def _subcommands(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("the parser has no subcommands")


def _fenced_lines(text: str) -> list[str]:
    """Shell lines inside fences, with trailing-backslash continuations joined."""
    lines: list[str] = []
    inside = False
    shell = False
    pending = ""
    for raw in text.splitlines():
        fence = FENCE.match(raw)
        if fence:
            inside = not inside
            shell = fence.group("lang") in SHELL_FENCES
            pending = ""
            continue
        if not inside or not shell:
            continue
        line = pending + raw.strip()
        if line.endswith("\\"):
            pending = line[:-1].rstrip() + " "
            continue
        pending = ""
        lines.append(line)
    return lines


def _inline_spans(text: str) -> list[str]:
    outside: list[str] = []
    inside = False
    for raw in text.splitlines():
        if FENCE.match(raw):
            inside = not inside
        elif not inside:
            outside.append(raw)
    return [span for line in outside for span in INLINE_CODE.findall(line)]


def _argv(line: str) -> list[str] | None:
    """The argv after `reasonledger`, or None when the line is not a command."""
    line = line.split("#", 1)[0]
    match = COMMAND.search(line)
    if match is None or match.group("rest").startswith("-"):
        return None
    rest = ANGLED.sub(PLACEHOLDER_ARG, BRACKETED.sub("", match.group("rest")))
    rest = rest.split("|", 1)[0].split(" > ", 1)[0]
    try:
        return shlex.split(rest)
    except ValueError:
        return None


def _documented() -> list[tuple[str, bool, list[str]]]:
    found: list[tuple[str, bool, list[str]]] = []
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        blocks = [(line, True) for line in _fenced_lines(text)]
        spans = [(span, False) for span in _inline_spans(text)]
        for line, fenced in blocks + spans:
            argv = _argv(line)
            if argv:
                found.append((f"{doc.name}: {line}", fenced, argv))
    return found


DOCUMENTED = _documented()


def test_the_scan_finds_commands() -> None:
    """A regex that silently matches nothing would make the real test vacuous."""
    assert len(DOCUMENTED) >= 20


@pytest.mark.phase_3
@pytest.mark.parametrize(("where", "fenced", "argv"), DOCUMENTED, ids=[d[0] for d in DOCUMENTED])
def test_documented_commands_parse(
    where: str, fenced: bool, argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    parser = build_parser()
    known = _subcommands(parser)
    assert argv[0] in known, f"{where}: `{argv[0]}` is not a subcommand"
    if len(argv) == 1 and not fenced:
        return  # a bare mention names the command; it does not claim to run as written
    if PRESENTATION_ONLY & set(argv):
        return
    try:
        parser.parse_args(argv)
    except SystemExit as exit_:
        message = capsys.readouterr().err.strip().splitlines()
        assert exit_.code == 0, f"{where}: parser rejected it: {message[-1] if message else ''}"
