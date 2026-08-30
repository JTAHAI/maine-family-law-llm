"""Train seven synthetic source-bound workflow adapters in repository ``dist``.

This development-only builder uses a separately supplied, read-only Apache-2.0
base and company-owned fictional rows.  It does not download, publish, admit,
or package a model, and does not train from legal authority or private matter
data.  A candidate from this script is not a Maine-law model and cannot be
activated by the production worker without independent signed admission.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import socket
import sys
import time
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.build_fast_interchange_protocol_r0002 import (
    CAPABILITIES,
    PROMPT_TEMPLATE,
    PROMPT_TEMPLATE_SHA256,
    _canonical,
    _require_base,
    _sanitize_adapter_config,
    _select_cuda_device,
    _sha256_file,
    render_prompt,
)
from scripts.fast_interchange_workflow_training_data import (
    DATASET_CLASS,
    DATASET_SCOPE,
    dataset_digest,
    workflow_training_rows,
)

ROOT = Path(__file__).resolve().parents[1]
DIST_ROOT = (ROOT / "dist").resolve()
CANDIDATE_PARENT = (DIST_ROOT / "model-candidates").resolve()
RELEASE_TAG = "workflow-r0004"


class OfflineTrainingError(RuntimeError):
    """Raised if a local-only training child attempts a network connection."""


class _NetworkDenied:
    def __enter__(self):
        self._originals = {
            "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex,
            "create_connection": socket.create_connection,
        }

        def denied(*_args, **_kwargs):
            raise OfflineTrainingError("fast_interchange_training_network_forbidden")

        socket.socket.connect = denied
        socket.socket.connect_ex = denied
        socket.create_connection = denied
        return self

    def __exit__(self, *_exc):
        socket.socket.connect = self._originals["connect"]
        socket.socket.connect_ex = self._originals["connect_ex"]
        socket.create_connection = self._originals["create_connection"]


def _assert_candidate_root(path: Path) -> Path:
    resolved = path.resolve()
    if (
        not resolved.is_relative_to(CANDIDATE_PARENT)
        or resolved == CANDIDATE_PARENT
        or path.is_symlink()
        or resolved.exists()
    ):
        raise ValueError("candidate_output_must_be_new_child_of_repository_dist")
    return resolved


def _encode_rows(tokenizer: Any, rows: list[Any], *, max_length: int) -> list[dict[str, list[int]]]:
    eos, eos_id = tokenizer.eos_token, tokenizer.eos_token_id
    if not isinstance(eos, str) or not eos or not isinstance(eos_id, int):
        raise RuntimeError("workflow_training_tokenizer_eos_unavailable")
    encoded: list[dict[str, list[int]]] = []
    for row in rows:
        prompt = render_prompt(role="USER", content=row.prompt)
        prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        full_ids = tokenizer(prompt + row.response + eos, add_special_tokens=False)["input_ids"]
        if (
            not isinstance(prompt_ids, list)
            or not isinstance(full_ids, list)
            or len(full_ids) > max_length
        ):
            raise RuntimeError("workflow_training_row_tokenization_invalid")
        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
        if not labels or labels[-1] != eos_id or not any(token != -100 for token in labels):
            raise RuntimeError("workflow_training_eos_label_missing")
        encoded.append({"input_ids": full_ids, "labels": labels})
    return encoded


def _batches(
    rows: list[dict[str, list[int]]], *, batch_size: int, seed: int
) -> Iterable[list[dict[str, list[int]]]]:
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    for index in range(0, len(shuffled), batch_size):
        yield shuffled[index : index + batch_size]


def _train_adapter(
    *,
    base_root: Path,
    adapter_root: Path,
    capability: str,
    rows: list[Any],
    epochs: int,
    batch_size: int,
    learning_rate: float,
    max_length: int,
    seed: int,
) -> dict[str, Any]:
    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("workflow_training_cuda_device_unavailable")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda:0")
    tokenizer = AutoTokenizer.from_pretrained(
        str(base_root), local_files_only=True, trust_remote_code=False
    )
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
            r=32,
            lora_alpha=64,
            lora_dropout=0.0,
            bias="none",
            target_modules=(
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ),
        ),
    )
    encoded = _encode_rows(tokenizer, rows, max_length=max_length)
    optimizer = torch.optim.AdamW(
        (item for item in adapted.parameters() if item.requires_grad), lr=learning_rate
    )
    losses: list[float] = []
    started = time.monotonic()
    adapted.train()
    for epoch in range(epochs):
        for batch in _batches(encoded, batch_size=batch_size, seed=seed + epoch):
            width = max(len(item["input_ids"]) for item in batch)
            input_ids = torch.full(
                (len(batch), width), tokenizer.pad_token_id, dtype=torch.long, device=device
            )
            attention_mask = torch.zeros((len(batch), width), dtype=torch.long, device=device)
            labels = torch.full((len(batch), width), -100, dtype=torch.long, device=device)
            for row_index, row in enumerate(batch):
                length = len(row["input_ids"])
                input_ids[row_index, :length] = torch.tensor(
                    row["input_ids"], dtype=torch.long, device=device
                )
                attention_mask[row_index, :length] = 1
                labels[row_index, :length] = torch.tensor(
                    row["labels"], dtype=torch.long, device=device
                )
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                loss = adapted(
                    input_ids=input_ids, attention_mask=attention_mask, labels=labels
                ).loss
            if not torch.isfinite(loss):
                raise RuntimeError("workflow_training_loss_nonfinite")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(adapted.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach().float().cpu()))
    adapter_root.mkdir(parents=True, exist_ok=False)
    adapted.save_pretrained(adapter_root, safe_serialization=True)
    _sanitize_adapter_config(adapter_root)
    weights = adapter_root / "adapter_model.safetensors"
    if not weights.is_file() or not (adapter_root / "adapter_config.json").is_file():
        raise RuntimeError("workflow_training_adapter_artifact_missing")
    adapter_sha256 = _sha256_file(weights)
    report = {
        "capability": capability,
        "adapter_sha256": adapter_sha256,
        "adapter_bytes": weights.stat().st_size,
        "examples": len(rows),
        "epochs": epochs,
        "steps": len(losses),
        "initial_loss": round(losses[0], 6),
        "final_loss": round(losses[-1], 6),
        "duration_seconds": round(time.monotonic() - started, 3),
        "peak_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
        "cuda_device": torch.cuda.get_device_name(device),
        "cuda_runtime": str(torch.version.cuda or ""),
        "eos_label_verified": True,
    }
    del adapted, model
    torch.cuda.empty_cache()
    return report


def build(
    *,
    base_root: Path,
    base_provenance: Path,
    output_root: Path,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    max_length: int,
    visible_device: int,
) -> dict[str, Any]:
    output = _assert_candidate_root(output_root)
    if not 1 <= epochs <= 12 or not 1 <= batch_size <= 16 or not 64 <= max_length <= 1024:
        raise ValueError("workflow_training_parameter_invalid")
    base = _require_base(base_root.resolve(strict=True), base_provenance.resolve(strict=True))
    if base_root.resolve().is_relative_to(ROOT):
        raise ValueError("workflow_training_base_must_remain_external_to_repository")
    rows = workflow_training_rows()
    by_capability: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        by_capability[row.capability].append(row)
    if tuple(sorted(by_capability)) != tuple(sorted(CAPABILITIES)):
        raise RuntimeError("workflow_training_capability_partition_invalid")
    stage = output.with_name(output.name + ".building")
    if stage.exists() or stage.is_symlink():
        raise ValueError("workflow_training_stage_exists")
    stage.mkdir(parents=True, mode=0o700)
    _select_cuda_device(visible_device)
    os.environ.update(
        {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1"}
    )
    reports: list[dict[str, Any]] = []
    started = time.monotonic()
    with _NetworkDenied():
        for index, capability in enumerate(CAPABILITIES):
            reports.append(
                _train_adapter(
                    base_root=base_root,
                    adapter_root=stage / "adapters" / capability,
                    capability=capability,
                    rows=by_capability[capability],
                    epochs=epochs,
                    batch_size=batch_size,
                    learning_rate=learning_rate,
                    max_length=max_length,
                    seed=2026083000 + index,
                )
            )
    adapter_hashes = {row["adapter_sha256"] for row in reports}
    if len(adapter_hashes) != len(CAPABILITIES):
        raise RuntimeError("workflow_training_adapter_weights_not_distinct")
    dataset = {
        "class": DATASET_CLASS,
        "scope": DATASET_SCOPE,
        "rights_class": "company_owned_fictional_synthetic",
        "private_matter_data_included": False,
        "legal_authority_content_included": False,
        "attorney_reviewed": False,
        "row_count": len(rows),
        "per_capability_rows": {key: len(value) for key, value in sorted(by_capability.items())},
        "sha256": dataset_digest(rows),
        "held_out_acceptance_set_included": False,
    }
    receipt = {
        "schema_version": "mfl_fast_interchange_workflow_training_v1",
        "release_tag": RELEASE_TAG,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": DATASET_SCOPE,
        "training_data": dataset,
        "base": base,
        "prompt_template": {"literal": PROMPT_TEMPLATE, "sha256": PROMPT_TEMPLATE_SHA256},
        "runtime": {
            "python": sys.version.split()[0],
            "cuda_visible_device": visible_device,
            "device_required": "cuda:0",
        },
        "adapters": reports,
        "review_required": True,
        "production_admitted": False,
        "next_required": [
            "held_out_task_acceptance",
            "rights_cleared_substantive_source_approval",
            "independent_human_evaluation",
            "signed_admission",
            "production_ui_frozen_package_qualification",
        ],
    }
    manifest = {
        "schema_version": "mfl_fast_interchange_workflow_candidate_v1",
        "candidate_id": f"mfl-fast-interchange-{RELEASE_TAG}",
        "scope": DATASET_SCOPE,
        "shared_base": "Qwen/Qwen3-0.6B",
        "base_license": "Apache-2.0",
        "base_model_sha256": base["model_sha256"],
        "base_provenance_sha256": base["provenance_sha256"],
        "capabilities": list(CAPABILITIES),
        "adapter_count": len(reports),
        "training_data": dataset,
        "review_required": True,
        "production_admitted": False,
        "redistribution_or_packaging_approved": False,
        "contains_real_legal_authority": False,
        "contains_private_matter_data": False,
    }
    (stage / "training-receipt.json").write_bytes(_canonical(receipt))
    (stage / "candidate-manifest.json").write_bytes(_canonical(manifest))
    output.parent.mkdir(parents=True, exist_ok=True)
    stage.replace(output)
    return {
        "status": "development_source_bound_workflow_candidate_built",
        "output_root": str(output),
        "candidate_manifest_sha256": _sha256_file(output / "candidate-manifest.json"),
        "training_receipt_sha256": _sha256_file(output / "training-receipt.json"),
        "adapter_count": len(reports),
        "duration_seconds": round(time.monotonic() - started, 3),
        "production_admitted": False,
        "substantive_maine_law_claim": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--base-provenance", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--visible-device", type=int, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=768)
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
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
