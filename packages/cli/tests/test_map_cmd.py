"""Phase 5 — `reasonledger map`: drift, refusals, dry run and a stubbed end-to-end proposal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from reasonledger_cli import map_cmd
from reasonledger_cli.main import main
from reasonledger_core.importer.config import ExtractorConfig
from reasonledger_core.modules import Manifest, Module, ModuleStatus, load_manifest, write_manifest
from reasonledger_core.modules.llm_mapper import LlmMapper

MARKER = "NEVER_SENT_FILE_BODY"


def _app(root: Path) -> Path:
    for folder in ("orders", "payments", "users"):
        for index in range(4):
            path = root / "app" / folder / f"f{index}.py"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {MARKER}\n", encoding="utf-8")
    return root


def _configure(root: Path, provider: str, url: str | None) -> None:
    settings = root / ".reasonledger" / "config.yml"
    settings.parent.mkdir(parents=True, exist_ok=True)
    extractor = {"provider": provider, "model": "m", **({"base_url": url} if url else {})}
    settings.write_text(yaml.safe_dump({"extractor": extractor}), encoding="utf-8")


@pytest.mark.phase_5
def test_drift_exits_nonzero_only_when_too_much_is_unplaced(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _app(tmp_path)
    mapped = Module(
        id="orders", name="Orders", paths=["app/orders/**"], status=ModuleStatus.CONFIRMED
    )
    write_manifest(root, Manifest(modules=[mapped]))
    assert main(["map", "--root", str(root), "--drift"]) == 1
    out = capsys.readouterr().out
    assert "unplaced source files: 8 of 12" in out and "new-module candidate" in out
    everything = Module(id="all", name="All", paths=["app/**"], status=ModuleStatus.CONFIRMED)
    write_manifest(root, Manifest(modules=[everything]))
    assert main(["map", "--root", str(root), "--drift"]) == 0


@pytest.mark.phase_5
def test_map_without_a_model_points_to_the_agent_route(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["map", "--root", str(_app(tmp_path))]) == 2
    assert "get_mapping_task" in capsys.readouterr().err


@pytest.mark.phase_5
def test_a_cloud_provider_needs_an_explicit_flag_and_dry_run_sends_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _app(tmp_path)
    _configure(root, "anthropic", None)
    assert main(["map", "--root", str(root)]) == 2
    captured = capsys.readouterr()
    assert "off this machine" in captured.out and "--allow-cloud" in captured.err
    assert main(["map", "--root", str(root), "--allow-cloud", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "12 file paths" in out and "never file contents" in out and MARKER not in out
    assert not (root / ".reasonledger" / "modules.yml").exists()


@pytest.mark.phase_5
def test_map_writes_validated_proposals_from_the_configured_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _app(tmp_path)
    _configure(root, "openai_compatible", "http://127.0.0.1:9/v1")
    bodies: list[str] = []

    def post(
        url: str, payload: dict[str, object], headers: object, timeout: float
    ) -> dict[str, object]:
        bodies.append(json.dumps(payload))
        answer = {
            "modules": [
                {
                    "id": "orders",
                    "name": "Orders",
                    "kind": "feature",
                    "description": "d",
                    "paths": ["app/orders/**"],
                },
                {
                    "id": "pay",
                    "name": "Pay",
                    "kind": "feature",
                    "description": "d",
                    "paths": ["app/payments/**", "app/ghost/**"],
                },
            ]
        }
        return {"choices": [{"message": {"role": "assistant", "content": json.dumps(answer)}}]}

    class Stubbed(LlmMapper):
        def __init__(self, config: ExtractorConfig, *, model: str | None = None) -> None:
            super().__init__(config, model=model, http_post=post)

    monkeypatch.setattr(map_cmd, "LlmMapper", Stubbed)
    assert main(["map", "--root", str(root), "--mode", "single"]) == 0
    out = capsys.readouterr().out
    assert "single mode: 2 modules proposed, 8 of 12 source files in a module" in out
    assert "buckets (files no capability owns): shared 4" in out
    assert "dropped 1 path" in out
    manifest = load_manifest(root)
    assert [m.id for m in manifest.modules] == ["orders", "pay", "shared"]
    assert manifest.mapped_by == "openai_compatible:m"
    assert MARKER not in bodies[0]
