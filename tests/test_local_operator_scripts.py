from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_script_module(rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_required_corpus_source_package_is_present_in_release_tree():
    required = [
        "legal/corpus/__init__.py",
        "legal/corpus/source_normalizer.py",
        "legal/corpus/source_registry.py",
        "legal/corpus/source_snapshotter.py",
        "legal/corpus/maine_source_manifest.schema.json",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel


def test_local_smoke_report_passes_without_external_corpus_or_pytest(tmp_path):
    module = _load_script_module("scripts/run-local-smoke.py")
    report = module.build_report(ROOT, tmp_path / "ME_FM_LLM_data", run_pytest=False).as_dict()
    assert report["status"] == "pass"
    assert report["production_legal_ga"] is False
    assert "http://127.0.0.1:8000/docs" in report["api_endpoints"]
    checks = {check["name"]: check for check in report["checks"]}
    assert checks["required_source_files"]["status"] == "pass"
    assert checks["single_running_txt_log"]["status"] == "pass"
    assert checks["external_data_root"]["status"] == "pass"
    assert checks["pytest"]["status"] == "skipped"


def test_local_smoke_cli_writes_json(tmp_path):
    module = _load_script_module("scripts/run-local-smoke.py")
    output = tmp_path / "local_smoke_report.json"
    report = module.build_report(ROOT, tmp_path / "data", run_pytest=False)
    output.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["status"] == "pass"
    assert loaded["production_legal_ga"] is False


def test_windows_operator_scripts_exist_and_reference_expected_commands():
    for rel in [
        "scripts/install.ps1",
        "scripts/run-tests.ps1",
        "scripts/run-local-smoke.ps1",
        "scripts/run-local-api.ps1",
        "scripts/run-local-demo.ps1",
    ]:
        assert (ROOT / rel).is_file(), rel
    smoke = (ROOT / "scripts/run-local-smoke.ps1").read_text(encoding="utf-8")
    api = (ROOT / "scripts/run-local-api.ps1").read_text(encoding="utf-8")
    assert "clean-local-artifacts.py" in smoke
    assert "run-local-smoke.py" in smoke
    assert "MAINE_FAMILY_LAW_DATA_ROOT" in api
    assert "/api/health" in api
    assert "/docs" in api


def test_package_scripts_refuse_to_build_without_corpus_source_package():
    sh = (ROOT / "scripts/package-release.sh").read_text(encoding="utf-8")
    ps1 = (ROOT / "scripts/package-release.ps1").read_text(encoding="utf-8")
    for needle in [
        "legal/corpus/source_registry.py",
        "legal/corpus/source_normalizer.py",
        "legal/corpus/source_snapshotter.py",
    ]:
        assert needle in sh
        assert needle in ps1
