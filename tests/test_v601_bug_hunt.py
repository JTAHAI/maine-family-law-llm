from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.store_entrypoint import _is_outside_root
from legal.release.release_candidate_operations import (
    GAReleaseCandidateError,
    GAReleaseCandidateOperationsStore,
)
from legal.release.shipment_readiness_operations import (
    GAShipmentReadinessError,
    GAShipmentReadinessStore,
)
from maine_family_law_llm.api import (
    GAReleaseCandidateCreateRequest,
    RealMatterPilotEnrollmentRequest,
)

ROOT = Path(__file__).resolve().parents[1]
HASH_A = "a" * 64


def _policy(path: Path, version: str = "6.0.1") -> Path:
    path.write_text(json.dumps({"product_version": version}), encoding="utf-8")
    return path


def test_v601_store_boundary_uses_path_components_not_string_prefix(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    inside = bundle / "data" / "matter"
    sibling_with_same_prefix = tmp_path / "bundle-old" / "matter"
    assert _is_outside_root(inside, bundle) is False
    assert _is_outside_root(sibling_with_same_prefix, bundle) is True


def test_v601_release_candidate_rejects_windows_paths_on_non_windows_hosts(tmp_path: Path) -> None:
    store = GAReleaseCandidateOperationsStore(
        ROOT,
        tmp_path / "release",
        policy_path=_policy(tmp_path / "candidate-policy.json"),
    )
    for unsafe in (r"C:\private\source.zip", r"folder\source.zip", "folder/source.zip"):
        with pytest.raises(GAReleaseCandidateError, match="source_zip_name_invalid"):
            store.create_candidate(
                candidate_id="candidate-one",
                version="6.0.1",
                source_repo_zip_sha256=HASH_A,
                source_repo_zip_name=unsafe,
                approved=True,
            )


def test_v601_shipment_rejects_windows_paths_on_non_windows_hosts(tmp_path: Path) -> None:
    store = GAShipmentReadinessStore(
        ROOT,
        tmp_path / "release",
        policy_path=_policy(tmp_path / "shipment-policy.json"),
    )
    for unsafe in (r"C:\private\source.zip", r"folder\source.zip", "folder/source.zip"):
        with pytest.raises(GAShipmentReadinessError, match="source_zip_name_invalid"):
            store.create_shipment(
                shipment_id="shipment-one",
                version="6.0.1",
                source_repo_zip_name=unsafe,
                source_repo_zip_sha256=HASH_A,
                release_candidate_id="candidate-one",
                release_candidate_report_sha256="b" * 64,
                release_candidate_inventory_hash="c" * 64,
                release_channel="source_release",
                approved=True,
            )


def test_v601_release_references_reject_active_or_local_uri_schemes(tmp_path: Path) -> None:
    candidate = GAReleaseCandidateOperationsStore(
        ROOT,
        tmp_path / "candidate",
        policy_path=_policy(tmp_path / "candidate-policy.json"),
    )
    shipment = GAShipmentReadinessStore(
        ROOT,
        tmp_path / "shipment",
        policy_path=_policy(tmp_path / "shipment-policy.json"),
    )
    for unsafe in ("javascript:alert(1)", "data:text/html,unsafe", "file:///private/evidence.json"):
        with pytest.raises(GAReleaseCandidateError, match="reference_invalid"):
            candidate._safe_reference(unsafe)
        with pytest.raises(GAShipmentReadinessError, match="reference_invalid"):
            shipment._safe_reference(unsafe)
    assert candidate._safe_reference("urn:release:candidate-one") == "urn:release:candidate-one"
    assert shipment._safe_reference("https://example.invalid/evidence/receipt") == "https://example.invalid/evidence/receipt"
    with pytest.raises(GAReleaseCandidateError, match="reference_invalid"):
        candidate._safe_reference("https://user:secret@example.invalid/evidence")


def test_v601_release_signoff_requires_timezone_aware_timestamp(tmp_path: Path) -> None:
    store = GAReleaseCandidateOperationsStore(
        ROOT,
        tmp_path / "release",
        policy_path=_policy(tmp_path / "policy.json"),
    )
    for unsafe in ("2026-07-29", "2026-07-29T01:30:00"):
        with pytest.raises(GAReleaseCandidateError, match="timezone_required"):
            store._safe_signed_at(unsafe)
    assert store._safe_signed_at("2026-07-29T01:30:00-04:00") == "2026-07-29T01:30:00-04:00"
    assert store._safe_signed_at("2026-07-29T05:30:00Z") == "2026-07-29T05:30:00Z"


def test_v601_api_safety_booleans_do_not_coerce_strings() -> None:
    with pytest.raises(ValidationError):
        GAReleaseCandidateCreateRequest(
            candidate_id="candidate-one",
            version="6.0.1",
            source_repo_zip_sha256=HASH_A,
            source_repo_zip_name="source.zip",
            approved="yes",  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError):
        RealMatterPilotEnrollmentRequest(
            matter_id="matter-one",
            tenant_id="tenant-one",
            participant_id="reviewer-one",
            consent_version="v1",
            client_consent_evidence_sha256="1" * 64,
            privacy_notice_sha256="2" * 64,
            matter_store_sha256="3" * 64,
            tenant_isolation_evidence_sha256="4" * 64,
            encryption_evidence_sha256="5" * 64,
            retention_policy_version="v1",
            explicit_real_matter_consent="yes",  # type: ignore[arg-type]
            approved=True,
        )


def test_v601_api_module_still_imports_without_api_extras() -> None:
    code = r'''
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "fastapi" or fullname.startswith("fastapi.") or fullname == "pydantic" or fullname.startswith("pydantic."):
            raise ModuleNotFoundError(fullname)
        return None
sys.meta_path.insert(0, Block())
import maine_family_law_llm.api as api
assert api.FastAPI is None
assert api.StrictBool is bool
print("fallback-import-pass")
'''
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "fallback-import-pass" in result.stdout


def test_v601_evidence_jump_respects_reduced_motion_and_mirrors_match() -> None:
    first = ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js"
    second = ROOT / "maine_family_law_llm" / "ui" / "workbench.js"
    text = first.read_text(encoding="utf-8")
    assert first.read_bytes() == second.read_bytes()
    assert "prefers-reduced-motion: reduce" in text
    assert "? 'auto' : 'smooth'" in text
