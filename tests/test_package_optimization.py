from __future__ import annotations

import json
from pathlib import Path

from maine_family_law_llm.package_optimization import (
    build_package_optimization_report,
    collect_duplicate_report,
    collect_package_inventory,
    write_json,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_package_inventory_and_duplicate_report_classify_and_group(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    (runtime_root / "app").mkdir(parents=True)
    (runtime_root / "ui").mkdir(parents=True)
    (runtime_root / "licenses").mkdir(parents=True)
    (runtime_root / "_internal" / "spacy").mkdir(parents=True)
    (runtime_root / "_internal" / "fonts").mkdir(parents=True)
    (runtime_root / "app" / "launcher.py").write_text("print('hello')", encoding="utf-8")
    (runtime_root / "ui" / "workbench.html").write_text("<html></html>", encoding="utf-8")
    (runtime_root / "licenses" / "LICENSE.txt").write_text("license text", encoding="utf-8")
    (runtime_root / "_internal" / "spacy" / "model.bin").write_bytes(b"dup")
    (runtime_root / "_internal" / "fonts" / "font.ttf").write_bytes(b"dup")

    msix_path = tmp_path / "package.msix"
    msix_path.write_bytes(b"msix")
    inventory = collect_package_inventory(runtime_root, msix_path)
    duplicate_report = collect_duplicate_report(inventory)

    components = {row["package_component"] for row in inventory["entries"]}
    assert {"application code", "UI assets", "licenses", "spaCy/Presidio", "fonts"} <= components
    assert inventory["duplicate_bytes"] > 0
    assert duplicate_report["duplicate_hash_group_count"] >= 1
    assert duplicate_report["status"] == "pass"


def test_package_optimization_report_can_be_written(tmp_path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "app").mkdir()
    (runtime_root / "app" / "launcher.py").write_text("print('hello')", encoding="utf-8")
    msix_path = tmp_path / "MaineFamilyLawLLM_6.0.4.0_x64.msix"
    msix_path.write_bytes(b"msix")
    evidence_root = tmp_path / "evidence"

    def fake_measure(_: Path) -> dict[str, object]:
        return {
            "baseline_eager_import_ms": 12.5,
            "optimized_launcher_import_ms": 6.1,
            "baseline_returncode": 0,
            "optimized_returncode": 0,
            "baseline_error": "",
            "optimized_error": "",
            "status": "pass",
        }

    def fake_launch(*args, **kwargs) -> dict[str, object]:
        return {
            "status": "pass",
            "local_api_ready_ms": 123.4,
            "workbench_interactive_ms": 56.7,
            "first_source_card_open_ms": 12.3,
            "first_document_parse_ms": 45.6,
            "first_privacy_scan_ms": 78.9,
            "first_vector_query_ms": 11.1,
            "source_card_status": "pass",
            "first_document_parse_status": "pass",
            "first_privacy_scan_status": "pass",
            "first_vector_query_status": "pass",
        }

    monkeypatch.setattr("maine_family_law_llm.package_optimization.measure_launcher_import_budget", fake_measure)
    monkeypatch.setattr("maine_family_law_llm.package_optimization._package_launch_profile", fake_launch)

    report = build_package_optimization_report(REPO_ROOT, runtime_root, msix_path, evidence_root)
    assert report["status"] == "pass"
    assert report["conclusion"] == "retained_with_no_material_size_reduction"
    assert report["safe_removals"] == []
    assert len(report["package_hash"]) == 64


def test_write_json_round_trips(tmp_path) -> None:
    payload = {"alpha": 1, "beta": [1, 2, 3]}
    output = tmp_path / "report.json"
    write_json(output, payload)
    assert json.loads(output.read_text(encoding="utf-8")) == payload
