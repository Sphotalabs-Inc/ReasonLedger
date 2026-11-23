"""What `init` writes for each supported coding agent: its MCP config and its rule file.

One table drives every agent, so adding one is a row here and not a new code path. Project-level
files only; user-level configs (Codex, Windsurf, ...) are printed for the user, never written.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from reasonledger_core.importer.scan import RULE_BEGIN, RULE_END

CLI_EXECUTABLE = "reasonledger"
MCP_SUBCOMMAND = "mcp"
UVX_EXECUTABLE = "uvx"
# uv keeps `uvx` environments here; PATH holds one only while that process runs.
UV_EPHEMERAL_DIR = re.compile(r"^(environments|archive)-v\d+$")
SERVER_NAME = "reasonledger"
MDC_FRONTMATTER = "---\ndescription: ReasonLedger decision capture\nalwaysApply: true\n---\n\n"

AGENT_RULE = """\
# ReasonLedger

Before editing a file, call MCP `decisions_for` with its path: it returns the decisions that
cover that code, so you change it knowing why it is the way it is.

When making a non-trivial architectural or behavioral choice:
1. Call MCP `query_decisions` with a short description (use `semantic: true` when available).
2. Prefer aligning with prior Decision records; if diverging, explain why in the new record
   and pass the old record's id as `supersedes` when the new one replaces it.
3. After deciding, call `record_decision` with `ai_tool` set to the active tool (e.g.
   `claude-code`, `cursor`, `copilot`), `model` set to the exact model id, and `justifies`
   loci as `path::symbol` or `path:START-END`.
   Never pass `oversight` or `approved_by`: the record is saved `pending` and a person gives
   the verdict with `reasonledger approve` or in `reasonledger ui`.
   Set `proposed_by`: `human` only if the user stated or explicitly accepted the choice in
   chat before you acted, `ai` if you chose or recommended it. Never claim `human` to be safe.
4. Commit `.reasonledger/decisions/*.md` in the same PR as the code change.
5. Do not put secrets, customer PII, or source code dumps into decision bodies.
6. To backfill decisions already written in docs or commit messages, call `get_import_task`,
   read those paths, and call `submit_candidates`. That writes proposals for a person to
   confirm. Do not approve them.
