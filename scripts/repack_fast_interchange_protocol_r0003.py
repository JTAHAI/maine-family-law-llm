"""Create a clean external protocol-r0003 pack from inspected r0002 tensors.

This remediation never touches the application package.  It copies only seven
verified LoRA Safetensors tensors from an external protocol-only r0002 pack,
binds them to the separately acquired public Qwen base, rewrites PEFT adapter
metadata to a public base ID, and writes a derivation receipt.  It does not
train, upgrade legal knowledge, sign admission, or enable product use.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import struct
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_fast_interchange_protocol_r0002.py"
SOURCE_PACK_ID = "mfl-fast-interchange-protocol-r0002"
RELEASE_TAG = "protocol-r0003"
FORBIDDEN_HEADER_MARKERS = ("d:\\", "mc_models", "mainely", "northstar")


def _builder():
    specification = importlib.util.spec_from_file_location("mfl_protocol_builder", BUILDER_PATH)
    if specification is None or specification.loader is None:  # pragma: no cover - installed source corruption
        raise RuntimeError("protocol_builder_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("source_metadata_unreadable") from exc
    if not isinstance(value, dict):
        raise ValueError("source_metadata_invalid")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _outside_repository(path: Path) -> Path:
    candidate = path.resolve(strict=False)
    if candidate == ROOT or ROOT in candidate.parents:
        raise ValueError("repack_output_must_be_outside_repository")
    return candidate


def _tensor_header_is_clean(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        with path.open("rb") as handle:
            length = struct.unpack("<Q", handle.read(8))[0]
            if not 2 <= length <= 2 * 1024**2:
                return False
            header = handle.read(length).decode("utf-8")
    except (OSError, UnicodeDecodeError, struct.error):
        return False
    lowered = header.casefold()
    return not any(marker in lowered for marker in FORBIDDEN_HEADER_MARKERS)


def _source_adapter_hashes(source_root: Path, builder: Any) -> dict[str, str]:
    manifest = _read_json(source_root / "pack-manifest.json")
    receipt = _read_json(source_root / "training-receipt.json")
    releases = _read_json(source_root / "releases.json")
    artifacts = _read_json(source_root / "artifacts.json")
    if (
        manifest.get("pack_id") != SOURCE_PACK_ID
        or manifest.get("scope") != "runnable_protocol_and_safety_smoke_only_not_substantive_legal_knowledge"
        or receipt.get("admission") != "unadmitted_protocol_smoke"
        or receipt.get("training_data", {}).get("client_data_included") is not False
        or receipt.get("training_data", {}).get("legal_authority_content_included") is not False
        or manifest.get("release_registry_sha256") != builder._digest(releases)
        or manifest.get("artifact_registry_sha256") != builder._digest(artifacts)
    ):
        raise ValueError("source_pack_boundary_invalid")
    rows = releases.get("releases")
    bindings = artifacts.get("bindings")
    if not isinstance(rows, list) or not isinstance(bindings, list) or len(rows) != len(builder.CAPABILITIES):
        raise ValueError("source_pack_slots_invalid")
    by_capability = {str(row.get("capability")): row for row in rows if isinstance(row, dict)}
    by_release = {str(row.get("release_id")): row for row in bindings if isinstance(row, dict)}
    if set(by_capability) != set(builder.CAPABILITIES):
        raise ValueError("source_pack_capabilities_invalid")
    hashes: dict[str, str] = {}
    for capability in builder.CAPABILITIES:
        release = by_capability[capability]
        binding = by_release.get(str(release.get("release_id")))
        if not binding:
            raise ValueError("source_pack_binding_missing")
        path = source_root / "adapters" / capability / "adapter_model.safetensors"
        if not _tensor_header_is_clean(path):
            raise ValueError("source_tensor_metadata_unsafe")
        digest = _sha256(path)
        files = ((binding.get("adapter_inventory") or {}).get("files") or [])
        expected = next((row for row in files if row.get("path") == f"adapters/{capability}/adapter_model.safetensors"), None)
        if not isinstance(expected, dict) or expected.get("sha256") != digest or expected.get("bytes") != path.stat().st_size:
            raise ValueError("source_tensor_hash_mismatch")
        hashes[capability] = digest
    return hashes


def repack(*, source_root: Path, public_base_root: Path, output_root: Path) -> dict[str, Any]:
    """Build a distinct clean r0003 external pack; never overwrite a candidate."""

    builder = _builder()
    source_root = source_root.resolve(strict=True)
    public_base_root = public_base_root.resolve(strict=True)
    output_root = _outside_repository(output_root)
    if source_root.is_symlink() or public_base_root.is_symlink() or output_root.exists() or output_root.is_symlink():
        raise ValueError("repack_root_invalid")
    provenance = public_base_root / "base-provenance.json"
    base = builder._require_base(public_base_root, provenance)
    source_hashes = _source_adapter_hashes(source_root, builder)
    stage = output_root.with_name(output_root.name + ".building")
    if stage.exists() or stage.is_symlink():
        raise ValueError("repack_stage_exists")
    adapter_stage = stage.with_name(stage.name + ".adapters")
    stage.mkdir(parents=True)
    try:
        adapters: dict[str, Path] = {}
        for capability in builder.CAPABILITIES:
            destination = adapter_stage / capability
            destination.mkdir(parents=True, exist_ok=False)
            builder._copy(
                source_root / "adapters" / capability / "adapter_model.safetensors",
                destination / "adapter_model.safetensors",
            )
            builder._copy(
                source_root / "adapters" / capability / "adapter_config.json",
                destination / "adapter_config.json",
            )
            builder._sanitize_adapter_config(destination)
            adapters[capability] = destination
        manifest = builder._assemble_pack(
            stage=stage,
            base_root=public_base_root,
            adapters=adapters,
            release_tag=RELEASE_TAG,
        )
        receipt = {
            "schema_version": "mfl_fast_interchange_protocol_repack_v1",
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "release_tag": RELEASE_TAG,
            "source_pack_id": SOURCE_PACK_ID,
            "source_pack_manifest_sha256": _sha256(source_root / "pack-manifest.json"),
            "source_training_receipt_sha256": _sha256(source_root / "training-receipt.json"),
            "source_adapter_sha256": source_hashes,
            "base": base,
            "rebuild_reason": "remove_host_local_peft_metadata_and_rebind_to_public_hash_inventory",
            "training_performed_by_this_operation": False,
            "scope": "protocol_and_safety_only_not_substantive_legal_knowledge",
            "review_required": True,
            "admission": "unadmitted_protocol_smoke",
            "production_admitted": False,
            "next_required": [
                "application_backend_completion_verification",
                "independent_admission",
                "rights_cleared_legal_corpus",
                "legal_evaluation",
                "human_review",
            ],
        }
        (stage / "repack-receipt.json").write_bytes(builder._canonical(receipt))
        output_root.parent.mkdir(parents=True, exist_ok=True)
        stage.replace(output_root)
    except BaseException:
        raise
    return {
        "status": "clean_protocol_pack_repacked",
        "pack_id": manifest["pack_id"],
        "output_root": str(output_root),
        "adapter_count": len(source_hashes),
        "repack_receipt_sha256": _sha256(output_root / "repack-receipt.json"),
        "review_required": True,
        "production_admitted": False,
        "legal_knowledge_claim": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--public-base-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            repack(
                source_root=args.source_root,
                public_base_root=args.public_base_root,
                output_root=args.output_root,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI dispatch
    raise SystemExit(main())
