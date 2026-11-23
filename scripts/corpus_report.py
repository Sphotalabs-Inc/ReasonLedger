"""Run the module scan over a directory of cloned repos and print one comparable report.

Usage:  uv run python scripts/corpus_report.py CORPUS_DIR [--top N] [--out FILE]

Each sub-directory of CORPUS_DIR is scanned as a repo (read-only: git log and file
lists, nothing is executed). The report is what a maintainer rates by hand when
calibrating spec/14 S32: per repo, scan time, the confidence mix, what share of files
no module claims, and every proposed module with its evidence.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from reasonledger_core.modules import Manifest, PathMatcher, ScanResult, scan_repo
from reasonledger_core.modules.files import modelled_files

DEFAULT_TOP = 25
SHEET_ROWS_PER_REPO = 30
SAMPLE_FILES = 6
SHEET_INTRO = """\
# Module scan — rating sheet

You are checking whether a scan's proposed modules are ones a maintainer would accept.
For each row, look at the module name, how many files it has, where they sit, and the
sample files, then replace the `?` in the **rating** column with one letter:

- **y** — I would accept this module as it is (name and files) in `modules.yml`.
- **f** — Right idea, but it needs one edit: rename it, merge it with another, split it,
  or move a few files.
- **n** — Not a module: noise (vendored, generated, test data, scripts) or an arbitrary slice.

The target is **at least 70% `y`** over the rows you rate. Notes are optional but useful,
especially for `f` and `n` ("merge with order", "vendored OCR models").

Under each repo, add anything important the scan **missed** — a major part of the app that
no module covers. Repos you do not know: rate from the paths alone, or leave `?`.
Rows are the largest modules first.

