"""Parse `.reasonledger/policy.yml` into a typed policy document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from reasonledger_core.models.policy import (
    PolicyDocument,
    PolicyRequire,
    PolicyRule,
    PolicyWhen,
)

DEFAULT_POLICY_PATH = Path(".reasonledger/policy.yml")


class PolicyParseError(ValueError):
    """Raised when a policy file is missing or invalid."""


# The model that owns the keys under each location in the file, so an unknown key can be
# reported with the keys that would have been accepted in its place.
_SECTION_MODELS: dict[str | None, type[BaseModel]] = {
    None: PolicyRule,
    "when": PolicyWhen,
    "require": PolicyRequire,
}


def _describe(exc: ValidationError, data: dict[str, Any]) -> str:
    """One line per problem; an unknown key names its rule, the key and the allowed keys."""
    lines: list[str] = []
    for error in exc.errors():
        loc = error["loc"]
        if error["type"] != "extra_forbidden":
            lines.append(f"{'.'.join(str(part) for part in loc)}: {error['msg']}")
            continue
        *parents, key = loc
        if len(parents) <= 1:  # top level of the document
            allowed = sorted(PolicyDocument.model_fields)
            lines.append(f"unknown key {key!r} in the policy; allowed: {', '.join(allowed)}")
            continue
        index = parents[1]
        rule = data["rules"][index] if isinstance(data.get("rules"), list) else {}
        rule_id = rule.get("id", f"#{index}") if isinstance(rule, dict) else f"#{index}"
        section = parents[2] if len(parents) > 2 and isinstance(parents[2], str) else None
        allowed = sorted(_SECTION_MODELS[section].model_fields)
        where = f"{section!r} of rule" if section else "rule"
        lines.append(f"unknown key {key!r} in {where} {rule_id!r}; allowed: {', '.join(allowed)}")
    return "invalid policy document: " + "; ".join(lines)


def parse_policy_yaml(raw: str) -> PolicyDocument:
    try:
        data: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PolicyParseError(f"invalid YAML: {exc}") from exc
    if data is None:
        return PolicyDocument()
    if not isinstance(data, dict):
        raise PolicyParseError("policy root must be a mapping")
    try:
        return PolicyDocument.model_validate(data)
    except ValidationError as exc:
        raise PolicyParseError(_describe(exc, data)) from exc


def load_policy_file(path: Path) -> PolicyDocument:
    if not path.is_file():
        raise PolicyParseError(f"policy file not found: {path}")
    return parse_policy_yaml(path.read_text(encoding="utf-8"))
