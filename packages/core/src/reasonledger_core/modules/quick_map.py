"""The quick map: propose modules from folders, names and git history, with no model.

This is the scan written to the manifest as proposals, so a repo gets a first
module map in seconds, nothing is sent anywhere, and no consent is involved. A person (or a
model, later) can still refine it; confirmed and rejected modules are never touched.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from reasonledger_core.modules.digest import source_files
from reasonledger_core.modules.manifest import load_manifest, write_manifest
from reasonledger_core.modules.mapping import apply_map, bucket_sizes
from reasonledger_core.modules.models import ModuleStatus
from reasonledger_core.modules.scan import scan_repo

MAPPED_BY = "reasonledger-scan"


class QuickMapOutcome(BaseModel):
    proposed: int
    files_total: int
    placed: int
    unplaced: int
    buckets: dict[str, int]
    limitations: list[str]


def quick_map(root: Path) -> QuickMapOutcome:
    """Scan ``root`` and write the proposed modules to ``.reasonledger/modules.yml``."""
    manifest = load_manifest(root)
    result = scan_repo(root, manifest=manifest)
    proposals = [m for m in result.modules if m.status is not ModuleStatus.CONFIRMED]
    written = apply_map(manifest, proposals, MAPPED_BY, root)
    write_manifest(root, written)
    placed = sum(result.files_per_module.values())
    return QuickMapOutcome(
        proposed=len(proposals),
        files_total=result.files_total,
        placed=placed,
        unplaced=result.unplaced_files,
        buckets=bucket_sizes(written, source_files(root)),
        limitations=result.limitations,
    )
