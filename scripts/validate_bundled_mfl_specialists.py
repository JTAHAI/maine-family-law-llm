"""Fail-closed release check for a built-in Evidence/Drafting model pair.

This validator cannot create admission. It accepts only an externally signed,
production-scoped, attorney-reviewed catalog whose artifacts and runtime ABI
match the exact Store build environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.fast_interchange.admission import AdmissionAuthority  # noqa: E402
from legal.fast_interchange.worker import HotSwapRegistry  # noqa: E402

CAPABILITIES = frozenset({"evidence_review", "drafting"})
ROOT_METADATA = frozenset(
    {
        "BASE-LICENSE.txt",
        "BASE-MODEL-CARD.md",
        "admission.json",
        "artifacts.json",
        "pack-manifest.json",
        "releases.json",
    }
)
ROOT_DIRECTORIES = frozenset({"adapters", "base"})
MAX_RESIDENT_BYTES = 5 * 1024**3


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def tree_identity(root: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    count = total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        file_digest = sha256_file(path)
        size = path.stat().st_size
        digest.update(f"{relative}\0{size}\0{file_digest}\n".encode())
        count += 1
        total += size
    return digest.hexdigest(), count, total


def validate_inventory_coverage(pack: Path, registry: HotSwapRegistry) -> None:
    """Reject payload outside signed bindings, including unused adapter siblings."""
    expected = {}
    for release in registry.releases.values():
        binding = registry.bindings[release.release_id]
        for artifact in (
            *binding.base_inventory.files,
            *binding.tokenizer_inventory.files,
            *binding.adapter_inventory.files,
            binding.adapter_config,
        ):
            path = artifact.path.casefold()
            previous = expected.get(path)
            if previous is not None and previous != artifact:
                raise ValueError("bundled_specialist_inventory_conflict")
            expected[path] = artifact
    for path in pack.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(pack).as_posix()
        if relative in ROOT_METADATA:
            continue
        if relative.casefold() not in expected:
            raise ValueError("bundled_specialist_unlisted_payload_file")


def validate(pack: Path, trust: Path, state_root: Path) -> dict[str, Any]:
    original = pack
    pack = original.resolve(strict=True)
    original_is_junction = getattr(original, "is_junction", lambda: False)()
    if not pack.is_dir() or original.is_symlink() or original_is_junction:
        raise ValueError("bundled_specialist_root_invalid")
    for path in pack.rglob("*"):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError("bundled_specialist_link_forbidden")
        if path.is_file() and path.suffix.casefold() in {".key", ".pem", ".pfx", ".pvk"}:
            raise ValueError("bundled_specialist_private_key_forbidden")
    unknown_root_files = {
        path.name for path in pack.iterdir() if path.is_file() and path.name not in ROOT_METADATA
    }
    if unknown_root_files:
        raise ValueError("bundled_specialist_unlisted_root_file")
    unknown_root_directories = {
        path.name
        for path in pack.iterdir()
        if path.is_dir() and path.name not in ROOT_DIRECTORIES
    }
    if unknown_root_directories:
        raise ValueError("bundled_specialist_unlisted_root_directory")

    authority = AdmissionAuthority(
        trust_path=trust.resolve(strict=True),
        state_root=state_root.resolve(),
        allow_test_keys=False,
        record_high_water=False,
    )
    registry = HotSwapRegistry.load(
        root=pack,
        release_registry=pack / "releases.json",
        artifact_registry=pack / "artifacts.json",
        admission_catalog=pack / "admission.json",
        admission_authority=authority,
    )
    if {release.capability for release in registry.releases.values()} != CAPABILITIES:
        raise ValueError("bundled_specialist_capability_set_invalid")
    if len(registry.releases) != len(CAPABILITIES):
        raise ValueError("bundled_specialist_release_count_invalid")
    validate_inventory_coverage(pack, registry)

    releases = []
    for release in registry.releases.values():
        if release.admission != "admitted_for_production":
            raise ValueError("bundled_specialist_production_release_required")
        selected = registry.select(release.model_id, allow_test_only=False)
        grant = registry.admission(selected)
        if (
            grant.scope != "production"
            or grant.evaluation.dataset_kind != "attorney_reviewed"
            or not grant.licenses.redistribution_permitted
            or grant.compatibility.quantization != "fp32"
            or grant.compatibility.max_resident_bytes > MAX_RESIDENT_BYTES
            or grant.compatibility.max_new_tokens > 256
        ):
            raise ValueError("bundled_specialist_release_policy_invalid")
        try:
            for package in ("torch", "transformers", "peft", "safetensors"):
                if version(package) != getattr(grant.compatibility, f"{package}_version"):
                    raise ValueError("bundled_specialist_runtime_version_mismatch")
        except PackageNotFoundError as exc:
            raise ValueError("bundled_specialist_runtime_missing") from exc
        registry.bindings[release.release_id].verify(pack)
        releases.append(
            {
                "model_id": release.model_id,
                "release_id": release.release_id,
                "capability": release.capability,
                "release_fingerprint": release.release_fingerprint,
                "evaluation_report_sha256": grant.evaluation.report_sha256,
                "attorney_review_sample_count": grant.evaluation.sample_count,
                "max_resident_bytes": grant.compatibility.max_resident_bytes,
                "quantization": grant.compatibility.quantization,
            }
        )
    tree_sha256, file_count, total_bytes = tree_identity(pack)
    return {
        "schema_version": "bundled_mfl_specialist_validation_v1",
        "validated_at": datetime.now(UTC).isoformat(),
        "status": "pass",
        "capabilities": sorted(CAPABILITIES),
        "releases": sorted(releases, key=lambda item: item["capability"]),
        "tree_sha256": tree_sha256,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "production_signed_admission": True,
        "attorney_reviewed_evaluation": True,
        "redistribution_permitted": True,
        "runtime_versions_matched": True,
        "cpu_fallback_runtime_compatible": True,
        "cpu_fallback_qualified": False,
        "qualification_scope": "signed_metadata_and_artifact_integrity_not_measured_inference",
        "review_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--trust", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.pack, args.trust, args.state_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "tree_sha256": result["tree_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
