"""Conservative symbol spans for TypeScript and JavaScript, with no parser dependency.

Handles top-level ``function`` and ``class`` declarations, ``const NAME = (...) => ...`` and
``= function`` expressions, and class methods. Source is first *masked* (comments, strings,
template text and regex literals blanked, line structure kept) so braces can be matched safely.
Whenever the text is ambiguous the answer is nothing: a wrong symbol is worse than none, and a
locus without a symbol simply stays a fingerprinted line range.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")
_IDENT = r"[A-Za-z_$][\w$]*"
_REGEX_PRECEDERS = frozenset("(,=:[!&|?{};+-*%<>~^")
_REGEX_KEYWORDS = frozenset({"return", "typeof", "case", "in", "of", "delete", "void", "throw"})
_NOT_METHODS = frozenset({"if", "for", "while", "switch", "catch", "function", "return", "with"})
_FUNCTION = re.compile(
    rf"(?m)^[ \t]*(?:export[ \t]+(?:default[ \t]+)?)?(?:declare[ \t]+)?(?:async[ \t]+)?"
    rf"function[ \t]*\*?[ \t]*(?P<name>{_IDENT})"
)
_CLASS = re.compile(
    rf"(?m)^[ \t]*(?:export[ \t]+(?:default[ \t]+)?)?(?:declare[ \t]+)?(?:abstract[ \t]+)?"
    rf"class[ \t]+(?P<name>{_IDENT})"
)
_VARIABLE = re.compile(
    rf"(?m)^[ \t]*(?:export[ \t]+)?(?:const|let|var)[ \t]+(?P<name>{_IDENT})[ \t]*"
    rf"(?::[^=\n]*)?=[ \t]*(?P<rhs>async\b[ \t]*|function\b|\()"
)
_METHOD = re.compile(
    rf"(?m)^[ \t]*(?:(?:public|private|protected|static|async|readonly|override|get|set)[ \t]+)*"
    rf"\*?[ \t]*(?P<name>#?{_IDENT})[ \t]*(?:<[^>(\n]*>)?[ \t]*\("
)
_DECLARED_CONST = re.compile(
    rf"(?m)^[ \t]*(?:export[ \t]+)?(?:const|let|var)[ \t]+(?P<name>{_IDENT})"
)
_FUNCTION_EXPR_NAME = re.compile(rf"[ \t]*\*?[ \t]*(?:{_IDENT})?")
_OPENERS, _CLOSERS = {"(": ")", "[": "]", "{": "}"}, ")]}"


@dataclass(frozen=True)
class TsSpan:
    name: str
    start: int
    end: int


def _blank(text: str) -> str:
    return "".join(c if c == "\n" else " " for c in text)


def _mask(source: str) -> str | None:
    """``source`` with comments, strings, templates and regexes blanked; None when unsure."""
    out: list[str] = []
    i, n = 0, len(source)
    templates: list[int] = []  # open ${ } depth per nested template expression
    last = ""  # last significant (non-space, non-comment) code character
    word = ""
    while i < n:
        c = source[i]
        nxt = source[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            end = source.find("\n", i)
            end = n if end < 0 else end
            out.append(_blank(source[i:end]))
            i = end
        elif c == "/" and nxt == "*":
            end = source.find("*/", i + 2)
            if end < 0:
                return None
            out.append(_blank(source[i : end + 2]))
            i = end + 2
        elif c in "'\"":
            j = i + 1
            while j < n and source[j] != c:
                if source[j] == "\n" or (source[j] == "\\" and j + 1 < n and source[j + 1] == "\n"):
                    return None
                j += 2 if source[j] == "\\" else 1
            if j >= n:
                return None
            out.append(_blank(source[i : j + 1]))
            i, last, word = j + 1, c, ""
        elif c == "`":
            j = i + 1
            while j < n and source[j] not in "`$":
                j += 2 if source[j] == "\\" else 1
            if j >= n:
                return None
            if source[j] == "$" and source[j + 1 : j + 2] == "{":
                templates.append(0)
                out.append(_blank(source[i : j + 2]))
                i, last, word = j + 2, "{", ""
            elif source[j] == "`":
                out.append(_blank(source[i : j + 1]))
                i, last, word = j + 1, "`", ""
            else:
                return None
        elif c == "}" and templates and templates[-1] == 0:
            templates.pop()  # back into template text
            j = i + 1
            while j < n and source[j] not in "`$":
                j += 2 if source[j] == "\\" else 1
            if j >= n:
                return None
            if source[j] == "$" and source[j + 1 : j + 2] == "{":
                templates.append(0)
                out.append(_blank(source[i : j + 2]))
                i, last, word = j + 2, "{", ""
            else:
                out.append(_blank(source[i : j + 1]))
                i, last, word = j + 1, "`", ""
        elif c == "/":
            if last == "" or last in _REGEX_PRECEDERS or word in _REGEX_KEYWORDS:
                j, in_class = i + 1, False
                while j < n and source[j] != "\n" and (in_class or source[j] != "/"):
                    in_class = (source[j] == "[") or (in_class and source[j] != "]")
                    j += 2 if source[j] == "\\" else 1
                if j >= n or source[j] != "/":
                    return None
                while j + 1 < n and source[j + 1].isalpha():
                    j += 1
                out.append(_blank(source[i : j + 1]))
                i, last, word = j + 1, "/", ""
            elif last in ")]\"'`" or last.isalnum() or last in "_$":
                out.append(c)
                i, last, word = i + 1, "/", ""
            else:
                return None
        else:
            if templates:
                templates[-1] += (c == "{") - (c == "}")
            out.append(c)
            if not c.isspace():
                word = word + c if (c.isalnum() or c in "_$") else ""
                last = c
            elif c != "\n":
                word = word
            i += 1
    return "".join(out)


def _match(text: str, open_at: int) -> int | None:
    """Index of the bracket closing the one at ``open_at``; None when unbalanced."""
    stack: list[str] = []
    for i in range(open_at, len(text)):
        c = text[i]
        if c in _OPENERS:
            stack.append(_OPENERS[c])
        elif c in _CLOSERS:
            if not stack or stack.pop() != c:
                return None
            if not stack:
                return i
    return None


def _body_open(text: str, i: int) -> int | None:
    """Index of the ``{`` opening a body at or after ``i``, past an optional type annotation.

    None when a ``;`` comes first (an overload or abstract signature) or the ``{`` could be an
    object type rather than a body.
    """
    angle, previous, j = 0, "", i
    while j < len(text):
        c = text[j]
        if c == "<":
            angle += 1
        elif c == ">" and text[j - 1] != "=":
            angle = max(angle - 1, 0)
        elif c in "([":
            end = _match(text, j)
            if end is None:
                return None
            j, c = end, text[end]
        elif c == ";" and angle == 0:
            return None
        elif c == "{" and angle == 0:
            return None if previous and previous in ":|&,<" else j
        if not c.isspace():
            previous = c
        j += 1
    return None


def _line(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _function_end(text: str, after_name: int) -> int | None:
    """Index of the closing ``}`` of a function whose name (if any) ends at ``after_name``."""
    j = after_name
    while j < len(text) and text[j] in " \t":
        j += 1
    if text.startswith("<", j):
        depth = 0
        while j < len(text):
            depth += (text[j] == "<") - (text[j] == ">" and text[j - 1] != "=")
            j += 1
            if depth == 0:
                break
        while j < len(text) and text[j] in " \t":
            j += 1
    if not text.startswith("(", j):
        return None
    close = _match(text, j)
    opener = _body_open(text, close + 1) if close is not None else None
    return _match(text, opener) if opener is not None else None


def _arrow_end(text: str, open_paren: int) -> int | None:
    """Index of the last character of an arrow function whose ``(`` is at ``open_paren``."""
    close = _match(text, open_paren)
    if close is None:
        return None
    arrow = text.find("=>", close)
    if arrow < 0 or text[close + 1 : arrow].strip().startswith("{"):
        return None
    start = arrow + 2
    while start < len(text) and text[start] in " \t":
        start += 1
    if start < len(text) and text[start] == "{":
        return _match(text, start)
    depth = 0
    for j in range(start, len(text)):
        c = text[j]
        depth += (c in _OPENERS) - (c in _CLOSERS)
        if depth < 0 or (c == "\n" and depth == 0):
            return None
        if c == ";" and depth == 0:
            return j
    return None


def _depths(text: str) -> list[int]:
    """Bracket depth in front of each character."""
    depth, levels = 0, []
    for c in text:
        levels.append(depth)
        depth += (c in _OPENERS) - (c in _CLOSERS)
    return levels


def _methods(
    text: str, levels: list[int], class_name: str, open_at: int, close_at: int
) -> Iterator[TsSpan]:
    for found in _METHOD.finditer(text, open_at + 1, close_at):
        name = found["name"]
        if name in _NOT_METHODS or levels[found.start("name")] != levels[open_at] + 1:
            continue
        close = _match(text, found.end() - 1)
        opener = _body_open(text, close + 1) if close is not None else None
        end = _match(text, opener) if opener is not None else None
        if end is not None:
            yield TsSpan(f"{class_name}.{name}", _line(text, found.start()), _line(text, end))


def _after_function_keyword(text: str, index: int) -> int:
    """Past an optional ``*`` and name after ``function`` in a function expression."""
    return _FUNCTION_EXPR_NAME.match(text, index).end()  # type: ignore[union-attr]


def extract_ts_symbols(source: str) -> list[TsSpan]:
    """Top-level functions, classes, function-valued consts and class methods; [] when unsure."""
    text = _mask(source)
    if text is None:
        return []
    levels = _depths(text)
    spans: list[TsSpan] = []
    for found in _FUNCTION.finditer(text):
        if levels[found.start("name")] != 0:
            continue
        end = _function_end(text, found.end())
        if end is not None:
            spans.append(TsSpan(found["name"], _line(text, found.start()), _line(text, end)))
    for found in _CLASS.finditer(text):
        if levels[found.start("name")] != 0:
            continue
        opener = _body_open(text, found.end())
        end = _match(text, opener) if opener is not None else None
        if opener is None or end is None:
            continue
        name = found["name"]
        spans.append(TsSpan(name, _line(text, found.start()), _line(text, end)))
        spans.extend(_methods(text, levels, name, opener, end))
    for found in _VARIABLE.finditer(text):
        if levels[found.start("name")] != 0:
            continue
        rhs = found["rhs"].strip()
        if rhs == "(":
            end = _arrow_end(text, found.end() - 1)
        elif rhs == "function":
            end = _function_end(text, _after_function_keyword(text, found.end()))
        else:  # async (...) => ... or async function ...
            tail = found.end()
            if text.startswith("function", tail):
                end = _function_end(text, _after_function_keyword(text, tail + len("function")))
            elif text.startswith("(", tail):
                end = _arrow_end(text, tail)
            else:
                end = None
        if end is not None:
            spans.append(TsSpan(found["name"], _line(text, found.start()), _line(text, end)))
    return spans


def declared_ts_names(source: str) -> set[str] | None:
    """Every function, class or variable name declared at any nesting depth; None when unsure.

    For asking whether a name still exists, not where it is: comments and strings are masked
    first, so mentioning a name is not declaring it, but a function inside a wrapper such as
    an IIFE counts, which `extract_ts_symbols` deliberately skips.
    """
    text = _mask(source)
    if text is None:
        return None
    return {
        found["name"]
        for pattern in (_FUNCTION, _CLASS, _DECLARED_CONST)
        for found in pattern.finditer(text)
    }
