"""The agent route: the user's own coding agent proposes the map over MCP.

These helpers are what the MCP tools call. They hand an agent the digest (or the drift delta),
validate what it submits exactly as the configured-model route does, and write proposals.
Nothing here calls a model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from reasonledger_core.modules.digest import build_digest, source_files
from reasonledger_core.modules.drift import detect_drift
from reasonledger_core.modules.files import modelled_files
from reasonledger_core.modules.globs import compress_paths
from reasonledger_core.modules.llm_mapper import PLACE_SYSTEM, SINGLE_SCHEMA, SINGLE_SYSTEM
from reasonledger_core.modules.manifest import (
    dangling_labels,
    load_manifest,
    merge_proposals,
    write_manifest,
)
from reasonledger_core.modules.mapper_check import matching_files, validate_map
from reasonledger_core.modules.mapping import bucket_sizes, corroborate, with_buckets
from reasonledger_core.modules.models import Module, Suggestion
from reasonledger_core.sync.repo import head_commit

_ANSWER = (
    "\nAnswer by calling submit_module_map(modules, mapped_by) with a list of "
    "{id, name, kind, description, paths}. Use the digest as given; read a file only where you "
    "are unsure. mapped_by is your tool and model, for example claude-code/claude-sonnet-5."
)
_DELTA = (
    PLACE_SYSTEM
    + "\nThe modules below already exist. Submit, in the same format, one entry per new capability "
    "(a new id) and, for files that belong to an existing module, an entry with that module's id "
    "and only the new paths. Create a new module only for a group of three or more files."
)


def _summary(modules: Sequence[Module]) -> list[dict[str, object]]:
    return [
        {
            "id": m.id,
            "name": m.name,
            "kind": m.kind.value,
            "tier": m.tier.value if m.tier else None,
            "status": m.status.value,
            "description": m.description,
        }
        for m in modules
    ]


def mapping_task(root: Path, *, delta: bool = False) -> dict[str, object]:
    manifest = load_manifest(root)
    if not delta:
        digest = build_digest(root, manifest.hints)
        return {
            "mode": "full",
            "instructions": SINGLE_SYSTEM + _ANSWER,
            "answer_schema": SINGLE_SCHEMA,
            "digest": digest.text,
            "hints": manifest.hints,
            "truncated": digest.truncated,
        }
    drift = detect_drift(root, manifest, source_files(root))
    return {
        "mode": "delta",
        "instructions": _DELTA + _ANSWER,
        "answer_schema": SINGLE_SCHEMA,
        "existing_modules": _summary(manifest.capabilities),  # buckets are not for an agent
        "unplaced_files": drift.unplaced,
        "candidate_groups": [g.model_dump() for g in drift.groups],
    }


def _result(ok: bool, **fields: object) -> dict[str, object]:
    return {"ok": ok, **fields}


def submit_map(
    root: Path, modules: Sequence[Mapping[str, object]], mapped_by: str, *, delta: bool = False
) -> dict[str, object]:
    """Validate and write an agent's proposal; return what was wrong so it can resubmit."""
    manifest = load_manifest(root)
    files = source_files(root)
    universe, _ = modelled_files(root)
    existing = {m.id for m in manifest.capabilities} if delta else set()
    fresh = [m for m in modules if str(m.get("id", "")) not in existing]
    suggestions: list[Suggestion] = []
    issues: list[str] = []
    for entry in (m for m in modules if str(m.get("id", "")) in existing):
        matched, found = matching_files(entry.get("paths"), files)
        issues.extend(found)
        if matched:
            suggestions.append(
                Suggestion(
                    module=str(entry["id"]),
                    paths=compress_paths(matched, universe),
                    reason="proposed by agent",
                    by=mapped_by,
                )
            )
    validated = validate_map(fresh, files, universe) if fresh else None
    issues.extend(validated.issues if validated else [])
    if not (validated and validated.modules) and not suggestions:
        return _result(
            False, issues=issues or ["no usable module in the submission"], written=False
        )
    graded = corroborate(validated.modules, root, files, mapped_by) if validated else []
    if delta:
        taken = {m.id for m in manifest.modules}
        updated = manifest.model_copy(
            update={
                "modules": [*manifest.modules, *(m for m in graded if m.id not in taken)],
                "suggestions": [*manifest.suggestions, *suggestions],
            }
        )
    else:
        updated = merge_proposals(manifest, graded, files)
    updated = updated.model_copy(
        update={"mapped_by": mapped_by, "mapped_at_commit": head_commit(root)}
    )
    updated = with_buckets(updated, files, universe)
    write_manifest(root, updated)
    return _result(
        True,
        written=True,
        modules=[m.id for m in graded],
        suggestions=len(suggestions),
        coverage=round(validated.coverage, 3) if validated else None,
        buckets=bucket_sizes(updated, files),
        issues=issues,
    )


def modules_view(root: Path) -> dict[str, object]:
    manifest = load_manifest(root)
    drift = detect_drift(root, manifest, source_files(root))
    return {
        "mapped_by": manifest.mapped_by,
        "mapped_at_commit": manifest.mapped_at_commit,
        "modules": _summary(manifest.modules),
        "labels": len(manifest.labels),
        "dangling_labels": dangling_labels(manifest),
        "pending_suggestions": len(manifest.suggestions),
        "drift": {
            "unplaced": len(drift.unplaced),
            "unplaced_share": round(drift.unplaced_share, 3),
            "candidate_groups": [{"name": g.name, "files": len(g.files)} for g in drift.groups],
            "orphan_modules": drift.orphans,
        },
    }
