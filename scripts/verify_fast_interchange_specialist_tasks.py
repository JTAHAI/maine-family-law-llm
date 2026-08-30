"""Run real local weights on held-out fictional tasks without admitting them.

No training, downloading, production registry change, or legal certification.
All temporary snapshots and reports live in this repository's ignored dist/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event

from legal.fast_interchange.admission import Compatibility, digest
from legal.fast_interchange.process_backend import IsolatedAdapterBackend
from legal.fast_interchange.snapshot import VerifiedSnapshot
from legal.fast_interchange.worker import (
    FastInterchangeError,
    HotSwapRegistry,
    TransformersPeftAdapterBackend,
)
from legal.security.strict_json import strict_json_load_path
from scripts.fast_interchange_acceptance_cases import acceptance_cases, assess, dataset_digest


class OfflineTaskBackend(TransformersPeftAdapterBackend):
    """Actual backend with Python socket connections denied for this test child."""

    def __init__(self, **options):
        self.network_attempts = 0

        def blocked(*_args, **_kwargs):
            self.network_attempts += 1
            raise FastInterchangeError("fast_interchange_test_network_forbidden")

        socket.socket.connect = blocked
        socket.socket.connect_ex = blocked
        socket.create_connection = blocked
        super().__init__(**options)

    def complete(self, **kwargs):
        result = super().complete(**kwargs)
        result["test_network_attempts"] = self.network_attempts
        result["test_cpu_threads"] = self._torch.get_num_threads()
        result["test_resident_adapters"] = len(self._loaded_adapters)
        return result


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(
    pack_root: Path,
    provenance: Path,
    workspace: Path,
    *,
    device: str,
    activation_timeout: int = 120,
) -> dict:
    cases = acceptance_cases()
    manifest = strict_json_load_path(pack_root / "pack-manifest.json", require_object=True)
    releases = strict_json_load_path(pack_root / "releases.json", require_object=True)
    artifacts = strict_json_load_path(pack_root / "artifacts.json", require_object=True)
    receipt = strict_json_load_path(provenance, require_object=True)
    if (
        manifest.get("production_admitted") is not False
        or manifest.get("attorney_reviewed") is not False
        or manifest.get("release_registry_sha256") != digest(releases)
        or manifest.get("artifact_registry_sha256") != digest(artifacts)
        or file_hash(pack_root / "base/model.safetensors")
        != (receipt.get("files_sha256") or {}).get("model.safetensors")
    ):
        raise ValueError("development_pack_provenance_mismatch")
    registry = HotSwapRegistry.from_dicts(root=pack_root, releases=releases, artifacts=artifacts)
    by_capability = {release.capability: release for release in registry.releases.values()}
    if len(registry.releases) != 7 or set(by_capability) != {case.capability for case in cases}:
        raise ValueError("specialist_capability_set_invalid")
    if any(release.admission != "unadmitted_protocol_smoke" for release in by_capability.values()):
        raise ValueError("development_pack_scope_mismatch")
    policy = Compatibility(
        runtime_abi="fast_interchange_hotswap_v1",
        **{
            name + "_version": version(name)
            for name in ("torch", "transformers", "peft", "safetensors")
        },
        quantization="fp32" if device == "cpu" else "bf16",
        max_context_tokens=2048,
        max_new_tokens=128,
        max_resident_bytes=6 * 1024**3,
        prompt_template_sha256=hashlib.sha256(
            b"fi-fixed-role-v1:[ROLE]\\nCONTENT;join=\\n"
        ).hexdigest(),
    )
    report = {
        "schema_version": "mfl_specialist_task_acceptance_v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "execution_level": "actual_weights_owned_worker_production_prompt_builder",
        "dataset_kind": "fictional_unreviewed_held_out_from_known_r0002_builder",
        "dataset_sha256": dataset_digest(cases),
        "sample_count": len(cases),
        "python": sys.version,
        "device_requested": device,
        "policy": policy.model_dump(),
        "pack_id": manifest["pack_id"],
        "pack_manifest_sha256": file_hash(pack_root / "pack-manifest.json"),
        "production_admitted": False,
        "attorney_reviewed": False,
        "ui_e2e": "not_executed_unadmitted_pack",
        "frozen_package": "not_executed",
        "network_guard": "python_socket_denial_in_owned_child_not_os_firewall",
        "rows": [],
        "blockers": [],
        "limitations": [
            "Necessary exact extraction/review checks, not comprehensive legal-quality evaluation.",
            "No independent admission, attorney review, or production use is created by this run.",
        ],
    }
    backend = IsolatedAdapterBackend(
        factory=OfflineTaskBackend,
        allow_cpu=device == "cpu",
        force_cpu=device == "cpu",
        cpu_threads=4,
    )
    backend.configure(policy)
    snapshot = VerifiedSnapshot(directory=workspace)
    started = time.monotonic()
    try:
        for release in by_capability.values():
            snapshot.prepare(
                pack_root,
                registry.bindings[release.release_id],
                strict_models=True,
                maximum_bytes=policy.max_resident_bytes,
            )
        for capability, release in by_capability.items():
            backend.set_cancellation(Event(), time.monotonic() + activation_timeout)
            load_started = time.monotonic()
            backend.activate(
                root=snapshot.root, binding=registry.bindings[release.release_id], release=release
            )
            load_ms = round((time.monotonic() - load_started) * 1000, 2)
            if load_ms > 120_000:
                report["blockers"].append("cold_start_exceeds_production_120_second_budget")
            report["diagnostic_activation_timeout_seconds"] = activation_timeout
            for case in (row for row in cases if row.capability == capability):
                row = {
                    "case_id": case.case_id,
                    "capability": capability,
                    "load_or_swap_ms": load_ms,
                }
                backend.set_cancellation(Event(), time.monotonic() + 120)
                action_started = time.monotonic()
                try:
                    result = backend.complete(
                        release=release, messages=[{"role": "user", "content": case.prompt()}]
                    )
                    answer = result["choices"][0]["message"]["content"]
                    row.update(assess(case, answer))
                    row["finish_reason"] = result["choices"][0]["finish_reason"]
                    row["network_attempts"] = result["test_network_attempts"]
                    row["cpu_threads"] = result["test_cpu_threads"]
                    row["resident_adapters"] = result["test_resident_adapters"]
                    row["passed"] = (
                        row["passed"]
                        and row["network_attempts"] == 0
                        and row["resident_adapters"] == 1
                    )
                except FastInterchangeError as exc:
                    row.update(passed=False, safe_error=exc.code)
                finally:
                    row["duration_ms"] = round((time.monotonic() - action_started) * 1000, 2)
                    backend.clear_context()
                report["rows"].append(row)
                print(
                    json.dumps(
                        {
                            "case_id": case.case_id,
                            "passed": row["passed"],
                            "duration_ms": row["duration_ms"],
                        }
                    ),
                    flush=True,
                )
    except Exception as exc:
        report["blockers"].append(getattr(exc, "code", "specialist_evaluation_runtime_failed"))
    finally:
        backend.close()
        snapshot.close()
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    report["peak_worker_resident_bytes"] = backend.peak_resident_bytes
    report["passed"] = sum(row["passed"] for row in report["rows"])
    report["failed"] = sum(not row["passed"] for row in report["rows"])
    report["not_executed"] = len(cases) - len(report["rows"])
    if report["passed"] != len(cases):
        report["blockers"].append("meaningful_specialist_task_acceptance_failed")
    report["blockers"].append("independent_production_admission_and_human_evaluation_missing")
    report["decision"] = "BLOCKED"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument("--base-provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--activation-timeout", type=int, default=120)
    args = parser.parse_args()
    if not 120 <= args.activation_timeout <= 600:
        parser.error("diagnostic_activation_timeout_must_be_120_through_600")
    repo_dist = (Path(__file__).resolve().parents[1] / "dist").resolve()
    output = args.output.resolve()
    if not output.is_relative_to(repo_dist) or output.exists():
        parser.error("output_must_be_new_and_inside_repository_dist")
    output.parent.mkdir(parents=True, exist_ok=True)
    for name in ("TEMP", "TMP", "HF_HOME", "TORCH_HOME"):
        os.environ[name] = str(output.parent)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    report = run(
        args.pack_root.resolve(strict=True),
        args.base_provenance.resolve(strict=True),
        output.parent,
        device=args.device,
        activation_timeout=args.activation_timeout,
    )
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "passed": report["passed"],
                "failed": report["failed"],
                "output": str(output),
            }
        )
    )
    # Task-level success alone must never become a shell-level release approval.
    return 0 if report["decision"] == "RELEASE_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
