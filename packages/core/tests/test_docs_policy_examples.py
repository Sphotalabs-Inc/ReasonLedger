"""S47 — every policy example in the docs parses through the real policy loader."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from reasonledger_core.policy.parse import parse_policy_yaml

DOCS = Path(__file__).resolve().parents[3] / "docs"
_HEADING = re.compile(r"^#{1,6} .*policy", re.IGNORECASE)
_FENCE = re.compile(r"```yaml\n(.*?)```", re.DOTALL)


def _policy_blocks() -> list[tuple[str, str]]:
    """``(doc, yaml)`` for each ```yaml block that sits under a heading mentioning policy."""
    blocks: list[tuple[str, str]] = []
    for doc in sorted(DOCS.glob("*.md")):
        in_policy = False
        for section in re.split(r"(?m)^(?=#{1,6} )", doc.read_text("utf-8")):
            in_policy = bool(_HEADING.match(section))
            if in_policy:
                blocks.extend((doc.name, m.group(1)) for m in _FENCE.finditer(section))
    return blocks


@pytest.mark.phase_2
def test_docs_policy_examples_parse() -> None:
    blocks = _policy_blocks()
    assert blocks, "expected at least one policy example under a policy heading in docs/"
    for _doc, raw in blocks:
        parse_policy_yaml(raw)
