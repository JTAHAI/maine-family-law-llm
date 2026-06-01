from __future__ import annotations

import json
import subprocess
import sys

from legal.connectors.http_fetcher import OfficialSourceFetcher


def test_strict_content_type_matching_accepts_common_official_variants() -> None:
    assert OfficialSourceFetcher._content_type_matches("application/pdf", "application/pdf; charset=binary", b"not checked")
    assert OfficialSourceFetcher._content_type_matches("application/pdf", "application/octet-stream", b"%PDF-1.7")
    assert OfficialSourceFetcher._content_type_matches("text/html", "text/html; charset=utf-8", b"<html></html>")
    assert OfficialSourceFetcher._content_type_matches("text/html", "text/plain", b"<!doctype html><html></html>")
    assert not OfficialSourceFetcher._content_type_matches("application/pdf", "text/html", b"<html></html>")


def test_ingest_script_dry_run_validates_catalog_without_fetching(tmp_path) -> None:
    data_root = tmp_path / "external_data"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/ingest-maine-authority.py",
            "--data-root",
            str(data_root),
            "--dry-run",
            "--max-targets",
            "2",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    assert payload["status"] == "pass"
    assert payload["mode"] == "dry_run"
    assert payload["target_count"] == 2
    assert payload["target_problems"] == {}


def test_authority_data_product_harness_plan_only_lists_required_steps(tmp_path) -> None:
    data_root = tmp_path / "external_data"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-authority-data-product.py",
            "--data-root",
            str(data_root),
            "--plan-only",
            "--max-targets",
            "1",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    assert payload["status"] == "pass"
    step_names = [step["name"] for step in payload["steps"]]
    assert step_names[:4] == [
        "ingest_official_authority",
        "audit_authority_build",
        "build_parsed_authority_store",
        "audit_parsed_authority_store",
    ]
    assert "build_retrieval_indexes" in step_names
    assert "build_gold_annotation_queue" in step_names
    assert all(str(data_root) in " ".join(step["command"]) for step in payload["steps"][:8])


def test_authority_data_product_harness_plan_can_require_direct_authority(tmp_path) -> None:
    data_root = tmp_path / "external_data"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-authority-data-product.py",
            "--data-root",
            str(data_root),
            "--plan-only",
            "--require-direct-authority",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    audit_steps = [step for step in payload["steps"] if step["name"] == "audit_parsed_authority_store"]
    assert audit_steps
    assert "--require-direct-authority" in audit_steps[0]["command"]


def test_followup_ingest_defers_direct_authority_gate_until_after_rebuild(tmp_path) -> None:
    data_root = tmp_path / "external_data"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-authority-data-product.py",
            "--data-root",
            str(data_root),
            "--plan-only",
            "--require-direct-authority",
            "--ingest-followup-targets",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    first_audit = next(step for step in payload["steps"] if step["name"] == "audit_parsed_authority_store")
    re_audit = next(step for step in payload["steps"] if step["name"] == "reaudit_parsed_authority_store")
    assert "--require-direct-authority" not in first_audit["command"]
    assert "--require-direct-authority" in re_audit["command"]
    assert [
        step["name"] for step in payload["steps"] if step["name"] in {
            "audit_parsed_authority_store",
            "build_authority_followup_targets",
            "ingest_derived_authority_targets",
            "rebuild_parsed_authority_store",
            "reaudit_parsed_authority_store",
        }
    ] == [
        "audit_parsed_authority_store",
        "build_authority_followup_targets",
        "ingest_derived_authority_targets",
        "rebuild_parsed_authority_store",
        "reaudit_parsed_authority_store",
    ]


def test_authority_data_product_harness_can_require_measured_retrieval_smoke(tmp_path) -> None:
    data_root = tmp_path / "external_data"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-authority-data-product.py",
            "--data-root",
            str(data_root),
            "--plan-only",
            "--require-retrieval-smoke",
            "--retrieval-min-case-count",
            "25",
            "--retrieval-min-recall-at-20",
            "0.95",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    smoke_steps = [step for step in payload["steps"] if step["name"] == "run_retrieval_smoke_eval"]
    assert smoke_steps
    assert smoke_steps[0]["required"] is True
    assert "--min-case-count" in smoke_steps[0]["command"]
    assert "25" in smoke_steps[0]["command"]
    assert "--min-recall-at-20" in smoke_steps[0]["command"]
    assert "0.95" in smoke_steps[0]["command"]


