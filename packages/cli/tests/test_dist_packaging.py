"""S15 — the CLI must be publishable and must carry its UI assets into the wheel.

The wheel build runs `uv build --offline`, so it resolves the build backend from uv's
cache rather than an index: no network, per the determinism rule in AGENTS.md. `uv sync` (which
CI runs before pytest) is what populates that cache.
"""

from __future__ import annotations

import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PYPROJECT = REPO_ROOT / "packages" / "cli" / "pyproject.toml"

DIST_NAME = "reasonledger"
PACKAGES = ("reasonledger-core", "reasonledger", "reasonledger-mcp")
CORE_REQUIREMENT = "reasonledger-core>=0.3.0a1,<0.4.0"
MCP_REQUIREMENT = "reasonledger-mcp>=0.3.0a1,<0.4.0"
EXPECTED_ASSETS = {
    "agent_card.js",
    "api.js",
    "app.js",
    "ask.js",
    "config.js",
    "browse.js",
    "browse_refs.js",
    "conflict_config.js",
    "conflicts.js",
    "consent.js",
    "index.html",
    "judge.js",
    "ledger_list.js",
    "logo.svg",
    "map.css",
    "map.js",
    "map_actions.js",
    "map_page.js",
    "needs.js",
    "organize.css",
    "organize.js",
    "organize_actions.js",
    "organize_decisions.js",
    "organize_inbox.js",
    "organize_inbox_ui.js",
    "organize_ui.js",
    "overview.js",
    "provenance.js",
    "review.css",
    "review.js",
    "stats.css",
    "stats.js",
    "render.js",
    "setup.js",
    "style.css",
}


def _cli_metadata() -> dict[str, object]:
    project: dict[str, object] = tomllib.loads(CLI_PYPROJECT.read_text("utf-8"))["project"]
    return project


@pytest.fixture(scope="module")
def cli_wheel(tmp_path_factory: pytest.TempPathFactory) -> zipfile.ZipFile:
    """Build the CLI wheel offline and hand back the opened archive."""
    out_dir = tmp_path_factory.mktemp("dist")
    subprocess.run(
        ["uv", "build", "--package", DIST_NAME, "--wheel", "--offline", "--out-dir", str(out_dir)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    return zipfile.ZipFile(wheels[0])


@pytest.fixture(scope="module")
def all_dists(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    """Every package as published: a bare `uv build` makes the sdist, then the wheel from it."""
    out_dir = tmp_path_factory.mktemp("all-dists")
    for package in PACKAGES:
        subprocess.run(
            ["uv", "build", "--package", package, "--offline", "--out-dir", str(out_dir)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
    return sorted(out_dir.glob("*.tar.gz")) + sorted(out_dir.glob("*.whl"))


def _archive_names(artifact: Path) -> list[str]:
    if artifact.suffix == ".whl":
        return zipfile.ZipFile(artifact).namelist()
    return tarfile.open(artifact).getnames()


@pytest.mark.phase_3
def test_dists_carry_license_and_notice(all_dists: list[Path]) -> None:
    """S54: all six artifacts carry the licence and the notice a redistributor must keep."""
    assert len(all_dists) == 2 * len(PACKAGES), [p.name for p in all_dists]
    for artifact in all_dists:
        names = _archive_names(artifact)
        for legal in ("LICENSE", "NOTICE"):
            assert any(n.rsplit("/", 1)[-1] == legal for n in names), f"{artifact.name}: {legal}"


@pytest.mark.phase_3
def test_cli_dist_is_named_reasonledger() -> None:
    """`uvx reasonledger` only works if the dist itself is called that."""
    assert _cli_metadata()["name"] == DIST_NAME


@pytest.mark.phase_3
def test_cli_declares_publishable_core_and_mcp_dependencies() -> None:
    """A bare `reasonledger-core` is unresolvable from an index — it needs a range."""
    assert _cli_metadata()["dependencies"] == [CORE_REQUIREMENT, MCP_REQUIREMENT]


@pytest.mark.phase_3
def test_cli_exposes_both_console_scripts() -> None:
    scripts = _cli_metadata()["scripts"]
    assert scripts == {
        "reasonledger": "reasonledger_cli.main:main",
        "rl": "reasonledger_cli.main:main",
    }


@pytest.mark.phase_3
def test_cli_carries_pypi_metadata() -> None:
    metadata = _cli_metadata()
    for field in ("description", "readme", "requires-python", "classifiers", "urls"):
        assert metadata.get(field), f"missing PyPI metadata: {field}"
    assert (REPO_ROOT / "packages" / "cli" / str(metadata["readme"])).is_file()


@pytest.mark.phase_3
def test_wheel_contains_ui_assets(cli_wheel: zipfile.ZipFile) -> None:
    """`reasonledger ui` serves these from the installed package — losing them is silent."""
    shipped = {
        Path(name).name
        for name in cli_wheel.namelist()
        if name.startswith("reasonledger_cli/ui_assets/")
    }
    assert shipped == EXPECTED_ASSETS


@pytest.mark.phase_3
def test_wheel_entry_points_are_installable(cli_wheel: zipfile.ZipFile) -> None:
    entry_points = next(n for n in cli_wheel.namelist() if n.endswith("entry_points.txt"))
    declared = cli_wheel.read(entry_points).decode("utf-8")
    assert "reasonledger = reasonledger_cli.main:main" in declared
    assert "rl = reasonledger_cli.main:main" in declared
