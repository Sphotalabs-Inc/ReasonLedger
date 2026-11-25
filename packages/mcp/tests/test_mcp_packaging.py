"""The MCP package must install from wheels alone on every platform it supports."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
INTEL_MAC = {"sys_platform": "darwin", "platform_machine": "x86_64"}
OTHER_PLATFORMS = (
    {"sys_platform": "darwin", "platform_machine": "arm64"},
    {"sys_platform": "linux", "platform_machine": "x86_64"},
    {"sys_platform": "win32", "platform_machine": "AMD64"},
)
# The newest cryptography release that still ships an Intel macOS wheel.
LAST_INTEL_MAC_WHEEL = "48.0.1"
FIRST_WITHOUT_INTEL_MAC_WHEEL = "49.0.0"


def _cryptography_rule() -> Requirement:
    deps = tomllib.loads(PYPROJECT.read_text("utf-8"))["project"]["dependencies"]
    rules = [Requirement(dep) for dep in deps if Requirement(dep).name == "cryptography"]
    assert len(rules) == 1, rules
    return rules[0]


@pytest.mark.phase_3
def test_intel_macs_are_held_to_a_cryptography_with_a_wheel() -> None:
    """Without it, an Intel Mac builds cryptography from source and needs Rust 1.83+."""
    rule = _cryptography_rule()
    assert rule.marker is not None and rule.marker.evaluate(INTEL_MAC)
    assert rule.specifier.contains(LAST_INTEL_MAC_WHEEL)
    assert not rule.specifier.contains(FIRST_WITHOUT_INTEL_MAC_WHEEL)


@pytest.mark.phase_3
@pytest.mark.parametrize("platform", OTHER_PLATFORMS, ids=lambda p: p["platform_machine"])
def test_other_platforms_keep_the_current_cryptography(platform: dict[str, str]) -> None:
    marker = _cryptography_rule().marker
    assert marker is not None and not marker.evaluate(platform)
