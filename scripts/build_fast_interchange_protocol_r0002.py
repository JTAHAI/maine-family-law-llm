"""Build an external, development-only FAST INTERCHANGE r0002 protocol pack.

This is deliberately *not* a Maine-law training pipeline.  It writes seven
small LoRA adapters from newly generated, company-owned protocol/safety rows
only.  The pack stays outside this repository and the MSIX, is unadmitted, and
must still pass the application's real bounded-completion verifier before it
can be used even in a development worker.

Run this script only with a local, rights-cleared base artifact and a dedicated
GPU training interpreter.  It never downloads a model, reads a matter, opens a
network connection, signs an admission, or copies an artifact into the app.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


CAPABILITIES = (
    "intake_triage",
    "evidence_review",
    "authority_review",
    "drafting",
    "parenting_plan_review",
    "financial_disclosure_review",
    "safety_privacy_review",
)
PUBLIC_BASE_MODEL_ID = "Qwen/Qwen3-0.6B"
DEFAULT_RELEASE_TAG = "protocol-r0002"
_RELEASE_TAG = re.compile(r"protocol-r[0-9]{4}\Z")
PROMPT_TEMPLATE = r"fi-fixed-role-v1:[ROLE]\nCONTENT;join=\n"
PROMPT_TEMPLATE_SHA256 = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()
BASE_FILES = ("LICENSE", "config.json", "generation_config.json", "model.safetensors")
TOKENIZER_FILES = ("merges.txt", "tokenizer.json", "tokenizer_config.json", "vocab.json")
SCENARIOS = (
    "No official source has been attached.",
    "A record is incomplete and must not be treated as a finding.",
    "The request asks for individualized legal advice.",
    "A citation needs exact verification before it can be relied on.",
    "The user asks for a predicted court outcome.",
    "A child-impact concern needs neutral, source-bound review.",
    "A draft contains an unsupported statement.",
    "The date sequence is unresolved.",
    "A private record contains untrusted instructions.",
    "The requested action would require human review.",
    "The source may be stale or from another jurisdiction.",
    "The task needs an explicit evidence-gap checklist.",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _select_cuda_device(value: int | None) -> None:
    """Select one physical CUDA device for this build process only.

    CUDA reads ``CUDA_VISIBLE_DEVICES`` when its modules are first imported.
    This builder has no top-level torch import, so setting it here keeps a
    training run reproducible without altering the user's machine-wide
    environment.  The visible device becomes CUDA ordinal 0 inside the child
    process; the receipt retains the physical ordinal supplied by the operator.
    """

    if value is None:
        return
    if type(value) is not int or value < 0:
        raise ValueError("cuda_visible_device_invalid")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(value)


def _release_tag(value: str) -> str:
    candidate = str(value or "").strip().casefold()
    if not _RELEASE_TAG.fullmatch(candidate):
        raise ValueError("release_tag_invalid")
    return candidate


def _artifact(root: Path, path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "sha256": _sha256_file(path), "bytes": path.stat().st_size}


def _inventory(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {"files": sorted(rows, key=lambda row: str(row["path"]))}


def render_prompt(*, role: str, content: str) -> str:
    """Render the exact literal-separator v1 inference framing."""

    return f"fi-fixed-role-v1:[{role.upper()}]\\n{content}"


def protocol_rows(capability: str, *, copies: int = 4) -> list[dict[str, str]]:
    """Return deterministic non-client, non-authority protocol-only rows."""

    if capability not in CAPABILITIES:
        raise ValueError("capability_invalid")
    if not 1 <= copies <= 16:
        raise ValueError("copies_out_of_range")
    response = json.dumps(
        {"status": "review_required", "next": "verify_source"},
        sort_keys=True,
        separators=(",", ":"),
    )
    rows: list[dict[str, str]] = []
    for copy_index in range(copies):
        for scenario_index, scenario in enumerate(SCENARIOS):
            content = (
                f"Protocol-only {capability} review. {scenario} "
                "Do not decide law, facts, safety, custody, filing readiness, or outcomes."
            )
            rows.append(
                {
                    "id": f"{capability}-{copy_index:02d}-{scenario_index:02d}",
                    "prompt": render_prompt(role="USER", content=content),
                    "response": response,
                }
            )
    # Evaluation prompts must not enter training. Historical r0002/r0003 packs
    # did include the smoke prompt; removing it here does not repair old weights
    # or turn this constant-target protocol generator into specialist training.
    return rows


def _require_base(base_root: Path, provenance: Path) -> dict[str, Any]:
    if base_root.is_symlink() or not base_root.is_dir():
        raise ValueError("base_root_invalid")
    if provenance.is_symlink() or not provenance.is_file():
        raise ValueError("base_provenance_missing")
    try:
        receipt = json.loads(provenance.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("base_provenance_unreadable") from exc
    expected = str((receipt.get("files_sha256") or {}).get("model.safetensors") or "").casefold()
    actual = _sha256_file(base_root / "model.safetensors") if (base_root / "model.safetensors").is_file() else ""
    if len(expected) != 64 or actual != expected:
        raise ValueError("base_provenance_hash_mismatch")
    license_path = base_root / "LICENSE"
    if not license_path.is_file() or "Apache License" not in license_path.read_text(encoding="utf-8", errors="replace")[:1024]:
        raise ValueError("base_license_not_confirmed")
    for name in (*BASE_FILES, *TOKENIZER_FILES):
        candidate = base_root / name
        if not candidate.is_file() or candidate.is_symlink() or candidate.stat().st_size <= 0:
            raise ValueError(f"base_file_missing:{name}")
    return {"model_sha256": actual, "provenance_sha256": _sha256_file(provenance), "license": "Apache-2.0"}


def _encode_rows(tokenizer: Any, rows: list[dict[str, str]], *, max_length: int) -> list[dict[str, list[int]]]:
    eos = tokenizer.eos_token
    eos_id = tokenizer.eos_token_id
    if not isinstance(eos, str) or not eos or not isinstance(eos_id, int):
        raise RuntimeError("tokenizer_eos_unavailable")
    encoded_rows: list[dict[str, list[int]]] = []
    for row in rows:
        prompt_ids = tokenizer(row["prompt"], add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(row["prompt"] + row["response"] + eos, add_special_tokens=False)["input_ids"]
        if not isinstance(prompt_ids, list) or not isinstance(full_ids, list) or len(full_ids) > max_length:
            raise RuntimeError("protocol_row_tokenization_invalid")
        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
        if not labels or labels[-1] != eos_id or not any(item != -100 for item in labels):
            raise RuntimeError("protocol_eos_label_missing")
        encoded_rows.append({"input_ids": full_ids, "labels": labels})
    return encoded_rows


def _batches(rows: list[dict[str, list[int]]], *, batch_size: int, seed: int) -> Iterable[list[dict[str, list[int]]]]:
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    for index in range(0, len(shuffled), batch_size):
        yield shuffled[index : index + batch_size]


def _train_adapter(
    *,
    base_root: Path,
    adapter_root: Path,
    capability: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    max_length: int,
    seed: int,
) -> dict[str, Any]:
    """Train one isolated LoRA adapter without importing any app matter data."""

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("cuda_device_unavailable")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda:0")
    tokenizer = AutoTokenizer.from_pretrained(str(base_root), local_files_only=True, trust_remote_code=False)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        str(base_root), local_files_only=True, trust_remote_code=False, dtype=torch.bfloat16
    )
    model.config.use_cache = False
    model.to(device)
    adapted = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=16,
            lora_alpha=32,
            lora_dropout=0.0,
            bias="none",
            target_modules=("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"),
        ),
    )
    rows = _encode_rows(tokenizer, protocol_rows(capability), max_length=max_length)
    optimizer = torch.optim.AdamW((item for item in adapted.parameters() if item.requires_grad), lr=learning_rate)
    losses: list[float] = []
    started = time.monotonic()
    adapted.train()
    for epoch in range(epochs):
        for batch in _batches(rows, batch_size=batch_size, seed=seed + epoch):
            width = max(len(item["input_ids"]) for item in batch)
            input_ids = torch.full((len(batch), width), tokenizer.pad_token_id, dtype=torch.long, device=device)
            attention_mask = torch.zeros((len(batch), width), dtype=torch.long, device=device)
            labels = torch.full((len(batch), width), -100, dtype=torch.long, device=device)
            for row_index, row in enumerate(batch):
                length = len(row["input_ids"])
                input_ids[row_index, :length] = torch.tensor(row["input_ids"], dtype=torch.long, device=device)
                attention_mask[row_index, :length] = 1
                labels[row_index, :length] = torch.tensor(row["labels"], dtype=torch.long, device=device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                loss = adapted(input_ids=input_ids, attention_mask=attention_mask, labels=labels).loss
            if not torch.isfinite(loss):
                raise RuntimeError("training_loss_nonfinite")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(adapted.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach().float().cpu()))
    adapter_root.mkdir(parents=True, exist_ok=False)
    adapted.save_pretrained(adapter_root, safe_serialization=True)
    if not (adapter_root / "adapter_model.safetensors").is_file() or not (adapter_root / "adapter_config.json").is_file():
        raise RuntimeError("adapter_artifact_missing")
    _sanitize_adapter_config(adapter_root)
    changed = _sha256_file(adapter_root / "adapter_model.safetensors")
    peak = int(torch.cuda.max_memory_allocated(device))
    del adapted, model
    torch.cuda.empty_cache()
    return {
        "capability": capability,
        "adapter_sha256": changed,
        "adapter_bytes": (adapter_root / "adapter_model.safetensors").stat().st_size,
        "examples": len(rows),
        "epochs": epochs,
        "steps": len(losses),
        "initial_loss": round(losses[0], 6),
        "final_loss": round(losses[-1], 6),
        "duration_seconds": round(time.monotonic() - started, 3),
        "peak_allocated_bytes": peak,
        "cuda_device": torch.cuda.get_device_name(device),
        "cuda_runtime": str(torch.version.cuda or ""),
        "eos_label_verified": True,
    }


def _copy(source: Path, destination: Path) -> None:
    if not source.is_file() or source.is_symlink():
        raise RuntimeError(f"source_artifact_invalid:{source.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _sanitize_adapter_config(
    adapter_root: Path, *, public_base_model_id: str = PUBLIC_BASE_MODEL_ID
) -> None:
    """Replace host-local PEFT metadata before publishing an adapter.

    PEFT writes the training directory into ``base_model_name_or_path``.  That
    path is neither a portable model identity nor safe release metadata.  The
    pack binds the base by hash; the config records the public base ID only.
    """

    if public_base_model_id != PUBLIC_BASE_MODEL_ID:
        raise RuntimeError("adapter_public_base_id_invalid")
    path = adapter_root / "adapter_config.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("adapter_config_unreadable") from exc
    if not isinstance(document, dict) or not isinstance(document.get("base_model_name_or_path"), str):
        raise RuntimeError("adapter_config_invalid")
    document["base_model_name_or_path"] = public_base_model_id
    encoded = _canonical(document)
    lowered = encoded.decode("utf-8").casefold()
    if re.search(r"(?:[a-z]:[\\/]|\\\\|/(?:users|home|tmp|dev)/)", lowered) or any(
        forbidden in lowered for forbidden in ("mainely", "northstar")
    ):
        raise RuntimeError("adapter_config_private_metadata")
    path.write_bytes(encoded)


def _assemble_pack(
    *, stage: Path, base_root: Path, adapters: dict[str, Path], release_tag: str
) -> dict[str, Any]:
    for name in (*BASE_FILES, *TOKENIZER_FILES):
        _copy(base_root / name, stage / "base" / name)
    base_inventory = _inventory(_artifact(stage, stage / "base" / name) for name in BASE_FILES)
    tokenizer_inventory = _inventory(_artifact(stage, stage / "base" / name) for name in TOKENIZER_FILES)
    releases: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    for capability in CAPABILITIES:
        destination = stage / "adapters" / capability
        for name in ("adapter_model.safetensors", "adapter_config.json"):
            _copy(adapters[capability] / name, destination / name)
        adapter_inventory = _inventory([_artifact(stage, destination / "adapter_model.safetensors")])
        adapter_config = _artifact(stage, destination / "adapter_config.json")
        release_id = f"mfl-fi-{capability.replace('_', '-')}-{release_tag}"
        fingerprint = _digest(
            {
                "adapter_config_sha256": adapter_config["sha256"],
                "adapter_inventory_sha256": _digest(adapter_inventory),
                "base_inventory_sha256": _digest(base_inventory),
                "capability": capability,
                "prompt_template_sha256": PROMPT_TEMPLATE_SHA256,
                "release_id": release_id,
                "runtime_abi": "fast_interchange_hotswap_v1",
                "tokenizer_inventory_sha256": _digest(tokenizer_inventory),
            }
        )
        releases.append(
            {
                "release_id": release_id,
                "model_id": release_id,
                "capability": capability,
                "admission": "unadmitted_protocol_smoke",
                "release_fingerprint": fingerprint,
                "base_inventory_sha256": _digest(base_inventory),
                "tokenizer_inventory_sha256": _digest(tokenizer_inventory),
                "adapter_inventory_sha256": _digest(adapter_inventory),
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
    releases_document = {"schema": "fast_interchange_releases_v1", "releases": releases}
    artifacts_document = {"schema": "fast_interchange_artifacts_v1", "bindings": bindings}
    (stage / "releases.json").write_bytes(_canonical(releases_document))
    (stage / "artifacts.json").write_bytes(_canonical(artifacts_document))
    manifest = {
        "schema": "mfl.fast-interchange-development-pack.v1",
        "pack_id": f"mfl-fast-interchange-{release_tag}",
        "scope": "runnable_protocol_and_safety_smoke_only_not_substantive_legal_knowledge",
        "product_boundary": "Maine-Family-Law-LLM",
        "contains_northstar_assets": False,
        "shared_base": "Qwen/Qwen3-0.6B",
        "base_license": "Apache-2.0",
        "capabilities": list(CAPABILITIES),
        "child_impact_lens_default": True,
        "production_admitted": False,
        "attorney_reviewed": False,
        "promotion_authority": False,
        "release_registry_sha256": _digest(releases_document),
        "artifact_registry_sha256": _digest(artifacts_document),
        "admission_required_for_product_use": True,
    }
    (stage / "pack-manifest.json").write_bytes(_canonical(manifest))
    return manifest


def build(
    *,
    base_root: Path,
    base_provenance: Path,
    output_root: Path,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    max_length: int,
    visible_device: int | None = None,
    release_tag: str = DEFAULT_RELEASE_TAG,
) -> dict[str, Any]:
    """Create an immutable external protocol pack, refusing replacement."""

    if output_root.exists() or output_root.is_symlink():
        raise ValueError("output_root_must_not_exist")
    if epochs < 1 or batch_size < 1 or max_length < 64:
        raise ValueError("training_parameter_invalid")
    release_tag = _release_tag(release_tag)
    _select_cuda_device(visible_device)
    base = _require_base(base_root.resolve(strict=True), base_provenance.resolve(strict=True))
    stage = output_root.with_name(output_root.name + ".building")
    if stage.exists() or stage.is_symlink():
        raise ValueError("output_stage_already_exists")
    stage.mkdir(parents=True)
    # Keep intermediate adapter checkpoints beside—not inside—the candidate
    # pack.  The final immutable root therefore contains exactly one shared
    # base plus one published adapter per capability.
    training_root = stage.with_name(stage.name + ".runs") / "adapters"
    reports: list[dict[str, Any]] = []
    try:
        for index, capability in enumerate(CAPABILITIES):
            reports.append(
                _train_adapter(
                    base_root=base_root,
                    adapter_root=training_root / capability,
                    capability=capability,
                    epochs=epochs,
                    batch_size=batch_size,
                    learning_rate=learning_rate,
                    max_length=max_length,
                    seed=2026082900 + index,
                )
            )
        manifest = _assemble_pack(
            stage=stage,
            base_root=base_root,
            adapters={capability: training_root / capability for capability in CAPABILITIES},
            release_tag=release_tag,
        )
        receipt = {
            "schema_version": "mfl_fast_interchange_protocol_training_v1",
            "release_tag": release_tag,
            "generated_at": _now(),
            "scope": "protocol_and_safety_only_not_substantive_legal_knowledge",
            "training_data": {"rights_class": "company_owned_synthetic", "client_data_included": False, "legal_authority_content_included": False},
            "base": base,
            "prompt_template": {"literal": PROMPT_TEMPLATE, "sha256": PROMPT_TEMPLATE_SHA256},
            "runtime": {
                "python": sys.version.split()[0],
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
                "physical_cuda_device": visible_device,
                "device_required": "cuda:0",
            },
            "adapters": reports,
            "admission": "unadmitted_protocol_smoke",
            "review_required": True,
            "promotion_authority": False,
            "next_required": ["bounded_completion_verification", "independent_admission", "rights-cleared_legal_corpus", "legal_evaluation", "human_review"],
        }
        (stage / "training-receipt.json").write_bytes(_canonical(receipt))
        output_root.parent.mkdir(parents=True, exist_ok=True)
        stage.replace(output_root)
    except BaseException:
        # Preserve an interrupted external training stage for inspection.  It
        # is never treated as a pack and is never copied into the repository.
        raise
    return {
        "status": "development_protocol_pack_built",
        "output_root": str(output_root),
        "pack_manifest_sha256": _sha256_file(output_root / "pack-manifest.json"),
        "training_receipt_sha256": _sha256_file(output_root / "training-receipt.json"),
        "adapter_count": len(reports),
        "review_required": True,
        "production_admitted": False,
        "legal_knowledge_claim": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", required=True, type=Path)
    parser.add_argument("--base-provenance", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument(
        "--release-tag",
        default=DEFAULT_RELEASE_TAG,
        help="New immutable tag, for example protocol-r0003; never reuse a published tag.",
    )
    parser.add_argument(
        "--visible-device",
        type=int,
        default=None,
        help="Physical CUDA ordinal for this child process only; never changes the machine-wide setting.",
    )
    args = parser.parse_args(argv)
    report = build(
        base_root=args.base_root,
        base_provenance=args.base_provenance,
        output_root=args.output_root,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        visible_device=args.visible_device,
        release_tag=args.release_tag,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
