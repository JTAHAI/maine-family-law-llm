from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_store_runtime_includes_the_security_privacy_route_dependency() -> None:
    spec_path = ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec"
    spec = spec_path.read_text(encoding="utf-8")
    assert '"legal.security.privacy_fortress"' in spec


def test_store_build_runs_frozen_smoke_before_hand_off() -> None:
    script = (ROOT / "scripts" / "build-store-runtime.ps1").read_text(encoding="utf-8")

    assert "[switch]$SkipRuntimeSmoke" in script
    assert "test-store-runtime.ps1" in script
    assert "Frozen Store runtime smoke failed" in script


def test_security_privacy_runtime_module_compiles_on_the_store_python_version() -> None:
    path = ROOT / "legal" / "security" / "privacy_fortress.py"
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_engine_inventory_does_not_depend_on_application_import_paths() -> None:
    script = (ROOT / "scripts" / "generate_bundled_engine_inventory.py").read_text(encoding="utf-8")
    assert "from urllib.parse import urlparse" in script
    assert "from legal.retrieval.optional_backends" not in script
