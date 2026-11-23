"""`reasonledger ui` — the first-run checklist, consent and quick-map endpoints.

The checklist is built in the browser from the facts returned here; nothing in this module
calls a model. Consent is the one thing a request can change: a grant or a revoke for the
data classes the configured model would receive. Like every other mutation it needs the
session token, which only the page the server itself served holds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reasonledger_core.consent import (
    DESCRIPTIONS,
    LABELS,
    ConsentError,
    DataClass,
    destination,
    grant,
    granted_classes,
    parse_classes,
    revoke,
)
from reasonledger_core.decisions import load_decisions_from_dir
from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.importer.config import (
    ConfigError,
    ExtractorConfig,
    ExtractorProvider,
    extracted_by_label,
    load_extractor_config,
)
from reasonledger_core.importer.propose import PROPOSED_DIR
from reasonledger_core.modules.manifest import ManifestError, load_manifest
from reasonledger_core.modules.models import ModuleStatus
from reasonledger_core.modules.quick_map import quick_map
from reasonledger_core.views import build_ledger_view_cached

from reasonledger_cli.agent_targets import TARGETS
from reasonledger_cli.consent_cmd import class_counts
from reasonledger_cli.init_cmd import scan_candidates

JsonResponse = tuple[int, dict[str, Any]]
HTTP_OK = 200
HTTP_BAD_REQUEST = 400


def _config(root: Path) -> ExtractorConfig:
    try:
        return load_extractor_config(root)
    except ConfigError:
        return ExtractorConfig()


def _model_facts(root: Path, config: ExtractorConfig) -> dict[str, Any]:
    host = destination(config)
    configured = config.provider is not ExtractorProvider.DISABLED
    return {
        "configured": configured,
        "provider": config.provider.value,
        "model": config.model,
        "off_machine": host is not None,
        "destination": host,
        "import_command": (
            f"reasonledger import --extracted-by {extracted_by_label(config)}"
            if configured
            else None
        ),
    }


def _map_facts(root: Path) -> dict[str, int]:
    try:
        modules = load_manifest(root).modules
    except ManifestError:
        modules = []
    return {
        "modules": len(modules),
        "confirmed": sum(1 for m in modules if m.status is ModuleStatus.CONFIRMED),
    }


def handle_get_setup(root: Path) -> JsonResponse:
    """The facts the first-run checklist is drawn from."""
    config = _config(root)
    view = build_ledger_view_cached(root)
    counts = view.counts or {}
    return HTTP_OK, {
        "ledger": (root / ".reasonledger").is_dir(),
        "mcp_files": [t.mcp_path for t in TARGETS if t.mcp_path and (root / t.mcp_path).is_file()],
        "decisions": len(load_decisions_from_dir(root / DECISIONS_DIR)),
        "proposals": len(load_decisions_from_dir(root / PROPOSED_DIR)),
        "candidates": scan_candidates(root=root).total,
        "model": _model_facts(root, config),
        "map": _map_facts(root),
        "unjudged": int(counts.get("unverified", 0)),
        "conflicts": int(counts.get("conflicts", 0)),
    }


def consent_payload(root: Path) -> dict[str, Any]:
    config = _config(root)
    host = destination(config)
    allowed = granted_classes(root, config)
    classes = list(DataClass)
    counts = class_counts(root, classes) if host is not None else {}
    return {
        "configured": config.provider is not ExtractorProvider.DISABLED,
        "off_machine": host is not None,
        "destination": host,
        "model": f"{config.provider.value}:{config.model or '?'}",
        "classes": [
            {
                "id": item.value,
                "label": LABELS[item],
                "description": DESCRIPTIONS[item],
                "count": counts.get(item, ""),
                "allowed": item in allowed,
            }
            for item in classes
        ],
    }


def handle_get_consent(root: Path) -> JsonResponse:
    return HTTP_OK, consent_payload(root)


def handle_post_consent(root: Path, body: dict[str, Any]) -> JsonResponse:
    """Grant or revoke named classes. Nothing is granted for a model on this machine."""
    action = body.get("action")
    names = body.get("classes")
    if action not in {"grant", "revoke"} or not isinstance(names, list):
        return HTTP_BAD_REQUEST, {"error": "send action (grant or revoke) and a classes list"}
    try:
        classes = parse_classes([str(name) for name in names])
        if action == "grant":
            if not classes:
                return HTTP_BAD_REQUEST, {"error": "name what to allow"}
            grant(root, _config(root), classes)
        else:
            revoke(root, classes or None)
    except ConsentError as exc:
        return HTTP_BAD_REQUEST, {"error": str(exc)}
    return HTTP_OK, consent_payload(root)


def handle_post_map_scan(root: Path) -> JsonResponse:
    """Write the model-free quick map. Local, offline; nothing is sent anywhere."""
    return HTTP_OK, quick_map(root).model_dump(mode="json")
