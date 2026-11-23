"""Module detection: propose an application's modules from the repo alone."""

from reasonledger_core.modules.globs import PathMatcher
from reasonledger_core.modules.manifest import (
    ManifestError,
    load_manifest,
    merge_proposals,
    reject,
    write_manifest,
)
from reasonledger_core.modules.models import (
    Confidence,
    Manifest,
    Module,
    ModuleKind,
    ModuleStatus,
    ScanResult,
)
from reasonledger_core.modules.scan import scan_repo

__all__ = [
    "Confidence",
    "Manifest",
    "ManifestError",
    "Module",
    "ModuleKind",
    "ModuleStatus",
    "PathMatcher",
    "ScanResult",
    "load_manifest",
    "merge_proposals",
    "reject",
    "scan_repo",
    "write_manifest",
]
