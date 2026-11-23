"""`reasonledger modules` — list, confirm, rename, merge, reject and label the module map.

A mapper only proposes modules; these commands are how a person decides. Confirmed modules are
never touched by a later `reasonledger map`, a rejected one stays down while a new map covers about
the same files, and a label (a file placed by hand) outranks every module glob.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from reasonledger_core.decisions.format import DECISIONS_DIR
from reasonledger_core.models.decision import DecisionRecord
from reasonledger_core.modules.digest import labelable_files, source_files
from reasonledger_core.modules.editing import (
    ModuleEditError,
    confirm_modules,
    high_confidence_ids,
    merge_modules,
    reject_module,
    rename_module,
)
from reasonledger_core.modules.hand_placement import (
    PlacementError,
    clear_hand_placement,
    place_by_hand,
    stale_placements,
)
from reasonledger_core.modules.labels import LabelError, label_files
from reasonledger_core.modules.manifest import (
    ManifestError,
    load_manifest,
    membership,
    write_manifest,
)
from reasonledger_core.modules.models import Manifest, Module, ModuleKind, ModuleStatus
from reasonledger_core.modules.review import next_up, pending_queue
from reasonledger_core.views.organize_files import load_records

from reasonledger_cli.identity import BY_HELP, no_identity_message, resolve_identity

EXIT_PASS = 0
EXIT_USAGE = 2
_ROOT_HELP = "Repo root (default: cwd)"


def _root(parser: argparse.ArgumentParser, *, nested: bool = False) -> None:
    """`--root` on `modules` and on each action. A nested one must not reset a parent's value."""
    default = argparse.SUPPRESS if nested else Path.cwd()
    parser.add_argument("--root", type=Path, default=default, help=_ROOT_HELP)


def add_modules_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = sub.add_parser(
        "modules", help="List, confirm, rename, merge, reject or label modules; place decisions"
    )
    _root(parser)
    parser.add_argument("--all", action="store_true", help="List every proposal (bare `modules`)")
    actions = parser.add_subparsers(dest="modules_command")
    listing = actions.add_parser("list", help="Show confirmed modules, the proposal queue, buckets")
    _root(listing, nested=True)
    listing.add_argument(
        "--all", action="store_true", default=argparse.SUPPRESS, help="List every proposal"
    )
    confirm = actions.add_parser("confirm", help="Confirm proposed modules, as a person")
    _root(confirm, nested=True)
    confirm.add_argument("ids", nargs="*", metavar="ID", help="modules to confirm")
    confirm.add_argument(
        "--all-high", action="store_true", help="Confirm every high-confidence one"
    )
    confirm.add_argument("--by", default=None, help=BY_HELP)
    rename = actions.add_parser("rename", help="Give a module a new name (its id follows)")
    _root(rename, nested=True)
    rename.add_argument("module_id")
    rename.add_argument("name", nargs="+", help="the new name")
    merge = actions.add_parser("merge", help="Fold the second module into the first")
    _root(merge, nested=True)
    merge.add_argument("keep", help="module that stays")
    merge.add_argument("absorb", help="module folded into it")
    reject = actions.add_parser("reject", help="Turn a proposal down; it stays down across maps")
    _root(reject, nested=True)
    reject.add_argument("module_id")
    reject.add_argument("--reason", default="", help="Why (kept with the rejection)")
    label = actions.add_parser(
        "label", help="Put files into a module or a bucket; the placement survives re-mapping"
    )
    _root(label, nested=True)
    label.add_argument(
        "items",
        nargs="+",
        metavar="PATH_OR_GLOB... TARGET",
        help="paths or globs, then the module id or bucket id (shared-frontend, shared-backend, "
        "shared, tooling) to put them in",
    )
    place = actions.add_parser(
        "place",
        help="Put a decision that has no working anchor into modules, as a person",
    )
    _root(place, nested=True)
    place.add_argument("decision_id")
    place.add_argument("modules", nargs="+", metavar="MODULE", help="module or bucket ids")
    place.add_argument("--by", default=None, help=BY_HELP)
    unplace = actions.add_parser("unplace", help="Take back a hand placement of a decision")
    _root(unplace, nested=True)
    unplace.add_argument("decision_id")


def _counts(root: Path, manifest: Manifest) -> Counter[str]:
    owner = membership(manifest)
    return Counter(o for p in source_files(root) if (o := owner.module_of(p)))


def _row(module: Module, files: int, extra: str) -> str:
    tier = module.tier.value if module.tier else "-"
    return f"  {module.id:30} {module.kind.value:10} {tier:9} {files:>5} files  {extra}".rstrip()


