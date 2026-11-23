"""`reasonledger init` — scaffold Decision record layout in an application repo."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.scan import commit_sources, count_scannable_docs
from reasonledger_core.reasoning.conflict_config import (
    CONFLICT_CONFIG_PATH,
    ConflictConfig,
    write_conflict_config,
)
from reasonledger_core.reasoning.embeddings import local_embedder_available
from reasonledger_core.sync import is_git_repo, recent_commit_messages

from reasonledger_cli.agent_targets import (
    ALL_AGENTS,
    TARGET_KEYS,
    TARGETS,
    USER_LEVEL_CONFIGS,
    AgentTarget,
    detection_reasons,
    installed_cli,
    parse_agents,
    write_mcp_config,
    write_rule,
)

REASONLEDGER_DIR = Path(".reasonledger")
POLICY_REL_PATH = REASONLEDGER_DIR / "policy.yml"
GITKEEP = ".gitkeep"
GITIGNORE = ".gitignore"
CACHE_IGNORE = ".reasonledger/cache/"
DEFAULT_SCAN_MAX_COMMITS = 200

# Matches fixtures/sandbox/pr-workflows/policy.yml with an explicit version field.
POLICY_STUB = """\
version: "1"
rules:
  - id: payments-need-owner-review
    when:
      provenance: ai_assisted
      paths:
        - "payments/**"
    require:
      oversight: reviewed
      approver: codeowner
      approver_not: author
    on_violation: fail
  - id: ai-should-be-reviewed
    when:
      provenance: ai_assisted
    require:
      oversight: reviewed
    on_violation: warn
