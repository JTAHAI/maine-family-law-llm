from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_script(script: str, *args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )


def _authority_record(official_store: Path, source_id: str, source_class: str) -> dict:
    body = f"official authority snapshot for {source_id}".encode("utf-8")
    snapshot = official_store / f"{source_id}.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(body)
    return {
        "source_id": source_id,
        "source_class": source_class,
        "jurisdiction": "maine",
        "retrieved_at": datetime(2026, 5, 31, tzinfo=timezone.utc).isoformat(),
        "hash": hashlib.sha256(body).hexdigest(),
        "parser_status": "parsed",
        "freshness_status": "known_extracted_timestamp",
        "data_class": "official_public_authority",
        "source_url_or_path": f"https://example.maine.gov/{source_id}",
        "snapshot_path": str(snapshot),
        "parser_audit": {"status": "parsed", "parser_version": "test"},
    }


def test_audit_authority_build_cli_fails_closed_when_manifest_missing(tmp_path: Path):
    result = _run_script("audit-authority-build.py", "--data-root", tmp_path)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["production_ready"] is False
    assert "manifest_missing" in payload["blockers"]


def test_audit_authority_build_cli_allows_valid_external_build(tmp_path: Path):
    official_store = tmp_path / "official_authority_store"
    manifest = []
    for index in range(9):
        manifest.append(
            _authority_record(official_store, f"statute-title-index-{index}", "statute_title_index")
        )
        manifest.append(
            {
                **_authority_record(official_store, f"statute-title-pdf-{index}", "statute_title_pdf"),
                "parser_status": "snapshot_only",
                "parser_audit": {"status": "snapshot_only", "parser_version": "test"},
                "freshness_status": "retrieved_pdf_metadata_known",
            }
        )
    for index in range(4):
        manifest.append(_authority_record(official_store, f"court-rules-index-{index}", "court_rules_index"))
    manifest.append(_authority_record(official_store, "forms-index", "court_forms_index"))
    manifest.append(_authority_record(official_store, "court-policy-index", "court_policy_index"))
    for index in range(7):
        manifest.append(_authority_record(official_store, f"law-court-index-{index}", "law_court_opinion_index"))
    (official_store / "source_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = _run_script("audit-authority-build.py", "--data-root", tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["production_ready"] is True
    assert payload["blockers"] == []


def test_audit_enterprise_readiness_cli_fails_closed_when_not_production_ready(tmp_path: Path):
    result = _run_script("audit-enterprise-readiness.py", "--data-root", tmp_path)

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["production_ready"] is False
    assert any(blocker.startswith("authority:") for blocker in payload["blockers"])
