"""Verify an explicit development-only FAST INTERCHANGE pack without promoting it.

The verifier reads one pack outside the repository, verifies its recorded
artifact hashes into a private temporary snapshot, then loads the shared base
and swaps every adapter using the application's own PEFT backend.  It performs
one deterministic neural forward pass per adapter.  It never writes to the
pack, downloads a model, creates an admission catalog, starts a network
service, or treats a protocol/safety adapter as substantive Maine-law work.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.fast_interchange.admission import Compatibility, digest
from legal.fast_interchange.snapshot import VerifiedSnapshot
from legal.fast_interchange.worker import (
    FastInterchangeError,
    HotSwapRegistry,
    TransformersPeftAdapterBackend,
)
from legal.security.strict_json import strict_json_load_path


EXPECTED_CAPABILITIES = (
    "intake_triage",
    "evidence_review",
    "authority_review",
    "drafting",
    "parenting_plan_review",
    "financial_disclosure_review",
    "safety_privacy_review",
)
EXPECTED_SCOPE = "runnable_protocol_and_safety_smoke_only_not_substantive_legal_knowledge"
EXPECTED_TEMPLATE = hashlib.sha256(b"fi-fixed-role-v1:[ROLE]\\nCONTENT;join=\\n").hexdigest()


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _read_object(path: Path, *, maximum_bytes: int = 2 * 1024**2) -> dict[str, Any]:
    return strict_json_load_path(path, max_bytes=maximum_bytes, require_object=True)


def _compatibility(*, quantization: str, max_new_tokens: int = 8) -> Compatibility:
    return Compatibility(
        runtime_abi="fast_interchange_hotswap_v1",
        torch_version=importlib.metadata.version("torch"),
        transformers_version=importlib.metadata.version("transformers"),
        peft_version=importlib.metadata.version("peft"),
        safetensors_version=importlib.metadata.version("safetensors"),
        quantization=quantization,
        max_context_tokens=128,
        max_new_tokens=max_new_tokens,
        max_resident_bytes=16 * 1024**3,
        prompt_template_sha256=EXPECTED_TEMPLATE,
    )


def _report_failure(report: dict[str, Any], error: Exception) -> dict[str, Any]:
    report["decision"] = "BLOCKED"
    report["blockers"] = [f"development_pack_exception:{type(error).__name__}"]
    report["safe_error"] = type(error).__name__
    if isinstance(error, FastInterchangeError):
        report["safe_error_code"] = error.code
    else:
        detail = str(error).strip()
        if re.fullmatch(r"[a-z0-9_:-]{1,120}", detail):
            report["safe_error_code"] = detail
    return report


def verify(
    *,
    pack_root: Path,
    provenance: Path,
    allow_cpu: bool,
    exercise_completions: bool = False,
    max_new_tokens: int = 8,
) -> dict[str, Any]:
    pack_root = pack_root.resolve(strict=True)
    provenance = provenance.resolve(strict=True)
    report: dict[str, Any] = {
        "schema_version": "mfl_fast_interchange_development_pack_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "execution_level": (
            "application_worker_backend_actual_local_load_swap_and_bounded_generation"
            if exercise_completions
            else "application_worker_backend_actual_local_load_and_forward"
        ),
        "fictional_prompt_only": True,
        "development_only": True,
        "completion_contract_exercised": bool(exercise_completions),
        "decision": "BLOCKED",
        "pack_root": str(pack_root),
        "checks": {},
        "adapters": [],
        "blockers": [],
        "limitations": [
            "This proves local artifact verification, shared-base loading, adapter interchange, and one neural forward pass per slot unless the bounded completion option is explicitly enabled.",
            "It does not prove substantive Maine-law knowledge, answer quality, legal advice, a user-facing response, attorney review, production admission, installed-package inference, Store readiness, or Enterprise readiness.",
            "The source pack remains external to this repository and MSIX. No model was downloaded, trained, copied, signed, or promoted by this verification.",
        ],
    }
    snapshot: VerifiedSnapshot | None = None
    backend: TransformersPeftAdapterBackend | None = None
    try:
        if pack_root.is_symlink() or not pack_root.is_dir():
            raise ValueError("development_pack_root_invalid")
        manifest = _read_object(pack_root / "pack-manifest.json")
        releases = _read_object(pack_root / "releases.json")
        artifacts = _read_object(pack_root / "artifacts.json")
        base_provenance = _read_object(provenance)
        base_path = pack_root / "base" / "model.safetensors"
        if not base_path.is_file():
            raise ValueError("development_pack_base_missing")
        base_sha256 = _sha256(base_path)
        report["pack"] = {
            "pack_id": manifest.get("pack_id"),
            "shared_base": manifest.get("shared_base"),
            "base_license": manifest.get("base_license"),
            "production_admitted": manifest.get("production_admitted"),
            "attorney_reviewed": manifest.get("attorney_reviewed"),
            "scope": manifest.get("scope"),
            "capabilities": manifest.get("capabilities"),
            "base_model_sha256": base_sha256,
        }
        manifest_checks = {
            "development_scope_declared": manifest.get("scope") == EXPECTED_SCOPE,
            "production_admission_absent": manifest.get("production_admitted") is False,
            "attorney_review_absent": manifest.get("attorney_reviewed") is False,
            "northstar_assets_absent": manifest.get("contains_northstar_assets") is False,
            "capabilities_exact": tuple(manifest.get("capabilities") or ()) == EXPECTED_CAPABILITIES,
            "base_license_recorded": manifest.get("base_license") == "Apache-2.0",
            "base_hash_matches_recorded_provenance": base_sha256
            == str((base_provenance.get("files_sha256") or {}).get("model.safetensors") or ""),
            "release_registry_digest_matches_manifest": digest(releases)
            == str(manifest.get("release_registry_sha256") or ""),
            "artifact_registry_digest_matches_manifest": digest(artifacts)
            == str(manifest.get("artifact_registry_sha256") or ""),
        }
        report["checks"].update({name: "pass" if passed else "fail" for name, passed in manifest_checks.items()})
        if not all(manifest_checks.values()):
            report["blockers"] = sorted(name for name, passed in manifest_checks.items() if not passed)
            return report

        registry = HotSwapRegistry.from_dicts(root=pack_root, releases=releases, artifacts=artifacts)
        release_rows = tuple(registry.releases.values())
        registry_checks = {
            "seven_release_slots": len(release_rows) == len(EXPECTED_CAPABILITIES),
            "release_capabilities_exact": tuple(row.capability for row in release_rows) == EXPECTED_CAPABILITIES,
            "all_releases_unadmitted_protocol_smoke": all(row.admission == "unadmitted_protocol_smoke" for row in release_rows),
            "shared_base_binding": len(
                {
                    (binding.base_dir, binding.base_inventory.digest, binding.tokenizer_inventory.digest)
                    for binding in registry.bindings.values()
                }
            )
            == 1,
        }
        report["checks"].update({name: "pass" if passed else "fail" for name, passed in registry_checks.items()})
        if not all(registry_checks.values()):
            report["blockers"] = sorted(name for name, passed in registry_checks.items() if not passed)
            return report

        # The snapshot hashes one shared base once, then hashes each unique adapter
        # before the native loader sees it. It is read-only and removed on close.
        snapshot = VerifiedSnapshot()
        first = release_rows[0]
        snapshot.prepare(pack_root, registry.bindings[first.release_id], strict_models=True, maximum_bytes=16 * 1024**3)
        for release in release_rows[1:]:
            snapshot.prepare(pack_root, registry.bindings[release.release_id], strict_models=True, maximum_bytes=16 * 1024**3)
        report["checks"]["all_artifacts_verified_into_private_snapshot"] = "pass"

        import torch

        cuda_available = bool(torch.cuda.is_available())
        if not cuda_available and not allow_cpu:
            raise FastInterchangeError("fast_interchange_cpu_mode_not_authorized")
        quantization = "bf16" if cuda_available else "fp32"
        backend = TransformersPeftAdapterBackend(allow_cpu=allow_cpu, cuda_device=0)
        backend.configure(
            _compatibility(quantization=quantization, max_new_tokens=max_new_tokens)
        )
        report["runtime"] = {
            "torch": torch.__version__,
            "cuda_available": cuda_available,
            "device": torch.cuda.get_device_name(0) if cuda_available else "cpu",
            "quantization": quantization,
            "external_downloads_permitted": False,
            "max_new_tokens": max_new_tokens,
        }
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["TLD_EXTRACT_NO_FETCH"] = "1"
        for release in release_rows:
            started = time.monotonic()
            binding = registry.bindings[release.release_id]
            identity = backend.activate(root=snapshot.root, binding=binding, release=release)
            tokenizer = backend._tokenizer
            model = backend._model
            if tokenizer is None or model is None:
                raise FastInterchangeError("fast_interchange_backend_not_active")
            # Exercise exactly the immutable framing enforced by the worker.
            # The literal ``\\n`` separators are part of the v1 contract and
            # therefore part of every r0002 training receipt.
            prompt = "fi-fixed-role-v1:[USER]\\\\nFictional protocol-safety verification only. Do not provide legal advice."
            encoded = tokenizer(prompt, return_tensors="pt", truncation=False)
            device = next(model.parameters()).device
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.no_grad():
                logits = model(**encoded).logits[0, -1].to(dtype=torch.float32).cpu().contiguous()
            adapter_result: dict[str, Any] = {
                "capability": release.capability,
                "release_id": release.release_id,
                "model_id": release.model_id,
                "identity_matches": identity == {
                    "release_id": release.release_id,
                    "model_id": release.model_id,
                    "release_fingerprint": release.release_fingerprint,
                },
                "resident_adapter_ids": sorted(backend._loaded_adapters),
                "logits_sha256": hashlib.sha256(logits.numpy().tobytes()).hexdigest(),
                "context_cleared_before_next_request": True,
            }
            try:
                if exercise_completions:
                    completion = backend.complete(
                        release=release,
                        messages=[
                            {
                                "role": "user",
                                "content": "Fictional protocol-safety verification only. Do not provide legal advice.",
                            }
                        ],
                    )
                    content = str(completion["choices"][0]["message"]["content"])
                    adapter_result.update(
                        completion_contract="pass",
                        completion_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        completion_characters=len(content),
                        completion_finish_reason=str(completion["choices"][0]["finish_reason"]),
                    )
                else:
                    adapter_result["completion_contract"] = "not_exercised"
            except FastInterchangeError as exc:
                adapter_result.update(
                    completion_contract="fail",
                    completion_safe_error=exc.code,
                )
            finally:
                backend.clear_context()
            adapter_result["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
            report["adapters"].append(adapter_result)
        adapter_checks = {
            "all_adapters_loaded_and_forwarded": len(report["adapters"]) == len(EXPECTED_CAPABILITIES),
            "every_identity_matched": all(item["identity_matches"] for item in report["adapters"]),
            "one_resident_adapter_per_swap": all(len(item["resident_adapter_ids"]) == 1 for item in report["adapters"]),
            "distinct_adapter_forward_outputs": len({item["logits_sha256"] for item in report["adapters"]}) == len(report["adapters"]),
        }
        if exercise_completions:
            adapter_checks["all_adapters_completed_fixed_contract"] = all(
                item.get("completion_contract") == "pass" for item in report["adapters"]
            )
        report["checks"].update({name: "pass" if passed else "fail" for name, passed in adapter_checks.items()})
        report["blockers"] = sorted(name for name, passed in adapter_checks.items() if not passed)
        report["decision"] = (
            "PASS_DEVELOPMENT_LOAD_AND_GENERATE"
            if exercise_completions and not report["blockers"]
            else "PASS_DEVELOPMENT_LOAD_AND_FORWARD"
            if not report["blockers"]
            else "BLOCKED"
        )
        return report
    except Exception as exc:  # noqa: BLE001 - write safe evidence for the supplied pack
        return _report_failure(report, exc)
    finally:
        if backend is not None:
            backend.close()
        if snapshot is not None:
            snapshot.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", required=True, type=Path)
    parser.add_argument("--base-provenance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-cpu", action="store_true", help="Permit the slow, non-performance-qualified CPU loader.")
    parser.add_argument(
        "--exercise-completions",
        action="store_true",
        help="Generate one bounded fictional completion per adapter and record only hashes and lengths.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=8,
        help="Fixed completion ceiling, 1 through 128 (default: 8).",
    )
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("refusing_to_overwrite_evidence")
    if not 1 <= args.max_new_tokens <= 128:
        parser.error("max_new_tokens_must_be_between_1_and_128")
    report = verify(
        pack_root=args.pack_root,
        provenance=args.base_provenance,
        allow_cpu=bool(args.allow_cpu),
        exercise_completions=bool(args.exercise_completions),
        max_new_tokens=args.max_new_tokens,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if str(report["decision"]).startswith("PASS_DEVELOPMENT_LOAD_AND_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
