"""What a first-time user sees: the bare command's welcome and a hint on a mistyped command."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path
from typing import NoReturn

from reasonledger_core.links import INSTALL_DOCS_URL

LEDGER_DIR = ".reasonledger"
PROG = "reasonledger"
EXIT_USAGE = 2
# Only the top-level command argument is rewritten; an option's `invalid choice` stays argparse's.
_BAD_COMMAND = re.compile(r"^argument <command>: invalid choice: '(?P<typed>[^']*)'")

_TAGLINE = (
    "ReasonLedger: your AI coding agent records why it made each choice; you approve it;\n"
    "`why` shows which decision justifies a line, function, or file."
)
_STATUS = "reasonledger status           # what is waiting for review, what is in force"
_INIT = "reasonledger init             # set up .reasonledger/, the MCP config, the agent rule"
_UI = "reasonledger ui               # approve what your agent recorded, on 127.0.0.1"
_WHY = "reasonledger why <file:line>  # which decision justifies this line (or ::function)?"
_FOOTER = f"`reasonledger --help` lists every command; setup: {INSTALL_DOCS_URL}"


def welcome_text(root: Path) -> str:
    """The welcome for `root`: `status` first when a ledger is already there, else `init`."""
    if (root / LEDGER_DIR).is_dir():
        intro = f"This folder already has a {LEDGER_DIR}/ ledger. Start here:"
        steps = (_STATUS, _UI, _WHY)
    else:
        intro = "First run, in your repository:"
        steps = (_INIT, _UI, _WHY)
    lines = [_TAGLINE, "", intro, *(f"  {step}" for step in steps), "", _FOOTER]
    return "\n".join(lines)


def run_welcome(root: Path) -> int:
    print(welcome_text(root))
    return 0


def command_hint(typed: str, commands: list[str]) -> str:
    """Why `typed` is not a command, naming the closest real one when there is one."""
    message = f"unknown command '{typed}'."
    close = difflib.get_close_matches(typed, commands, n=1)
    if close:
        message += f" Did you mean `{close[0]}`?"
    return f"{message}\nRun `{PROG} --help` to see all commands."


class HintingParser(argparse.ArgumentParser):
    """Turns argparse's bare `invalid choice` for a mistyped command into a suggestion."""

    def error(self, message: str) -> NoReturn:
        found = _BAD_COMMAND.match(message)
        if found is None:
            super().error(message)
        commands = [
            name
            for action in self._actions
            if isinstance(action, argparse._SubParsersAction)
            for name in action.choices
        ]
        print(f"{PROG}: error: {command_hint(found['typed'], commands)}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)
