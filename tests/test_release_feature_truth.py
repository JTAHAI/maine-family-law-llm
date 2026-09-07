from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.production import LEGACY_REACHABLE_FEATURE_IDS, app
from legal.release.feature_truth import (
    FeatureTruthError,
    feature_truth_inventory,
    load_feature_truth,
)

ROOT = Path(__file__).resolve().parents[1]


def test_release_feature_truth_marks_current_package_claims_unavailable_until_qualified() -> None:
    truth = load_feature_truth(ROOT / "configs/release_feature_truth.json")
    inventory = feature_truth_inventory(ROOT / "configs/release_feature_truth.json")

    assert truth["release"]["status"] == "pending_current_package_verification"
    assert inventory["store_feature_claim_eligible"] is False
    assert inventory["store_claim_feature_ids"] == []
    assert inventory["legacy_reachable_feature_ids"] == list(LEGACY_REACHABLE_FEATURE_IDS)
    assert [row["feature_id"] for row in inventory["features"]] == list(
        LEGACY_REACHABLE_FEATURE_IDS
    )
    assert all(
        row["release_claim_status"] == "pending_current_package_verification"
        for row in inventory["features"]
    )
    assert all(row["required_evidence"] for row in inventory["features"])
    assert {row["id"] for row in inventory["unavailable_features"]} >= {
        "mfl-evidence-review-research-r0013",
        "mfl-drafting-research-r0003",
    }


def test_runtime_release_scope_exposes_the_same_safe_truth_ledger() -> None:
    expected = feature_truth_inventory(ROOT / "configs/release_feature_truth.json")
    with TestClient(app) as client:
        response = client.get("/api/runtime/release-scope")
    assert response.status_code == 200
    assert response.json()["manifest_sha256"] == expected["manifest_sha256"]
    assert response.json()["store_feature_claim_eligible"] is False
    assert response.json()["release"]["status"] == "pending_current_package_verification"


def test_feature_truth_rejects_store_claims_without_current_package_evidence(
    tmp_path: Path,
) -> None:
    path = ROOT / "configs/release_feature_truth.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["current_store_claim_feature_ids"] = [payload["legacy_reachable_feature_ids"][0]]
    altered = tmp_path / "altered-release-feature-truth.json"
    altered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        FeatureTruthError,
        match="feature_truth_store_claim_without_current_package_evidence",
    ):
        load_feature_truth(altered)


def test_feature_truth_manifest_contains_no_private_machine_paths() -> None:
    content = (ROOT / "configs/release_feature_truth.json").read_text(encoding="utf-8")
    for forbidden in ("C:\\Users\\", "D:\\dev\\", "G:\\", "@example.com"):
        assert forbidden not in content


def test_feature_truth_validator_is_read_only_and_machine_readable() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate-release-feature-truth.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["report"]["store_feature_claim_eligible"] is False


@pytest.mark.parametrize("mutate", [
    lambda p: p["evidence"].update(msix="malformed"),
    lambda p: p["evidence"]["full_regression"].update(current_tree_bound="false"),
    lambda p: p.update(release_blockers=None),
    lambda p: p["release"].update(review_required="true"),
])
def test_malformed_ledgers_fail_closed_without_server_errors(tmp_path, mutate):
    payload = load_feature_truth()
    mutate(payload)
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(FeatureTruthError):
        load_feature_truth(path)


def test_duplicate_ledger_keys_are_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":"release_feature_truth_v1","schema_version":"release_feature_truth_v1"}')
    with pytest.raises(FeatureTruthError):
        load_feature_truth(path)


def test_frozen_manifest_uses_bundle_root_not_collected_src_directory(tmp_path, monkeypatch):
    from legal.release.feature_truth import default_manifest_path
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert default_manifest_path() == tmp_path / "configs/release_feature_truth.json"
