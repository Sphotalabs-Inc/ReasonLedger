"""S52 — anchors survive edits, in any language, and reading never rewrites the ledger."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.decisions import load_decisions_from_dir, record_decision_to_path
from reasonledger_core.decisions.fingerprint import Drift, fingerprint_range, resolve_anchor
from reasonledger_core.decisions.format import DECISIONS_DIR, write_decision_file
from reasonledger_core.models.decision import AiTool, RecordDecisionInput
from reasonledger_core.reasoning import MatchKind, resolve_why
from reasonledger_core.reasoning.ts_symbols import extract_ts_symbols
from reasonledger_core.reasoning.why import WhyTarget
from reasonledger_core.views import build_ledger_view

TS = """import { db } from "./db";

export function save(row: Row): void {
  validate(row);
  db.insert(row);
  audit("saved");
}

export function other(): number {
  return 1;
}
"""
GO = """package store

func Save(row Row) error {
	if err := validate(row); err != nil {
		return err
	}
	return insert(row)
}

func Other() int {
	return 1
}
"""
INSERTED = "".join(f"// padding line {n}\n" for n in range(20))


def _record(root: Path, locus: str, decision_id: str = "dec_drift01") -> Path:
    _, path = record_decision_to_path(
        RecordDecisionInput(
            context="How do we persist rows?",
            choice="Validate then insert",
            ai_tool=AiTool.NONE,
            alternatives_rejected=["Insert first"],
            justifies=[locus],
            decision_id=decision_id,
        ),
        root=root,
    )
    return path


def _why(root: Path, path: str, line: int | None) -> list[MatchKind]:
    records = load_decisions_from_dir(root / DECISIONS_DIR)
    return [h.match for h in resolve_why(records, WhyTarget(path=path, line=line), root=root)]


@pytest.mark.phase_4
@pytest.mark.parametrize(
    ("name", "source", "locus", "new_line"),
    [("store.ts", TS, "store.ts:3-7", 24), ("store.go", GO, "store.go:3-8", 24)],
)
def test_anchor_moved_is_found(
    tmp_path: Path, name: str, source: str, locus: str, new_line: int
) -> None:
    (tmp_path / name).write_text(source, encoding="utf-8")
    _record(tmp_path, locus)
    assert _why(tmp_path, name, int(locus.split(":")[1].split("-")[0])) == [MatchKind.LINE]
    (tmp_path / name).write_text(INSERTED + source, encoding="utf-8")
    assert _why(tmp_path, name, new_line) == [MatchKind.MOVED]
    assert _why(tmp_path, name, 3) == []  # the old lines now hold padding


@pytest.mark.phase_4
def test_anchor_lost_when_block_rewritten(tmp_path: Path) -> None:
    (tmp_path / "store.ts").write_text(TS, encoding="utf-8")
    _record(tmp_path, "store.ts:3-7")
    (tmp_path / "store.ts").write_text(TS.replace("db.insert(row)", "queue.push(row)"), "utf-8")
    assert _why(tmp_path, "store.ts", 4) == [MatchKind.LOST]


@pytest.mark.phase_4
def test_anchor_ambiguous_is_lost(tmp_path: Path) -> None:
    (tmp_path / "store.ts").write_text(TS, encoding="utf-8")
    _record(tmp_path, "store.ts:3-7")
    block = "\n".join(TS.splitlines()[2:7]) + "\n"
    (tmp_path / "store.ts").write_text(INSERTED + TS + "\n" + block, encoding="utf-8")
    assert _why(tmp_path, "store.ts", 24) == [MatchKind.LOST]


@pytest.mark.phase_4
def test_whitespace_and_blank_lines_do_not_move_the_fingerprint() -> None:
    lines = ["a  ", "", "  b", "c"]
    assert fingerprint_range(lines, 1, 4) == fingerprint_range(["a", "  b", "", "", "c"], 1, 5)
    assert resolve_anchor(["x", *lines], 2, 5, fingerprint_range(lines, 1, 4) or "").state is (
        Drift.INTACT
    )


@pytest.mark.phase_4
def test_legacy_locus_without_hash_unchanged(tmp_path: Path) -> None:
    (tmp_path / "store.ts").write_text(TS, encoding="utf-8")
    path = _record(tmp_path, "store.ts:3-7")
    record = load_decisions_from_dir(tmp_path / DECISIONS_DIR)[0]
    record.frontmatter.anchor_hashes = None
    write_decision_file(path, record)
    (tmp_path / "store.ts").write_text(INSERTED + TS, encoding="utf-8")
    assert _why(tmp_path, "store.ts", 24) == []  # raw range, exactly as before
    assert _why(tmp_path, "store.ts", 4) == [MatchKind.LINE]


@pytest.mark.phase_4
def test_why_never_writes(tmp_path: Path) -> None:
    from reasonledger_cli.main import main
    from reasonledger_mcp.tools import call_decisions_for

    (tmp_path / "store.ts").write_text(TS, encoding="utf-8")
    _record(tmp_path, "store.ts:3-7")
    (tmp_path / "store.ts").write_text(INSERTED + TS, encoding="utf-8")
    ledger = tmp_path / DECISIONS_DIR
    before = {p.name: p.read_bytes() for p in ledger.glob("dec_*.md")}
    main(["why", "store.ts:24", "--root", str(tmp_path)])
    main(["status", "--root", str(tmp_path)])
    build_ledger_view(tmp_path)
    assert call_decisions_for(tmp_path, paths=["store.ts"], line=24)["decisions"][0]["match"] == (
        "moved"
    )
    assert {p.name: p.read_bytes() for p in ledger.glob("dec_*.md")} == before


@pytest.mark.phase_4
def test_status_reports_moved_and_lost_beside_orphaned(tmp_path: Path) -> None:
    (tmp_path / "store.ts").write_text(TS, encoding="utf-8")
    _record(tmp_path, "store.ts:3-7")
    (tmp_path / "store.ts").write_text(INSERTED + TS, encoding="utf-8")
    view = build_ledger_view(tmp_path)
    assert [(o.locus, o.reason) for o in view.orphaned] == [("store.ts:3-7", "anchor_moved")]
    assert view.counts["moved_anchors"] == 1 and view.counts["orphaned"] == 0


@pytest.mark.phase_4
def test_ts_symbol_extraction() -> None:
    source = (
        "import x from 'y';\n"
        "// function ignored() {}\n"
        "export async function load(a: number): Promise<void> {\n"
        '  const s = "}";\n'
        "  return fetch(`/a/${a}`);\n"
        "}\n"
        "export const add = (a: number, b: number): number => a + b;\n"
        "const run = async (x) => {\n  if (x) { return 1; }\n};\n"
        "export default class Store<T> extends Base<{ a: 1 }> {\n"
        "  constructor(private x: number) { super(); }\n"
        "  static async get<K>(key: K): Promise<T | undefined> {\n    return undefined;\n  }\n"
        "}\n"
        "const fe = function named(a) { return a; };\n"
    )
    spans = {s.name: (s.start, s.end) for s in extract_ts_symbols(source)}
    assert spans == {
        "load": (3, 6),
        "add": (7, 7),
        "run": (8, 10),
        "Store": (11, 16),
        "Store.constructor": (12, 12),
        "Store.get": (13, 15),
        "fe": (17, 17),
    }


@pytest.mark.phase_4
@pytest.mark.parametrize(
    "source",
    [
        "function over(a: string): void;\n",
        "function typed(): { a: number } { return { a: 1 }; }\n",
        "function broken() {\n  const s = 'unterminated;\n}\n",
        "const f = (x) => x + 1\nconst g = 2\n",
        "function a() { return 1 }\n/* never closed\n",
    ],
)
def test_ts_symbol_unsure_returns_none(source: str) -> None:
    assert extract_ts_symbols(source) == []