def _list(args: argparse.Namespace, manifest: Manifest) -> int:
    if not manifest.modules:
        print("no module map yet: run `reasonledger map`, or ask your coding agent to map the app")
        return EXIT_PASS
    counts = _counts(args.root, manifest)
    queue = pending_queue(manifest, counts)
    confirmed = [m for m in manifest.capabilities if m not in queue]
    buckets = [m for m in manifest.modules if m.kind is ModuleKind.BUCKET]
    print(f"{len(confirmed)} confirmed, {len(queue)} proposed, {len(buckets)} buckets")
    if confirmed:
        print("\nconfirmed")
        for m in sorted(confirmed, key=lambda m: m.id):
            print(_row(m, counts[m.id], f"by {m.confirmed_by}" if m.confirmed_by else ""))
    shown, waiting = (queue, 0) if args.all else next_up(queue)
    if queue:
        print(f"\nproposed, most trusted first (showing {len(shown)} of {len(queue)})")
        for m in shown:
            print(_row(m, counts[m.id], m.confidence.value if m.confidence else "-"))
        if waiting:
            print(f"  {waiting} more waiting; `reasonledger modules list --all` shows them")
        print("confirm with `reasonledger modules confirm <id>... --by <you>`")
    if buckets:
        print("\nbuckets (files no module owns; not modules)")
        for m in buckets:
            print(_row(m, counts[m.id], ""))
    records = {r.frontmatter.id: r for r in load_records(args.root)}
    for decision_id, why in stale_placements(manifest, records, args.root).items():
        print(f"hand placement of {decision_id} no longer applies: {why}")
    return EXIT_PASS


def _who(args: argparse.Namespace) -> str:
    who = resolve_identity(args.root, args.by)
    if who is None:
        raise ModuleEditError(no_identity_message("--by"))
    return who


def _confirm(args: argparse.Namespace, manifest: Manifest) -> tuple[Manifest, str]:
    ids = list(args.ids)
    if args.all_high:
        ids += [i for i in high_confidence_ids(manifest) if i not in ids]
    if not ids:
        raise ModuleEditError("name the modules to confirm, or pass --all-high")
    updated, changed = confirm_modules(manifest, ids, by=_who(args), at=datetime.now(UTC))
    done = f"confirmed {len(changed)}: {', '.join(changed)}" if changed else "already confirmed"
    return updated, done


def _rename(args: argparse.Namespace, manifest: Manifest) -> tuple[Manifest, str]:
    updated, new_id = rename_module(manifest, args.module_id, " ".join(args.name))
    note = ""
    if next(m for m in updated.modules if m.id == new_id).status is ModuleStatus.PROPOSED:
        note = "; it is still a proposal, so confirm it or the next map replaces it"
    return updated, f"renamed {args.module_id} to {new_id}{note}"


def _merge(args: argparse.Namespace, manifest: Manifest) -> tuple[Manifest, str]:
    by_id = {m.id: m for m in manifest.modules}
    updated = merge_modules(manifest, args.keep, args.absorb)
    note = ""
    keep, absorb = by_id[args.keep], by_id[args.absorb]
    if keep.tier and absorb.tier and keep.tier != absorb.tier:
        note = "; it now mixes frontend and backend, which the map keeps apart"
    return updated, f"merged {args.absorb} into {args.keep}{note}"


def _reject(args: argparse.Namespace, manifest: Manifest) -> tuple[Manifest, str]:
    updated = reject_module(manifest, args.module_id, args.reason)
    pointing = sum(1 for target in manifest.labels.values() if target == args.module_id)
    note = f"; {pointing} label(s) point at it and `map --drift` will name them" if pointing else ""
    return (
        updated,
        f"rejected {args.module_id}; it stays down while a map covers about its files{note}",
    )


def _label(args: argparse.Namespace, manifest: Manifest) -> tuple[Manifest, str]:
    *patterns, target = args.items
    updated, matched = label_files(manifest, patterns, target, labelable_files(args.root, patterns))
    return updated, f"labelled {len(matched)} file(s) as {target}"


def _record(root: Path, decision_id: str) -> DecisionRecord:
    found = next((r for r in load_records(root) if r.frontmatter.id == decision_id), None)
    if found is None:
        raise PlacementError(f"no decision {decision_id} in {DECISIONS_DIR}")
    return found


def _place(args: argparse.Namespace, manifest: Manifest) -> tuple[Manifest, str]:
    record = _record(args.root, args.decision_id)
    updated = place_by_hand(manifest, record, args.root, args.modules, _who(args))
    return updated, f"placed {args.decision_id} in {', '.join(dict.fromkeys(args.modules))}"


def _unplace(args: argparse.Namespace, manifest: Manifest) -> tuple[Manifest, str]:
    return clear_hand_placement(
        manifest, args.decision_id
    ), f"took back {args.decision_id}'s placement"


_EDITS: dict[str, Callable[[argparse.Namespace, Manifest], tuple[Manifest, str]]] = {
    "confirm": _confirm,
    "rename": _rename,
    "merge": _merge,
    "reject": _reject,
    "label": _label,
    "place": _place,
    "unplace": _unplace,
}


def run_modules_cmd(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.root)
        command = args.modules_command or "list"
        if command == "list":
            return _list(args, manifest)
        updated, message = _EDITS[command](args, manifest)
    except (ManifestError, ModuleEditError, LabelError, PlacementError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    write_manifest(args.root, updated)
    print(message)
    return EXIT_PASS
