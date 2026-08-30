from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_bundled_engine_inventory.py"


def _module():
    spec = importlib.util.spec_from_file_location("bundled_engine_inventory_feature_tier", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_essential_inventory_does_not_run_full_engine_smokes(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    essential = module.EngineDefinition("pypdfium2", "pypdfium2", "essential_smoke")
    full_only = module.EngineDefinition("presidio-analyzer", "presidio_analyzer", "full_smoke")
    monkeypatch.setattr(module, "ENGINE_DEFINITIONS", (essential, full_only))
    monkeypatch.setattr(module, "ESSENTIAL_ENGINE_PACKAGES", {"pypdfium2"})
    monkeypatch.setattr(module, "SMOKE_HANDLERS", {"essential_smoke": lambda _root: {"status": "pass"}})
    monkeypatch.setattr(module, "_measure_import", lambda _name: (True, 1, "ok"))
    monkeypatch.setattr(module, "_collect_runtime_files", lambda *_args: [])
    monkeypatch.setattr(module, "_distribution_files_size", lambda _name: 0)
    monkeypatch.setattr(module, "_distribution_version", lambda _name: "test")
    monkeypatch.setattr(module, "_distribution_license", lambda _name: "test")
    monkeypatch.setattr(module, "_native_whisper_inventory", lambda _root: {"package_name": "whisper.cpp"})

    inventory = module.build_inventory(tmp_path, feature_tier="essential")

    assert [row["package_name"] for row in inventory] == ["pypdfium2", "whisper.cpp"]
