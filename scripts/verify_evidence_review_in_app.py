"""Real Evidence Review or Drafting inference in the production workbench.

The sole test seam is operator registry selection: an ephemeral TEST key signs
a DEVELOPMENT grant. Production admission is deliberately not created. All
routes, record tokens, context approval, auditing and UI assets are unchanged.
No real matters, training jobs, GPU state, or source pack files are modified.

The default verification path requires an independently reproducible local
research-quality result.  ``--bounded-fictional-research`` is narrower: it is
only for a known-unqualified Evidence Review candidate running against the
script's built-in fictional records.  It proves that the production host
withholds every unverified model word and reconstructs only exact record
excerpts.  It never turns a failed quality result into a user, legal, client
matter, package, or production admission.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def require_fixed_worker_port(port=8105):
    """Use the exact production UI endpoint; never silently test a different port."""
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError("fast_interchange_worker_port_unavailable") from exc
    return port


def _quality_disclosure(
    quality: dict,
    manifest: dict,
    release,
    *,
    capability: str,
    bounded_fictional_research: bool,
    pack_manifest_path: Path | None = None,
) -> dict:
    """Describe the exact test boundary without creating an admission.

    A false quality gate is never accepted by the normal E2E path.  The
    optional bounded path exists solely to regression-test the host's
    deterministic Evidence Review output filter with a real, unqualified
    candidate.  It is intentionally unavailable to Drafting and refuses any
    pack that claims legal or production use.
    """

    if not bounded_fictional_research:
        from scripts.run_mfl_specialist_regression import MINIMUM_FROZEN_CASES
        from scripts.summarize_mfl_specialist_quality import require_quality_evidence, sha256_file

        if pack_manifest_path is None:
            raise ValueError("specialist_pack_manifest_path_required")
        require_quality_evidence(
            quality,
            capability=capability,
            pack_manifest_sha256=sha256_file(pack_manifest_path),
            release_fingerprint=release.release_fingerprint,
            minimum_cases=MINIMUM_FROZEN_CASES[capability],
        )
        if (
            quality.get("decision") != "LOCAL_RESEARCH_QUALITY_PASS"
            or quality.get("attorney_reviewed") is not False
            or quality.get("production_admitted") is not False
        ):
            raise ValueError("specialist_quality_report_required")
        mode = "fictional_UI_test_only"
    else:
        # This is deliberately a one-capability output-filter regression.  It
        # cannot be expanded to a fluent Drafting test or to a candidate that
        # represents itself as having legal, client-matter, or product status.
        if (
            capability != "evidence_review"
            or release.capability != "evidence_review"
            or manifest.get("scope")
            != "fictional_evidence_handling_research_only_not_substantive_legal_knowledge"
            or manifest.get("product_admission")
            != "not_supplied; use only explicit offline research diagnostics"
            or manifest.get("production_admitted") is not False
            or manifest.get("attorney_reviewed") is not False
            or quality.get("quality_gate_passed") is not False
            or quality.get("legal_use_approved") is not False
            or quality.get("runnable_research_only") is not True
        ):
            raise ValueError("bounded_fictional_research_profile_required")
        mode = "bounded_fictional_research_verifier_only"

    return {
        "scope": mode,
        "model_id": release.model_id,
        "capability": capability,
        "attorney_approval": False,
        "production_admission": False,
        "legal_use_approved": False,
        "quality_gate_passed": quality.get("quality_gate_passed") is True,
        "runnable_research_only": quality.get("runnable_research_only") is True,
        "raw_model_narrative_visible": False,
        "client_matter_use": False,
        "package_qualification": False,
        "diagnostic_attempts": int(quality.get("adapter_case_attempts") or 0),
        "diagnostic_semantic_passes": int(quality.get("aggregate_semantic_passes") or 0),
        "quality_observed_at": str(quality.get("observed_at") or "not_supplied"),
    }


def test_registry(
    pack,
    out,
    quality_report=None,
    *,
    capability="evidence_review",
    bounded_fictional_research=False,
):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from legal.fast_interchange.admission import AdmissionAuthority, canonical, digest
    from legal.fast_interchange.worker import HotSwapRegistry
    from legal.security.strict_json import strict_json_load_path

    def read(name):
        return strict_json_load_path(pack / name, max_bytes=2 * 1024**2, require_object=True)

    manifest, releases, artifacts = read("pack-manifest.json"), read("releases.json"), read("artifacts.json")
    capabilities = manifest.get("capabilities")
    if (not isinstance(capabilities, list) or capability not in capabilities
            or any(item not in {"evidence_review", "drafting"} for item in capabilities)
            or manifest.get("production_admitted") is not False
            or digest(releases) != manifest["release_registry_sha256"]
            or digest(artifacts) != manifest["artifact_registry_sha256"]):
        raise ValueError("evidence_pack_contract_or_digest_invalid")
    matching = [item for item in releases["releases"] if item.get("capability") == capability]
    if len(matching) != 1 or len(releases["releases"]) not in {1, 2}:
        raise ValueError("specialist_pack_capability_mismatch")
    # Derived in memory ONLY. Never edit or promote the source release registry.
    matching[0]["admission"] = "admitted_for_dev"
    registry = HotSwapRegistry.from_dicts(root=pack, releases=releases, artifacts=artifacts)
    selected = [item for item in registry.releases.values() if item.capability == capability]
    if len(selected) != 1:
        raise ValueError("specialist_pack_capability_mismatch")
    release = selected[0]
    now = datetime.now(UTC)
    past, future = (now - timedelta(minutes=1)).isoformat(), (now + timedelta(hours=2)).isoformat()
    key = Ed25519PrivateKey.generate()
    trust = {"schema_version": "fast_interchange_admission_trust_v1", "revision": 1,
        "minimum_catalog_sequence": 1, "trusted_keys": {"fictional-ui-test-key": {
            "public_key_base64": base64.b64encode(key.public_key().public_bytes_raw()).decode(),
            "not_before": past, "expires_at": future, "test_only": True}},
        "revoked_key_ids": [], "revoked_release_ids": [], "approved_download_origins": []}
    save(out / "test-trust.json", trust)
    quality = quality_report or {}
    disclosure = _quality_disclosure(
        quality,
        manifest,
        release,
        capability=capability,
        bounded_fictional_research=bounded_fictional_research,
        pack_manifest_path=pack / "pack-manifest.json",
    )
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
    parser.add_argument("--quality-report", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--capability",
        choices=("evidence_review", "drafting"),
        default="evidence_review",
    )
    parser.add_argument(
        "--bounded-fictional-research",
        action="store_true",
        help=(
            "Run only the Evidence Review verifier-mediated fictional-data harness for an "
            "otherwise unqualified research pack; never enables client, legal, package, or "
            "production use."
        ),
    )
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
    if args.device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    elif args.device == "cuda":
        # The desktop host can inherit a restrictive CUDA_VISIBLE_DEVICES
        # setting.  This isolated QA command is explicitly requesting the
        # machine's locally installed CUDA runtime, so expose it before the
        # runtime capability probe imports Torch.  The probe maps the driver
        # inventory to Torch's own index by UUID; do not pass a Windows device
        # number through as though it were a Torch index.
        os.environ.pop("CUDA_VISIBLE_DEVICES", None)
    os.environ["MAINE_FAST_INTERCHANGE_WORKER_TOKEN"] = secrets.token_hex(32)
    os.environ["MFL_RUNTIME_MODE"] = "store"
    for key in tuple(os.environ):
        if key.startswith("MFL_FAST_INTERCHANGE_"):
            os.environ.pop(key)
    quality_report = None
    if args.quality_report is not None:
        from legal.security.strict_json import strict_json_load_path
        quality_report = strict_json_load_path(
            args.quality_report.resolve(strict=True), max_bytes=2 * 1024**2,
            require_object=True,
        )
    registry, release = test_registry(
        args.pack_root.resolve(strict=True), out, quality_report=quality_report,
        capability=args.capability,
        bounded_fictional_research=args.bounded_fictional_research,
    )
    seed_matter(out)
    from legal.fast_interchange import host
    from legal.fast_interchange.hardware import assess_specialist_hardware, installed_torch_runtime
    from legal.fast_interchange.host import release_identity
    from legal.model_orchestration.hardware import profile_hardware

    host.load_operator_registry = lambda: registry  # explicit isolated test-key seam
    import uvicorn

    from legal.fast_interchange.process_backend import IsolatedAdapterBackend
    from legal.fast_interchange.worker import HotSwapManager, create_worker_app
    from maine_family_law_llm.api import app

    identity = release_identity(registry, release)
    readiness = assess_specialist_hardware(
        profile_hardware(out).as_dict(),
        identity.get("compatibility") or {},
        runtime=installed_torch_runtime(),
    )
    if readiness["blockers"]:
        raise RuntimeError("fast_interchange_hardware_not_ready")
    accelerator = (
        readiness.get("execution_accelerator")
        or readiness.get("recommended_accelerator")
        or {}
    )
    if args.device == "cuda" and accelerator.get("kind") != "gpu":
        raise RuntimeError("fast_interchange_cuda_runtime_not_ready")
    force_cpu = args.device == "cpu" or accelerator.get("kind") == "cpu"
    cuda_device = int(accelerator.get("index") or 0)
    backend = IsolatedAdapterBackend(
        allow_cpu=True,
        force_cpu=force_cpu,
        cuda_device=cuda_device,
        cpu_threads=4,
    )
    manager = HotSwapManager(registry=registry, backend=backend)
    port, worker_port = free_port(), require_fixed_worker_port()
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
    descriptor = {"level": "production_UI_canonical_API_real_weights_ephemeral_development_test_key",
        "url": f"http://127.0.0.1:{port}", "worker_endpoint": f"http://127.0.0.1:{worker_port}",
        "model": release.model_id, "capability": args.capability,
        "device_requested": args.device,
        "device_selected": "cpu" if force_cpu else f"cuda:{cuda_device}",
        "hardware_readiness": readiness,
        "cpu_threads": 4,
        "frozen_app": "not_tested", "production_admitted": False, "fictional_only": True,
        "test_mode": (
            "bounded_fictional_research_verifier_only"
            if args.bounded_fictional_research else "fictional_UI_test_only"
        )}
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