"""

# Leads with developer value (S29): what the tool does for the person running `init`.
EMBEDDINGS_LABEL = "Optional real embeddings for related decisions:"
EMBEDDINGS_TOOL_COMMAND = 'uv tool install --force "reasonledger[embeddings]"'
EMBEDDINGS_DOCS_POINTER = "see docs/install.md"
HEADLINE = "Decision memory for AI-assisted codebases — never lose the why behind a line of code."


@dataclass(frozen=True)
class ScanReport:
    doc_count: int
    commit_count: int

    @property
    def total(self) -> int:
        return self.doc_count + self.commit_count


def scan_candidates(*, root: Path, max_commits: int = DEFAULT_SCAN_MAX_COMMITS) -> ScanReport:
    """Count decision candidates without a model, a network call, or a write.

    Never raises: a repo that is not a git checkout still yields a doc count.
    """
    try:
        doc_count = count_scannable_docs(root)
    except OSError:
        doc_count = 0

    commit_count = 0
    try:
        if is_git_repo(root):
            commit_count = len(commit_sources(recent_commit_messages(root, limit=max_commits)))
    except OSError:
        commit_count = 0
    return ScanReport(doc_count=doc_count, commit_count=commit_count)


def embeddings_command() -> str:
    """One thing to do, for the way this process was installed: a command, or the docs."""
    return EMBEDDINGS_TOOL_COMMAND if installed_cli() else EMBEDDINGS_DOCS_POINTER


def scaffold_repo(*, root: Path, policy: bool = False) -> list[str]:
    """Create ReasonLedger layout when missing. Returns human-readable actions taken.

    The CI policy stub is written only on request (``init --policy``): most repos never use it.
    """
    actions: list[str] = []
    rl_dir = root / REASONLEDGER_DIR
    decisions_dir = root / DECISIONS_DIR
    policy_path = root / POLICY_REL_PATH

    rl_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)

    has_decision_files = any(decisions_dir.glob("*.md"))
    gitkeep_path = decisions_dir / GITKEEP
    if not has_decision_files and not gitkeep_path.exists():
        gitkeep_path.write_text("", encoding="utf-8")
        actions.append(f"created {decisions_dir.relative_to(root)}/{GITKEEP}")

    if policy and not policy_path.is_file():
        policy_path.write_text(POLICY_STUB, encoding="utf-8")
        actions.append(f"created {policy_path.relative_to(root)}")

    _ensure_local_embedder(root, actions)
    _ensure_cache_ignored(root, actions)
    return actions


def _ensure_local_embedder(root: Path, actions: list[str]) -> None:
    """Start a new repo on the semantic embedder when it is installed.

    Only when no conflict.yml exists: an existing one is the team's choice. Without
    the extra, nothing is written — saving `local` would just degrade on every run;
    `format_init_output` tells the user how to install it instead.
    """
    if (root / CONFLICT_CONFIG_PATH).exists() or not local_embedder_available():
        return
    write_conflict_config(root, ConflictConfig(embedding_provider="local"))
    actions.append(f"created {CONFLICT_CONFIG_PATH} (local embedding model)")


def _ensure_cache_ignored(root: Path, actions: list[str]) -> None:
    """Add the local cache exclusion without changing other ignore rules."""
    _ensure_ignored(root, CACHE_IGNORE, actions)


def _ensure_ignored(root: Path, line: str, actions: list[str]) -> None:
    """Append `line` to .gitignore when missing, leaving other rules alone."""
    path = root / GITIGNORE
    if path.is_file():
        contents = path.read_text(encoding="utf-8")
        if line in contents.splitlines():
            return
        separator = "" if not contents or contents.endswith("\n") else "\n"
        path.write_text(f"{contents}{separator}{line}\n", encoding="utf-8")
        note = f"updated {GITIGNORE}"
    else:
        path.write_text(f"{line}\n", encoding="utf-8")
        note = f"created {GITIGNORE}"
    if note not in actions and f"created {GITIGNORE}" not in actions:
        actions.append(note)


def _ensure_agent_files(
    root: Path,
    reasonledger_root: Path | None,
    targets: tuple[AgentTarget, ...],
    *,
    rules: bool,
    actions: list[str],
    notes: list[str],
) -> list[AgentTarget]:
    """Write each chosen agent's MCP config and rule file; returns the agents that changed.

    A config holds an absolute path, so it is git-ignored; a rule file holds none and is
    meant to be committed.
    """
    changed: list[AgentTarget] = []
    for target in targets:
        before = len(actions)
        if write_mcp_config(
            root, target, reasonledger_root=reasonledger_root, actions=actions, notes=notes
        ):
            _ensure_ignored(root, target.mcp_path or "", actions)
        if rules:
            write_rule(root, target, actions)
        if len(actions) > before:
            changed.append(target)
    return changed


def add_init_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    init = sub.add_parser(
        "init",
        help="Set up .reasonledger/ and every coding agent's MCP config and rule in this repo",
    )
    init.add_argument(
        "--root", type=Path, default=Path.cwd(), help="Repo root to set up (default: cwd)"
    )
    init.add_argument(
        "--reasonledger-root",
        type=Path,
        default=None,
        help="ReasonLedger checkout to wrap the MCP command in (default: the installed executable)",
    )
    init.add_argument("--no-scan", action="store_true", help="Skip the candidate scan")
    init.add_argument(
        "--agents",
        default=None,
        help=(
            f"Comma-separated agents to set up, or '{ALL_AGENTS}' "
            f"(default: the ones this repo uses; choose from {', '.join(TARGET_KEYS)})"
        ),
    )
    init.add_argument(
        "--policy",
        action="store_true",
        help="Also write a starter .reasonledger/policy.yml for `reasonledger check --policy`",
    )
    init.add_argument(
        "--no-rules", action="store_true", help="Write MCP configs only, not the rule files"
    )


def _scan_lines(report: ScanReport) -> list[str]:
    if report.total == 0:
        return [
            "No decision candidates found. Records will accrue as your agent "
            "calls `record_decision`."
        ]
    return [
        f"Found {report.total} decision candidates in this repo "
        f"({report.doc_count} documents, {report.commit_count} commit messages). "
        "They were read on this machine; nothing was sent anywhere.",
        "",
        "To turn them into decisions (needs a model; a local one keeps it all here):",
        "  reasonledger config --provider anthropic --model claude-sonnet-5   # one-time",
        "  reasonledger import --extracted-by anthropic/claude-sonnet-5       # propose them",
        "  reasonledger confirm --all                                         # review, accept",
    ]


# Cursor reads .cursor/mcp.json only from the folder it has open. Opened one level up, it never sees
# this file, and a hand-written "." entry then points the server at the wrong repo.
CURSOR_MCP_HINT = (
    "Cursor reads .cursor/mcp.json only from the folder you open, so open {root} itself "
    "(`cursor {root}`), not a parent folder. Then check Settings > MCP shows reasonledger "
    "switched on."
)


def format_init_output(
    *,
    root: Path,
    actions: list[str],
    changed: list[AgentTarget],
    notes: list[str],
    report: ScanReport | None = None,
    show_user_level: bool = True,
    agent_notes: list[str] | None = None,
) -> str:
    lines = [HEADLINE, "", f"ReasonLedger initialized in {root.resolve()}", ""]
    lines.append("Decision records live in .reasonledger/decisions/")
    lines.extend(f"  + {action}" for action in actions)
    if not actions:
        lines.append("  No changes: everything was already set up.")
    lines.extend(["", *agent_notes] if agent_notes else [])
    if changed:
        names = ", ".join(t.label for t in changed if t.mcp_path) or "your agent"
        lines.extend(["", f"Restart {names} to pick up the MCP server and the rule."])
        if any(t.key == "cursor" for t in changed):
            lines.append(CURSOR_MCP_HINT.format(root=root.resolve()))
    for note in notes:
        lines.extend(["", note])
    if show_user_level:
        lines.extend(["", "Other agents keep their MCP config in your home directory:"])
        lines.extend(f"  {name}: {where}" for name, where in USER_LEVEL_CONFIGS)
    if report is not None:
        lines.extend(["", *_scan_lines(report)])
    if not local_embedder_available():
        lines.extend(["", f"{EMBEDDINGS_LABEL} {embeddings_command()}"])
    lines.extend(
        [
            "",
            "Next:",
            "  reasonledger ui     # a checklist walks you through the rest",
            "",
            "What shows up when:",
            "  Review     after your agent records its first decision",
            "  Map        after `reasonledger map --scan` (no model needed), or your agent maps it",
            "  Conflicts  once related decisions are judged (optional; your agent can do it)",
        ]
    )
    return "\n".join(lines) + "\n"


def _select_agents(root: Path, agents: str | None) -> tuple[tuple[AgentTarget, ...], list[str]]:
    """The agents to set up, and the lines that say what was skipped and why.

    Raises ValueError for an unknown key.
    """
    if agents:
        return parse_agents(agents), []
    reasons = detection_reasons(root)
    detected = tuple(t for t in TARGETS if t.key in reasons)
    if not detected:
        return TARGETS, [
            "No coding agent detected, so all of them were set up "
            f"(`reasonledger init --agents <{'|'.join(TARGET_KEYS)}>` to choose)."
        ]
    skipped = [t for t in TARGETS if t not in detected]
    notes = [
        "Set up for: " + ", ".join(f"{t.label} ({reasons[t.key]})" for t in detected) + ".",
    ]
    if skipped:
        notes.append("Skipped (not detected); add one with:")
        notes.extend(f"  reasonledger init --agents {t.key}   # {t.label}" for t in skipped)
    return detected, notes


def run_init(
    *,
    root: Path,
    reasonledger_root: Path | None = None,
    scan: bool = True,
    agents: str | None = None,
    rules: bool = True,
    policy: bool = False,
) -> str:
    """Scaffold the target repo and return stdout text (always idempotent).

    Raises ValueError for an unknown ``agents`` key.
    """
    resolved_root = root.resolve()
    targets, agent_notes = _select_agents(resolved_root, agents)
    # Scan first: the rule files written below are prose too, and are not the repo's decisions.
    report = scan_candidates(root=resolved_root) if scan else None
    actions = scaffold_repo(root=resolved_root, policy=policy)
    notes: list[str] = []
    changed = _ensure_agent_files(
        resolved_root, reasonledger_root, targets, rules=rules, actions=actions, notes=notes
    )
    return format_init_output(
        root=resolved_root,
        actions=actions,
        changed=changed,
        notes=notes,
        report=report,
        show_user_level=len(targets) == len(TARGETS),
        agent_notes=agent_notes,
    )