"""


@dataclass(frozen=True)
class AgentTarget:
    key: str
    label: str
    mcp_path: str | None
    rule_path: str
    mcp_root_key: str = "mcpServers"
    stdio_type: bool = False  # VS Code entries name their transport
    owns_rule_file: bool = False  # whole file is ours; otherwise a marked block in a shared one


TARGETS = (
    AgentTarget("claude-code", "Claude Code", ".mcp.json", "CLAUDE.md"),
    AgentTarget(
        "cursor",
        "Cursor",
        ".cursor/mcp.json",
        ".cursor/rules/reasonledger.mdc",
        owns_rule_file=True,
    ),
    AgentTarget(
        "vscode",
        "VS Code",
        ".vscode/mcp.json",
        ".github/copilot-instructions.md",
        mcp_root_key="servers",
        stdio_type=True,
    ),
    AgentTarget("agents-md", "any agent that reads AGENTS.md", None, "AGENTS.md"),
)
TARGET_KEYS = tuple(t.key for t in TARGETS)

# Where agents with a user-level config keep it. Printed, never written.
USER_LEVEL_CONFIGS = (
    ("Codex", "~/.codex/config.toml  ([mcp_servers.reasonledger] command / args)"),
    ("Windsurf", "~/.codeium/windsurf/mcp_config.json"),
)


ALL_AGENTS = "all"

# Per agent: repo paths whose presence means the project uses it, and an executable on PATH.
_DETECT_PATHS = {
    "claude-code": ("CLAUDE.md", ".claude", ".mcp.json"),
    "cursor": (".cursor", ".cursorrules"),
    "vscode": (".vscode", ".github/copilot-instructions.md"),
    "agents-md": ("AGENTS.md",),
}
_DETECT_EXECUTABLE = {"claude-code": "claude", "cursor": "cursor"}


def agent_cli_found(executable: str) -> bool:
    """Whether an agent's CLI is on PATH. One seam, so tests can pin the machine's answer."""
    return shutil.which(executable) is not None


def detection_reasons(root: Path) -> dict[str, str]:
    """Agent key -> why this project is taken to use it, for each agent detected."""
    reasons: dict[str, str] = {}
    for target in TARGETS:
        found = next((rel for rel in _DETECT_PATHS[target.key] if (root / rel).exists()), None)
        executable = _DETECT_EXECUTABLE.get(target.key)
        if found is not None:
            reasons[target.key] = f"found {found}"
        elif executable is not None and agent_cli_found(executable):
            reasons[target.key] = f"found `{executable}` on PATH"
    return reasons


def detect_agents(root: Path) -> tuple[AgentTarget, ...]:
    """The agents this project already uses, by their files or by their CLI on PATH."""
    reasons = detection_reasons(root)
    return tuple(target for target in TARGETS if target.key in reasons)


def parse_agents(value: str | None) -> tuple[AgentTarget, ...]:
    """``--agents`` as targets; an empty value or ``all`` is every one.

    Raises ValueError on an unknown key.
    """
    if not value or value == ALL_AGENTS:
        return TARGETS
    wanted = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [key for key in wanted if key not in TARGET_KEYS]
    if unknown:
        raise ValueError(
            f"unknown agent {', '.join(unknown)}; choose from {', '.join(TARGET_KEYS)}"
        )
    return tuple(t for t in TARGETS if t.key in wanted)


def _is_ephemeral(executable: str) -> bool:
    """True for an executable inside a throwaway `uvx` environment or the uv cache."""
    path = Path(executable)
    if any(UV_EPHEMERAL_DIR.match(part) for part in path.parts):
        return True
    cache = os.environ.get("UV_CACHE_DIR")
    return cache is not None and cache != "" and path.is_relative_to(Path(cache))


def installed_cli() -> bool:
    """Whether a fresh login shell would find `reasonledger`, as opposed to only this process.

    Run through `uvx`, PATH carries the ephemeral environment's `bin`, so `shutil.which`
    finds an executable the agent will never have.
    """
    found = shutil.which(CLI_EXECUTABLE)
    return found is not None and not _is_ephemeral(found)


def mcp_server_entry(
    *, reasonledger_root: Path | None, app_root: Path, stdio_type: bool = False
) -> dict[str, object]:
    """The agent's spawn command for the MCP server, against *this* app repo.

    An installed `reasonledger` runs its `mcp` subcommand; otherwise `uvx` fetches it, so a
    `uvx reasonledger init` user needs no second install. A caller who named a checkout with
    `--reasonledger-root` gets `uv run --project`, not `--directory`: that moves the working
    directory to the checkout, which is how a relative path resolves against the wrong repo.
    """
    repo_args = [MCP_SUBCOMMAND, "--repo-root", str(app_root.resolve())]
    entry: dict[str, object]
    if reasonledger_root is not None:
        entry = {
            "command": "uv",
            "args": [
                "run",
                "--project",
                str(reasonledger_root.resolve()),
                CLI_EXECUTABLE,
                *repo_args,
            ],
        }
    elif installed_cli():
        entry = {"command": CLI_EXECUTABLE, "args": repo_args}
    else:
        entry = {"command": UVX_EXECUTABLE, "args": [CLI_EXECUTABLE, *repo_args]}
    return {"type": "stdio", **entry} if stdio_type else entry


def mcp_config_text(target: AgentTarget, entry: dict[str, object]) -> str:
    return json.dumps({target.mcp_root_key: {SERVER_NAME: entry}}, indent=2) + "\n"


def _has_entry(path: Path, target: AgentTarget) -> bool:
    try:
        servers = json.loads(path.read_text(encoding="utf-8")).get(target.mcp_root_key, {})
    except (OSError, ValueError, AttributeError):
        return False
    return isinstance(servers, dict) and SERVER_NAME in servers


def write_mcp_config(
    root: Path,
    target: AgentTarget,
    *,
    reasonledger_root: Path | None,
    actions: list[str],
    notes: list[str],
) -> bool:
    """Write the agent's MCP config when absent; True when a file was created.

    An existing file is the user's own and is never edited: when it has no ReasonLedger
    entry, the entry is left in ``notes`` to merge by hand.
    """
    if target.mcp_path is None:
        return False
    entry = mcp_server_entry(
        reasonledger_root=reasonledger_root, app_root=root, stdio_type=target.stdio_type
    )
    text = mcp_config_text(target, entry)
    path = root / target.mcp_path
    if path.exists():
        if not _has_entry(path, target):
            notes.append(f"{target.mcp_path} exists; add this entry yourself:\n{text.rstrip()}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    actions.append(f"created {target.mcp_path} (MCP server for {target.label})")
    return True


def _block() -> str:
    return f"{RULE_BEGIN}\n{AGENT_RULE.rstrip()}\n{RULE_END}"


def _merge_block(existing: str) -> str:
    """``existing`` with our block replaced in place, or appended; nothing else is touched."""
    pattern = re.compile(re.escape(RULE_BEGIN) + r".*?" + re.escape(RULE_END), re.DOTALL)
    block = _block()
    if pattern.search(existing):
        return pattern.sub(lambda _match: block, existing, count=1)
    if not existing or existing.endswith("\n\n"):
        return f"{existing}{block}\n"
    gap = "\n" if existing.endswith("\n") else "\n\n"
    return f"{existing}{gap}{block}\n"


def write_rule(root: Path, target: AgentTarget, actions: list[str]) -> None:
    """Write the agent rule: the whole file when ours, else a marked block in a shared one.

    Bytes are read and written raw so a file's own line endings survive a rewrite.
    """
    path = root / target.rule_path
    existed = path.exists()
    current = path.read_bytes().decode("utf-8") if existed else ""
    wanted = MDC_FRONTMATTER + AGENT_RULE if target.owns_rule_file else _merge_block(current)
    if existed and wanted == current:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(wanted.encode("utf-8"))
    verb = "updated" if existed else "created"
    actions.append(f"{verb} {target.rule_path} (decision-capture rule for {target.label})")
