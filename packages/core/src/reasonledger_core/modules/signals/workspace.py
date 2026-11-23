"""Workspace manifests: the strongest evidence, because a person declared the packages."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Collection, Sequence
from pathlib import Path, PurePosixPath

import yaml

from reasonledger_core.modules.config import MIN_MODULE_FILES
from reasonledger_core.modules.files import is_support
from reasonledger_core.modules.globs import ancestors, glob_regex
from reasonledger_core.modules.models import Candidate, SignalKind


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _as_strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _package_json(text: str) -> list[str]:
    try:
        data = json.loads(text)
    except ValueError:
        return []
    workspaces = data.get("workspaces") if isinstance(data, dict) else None
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    return _as_strings(workspaces)


def _pnpm(text: str) -> list[str]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    return _as_strings(data.get("packages")) if isinstance(data, dict) else []


def _toml_table(text: str, *keys: str) -> dict[str, object]:
    try:
        node: object = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return {}
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else {}


def _go_work(text: str) -> list[str]:
    members: list[str] = []
    inside = False
    for raw in text.splitlines():
        line = raw.split("//")[0].strip()
        if line.startswith("use ("):
            inside = True
        elif inside and line == ")":
            inside = False
        elif inside and line:
            members.append(line)
        elif line.startswith("use ") and "(" not in line:
            members.append(line[4:].strip())
    return members


def _member_patterns(root: Path) -> tuple[list[str], list[str]]:
    """(include, exclude) directory globs from every workspace manifest at the root."""
    include: list[str] = []
    exclude: list[str] = []
    readers = (
        ("package.json", _package_json),
        ("pnpm-workspace.yaml", _pnpm),
        ("go.work", _go_work),
    )
    for name, reader in readers:
        text = _read(root / name)
        if text:
            include += reader(text)
    for name, keys in (
        ("pyproject.toml", ("tool", "uv", "workspace")),
        ("Cargo.toml", ("workspace",)),
    ):
        text = _read(root / name)
        table = _toml_table(text, *keys) if text else {}
        include += _as_strings(table.get("members"))
        exclude += _as_strings(table.get("exclude"))
    return include, exclude


def _normal(pattern: str) -> str:
    return str(PurePosixPath(pattern.removeprefix("./").rstrip("/")))


def workspace_candidates(root: Path, files: Sequence[str]) -> list[Candidate]:
    include, exclude = _member_patterns(root)
    negated = [p[1:] for p in include if p.startswith("!")]
    wanted = [_normal(p) for p in include if not p.startswith("!") and p not in (".", "./")]
    if not wanted:
        return []
    skip = [glob_regex(_normal(p)) for p in [*exclude, *negated]]
    directories = sorted({d for path in files for d in ancestors(path)})
    chosen = [
        d
        for d in directories
        if any(glob_regex(p).match(d) for p in wanted)
        and not any(s.match(d) for s in skip)
        and not is_support(d + "/x")
    ]
    return [
        Candidate(name=PurePosixPath(d).name, signal=SignalKind.WORKSPACE, files=members)
        for d in chosen
        if len(members := _under(d, files)) >= MIN_MODULE_FILES
    ]


def _under(directory: str, files: Collection[str]) -> frozenset[str]:
    prefix = directory + "/"
    return frozenset(path for path in files if path.startswith(prefix))
