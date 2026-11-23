"""`reasonledger map` — propose, refresh and check the application's module map.

Uses the model the repo already has configured (`reasonledger config`), or you can let your own
coding agent do it over MCP (`get_mapping_task`). The model sees file paths and route paths, never
file contents. Drift checking needs no model at all.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from reasonledger_core.consent import DataClass
from reasonledger_core.importer.config import (
    ConfigError,
    ExtractorProvider,
    load_extractor_config,
)
from reasonledger_core.importer.llm import LlmError
from reasonledger_core.modules.config import DRIFT_FAIL_SHARE
from reasonledger_core.modules.digest import build_digest, source_files
from reasonledger_core.modules.drift import detect_drift
from reasonledger_core.modules.llm_mapper import LlmMapper, MapMode
from reasonledger_core.modules.manifest import (
    ManifestError,
    dangling_labels,
    load_manifest,
    write_manifest,
)
from reasonledger_core.modules.mapping import (
    accept_suggestions,
    apply_map,
    apply_refresh,
    bucket_sizes,
    propose_map,
    refresh_map,
)
from reasonledger_core.modules.models import Manifest
from reasonledger_core.modules.quick_map import quick_map

from reasonledger_cli.consent_cmd import ensure_consent

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
SHOWN_MODULES = 15
SHOWN_ISSUES = 8


def add_map_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = sub.add_parser("map", help="Propose, refresh or check the application's module map")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repo root (default: cwd)")
    parser.add_argument("--mode", choices=["auto", "single", "staged"], default="auto")
    parser.add_argument(
        "--model", default=None, help="Use this model instead of the configured one"
    )
    parser.add_argument("--refresh", action="store_true", help="Only place files no module claims")
    parser.add_argument("--drift", action="store_true", help="Report unplaced files; no model call")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be sent; call nothing"
    )
    parser.add_argument(
        "--allow-cloud", action="store_true", help="Allow a provider off this machine"
    )
    parser.add_argument("--accept-suggestions", action="store_true", help="Add suggested files")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Propose modules from folders, names and git history; no model, nothing is sent",
    )


def _print_drift(
    report_total: int, unplaced: int, share: float, groups: list[str], orphans: list[str]
) -> None:
    print(f"unplaced source files: {unplaced} of {report_total} ({share:.0%})")
    for line in groups:
        print(f"  new-module candidate: {line}")
    if orphans:
        print(f"modules matching no file: {', '.join(orphans)}")


def _drift(root: Path) -> int:
    manifest = load_manifest(root)
    files = source_files(root)
    report = detect_drift(root, manifest, files)
    _print_drift(
        report.total,
        len(report.unplaced),
        report.unplaced_share,
        [f"{g.name} ({len(g.files)} files) — {g.reason}" for g in report.groups],
        report.orphans,
    )
    lost = dangling_labels(manifest)
    if lost:
        print(f"labels pointing at a module that is gone: {', '.join(lost)}")
    over = report.unplaced_share > DRIFT_FAIL_SHARE
    if over:
        print(f"drift above {DRIFT_FAIL_SHARE:.0%}: run `reasonledger map --refresh`")
    return EXIT_FAIL if over else EXIT_PASS


def _accept(root: Path) -> int:
    manifest = load_manifest(root)
    if not manifest.suggestions:
        print("no suggestions waiting")
        return EXIT_PASS
    count = len(manifest.suggestions)
    write_manifest(root, accept_suggestions(manifest, root, source_files(root)))
    print(f"added the files from {count} suggestion(s) to their modules")
    return EXIT_PASS


def _scan(root: Path) -> int:
    outcome = quick_map(root)
    print(
        f"scan: {outcome.proposed} modules proposed, {outcome.placed} of {outcome.files_total} "
        f"files in a module. No model was used; nothing was sent."
    )
    if outcome.buckets:
        held = ", ".join(f"{name} {count}" for name, count in outcome.buckets.items())
        print(f"buckets (files no module owns): {held}")
    for note in outcome.limitations:
        print(f"  note: {note}")
    print("proposals are in .reasonledger/modules.yml; confirm the ones you accept")
    return EXIT_PASS


def _mapper(root: Path, args: argparse.Namespace) -> LlmMapper | int:
    try:
        config = load_extractor_config(root)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if config.provider is ExtractorProvider.DISABLED:
        print(
            "error: no model is configured. Run `reasonledger config`, or ask your coding agent to "
            "call the MCP tool get_mapping_task and submit_module_map.",
            file=sys.stderr,
        )
        return EXIT_USAGE
    return LlmMapper(config, model=args.model)


def run_map_cmd(args: argparse.Namespace) -> int:
    root: Path = args.root
    try:
        manifest = load_manifest(root)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.drift:
        return _drift(root)
    if args.accept_suggestions:
        return _accept(root)
    if args.scan:
        return _scan(root)
    mapper = _mapper(root, args)
    if isinstance(mapper, int):
        return mapper
    digest = build_digest(root, manifest.hints)
    print(f"model: {mapper.name} ({'off this machine' if mapper.sends_off_machine else 'local'})")
    if args.refresh:
        unplaced = len(detect_drift(root, manifest, list(digest.source_files)).unplaced)
        print(f"sends: {unplaced} file paths that no module claims; never file contents")
    else:
        print(
            f"sends: {len(digest.source_files)} file paths and {digest.route_count} route paths "
            f"({len(digest.text):,} characters); never file contents"
        )
    if mapper.sends_off_machine and not args.allow_cloud:
        denied = ensure_consent(
            root,
            load_extractor_config(root),
            [DataClass.PATHS],
            command="map",
            extra_hint=" (or add --allow-cloud to send the above for this run only)",
        )
        if denied is not None:
            return denied
    if args.dry_run:
        return EXIT_PASS
    try:
        if args.refresh:
            return _refresh(root, mapper, manifest)
        return _propose(root, mapper, manifest, cast(MapMode, args.mode))
    except LlmError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAIL


def _refresh(root: Path, mapper: LlmMapper, manifest: Manifest) -> int:
    outcome = refresh_map(root, mapper, manifest)
    write_manifest(root, apply_refresh(manifest, outcome, mapper.name, root))
    print(
        f"unplaced before: {len(outcome.drift.unplaced)}  new modules: {len(outcome.new_modules)}  "
        f"suggestions: {len(outcome.suggestions)}  to buckets: {len(outcome.unresolved)}"
    )
    for module in outcome.new_modules:
        print(f"  new module proposed: {module.id}")
    if outcome.suggestions:
        print("review the suggestions, then run `reasonledger map --accept-suggestions`")
    return EXIT_PASS


def _propose(root: Path, mapper: LlmMapper, manifest: Manifest, mode: MapMode) -> int:
    outcome = propose_map(root, mapper, manifest, mode)
    written = apply_map(manifest, outcome.validated.modules, mapper.name, root)
    write_manifest(root, written)
    validated = outcome.validated
    print(
        f"{outcome.mode} mode: {len(validated.modules)} modules proposed, "
        f"{validated.placed} of {validated.total} source files in a module "
        f"({validated.coverage:.0%})"
    )
    for module in validated.modules[:SHOWN_MODULES]:
        confidence = module.confidence.value if module.confidence else "-"
        tier = module.tier.value if module.tier else "-"
        print(f"  {module.id:32} {module.kind.value:10} {tier:9} {confidence}")
    for issue in validated.issues[:SHOWN_ISSUES]:
        print(f"  issue: {issue}")
    sizes = bucket_sizes(written, source_files(root))
    if sizes:
        held = ", ".join(f"{name} {count}" for name, count in sizes.items())
        print(f"buckets (files no capability owns): {held}")
        print("move any file with `reasonledger modules label <path-or-glob> <module|bucket>`")
    print("proposals are in .reasonledger/modules.yml; confirm the ones you accept")
    return EXIT_PASS
