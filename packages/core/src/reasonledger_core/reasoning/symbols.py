"""Symbol extraction for durable code loci: Python via stdlib ast, TS/JS conservatively."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from reasonledger_core.reasoning.ts_symbols import (
    TS_EXTENSIONS,
    declared_ts_names,
    extract_ts_symbols,
)


@dataclass(frozen=True)
class SymbolSpan:
    """A qualified Python symbol and its inclusive, one-based line span."""

    name: str
    start: int
    end: int


class _SymbolVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: list[SymbolSpan] = []
        self._prefix: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_symbol(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_symbol(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self._visit_symbol(node)

    def _visit_symbol(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> None:
        name = ".".join([*self._prefix, node.name])
        self.symbols.append(
            SymbolSpan(name=name, start=node.lineno, end=node.end_lineno or node.lineno)
        )
        self._prefix.append(node.name)
        self.generic_visit(node)
        self._prefix.pop()


def extract_symbols(source: str, path: str = "") -> list[SymbolSpan]:
    """Return all function and class spans, with nested symbols after parents.

    ``path`` picks the language by extension: TS/JS use a conservative extractor, anything
    else is read as Python.

    Never raises. Unparseable source yields no symbols, which degrades `why` to a
    file-level match — coarse, but never a crash and never a wrong answer.
    ``ast.parse`` signals bad input two ways: ``SyntaxError`` for malformed code and
    ``ValueError`` for source containing null bytes (which reads back cleanly as UTF-8,
    so the file read upstream cannot screen it out).
    """
    if path.lower().endswith(TS_EXTENSIONS):
        return [SymbolSpan(t.name, t.start, t.end) for t in extract_ts_symbols(source)]
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    visitor = _SymbolVisitor()
    visitor.visit(tree)
    return visitor.symbols


def _declared_python_names(source: str) -> set[str] | None:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def declared_names(source: str, path: str = "") -> set[str] | None:
    """Names declared anywhere in ``source`` (nested functions, module constants); None if unsure.

    Looser than `extract_symbols`, which gives spans for `why` and so stays conservative: this
    only answers whether a name still exists, where being unsure must not read as "gone".
    """
    if path.lower().endswith(TS_EXTENSIONS):
        return declared_ts_names(source)
    return _declared_python_names(source)


def symbol_at_line(source: str, line: int, path: str = "") -> str | None:
    """Return the innermost symbol containing ``line``, or ``None``."""
    matches = [span for span in extract_symbols(source, path) if span.start <= line <= span.end]
    if not matches:
        return None
    return min(matches, key=lambda span: span.end - span.start).name


def symbol_exists(source: str, symbol: str, path: str = "") -> bool:
    """Return whether a qualified symbol is present in ``source``."""
    return any(span.name == symbol for span in extract_symbols(source, path))


def supports(path: str) -> bool:
    """Return whether a symbol extractor exists for this file type."""
    return path.lower().endswith((".py", *TS_EXTENSIONS))
