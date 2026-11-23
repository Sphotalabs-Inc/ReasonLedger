"""S53 — loci in decision files always use forward slashes, on every platform."""

from __future__ import annotations

from pathlib import Path

import pytest
from reasonledger_core.decisions.fingerprint import fingerprint_loci
from reasonledger_mcp.tools import call_decisions_for


@pytest.mark.phase_4
def test_loci_use_forward_slashes(tmp_path: Path) -> None:
    nested = tmp_path / "pkg" / "sub"
    nested.mkdir(parents=True)
    (nested / "m.ts").write_text("export const a = () => 1;\n", encoding="utf-8")
    assert list(fingerprint_loci(tmp_path, ["pkg/sub/m.ts:1-1"]) or {}) == ["pkg/sub/m.ts:1-1"]
    found = call_decisions_for(tmp_path, paths=[str(nested / "m.ts")])
    assert found["paths"] == ["pkg/sub/m.ts"]
