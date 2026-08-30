"""Real r0003 inference in the production workbench, isolated fictional QA only.

The sole test seam is operator registry selection: an ephemeral TEST key signs
a DEVELOPMENT grant. Production admission is deliberately not created. All
routes, record tokens, context approval, auditing and UI assets are unchanged.
No real matters, training jobs, GPU devices, or source pack files are modified.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import socket
import tempfile
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_registry(pack, out):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from legal.fast_interchange.admission import AdmissionAuthority, canonical, digest
    from legal.fast_interchange.worker import HotSwapRegistry
    from legal.security.strict_json import strict_json_load_path

    def read(name):
        return strict_json_load_path(pack / name, max_bytes=2 * 1024**2, require_object=True)

    manifest, releases, artifacts = read("pack-manifest.json"), read("releases.json"), read("artifacts.json")
    if (manifest.get("capabilities") != ["evidence_review"] or manifest.get("production_admitted") is not False
            or digest(releases) != manifest["release_registry_sha256"]
            or digest(artifacts) != manifest["artifact_registry_sha256"]):
        raise ValueError("evidence_pack_contract_or_digest_invalid")
    if len(releases["releases"]) != 1:
        raise ValueError("evidence_single_model_required")
    # Derived in memory ONLY. Never edit or promote the source release registry.
    releases["releases"][0]["admission"] = "admitted_for_dev"
    registry = HotSwapRegistry.from_dicts(root=pack, releases=releases, artifacts=artifacts)
    release = next(iter(registry.releases.values()))
    now = datetime.now(UTC)
    past, future = (now - timedelta(minutes=1)).isoformat(), (now + timedelta(hours=2)).isoformat()
    key = Ed25519PrivateKey.generate()
    trust = {"schema_version": "fast_interchange_admission_trust_v1", "revision": 1,
        "minimum_catalog_sequence": 1, "trusted_keys": {"fictional-ui-test-key": {
            "public_key_base64": base64.b64encode(key.public_key().public_bytes_raw()).decode(),
            "not_before": past, "expires_at": future, "test_only": True}},
        "revoked_key_ids": [], "revoked_release_ids": [], "approved_download_origins": []}
    save(out / "test-trust.json", trust)
    disclosure = {"scope": "fictional_UI_test_only", "attorney_approval": False,
                  "production_admission": False, "prior_quality": "6/12 source-project cases passed"}
    save(out / "test-scope.json", disclosure)
    grant = {"release_id": release.release_id, "model_id": release.model_id,
        "capability": release.capability, "release_fingerprint": release.release_fingerprint,
        "scope": "development", "review_required": True, "promotion_authority": False,
        "licenses": {"base": "Apache-2.0", "tokenizer": "Apache-2.0",
            "adapter": "local-fictional-research-only", "redistribution_permitted": False,
            "rights_evidence_sha256": digest(manifest)},
        "evaluation": {"report_sha256": digest(disclosure), "dataset_kind": "synthetic",
            "sample_count": 12, "reviewer_approval_sha256": digest(disclosure)},
        "compatibility": {"runtime_abi": release.runtime_abi,
            **{f"{name}_version": version(name) for name in ("torch", "transformers", "peft", "safetensors")},
            "quantization": "fp32", "max_context_tokens": 2048, "max_new_tokens": 256,
            # Measured CPU peak is 4.64 GiB; keep a hard 5 GiB worker cap.
            # The backend independently preserves another 1 GiB for the OS.
            "max_resident_bytes": 5 * 1024**3, "prompt_template_sha256": release.prompt_template_sha256}}
    payload = {"schema_version": "fast_interchange_admission_catalog_v1", "catalog_id": "fictional-ui-test",
        "sequence": 1, "published_at": past, "expires_at": future,
        "release_registry_sha256": digest(releases), "artifact_registry_sha256": digest(artifacts), "grants": [grant]}
    envelope = {"payload": payload, "key_id": "fictional-ui-test-key",
                "signature_base64": base64.b64encode(key.sign(canonical(payload))).decode()}
    authority = AdmissionAuthority(trust_path=out / "test-trust.json", state_root=out / "admission-state", allow_test_keys=True)
    registry = replace(registry, admission_authority=authority, signed_catalog=envelope)
    registry.select(release.model_id, allow_test_only=False)
    # Verify default production trust rejects the very same test envelope.
    from legal.fast_interchange.admission import AdmissionError
    try:
        AdmissionAuthority(trust_path=out / "test-trust.json", state_root=out / "must-not-admit").verify(
            envelope, releases=releases, artifacts=artifacts)
    except AdmissionError as exc:
        save(out / "production-rejection.json", {"status": "pass", "safe_code": str(exc)})
    else:
        raise RuntimeError("production_accepted_test_key")
    return registry, release


def seed_matter(out):
    from maine_family_law_llm.case_library import register_case_root
    matter = out / "FICTIONAL-Evidence-Review-QA"
    rows = []
    for number, text in enumerate((
        "FICTIONAL SOFTWARE TEST. The pickup note says pickup at 15:20. This is a reported recollection, not a finding.",
        "FICTIONAL SOFTWARE TEST. The message says pickup at 16:10. This is a reported recollection, not a finding.",
        "FICTIONAL SOFTWARE TEST. Only the March attachments subfolder was searched.",
    ), 1):
        relative = f"02_PRIVATE_FORENSIC_MASTER/files/fictional-note-{number}.txt"
        path = matter / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        rows.append({"evidence_id": f"FICTIONAL-{number}", "title": f"Fictional note {number}",
            "source_type": "txt", "source_locator": relative, "private_copy_relpath": relative,
            "source_hash": sha256(path.read_bytes()).hexdigest(), "page_number": 1, "page_count": 1,
            "parser_status": "parsed", "text_status": "available", "ocr_status": "not_required",
            "text_excerpt": text, "text_content": text, "issue_lanes": ["evidence", "pickup"]})
    save(matter / "04_INDEXES/private_search_index.json", rows)
    save(matter / "08_SOURCE_MANIFESTS_HASHES/source_manifest.json", [
        {**row, "source_path": str(matter / row["private_copy_relpath"])} for row in rows])
    from maine_family_law_llm.local_corpus_index import rebuild_local_content_index
    save(out / "index-build.json", rebuild_local_content_index(matter))
    register_case_root(matter, label="FICTIONAL Evidence Review QA", set_active=True)
    save(out / "fictional-manifest.json", rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to((ROOT / "dist").resolve()) or out.exists():
        parser.error("output_must_be_new_inside_repository_dist")
    out.mkdir(parents=True)
    for key, leaf in {"LOCALAPPDATA": "profile", "MAINE_FAMILY_LAW_DATA_ROOT": "data",
        "MFL_RUNTIME_STATE_ROOT": "state",
        "MFL_IDEMPOTENCY_STATE_ROOT": "idempotency", "MFL_VAULT_KEY_ROOT": "vault",
        "TEMP": "temporary", "TMP": "temporary", "HF_HOME": "temporary", "TORCH_HOME": "temporary"}.items():
        directory = out / leaf
        directory.mkdir(exist_ok=True)
        os.environ[key] = str(directory)
    tempfile.tempdir = str(out / "temporary")
    # Nonexistent external reference only; no store/data is created there.
    # Production forbids configuring authority products inside the repository.
    os.environ["MFL_AUTHORITY_DATA_ROOT"] = str(ROOT.parent / "MFL-unconfigured-authority-read-only")
    os.environ["MFL_CASE_LIBRARY_PATH"] = str(out / "case-library.json")
    os.environ["HF_HUB_OFFLINE"] = os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["MAINE_FAST_INTERCHANGE_WORKER_TOKEN"] = secrets.token_hex(32)
    os.environ["MFL_RUNTIME_MODE"] = "store"
    for key in tuple(os.environ):
        if key.startswith("MFL_FAST_INTERCHANGE_"):
            os.environ.pop(key)
    registry, release = test_registry(args.pack_root.resolve(strict=True), out)
    seed_matter(out)
    from legal.fast_interchange import host
    host.load_operator_registry = lambda: registry  # explicit isolated test-key seam
    from legal.fast_interchange.worker import HotSwapManager, create_worker_app
    from legal.fast_interchange.process_backend import IsolatedAdapterBackend
    import uvicorn
    from maine_family_law_llm.api import app

    backend = IsolatedAdapterBackend(allow_cpu=True, force_cpu=True, cpu_threads=4)
    manager = HotSwapManager(registry=registry, backend=backend)
    port, worker_port = free_port(), free_port()
    worker = create_worker_app(manager=manager, registry=registry, worker_token=os.environ["MAINE_FAST_INTERCHANGE_WORKER_TOKEN"])
    worker_server = uvicorn.Server(uvicorn.Config(worker, host="127.0.0.1", port=worker_port, log_level="warning"))
    worker_thread = threading.Thread(target=worker_server.run, daemon=True)
    worker_thread.start()
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import Response

    class EvidenceRecorder(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            start = time.monotonic()
            response = await call_next(request)
            if request.url.path in ("/api/local-agent/run", "/api/local-agent/preview", "/api/local-agent/cancel"):
                raw = b"".join([part async for part in response.body_iterator])
                try:
                    body = json.loads(raw)
                    # QA profile holds only generated fictional records. Never enabled in the app.
                    save(out / f"api-{time.time_ns()}.json", {"route": request.url.path, "status": response.status_code,
                        "duration_seconds": round(time.monotonic() - start, 3), "response": body})
                except ValueError:
                    pass
                return Response(raw, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
            return response
    app.add_middleware(EvidenceRecorder)
    descriptor = {"level": "production_source_UI_and_API_real_weights_ephemeral_development_test_key",
        "url": f"http://127.0.0.1:{port}", "worker_endpoint": f"http://127.0.0.1:{worker_port}",
        "model": release.model_id, "capability": "evidence_review", "device": "cpu", "cpu_threads": 4,
        "frozen_app": "not_tested", "production_admitted": False, "fictional_only": True}
    save(out / "launch.json", descriptor)
    print(json.dumps(descriptor), flush=True)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    def stop_when_requested():
        while not server.should_exit:
            if (out / "STOP").exists():
                server.should_exit = True
                return
            time.sleep(0.5)
    threading.Thread(target=stop_when_requested, daemon=True).start()
    try:
        server.run()
    finally:
        worker_server.should_exit = True
        worker_thread.join(timeout=10)
        manager.close()
        save(out / "shutdown.json", {"clean": not worker_thread.is_alive(), "peak_worker_resident_bytes": backend.peak_resident_bytes})


if __name__ == "__main__":
    main()
