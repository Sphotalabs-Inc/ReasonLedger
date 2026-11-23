"""`reasonledger consent` and the gate every model-calling command passes through.

A model on this machine needs no consent. A model anywhere else gets nothing until a person
has allowed that kind of data, for this repo, to that destination (reasonledger_core.consent).
In a terminal the gate asks once, showing what would be sent; with no terminal (CI, a script)
it refuses and names the command that grants it, so nothing is ever sent silently.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from reasonledger_core.consent import (
    DESCRIPTIONS,
    LABELS,
    ConsentError,
    DataClass,
    destination,
    grant,
    granted_classes,
    missing_classes,
    parse_classes,
    revoke,
)
from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.config import (
    ConfigError,
    ExtractorConfig,
    ExtractorProvider,
    load_extractor_config,
)
from reasonledger_core.importer.outgoing import HeldSource, preview_repo_text
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.modules.digest import source_files

EXIT_PASS = 0
EXIT_USAGE = 2
# The sample is printed whole up to this length; a longer one is cut here and the cut announced,
# so a terminal is not flooded by one long doc while the count of what was left out stays exact.
PREVIEW_SAMPLE_CHARS = 4000
PREVIEW_CLASSES = (DataClass.REPO_TEXT.value,)


def add_consent_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    consent = sub.add_parser(
        "consent",
        help="Show or change what this repo may send to a model that is off your machine",
    )
    consent.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Application repo root (default: cwd)"
    )
    consent.add_argument(
        "action", nargs="?", choices=("status", "grant", "revoke"), default="status"
    )
    consent.add_argument(
        "--preview",
        choices=PREVIEW_CLASSES,
        metavar="CLASS",
        help="Show what this class would send, with one message exactly as sent (repo_text)",
    )
    consent.add_argument(
        "classes",
        nargs="*",
        metavar="CLASS",
        help="decision_text, paths or repo_text (revoke with none revokes all)",
    )


def class_counts(root: Path, classes: list[DataClass]) -> dict[DataClass, str]:
    """A short, honest size for each class: how much would go if it were allowed."""
    counts: dict[DataClass, str] = {}
    for item in classes:
        if item is DataClass.DECISION_TEXT:
            total = len(load_decisions_from_dir(root / DECISIONS_DIR)) + len(
                load_decisions_from_dir(root / PROPOSED_DIR)
            )
            counts[item] = f"{total} decision(s) in this repo"
        elif item is DataClass.PATHS:
            counts[item] = f"{len(source_files(root))} source file path(s)"
        else:
            from reasonledger_cli.init_cmd import scan_candidates

            report = scan_candidates(root=root)
            counts[item] = (
                f"{report.doc_count} document(s) and {report.commit_count} commit message(s)"
            )
    return counts


def _describe(root: Path, classes: list[DataClass]) -> list[str]:
    counts = class_counts(root, classes)
    return [f"  {item.value}: {DESCRIPTIONS[item]} ({counts[item]})" for item in classes]


def ensure_consent(
    root: Path,
    config: ExtractorConfig,
    classes: list[DataClass],
    *,
    command: str,
    extra_hint: str = "",
) -> int | None:
    """``None`` when the call may go ahead, else the exit code to return.

    Asks interactively when it can; refuses, naming the grant command, when it cannot.
    """
    missing = missing_classes(root, config, classes)
    if not missing:
        return None
    host = destination(config)
    names = " ".join(item.value for item in missing)
    print(f"`reasonledger {command}` would send this to {host}, which is off your machine:")
    for line in _describe(root, missing):
        print(line)
    if DataClass.REPO_TEXT in missing:
        print("  see exactly what is sent: `reasonledger consent --preview repo_text`")
    if sys.stdin.isatty() and sys.stdout.isatty():
        answer = input(f"Allow this for this repo, to {host}? [y/N] ").strip().lower()
        if answer in {"y", "yes"}:
            grant(root, config, missing)
            print("allowed; change it any time with `reasonledger consent revoke`")
            return None
        print("nothing was sent", file=sys.stderr)
        return EXIT_USAGE
    print(
        f"error: no consent to send {names} to {host}. Review it with `reasonledger consent`, "
        f"then run `reasonledger consent grant {names}`{extra_hint}",
        file=sys.stderr,
    )
    return EXIT_USAGE


def print_held(held: list[HeldSource]) -> None:
    """Name each source the pre-send check kept on this machine, and the rules it matched."""
    if not held:
        return
    print(f"held back, not sent ({len(held)}): matched the PII/secret check")
    for item in held:
        print(f"  {item.path}: {', '.join(item.rules)}")


def _preview(root: Path, config: ExtractorConfig) -> int:
    preview = preview_repo_text(root)
    target = destination(config)
    where = (
        f"to {target}"
        if target
        else "to a model off this machine, if one were configured (none is, so nothing leaves)"
    )
    print(
        f"repo_text: up to {preview.docs} document(s) and {preview.commits} commit message(s) "
        f"{where}, one request each, with ReasonLedger's fixed extraction instructions. "
        "`import` sends the docs; `catchup` sends what changed since its last run."
    )
    print_held(preview.held)
    if preview.sample_message is None:
        print("nothing would be sent")
        return EXIT_PASS
    print(f"exactly as sent for {preview.sample_path}:")
    print(textwrap.indent(preview.sample_message[:PREVIEW_SAMPLE_CHARS], "  | "))
    hidden = len(preview.sample_message) - PREVIEW_SAMPLE_CHARS
    if hidden > 0:
        print(f"  [{hidden} more character(s) are sent but not shown here]")
    return EXIT_PASS


def _status(root: Path, config: ExtractorConfig) -> int:
    host = destination(config)
    if config.provider is ExtractorProvider.DISABLED:
        print("no model is configured, so nothing is sent anywhere (reasonledger config)")
        return EXIT_PASS
    if host is None:
        print("your model runs on this machine; nothing leaves it and no consent is needed")
        return EXIT_PASS
    print(f"model: {config.provider.value}:{config.model or '?'} -> {host} (off this machine)")
    have = granted_classes(root, config)
    counts = class_counts(root, list(DataClass))
    for item in DataClass:
        state = "allowed" if item in have else "not allowed"
        print(f"  {item.value:14} {state:12} {LABELS[item]}: {counts[item]}")
    print("allow: `reasonledger consent grant <class>`; withdraw: `reasonledger consent revoke`")
    return EXIT_PASS


def run_consent_cmd(args: argparse.Namespace) -> int:
    root: Path = args.root
    try:
        config = load_extractor_config(root)
        classes = parse_classes(list(args.classes))
    except (ConfigError, ConsentError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.preview:
        return _preview(root, config)
    if args.action == "status":
        return _status(root, config)
    if args.action == "revoke":
        revoke(root, classes or None)
        print("consent withdrawn" + (": " + " ".join(c.value for c in classes) if classes else ""))
        return EXIT_PASS
    if not classes:
        print("error: name what to allow: decision_text, paths or repo_text", file=sys.stderr)
        return EXIT_USAGE
    try:
        grant(root, config, classes)
    except ConsentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    print(f"allowed to {destination(config)}: " + " ".join(item.value for item in classes))
    return EXIT_PASS
