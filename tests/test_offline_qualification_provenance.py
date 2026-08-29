"""Failure-injection tests for the runner, not installed-app certification."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run-installed-offline-qualification.py"


@pytest.mark.parametrize("fault", ["none", "source", "page", "instance", "review", "audit", "hash", "format"])
def test_pdf_raster_receipt_verification_is_fail_closed(runner, monkeypatch, fault):
    from email.message import Message
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (16, 16), "white").save(out, format="PNG")
    data = out.getvalue()
    headers = Message()
    for name, value in {"Content-Type": "image/png", "X-MFL-Hash-Verified": "true",
        "X-MFL-Source-Hash": "c" * 64, "X-MFL-Preview-Hash": hashlib.sha256(data).hexdigest(),
        "X-MFL-Page": "1", "X-MFL-Page-Count": "2", "X-MFL-Service-Instance": "fixture-instance",
        "X-MFL-Audit-Receipt": "d" * 64, "X-MFL-Review-Required": "true"}.items():
        headers[name] = value
    if fault != "none":
        name = {"source": "X-MFL-Source-Hash", "page": "X-MFL-Page", "instance": "X-MFL-Service-Instance",
                "review": "X-MFL-Review-Required", "audit": "X-MFL-Audit-Receipt",
                "hash": "X-MFL-Preview-Hash", "format": "Content-Type"}[fault]
        headers.replace_header(name, "invalid")

    class Response(io.BytesIO):
        status = 200

    response = Response(data)
    response.headers = headers
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda *args, **kwargs: response)
    monkeypatch.setattr(runner, "verify_runtime_instance", lambda *args: fault != "instance")
    metadata = {"token": "a" * 64, "source_hash": "c" * 64}
    if fault == "none":
        actual, receipt = runner.verified_pdf_page("http://127.0.0.1:1234", metadata, 1, instance="fixture-instance")
        assert actual == data and receipt["review_required"] is True
        assert receipt["dimensions"] == [16, 16]
    else:
        with pytest.raises(ValueError):
            runner.verified_pdf_page("http://127.0.0.1:1234", metadata, 1, instance="fixture-instance")


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("offline_provenance_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("defect", ["none", "blocked", "failure", "no_pdf_text", "no_sidecar",
                                   "modified", "unreviewed", "blockers"])
def test_ocr_requires_real_nonempty_review_required_derivatives(runner, defect):
    result = {"status": "pass", "original_modified": False, "review_required": True}
    text, sidecar = "FICTIONAL Scan for OCR", b"FICTIONAL Scan for OCR"
    if defect in {"blocked", "failure"}:
        result["status"] = defect
    if defect == "no_pdf_text":
        text = ""
    if defect == "no_sidecar":
        sidecar = b""
    if defect == "modified":
        result["original_modified"] = True
    if defect == "unreviewed":
        result["review_required"] = False
    if defect == "blockers":
        result["blockers"] = ["missing_engine"]
    assert runner.ocr_completed(result, text, sidecar) is (defect == "none")


@pytest.mark.parametrize("defect", ["none", "external_url", "oversize", "wrong_hash", "wrong_size", "unverified"])
def test_artifact_download_is_capability_and_hash_bound(runner, monkeypatch, defect):
    data = b"FICTIONAL derivative"
    artifact = {"download_url": "/api/document-intelligence/artifacts/" + "a" * 64,
                "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if defect == "external_url":
        artifact["download_url"] = "https://example.invalid/private"
    if defect == "oversize":
        artifact["size_bytes"] = 65 * 1024 * 1024
    if defect == "wrong_hash":
        artifact["sha256"] = "0" * 64
    if defect == "wrong_size":
        artifact["size_bytes"] += 1
    observed = []

    def open_response(request, **kwargs):
        observed.append(request)
        response = io.BytesIO(data)
        response.headers = {"X-MFL-Hash-Verified": "false" if defect == "unverified" else "true"}
        return response

    monkeypatch.setattr(runner.urllib.request, "urlopen", open_response)
    if defect == "none":
        assert runner.verified_artifact_bytes("http://127.0.0.1:1234", artifact) == data
        assert observed[0].get_header("X-mfll-client-session")
    else:
        with pytest.raises(ValueError):
            runner.verified_artifact_bytes("http://127.0.0.1:1234", artifact)
    if defect in {"external_url", "oversize"}:
        assert observed == []


def test_driver_does_not_call_developer_document_or_duplicate_services():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    forbidden = {"analyze_document", "create_redacted_copy", "create_ocr_preservation_copy",
                 "_duplicate_report", "_record_compare"}
    calls = {node.func.id for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not calls & forbidden


def test_fictional_api_profile_and_production_ui_use_same_tenant(runner):
    assert runner.QA_HEADERS["X-Tenant-Id"] == "local-desktop"
    script = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    start = script.index("    function localRequestHeaders(")
    assert "headers.set('X-Tenant-Id', 'local-desktop')" in script[start:start + 1000]


def test_runtime_uses_an_isolated_profile_and_no_visible_helper_window(runner, monkeypatch, tmp_path):
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "must-not-inherit-real-matter-key")
    monkeypatch.setenv("MFL_VAULT_KEY_ROOT", "must-not-use-real-vault")
    monkeypatch.setenv("MFL_FAST_INTERCHANGE_TRUST_POLICY", "must-not-inherit")
    monkeypatch.setenv("MAINE_FAST_INTERCHANGE_WORKER_TOKEN", "must-not-inherit")
    observed = {}

    def popen(command, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    process = runner.start_runtime(tmp_path / "MaineFamilyLawLLM.exe", 1234, localappdata=tmp_path / "qa")
    assert "MFL_FAST_INTERCHANGE_TRUST_POLICY" not in observed["env"]
    assert "MAINE_FAST_INTERCHANGE_WORKER_TOKEN" not in observed["env"]
    assert "MAINE_MATTER_STORE_KEY" not in observed["env"]
    assert observed["env"]["MFL_VAULT_KEY_ROOT"] == str(tmp_path / "qa/vault")
    assert observed["env"]["MFL_AUTHORITY_DATA_ROOT"] == str(tmp_path / "qa/empty-authority")
    assert observed["env"]["MFL_LOCAL_API_INSTANCE_ID"] == process.qa_service_instance
    assert observed["creationflags"] == getattr(runner.subprocess, "CREATE_NO_WINDOW", 0)


def test_prior_qualification_evidence_is_not_overwritten(runner, tmp_path):
    report = tmp_path / "installed-offline-qualification.json"
    report.write_text('{"prior":"failure"}', encoding="utf-8")
    with pytest.raises(SystemExit, match="immutable"):
        runner.main(["--evidence-root", str(tmp_path)])
    assert json.loads(report.read_text()) == {"prior": "failure"}


def test_failed_runtime_call_is_persisted_as_blocked(runner, monkeypatch, tmp_path):
    executable = tmp_path / "MaineFamilyLawLLM.exe"
    executable.write_bytes(b"fake runtime, never launched")
    resolution = runner.InstalledRuntimeResolution(
        package_name="fictional", package_full_name="", version="",
        install_location=str(tmp_path), executable_path=str(executable),
        source="explicit_bundled_runtime", available=True)
    process = SimpleNamespace(pid=1, qa_service_instance="fictional",
                              terminate=lambda: None, wait=lambda **kw: None, kill=lambda: None)
    monitor = SimpleNamespace(start=lambda: None, stop=lambda: {
        "sample_count": 1, "external_connection_count": 0, "errors": []})
    monkeypatch.setattr(runner, "_runtime_resolution", lambda _: resolution)
    monkeypatch.setattr(runner, "build_case_fixture", lambda _: [])
    monkeypatch.setattr(runner.tempfile, "mkdtemp", lambda **kw: str(tmp_path / "fictional"))
    monkeypatch.setattr(runner, "start_runtime", lambda *a, **kw: process)
    monkeypatch.setattr(runner, "RuntimeNetworkMonitor", lambda _: monitor)
    monkeypatch.setattr(runner, "wait_json", lambda *a, **kw: {"status": "ok"})
    monkeypatch.setattr(runner, "verify_runtime_instance", lambda *a: True)

    def failed(*a, **kw):
        raise TimeoutError("FICTIONAL failure text must not leak into evidence")

    monkeypatch.setattr(runner, "request_json", failed)
    output = tmp_path / "evidence"
    assert runner.main(["--runtime-executable", str(executable), "--evidence-root", str(output)]) == 2
    text = (output / "installed-offline-qualification.json").read_text()
    report = json.loads(text)
    assert report["qualification_status"] == "blocked"
    assert report["feature_check_status"] == "blocked"
    assert "qualification_exception:TimeoutError" in report["blockers"]
    assert "must not leak" not in text
    assert report["installed_msix"] is False
