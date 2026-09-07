"""Assemble one shared-base research pack for Evidence Review and Drafting.

The result is intentionally unadmitted.  It is suitable for bounded local QA
and for later independent signing; this script cannot create production model
admission or duplicate the Qwen base per adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-run", type=Path, required=True)
    parser.add_argument("--evidence-checkpoint", type=Path, required=True)
    parser.add_argument("--drafting-run", type=Path, required=True)
    parser.add_argument("--drafting-checkpoint", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(args), sort_keys=True))
    return 0


def package(args: argparse.Namespace) -> dict:
    if args.output.exists():
        raise ValueError("paired pack is immutable; choose a new output")
    scripts = args.model_project / "scripts"
    sys.path.insert(0, str(scripts))
    from assemble_mfl_fast_interchange_protocol_pack import (
        BASE_FILES,
        PROMPT_TEMPLATE,
        TOKENIZER_FILES,
        artifact,
        canonical,
        copy_required,
        digest,
        inventory,
        sha256_file,
    )
    from package_mfl_research import inspect_adapter

    def candidate(run: Path, checkpoint: Path, expected_specialist: str) -> dict:
        identity = json.loads((run / "run-identity.json").read_text(encoding="utf-8"))
        record = json.loads((checkpoint / "checkpoint.json").read_text(encoding="utf-8"))
        completed = json.loads((run / "training-run.json").read_text(encoding="utf-8"))
        authorization = identity["admission"]["authorization"]
        if (
            record["identity"] != identity
            or record["adapter_sha256"] != sha256_file(checkpoint / "adapter_model.safetensors")
            or record["research_only"] is not True
            or record["production_admitted"] is not False
            or identity["admission"]["scope"] != "local_research_only"
            or authorization["specialist_id"] != expected_specialist
            or identity["admission"]["base_weights_sha256"]
            != sha256_file(args.base / "model.safetensors")
            or identity["base_config_sha256"] != sha256_file(args.base / "config.json")
            or checkpoint.name != "final"
            or completed["status"] != "completed-local-research-only"
            or completed["identity"] != identity
            or completed["adapter_sha256"] != record["adapter_sha256"]
            or completed["examples_seen"] != completed["train_examples"] * completed["epochs"]
        ):
            raise ValueError(f"incomplete or mismatched candidate: {expected_specialist}")
        return {
            "run": run,
            "checkpoint": checkpoint,
            "identity": identity,
            "record": record,
            "completed": completed,
            "tensor_proof": inspect_adapter(
                checkpoint / "adapter_model.safetensors", identity["rank"]
            ),
        }

    candidates = {
        "evidence_review": candidate(
            args.evidence_run, args.evidence_checkpoint, "mfl-evidence-review"
        ),
        "drafting": candidate(args.drafting_run, args.drafting_checkpoint, "mfl-drafting"),
    }
    staging = args.output.with_name(args.output.name + ".staging")
    if staging.exists():
        raise ValueError("paired pack staging path already exists")
    staging.mkdir(parents=True)
    for name in (*BASE_FILES, *TOKENIZER_FILES):
        copy_required(args.base / name, staging / "base" / name)
    copy_required(args.base / "LICENSE", staging / "BASE-LICENSE.txt")
    copy_required(args.base / "README.md", staging / "BASE-MODEL-CARD.md")

    base_inventory = inventory(artifact(staging, staging / "base" / name) for name in BASE_FILES)
    tokenizer_inventory = inventory(
        artifact(staging, staging / "base" / name) for name in TOKENIZER_FILES
    )
    releases, bindings, adapter_summaries = [], [], {}
    for capability, item in candidates.items():
        adapter_dir = staging / "adapters" / capability
        checkpoint = item["checkpoint"]
        copy_required(
            checkpoint / "adapter_model.safetensors", adapter_dir / "adapter_model.safetensors"
        )
        config = json.loads((checkpoint / "adapter_config.json").read_text(encoding="utf-8"))
        config["base_model_name_or_path"] = "Qwen/Qwen3-0.6B"
        (adapter_dir / "adapter_config.json").write_bytes(canonical(config) + b"\n")
        adapter_inventory = inventory(
            [artifact(staging, adapter_dir / "adapter_model.safetensors")]
        )
        adapter_config = artifact(staging, adapter_dir / "adapter_config.json")
        release_id = f"mfl-{capability.replace('_', '-')}-v9-research"
        release_binding = {
            "adapter_config_sha256": adapter_config["sha256"],
            "adapter_inventory_sha256": digest(adapter_inventory),
            "base_inventory_sha256": digest(base_inventory),
            "capability": capability,
            "prompt_template_sha256": hashlib.sha256(PROMPT_TEMPLATE).hexdigest(),
            "release_id": release_id,
            "runtime_abi": "fast_interchange_hotswap_v1",
            "tokenizer_inventory_sha256": digest(tokenizer_inventory),
        }
        fingerprint = digest(release_binding)
        releases.append(
            {
                **release_binding,
                "model_id": release_id,
                "admission": "unadmitted_local_research",
                "release_fingerprint": fingerprint,
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
        adapter_summaries[capability] = {
            "release_id": release_id,
            "release_fingerprint": fingerprint,
            "adapter_sha256": item["record"]["adapter_sha256"],
            "adapter_bytes": (adapter_dir / "adapter_model.safetensors").stat().st_size,
            "examples_seen": item["record"]["examples_seen"],
            "optimizer_steps": item["record"]["step"],
            "tensor_proof": item["tensor_proof"],
            "source_checkpoint_sha256": sha256_file(checkpoint / "checkpoint.json"),
            "research_authorization": item["identity"]["admission"],
        }

    release_document = {"schema": "fast_interchange_releases_v1", "releases": releases}
    artifact_document = {"schema": "fast_interchange_artifacts_v1", "bindings": bindings}
    manifest = {
        "schema": "mfl.fast-interchange-paired-research-pack.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "fictional_source_bound_research_only_not_substantive_legal_knowledge",
        "capabilities": sorted(candidates),
        "run_complete": True,
        "shared_base_copies": 1,
        "base_model": "Qwen/Qwen3-0.6B",
        "base_license": "Apache-2.0",
        "base_bytes": (args.base / "model.safetensors").stat().st_size,
        "adapters": adapter_summaries,
        "contains_northstar_assets": False,
        "contains_client_data": False,
        "contains_legal_authority_corpus": False,
        "production_admitted": False,
        "attorney_reviewed": False,
        "rc_complete": False,
        "promotion_authority": False,
        "child_impact_lens_default": True,
        "release_registry_sha256": digest(release_document),
        "artifact_registry_sha256": digest(artifact_document),
        "product_admission": "not supplied; independent signed admission remains mandatory",
        "limitations": [
            "Synthetic training and mechanical evaluation are not attorney-reviewed "
            "legal expertise.",
            "No real client matter use, filing readiness, RC, GA, or Store claim is "
            "granted by this pack.",
        ],
    }
    for name, value in (
        ("releases.json", release_document),
        ("artifacts.json", artifact_document),
        ("pack-manifest.json", manifest),
    ):
        (staging / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    staging.replace(args.output)
    return manifest


if __name__ == "__main__":
    raise SystemExit(main())