"""


def _samples(files: list[str]) -> tuple[str, str]:
    """Where a module's files sit (top directories) and a spread of sample paths."""
    folders = Counter(f.rsplit("/", 1)[0] if "/" in f else "." for f in files).most_common(3)
    spread = [files[i * len(files) // SAMPLE_FILES] for i in range(min(SAMPLE_FILES, len(files)))]
    where = "<br>".join(f"`{d}` ({n})" for d, n in folders)
    return where, "<br>".join(f"`{f}`" for f in spread)


def _members(repo: Path, result: ScanResult) -> dict[str, list[str]]:
    files, _ = modelled_files(repo)
    matcher = PathMatcher((m.id, m.paths) for m in result.modules)
    members: dict[str, list[str]] = {m.id: [] for m in result.modules}
    for path in files:
        owner = matcher.module_of(path)
        if owner:
            members[owner].append(path)
    return members


def _sheet_section(name: str, repo: Path, result: ScanResult) -> list[str]:
    members = _members(repo, result)
    ranked = sorted(result.modules, key=lambda m: -len(members[m.id]))[:SHEET_ROWS_PER_REPO]
    lines = [f"## {name}", ""]
    lines += [f"_{note}_" for note in result.limitations] + ([""] if result.limitations else [])
    lines += [
        "| # | module | files | confidence · evidence | biggest folders | sample files "
        "| rating | note |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for number, module in enumerate(ranked, 1):
        where, sample = _samples(members[module.id])
        confidence = module.confidence.value if module.confidence else "-"
        evidence = ", ".join(module.evidence)
        lines.append(
            f"| {number} | **{module.id}** ({module.kind.value}) | {len(members[module.id])} "
            f"| {confidence} · {evidence} | {where} | {sample} | ? | |"
        )
    if len(result.modules) > len(ranked):
        lines.append(
            f"| | _{len(result.modules) - len(ranked)} smaller modules not shown_ | | | | | | |"
        )
    return [*lines, "", "**Missed (major parts of the app no module covers):**", "", "", "---", ""]


def _section(name: str, result: ScanResult, top: int) -> list[str]:
    mix = Counter(m.confidence.value for m in result.modules if m.confidence)
    source = result.files_total - result.support_files
    share = 100 * (source - result.unplaced_files) / source if source else 0.0
    lines = [
        f"## {name}",
        "",
        f"- files: {result.files_total} · commits scanned: {result.commits_scanned} · "
        f"scan: {result.seconds}s",
        f"- modules: {len(result.modules)} "
        f"(high {mix['high']}, medium {mix['medium']}, low {mix['low']}) · "
        f"placed: {share:.0f}% of source files ({result.support_files} support files "
        f"in tests/docs/examples are outside any module)",
    ]
    lines += [f"- limitation: {text}" for text in result.limitations]
    lines += [
        "",
        "| module | kind | conf | files | evidence | paths |",
        "|---|---|---|---|---|---|",
    ]
    ranked = sorted(result.modules, key=lambda m: -result.files_per_module.get(m.id, 0))
    for module in ranked[:top]:
        paths = ", ".join(f"`{p}`" for p in module.paths[:2]) + (
            " …" if len(module.paths) > 2 else ""
        )
        lines.append(
            f"| {module.id} | {module.kind.value} "
            f"| {module.confidence.value if module.confidence else '-'} "
            f"| {result.files_per_module.get(module.id, 0)} "
            f"| {', '.join(module.evidence)} | {paths} |"
        )
    if len(ranked) > top:
        lines.append(f"| … {len(ranked) - top} more | | | | | |")
    return [*lines, ""]


def _write_xlsx(path: Path, scans: list[tuple[str, Path, ScanResult]]) -> None:
    """A spreadsheet with a y/f/n dropdown, for people who do not edit markdown tables."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
        from openpyxl.worksheet.datavalidation import DataValidation
    except ImportError:
        raise SystemExit("--xlsx needs openpyxl: run with `uv run --with openpyxl ...`") from None
    book = Workbook()
    guide = book.active
    guide.title = "How to rate"
    intro = (
        SHEET_INTRO.replace("replace the `?` in the **rating** column with one letter", "")
        .replace(
            "then ",
            "pick y, f or n in the rating column (use the dropdown) "
            "for each row in the Rating sheet",
        )
        .replace("`", "")
        .replace("**", "")
    )
    for row, line in enumerate(intro.splitlines(), 1):
        guide.cell(row=row, column=1, value=line)
    guide.column_dimensions["A"].width = 110
    rating = book.create_sheet("Rating")
    header = [
        "repo",
        "#",
        "module",
        "kind",
        "files",
        "confidence",
        "evidence",
        "biggest folders",
        "sample files",
        "rating (y / f / n)",
        "note",
    ]
    rating.append(header)
    for cell in rating[1]:
        cell.font = Font(bold=True)
    dropdown = DataValidation(type="list", formula1='"y,f,n"', allow_blank=True)
    rating.add_data_validation(dropdown)
    missed = book.create_sheet("Missed")
    missed.append(["repo", "major parts of the app that no module covers"])
    for name, repo, result in scans:
        members = _members(repo, result)
        ranked = sorted(result.modules, key=lambda m: -len(members[m.id]))[:SHEET_ROWS_PER_REPO]
        for number, module in enumerate(ranked, 1):
            where, sample = _samples(members[module.id])
            rating.append(
                [
                    name,
                    number,
                    module.id,
                    module.kind.value,
                    len(members[module.id]),
                    module.confidence.value if module.confidence else "-",
                    ", ".join(module.evidence),
                    where.replace("<br>", "\n").replace("`", ""),
                    sample.replace("<br>", "\n").replace("`", ""),
                    None,
                    None,
                ]
            )
            dropdown.add(rating.cell(row=rating.max_row, column=10))
        missed.append([name, None])
    widths = {
        "A": 16,
        "B": 4,
        "C": 24,
        "D": 11,
        "E": 7,
        "F": 11,
        "G": 20,
        "H": 46,
        "I": 70,
        "J": 14,
        "K": 40,
    }
    for column, width in widths.items():
        rating.column_dimensions[column].width = width
    for row in rating.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    rating.freeze_panes = "D2"
    missed.column_dimensions["A"].width = 18
    missed.column_dimensions["B"].width = 100
    book.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("corpus", type=Path, help="Directory containing the cloned repos")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP, help="Modules shown per repo")
    parser.add_argument("--out", type=Path, default=None, help="Also write the report here")
    parser.add_argument(
        "--xlsx", type=Path, default=None, help="Write the rating sheet as a spreadsheet (openpyxl)"
    )
    parser.add_argument(
        "--sheet", action="store_true", help="Write a rating sheet (with sample files) instead"
    )
    args = parser.parse_args(argv)
    if not args.corpus.is_dir():
        print(f"error: not a directory: {args.corpus}", file=sys.stderr)
        return 2
    if args.xlsx:
        repos = sorted(p for p in args.corpus.iterdir() if p.is_dir())
        scans = [(r.name, r, scan_repo(r, manifest=Manifest())) for r in repos]
        _write_xlsx(args.xlsx, scans)
        print(f"wrote {args.xlsx}")
        return 0
    lines = [SHEET_INTRO] if args.sheet else ["# Module scan — corpus report", ""]
    for repo in sorted(p for p in args.corpus.iterdir() if p.is_dir()):
        # An empty manifest: the report shows what the scan proposes unaided.
        result = scan_repo(repo, manifest=Manifest())
        lines += (
            _sheet_section(repo.name, repo, result)
            if args.sheet
            else _section(repo.name, result, args.top)
        )
    text = "\n".join(lines)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
