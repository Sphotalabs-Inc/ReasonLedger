"""S55 — the published core carries the developer tool and nothing priced as Enterprise.

Publishing under Apache-2.0 cannot be taken back, so the boundary is pinned by building the real
core wheel rather than by reading the source tree.
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMERCIAL_MODULES = ("attestation", "evidence", "connectors")
COMMERCIAL_MODELS = ("models/attestation.py", "models/evidence.py")
# Org-level rollups and the report built on them; nothing on the developer path called them.
ORG_ROLLUP_MODULES = ("coverage", "audit")
ORG_ROLLUP_MODELS = ("models/coverage.py",)


@pytest.fixture(scope="module")
def core_wheel(tmp_path_factory: pytest.TempPathFactory) -> zipfile.ZipFile:
    out_dir = tmp_path_factory.mktemp("core-dist")
    subprocess.run(
        ["uv", "build", "--package", "reasonledger-core", "--wheel", "--offline"]
        + ["--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one core wheel, got {wheels}"
    return zipfile.ZipFile(wheels[0])


@pytest.mark.phase_3
def test_core_wheel_has_no_commercial_modules(core_wheel: zipfile.ZipFile) -> None:
    names = core_wheel.namelist()
    leaked = [
        name
        for name in names
        if any(f"reasonledger_core/{module}/" in name for module in COMMERCIAL_MODULES)
        or any(name.endswith(model) for model in COMMERCIAL_MODELS)
    ]
    assert leaked == []


@pytest.mark.phase_3
def test_core_wheel_has_no_org_rollup_modules(core_wheel: zipfile.ZipFile) -> None:
    leaked = [
        name
        for name in core_wheel.namelist()
        if any(f"reasonledger_core/{module}/" in name for module in ORG_ROLLUP_MODULES)
        or any(name.endswith(model) for model in ORG_ROLLUP_MODELS)
    ]
    assert leaked == []


@pytest.mark.phase_3
def test_core_does_not_depend_on_cryptography(core_wheel: zipfile.ZipFile) -> None:
    metadata = next(n for n in core_wheel.namelist() if n.endswith(".dist-info/METADATA"))
    requires = [
        line
        for line in core_wheel.read(metadata).decode("utf-8").splitlines()
        if line.startswith("Requires-Dist:")
    ]
    assert not [line for line in requires if "cryptography" in line.lower()]
