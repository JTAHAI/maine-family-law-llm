"""Run held-out fictional tasks on the r0004 workflow candidate.

This is a development-quality check, not model admission or product E2E.  It
uses the same verified snapshot, PEFT backend, fixed worker framing, bounded
completion behavior, and source-bound host prompt as the application.  The
candidate stays test-only and every temporary model snapshot remains beneath
the repository's ignored ``dist`` directory.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import tempfile
import time
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any

from legal.fast_interchange.admission import Compatibility, digest
from legal.fast_interchange.snapshot import VerifiedSnapshot
from legal.fast_interchange.worker import HotSwapRegistry, TransformersPeftAdapterBackend
from legal.security.strict_json import strict_json_load_path
from scripts.build_fast_interchange_protocol_r0002 import (
    BASE_FILES,
    CAPABILITIES,
    PROMPT_TEMPLATE_SHA256,
    TOKENIZER_FILES,
    _canonical,
    _require_base,
    _sha256_file,
)
from scripts.fast_interchange_acceptance_cases import acceptance_cases, assess, dataset_digest

ROOT = Path(__file__).resolve().parents[1]
DIST_ROOT = (ROOT / "dist").resolve()
EXPECTED_SCOPE = "synthetic_source_bound_workflow_only_not_substantive_maine_law"


class _NetworkDenied:
    def __enter__(self):
        self.attempts = 0
        self._originals = {
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
            "create_connection": socket.create_connection,
        }

        def denied(*_args, **_kwargs):
            self.attempts += 1
            raise RuntimeError("fast_interchange_candidate_network_forbidden")

        socket.socket.connect = denied
        socket.socket.connect_ex = denied
        socket.create_connection = denied
        return self

    def __exit__(self, *_exc):
        socket.socket.connect = self._originals["connect"]
        socket.socket.connect_ex = self._originals["connect_ex"]
        socket.create_connection = self._originals["create_connection"]


def _assert_inside_dist(path: Path, *, new: bool) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(DIST_ROOT) or (new and resolved.exists()):
        raise ValueError("workflow_candidate_evidence_must_be_new_and_inside_repository_dist")
    return resolved


def _artifact(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
    }


def _inventory(root: Path, paths: tuple[Path, ...]) -> dict[str, Any]:
    return {"files": sorted((_artifact(root, path) for path in paths), key=lambda row: row["path"])}


def _link(source: Path, destination: Path) -> None:
    if not source.is_file() or source.is_symlink() or destination.exists():
        raise RuntimeError("workflow_candidate_link_source_invalid")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, destination)


def _test_registry(source_root: Path, candidate_root: Path, base_root: Path) -> HotSwapRegistry:
    base_paths = tuple(source_root / "base" / name for name in BASE_FILES)
    tokenizer_paths = tuple(source_root / "base" / name for name in TOKENIZER_FILES)
    base_inventory = _inventory(source_root, base_paths)
    tokenizer_inventory = _inventory(source_root, tokenizer_paths)
    releases: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    for capability in CAPABILITIES:
        adapter_root = source_root / "adapters" / capability
        adapter_paths = (adapter_root / "adapter_model.safetensors",)
        adapter_inventory = _inventory(source_root, adapter_paths)
        adapter_config = _artifact(source_root, adapter_root / "adapter_config.json")
        release_id = f"mfl-fi-{capability.replace('_', '-')}-workflow-r0004-test"
        fingerprint = digest(
            {
                "adapter_config_sha256": adapter_config["sha256"],
                "adapter_inventory_sha256": digest(adapter_inventory),
                "base_inventory_sha256": digest(base_inventory),
                "capability": capability,
                "prompt_template_sha256": PROMPT_TEMPLATE_SHA256,
                "release_id": release_id,
                "runtime_abi": "fast_interchange_hotswap_v1",
                "tokenizer_inventory_sha256": digest(tokenizer_inventory),
            }
        )
        releases.append(
            {
                "release_id": release_id,
                "model_id": release_id,
                "capability": capability,
                "admission": "test_only",
                "release_fingerprint": fingerprint,
                "base_inventory_sha256": digest(base_inventory),
                "tokenizer_inventory_sha256": digest(tokenizer_inventory),
                "adapter_inventory_sha256": digest(adapter_inventory),
                "adapter_config_sha256": adapter_config["sha256"],
                "runtime_abi": "fast_interchange_hotswap_v1",
                "prompt_template_sha256": PROMPT_TEMPLATE_SHA256,
                "review_required": True,
                "promotion_authority": False,
            }
        )
        bindings.append(
            {
                "release_id": release_id,
                "release_fingerprint": fingerprint,
                "base_dir": "base",
                "adapter_dir": f"adapters/{capability}",
                "base_inventory": base_inventory,
                "tokenizer_inventory": tokenizer_inventory,
                "adapter_inventory": adapter_inventory,
                "adapter_config": adapter_config,
            }
        )
    return HotSwapRegistry.from_dicts(
        root=source_root,
        releases={"schema": "fast_interchange_releases_v1", "releases": releases},
        artifacts={"schema": "fast_interchange_artifacts_v1", "bindings": bindings},
    )


def _materialize_test_source(
    *, stack: ExitStack, workspace: Path, candidate_root: Path, base_root: Path
) -> Path:
    temporary = stack.enter_context(
        tempfile.TemporaryDirectory(prefix="mfl-fi-r0004-source-", dir=workspace)
    )
    source_root = Path(temporary).resolve()
    for name in (*BASE_FILES, *TOKENIZER_FILES):
        _link(base_root / name, source_root / "base" / name)
    for capability in CAPABILITIES:
        for name in ("adapter_model.safetensors", "adapter_config.json"):
            _link(
                candidate_root / "adapters" / capability / name,
                source_root / "adapters" / capability / name,
            )
    return source_root


def run(
    *, candidate_root: Path, base_root: Path, base_provenance: Path, workspace: Path
) -> dict[str, Any]:
    manifest = strict_json_load_path(
        candidate_root / "candidate-manifest.json", require_object=True
    )
    receipt = strict_json_load_path(candidate_root / "training-receipt.json", require_object=True)
    base = _require_base(base_root, base_provenance)
    if (
        manifest.get("scope") != EXPECTED_SCOPE
        or manifest.get("production_admitted") is not False
        or manifest.get("contains_real_legal_authority") is not False
        or manifest.get("contains_private_matter_data") is not False
        or manifest.get("base_model_sha256") != base["model_sha256"]
        or manifest.get("base_provenance_sha256") != base["provenance_sha256"]
        or tuple(manifest.get("capabilities") or ()) != CAPABILITIES
        or receipt.get("training_data", {}).get("held_out_acceptance_set_included") is not False
    ):
        raise ValueError("workflow_candidate_manifest_boundary_invalid")
    cases = acceptance_cases()
    policy = Compatibility(
        runtime_abi="fast_interchange_hotswap_v1",
        **{
            name + "_version": version(name)
            for name in ("torch", "transformers", "peft", "safetensors")
        },
        quantization="bf16",
        max_context_tokens=2048,
        max_new_tokens=128,
        max_resident_bytes=6 * 1024**3,
        prompt_template_sha256=PROMPT_TEMPLATE_SHA256,
    )
    report: dict[str, Any] = {
        "schema_version": "mfl_fast_interchange_workflow_candidate_acceptance_v1",
        "execution_level": "actual_candidate_weights_verified_snapshot_production_backend",
        "dataset_kind": "fictional_unreviewed_held_out",
        "dataset_sha256": dataset_digest(cases),
        "sample_count": len(cases),
        "candidate_manifest_sha256": _sha256_file(candidate_root / "candidate-manifest.json"),
        "training_receipt_sha256": _sha256_file(candidate_root / "training-receipt.json"),
        "base_model_sha256": base["model_sha256"],
        "policy": policy.model_dump(),
        "production_admitted": False,
        "attorney_reviewed": False,
        "test_only_registry": True,
        "ui_e2e": "not_executed_unadmitted_candidate",
        "frozen_package": "not_executed",
        "rows": [],
        "blockers": ["independent_production_admission_and_human_evaluation_missing"],
    }
    workspace.mkdir(parents=True, exist_ok=True)
    backend = None
    started = time.monotonic()
    with ExitStack() as stack, _NetworkDenied() as network:
        source_root = _materialize_test_source(
            stack=stack, workspace=workspace, candidate_root=candidate_root, base_root=base_root
        )
        registry = _test_registry(source_root, candidate_root, base_root)
        snapshot = stack.enter_context(_SnapshotContext(VerifiedSnapshot(directory=workspace)))
        for release in registry.releases.values():
            snapshot.prepare(
                source_root,
                registry.bindings[release.release_id],
                strict_models=True,
                maximum_bytes=policy.max_resident_bytes,
            )
        backend = TransformersPeftAdapterBackend(allow_cpu=False, cuda_device=0)
        backend.configure(policy)
        for capability in CAPABILITIES:
            release = next(
                item for item in registry.releases.values() if item.capability == capability
            )
            backend.set_cancellation(Event(), time.monotonic() + 120)
            loaded = backend.activate(
                root=snapshot.root, binding=registry.bindings[release.release_id], release=release
            )
            for case in (item for item in cases if item.capability == capability):
                row: dict[str, Any] = {"case_id": case.case_id, "capability": capability}
                backend.set_cancellation(Event(), time.monotonic() + 120)
                call_started = time.monotonic()
                try:
                    result = backend.complete(
                        release=release, messages=[{"role": "user", "content": case.prompt()}]
                    )
                    answer = result["choices"][0]["message"]["content"]
                    row.update(assess(case, answer))
                    row["finish_reason"] = result["choices"][0]["finish_reason"]
                    row["identity"] = loaded
                except Exception as exc:  # noqa: BLE001 - persist only safe coded outcome
                    row.update(
                        passed=False, safe_error=getattr(exc, "code", "candidate_generation_failed")
                    )
                finally:
                    row["duration_ms"] = round((time.monotonic() - call_started) * 1000, 2)
                    backend.clear_context()
                report["rows"].append(row)
        report["network_attempts"] = network.attempts
        report["peak_gpu_allocated_bytes"] = int(
            getattr(
                getattr(backend, "_torch", None).cuda, "max_memory_allocated", lambda *_args: 0
            )(0)
        )
        backend.close()
        backend = None
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    report["passed"] = sum(bool(row.get("passed")) for row in report["rows"])
    report["failed"] = len(report["rows"]) - report["passed"]
    report["not_executed"] = len(cases) - len(report["rows"])
    if report["network_attempts"]:
        report["blockers"].append("candidate_attempted_network_connection")
    if report["passed"] != len(cases):
        report["blockers"].append("meaningful_specialist_task_acceptance_failed")
        report["decision"] = "BLOCKED"
    else:
        report["decision"] = "PASS_DEVELOPMENT_WORKFLOW_TASKS_NOT_RELEASE"
    return report


class _SnapshotContext:
    """Give the snapshot the context-manager protocol without changing its API."""

    def __init__(self, snapshot: VerifiedSnapshot):
        self.snapshot = snapshot

    def __enter__(self) -> VerifiedSnapshot:
        return self.snapshot

    def __exit__(self, *_exc) -> None:
        self.snapshot.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--base-provenance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = _assert_inside_dist(args.output, new=True)
    candidate = args.candidate_root.resolve(strict=True)
    if not candidate.is_relative_to(DIST_ROOT) or candidate.is_symlink():
        parser.error("candidate_must_be_inside_repository_dist")
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
    )
    report = run(
        candidate_root=candidate,
        base_root=args.base_root.resolve(strict=True),
        base_provenance=args.base_provenance.resolve(strict=True),
        workspace=output.parent,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(_canonical(report) + b"\n")
    print(
        json.dumps(
            {"decision": report["decision"], "passed": report["passed"], "output": str(output)}
        )
    )
    return 0 if report["decision"] == "PASS_DEVELOPMENT_WORKFLOW_TASKS_NOT_RELEASE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