def test_ingest_append_merge_preserves_first_wave_manifest_rows() -> None:
    import importlib.util
    from pathlib import Path

    script_path = Path("scripts/ingest-maine-authority.py").resolve()
    spec = importlib.util.spec_from_file_location("ingest_maine_authority_script", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    merged = module._merge_manifest_records(
        [
            {"source_id": "first-wave-index", "hash": "old-index"},
            {"source_id": "stale-replaced", "hash": "old"},
        ],
        [
            {"source_id": "stale-replaced", "hash": "new"},
            {"source_id": "second-wave-section", "hash": "new-section"},
        ],
    )

    assert [row["source_id"] for row in merged] == [
        "first-wave-index",
        "stale-replaced",
        "second-wave-section",
    ]
    assert merged[1]["hash"] == "new"


def test_authority_data_product_followup_ingest_appends_not_replaces(tmp_path) -> None:
    data_root = tmp_path / "external_data"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-authority-data-product.py",
            "--data-root",
            str(data_root),
            "--plan-only",
            "--ingest-followup-targets",
            "--max-derived-targets",
            "3",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    followup = next(step for step in payload["steps"] if step["name"] == "ingest_derived_authority_targets")
    assert "--append-existing-manifest" in followup["command"]


def test_followup_ingest_uses_resumable_chunked_runner(tmp_path) -> None:
    data_root = tmp_path / "external_data"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run-authority-data-product.py",
            "--data-root",
            str(data_root),
            "--plan-only",
            "--ingest-followup-targets",
            "--derived-batch-size",
            "25",
            "--derived-batch-timeout",
            "120",
        ],
        text=True,
        capture_output=True,
        timeout=45,
        check=False,
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr + result.stdout
    followup = next(step for step in payload["steps"] if step["name"] == "ingest_derived_authority_targets")
    assert "ingest-derived-authority-targets.py" in " ".join(followup["command"])
    assert "--batch-size" in followup["command"]
    assert "25" in followup["command"]
    assert "--batch-timeout" in followup["command"]
    assert "120" in followup["command"]


def test_derived_ingest_quarantines_partial_batch_and_continues(tmp_path, monkeypatch) -> None:
    import importlib.util
    from pathlib import Path
    import subprocess as subprocess_module

    script_path = Path("scripts/ingest-derived-authority-targets.py").resolve()
    spec = importlib.util.spec_from_file_location("ingest_derived_authority_targets", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    data_root = tmp_path / "external_data"
    official = data_root / "official_authority_store"
    official.mkdir(parents=True)
    catalog = official / "derived_authority_targets.json"
    catalog.write_text(
        json.dumps(
            {
                "targets": [
                    {"target_id": "good-1"},
                    {"target_id": "bad-1"},
                    {"target_id": "good-2"},
                ]
            }
        ),
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        ids = [cmd[index + 1] for index, value in enumerate(cmd[:-1]) if value == "--target-id"]
        if "bad-1" in ids:
            failure_report = official / "failed_sources.json"
            failure_report.write_text(
                json.dumps(
                    {
                        "failed_count": 1,
                        "failures": [
                            {
                                "target_id": "bad-1",
                                "source_class": "court_rule_pdf",
                                "parser_name": "maine_rules_pdf",
                                "url": "https://www.courts.maine.gov/rules/text/missing.pdf",
                                "failure_code": "fetch_failed",
                                "message": "HTTP 404: Not Found",
                                "attempts": [{"status_code": 404, "message": "HTTP 404: Not Found"}],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            return subprocess_module.CompletedProcess(
                cmd,
                2,
                stdout=json.dumps(
                    {
                        "status": "partial",
                        "ingested_count": 1,
                        "failed_count": 1,
                        "failure_report_path": str(failure_report),
                    }
                ),
                stderr="",
            )
        return subprocess_module.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({"status": "pass", "ingested_count": len(ids), "failed_count": 0}),
            stderr="",
        )

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "ingest-derived-authority-targets.py",
            "--data-root",
            str(data_root),
            "--target-catalog",
            str(catalog),
            "--batch-size",
            "2",
            "--max-quarantine-rate",
            "0.5",
        ],
    )

    assert module.main() == 0
    quarantine = json.loads((official / "derived_authority_quarantine.json").read_text(encoding="utf-8"))
    assert quarantine["failure_count"] == 1
    assert quarantine["failures"][0]["target_id"] == "bad-1"
    assert len(calls) == 2
