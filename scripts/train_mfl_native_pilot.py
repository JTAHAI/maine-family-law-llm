"""Bounded fresh-LoRA correction with native, compact source framing.

Only already hash-bound fictional TRAIN rows are eligible. The failed parent
adapter is NOT continued. Its verified base is shared read-only. No production
admission, corpus-rights certification, base copy, or optimizer dump is created.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import time

from scripts.diagnose_mfl_prompt_framing import render_native, validate_path
from scripts.mfl_compact_prompt_research import COMPACT_CONTRACT_ID, CONTRACTS, compact_messages
from scripts.mfl_research_device import (
    configure_device, validate_torch_device, check_gpu_headroom, research_lock, record_start_failure,
)
from scripts.train_mfl_adapter_continuation import (
    ROOT, cpu_training_headroom, learning_rate, prepare_workspace, sha, write_json,
)

BASE_SHA256 = "f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b"


def packet_digest(packet: dict) -> str:
    return hashlib.sha256(json.dumps(
        packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def answer_only_head_window(labels, prompt_tokens: int) -> dict:
    """Avoid full-vocabulary logits for masked prompt positions.

    Keep the last prompt position: it predicts the FIRST answer token. Keep
    the final EOS position too so the installed causal-loss shift is identical
    to full-sequence answer-only loss. Context attention is never truncated.
    """
    if len(labels.shape) != 2 or not 1 <= prompt_tokens < labels.shape[-1]:
        raise ValueError("invalid answer-only loss window")
    return {"logits_to_keep": labels.shape[-1] - prompt_tokens + 1,
            "labels": labels[:, prompt_tokens - 1:]}


def validate_pair(row: dict, packet: dict, capability: str, *, content_contract: str = COMPACT_CONTRACT_ID) -> dict:
    if (
        row.get("schema") != "mainely-code.sft-example.v1"
        or row.get("split") != "train" or packet.get("split") != "train"
        or row.get("example_id") != packet.get("case_id")
        or row.get("rights_class") != "company_owned"
        or row.get("privacy_class") != "no_client_data"
        or row.get("source_digest") != packet_digest(packet)
    ):
        raise ValueError("training-only source/rights/identity binding mismatch")
    answer = row.get("response", "")
    if not answer.endswith("Review required."):
        raise ValueError("training answer lacks review status")
    if any(value and value.casefold() in answer.casefold()
           for value in packet.get("forbidden_literals", [])):
        raise ValueError("training answer leaks a forbidden literal")
    sources = packet["sources"]
    for quote in packet["quotes"]:
        indexes = [index for index, source in enumerate(sources, 1) if quote in source]
        if not indexes or not any(f'"{quote}" [{index}]' in answer for index in indexes):
            raise ValueError("training quotation not bound to its source")
    case = {"capability": capability, "question": packet["question"], "sources": sources}
    messages = compact_messages(case, contract=content_contract)
    return {"example_id": row["example_id"], "family": row["task_family"],
            "messages": messages, "response": answer, "source_digest": row["source_digest"]}


def validate_training_budget(limit: int, device: str) -> None:
    allowed = {64, 128} if device == "cpu" else {64, 128, 512}
    if device not in {"cpu", "cuda"} or limit not in allowed:
        raise ValueError("native CPU pilot permits 64/128 rows; guarded CUDA permits up to 512")


def load_training(corpus: Path, capability: str, limit: int, *, device: str = "cpu",
                  content_contract: str = COMPACT_CONTRACT_ID) -> tuple[list[dict], dict]:
    validate_training_budget(limit, device)
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_schema = ("mfl.evidence-corpus-manifest.v1" if capability == "evidence_review"
                       else "mfl.practical-corpus-manifest.v1")
    if (manifest.get("schema") != expected_schema
        or manifest.get("specialist_id") != {"evidence_review": "mfl-evidence-review", "drafting": "mfl-drafting"}[capability]
        or any(manifest.get(key) is not False for key in (
            "client_data_included", "legal_authority_content_included", "northstar_assets_included",
        ))):
        raise ValueError("fictional corpus provenance required")
    corpus_path, packets_path = corpus / "corpus.jsonl", corpus / "source-packets.jsonl"
    if sha(corpus_path) != manifest["corpus_sha256"]:
        raise ValueError("corpus hash mismatch")
    if manifest.get("source_packets_sha256") and sha(packets_path) != manifest["source_packets_sha256"]:
        raise ValueError("source-packet file hash mismatch")
    # Do not consume development/test/challenge rows. Bind every selected packet
    # to its exact authorized corpus row even when the older manifest omitted
    # a whole-file packet hash. No source/question regex extraction is used.
    selected = []
    with corpus_path.open(encoding="utf-8") as rows, packets_path.open(encoding="utf-8") as packets:
        for _ in range(limit):
            raw_row, raw_packet = rows.readline(), packets.readline()
            if not raw_row or not raw_packet:
                raise ValueError("training selection incomplete")
            selected.append(validate_pair(json.loads(raw_row), json.loads(raw_packet), capability,
                                          content_contract=content_contract))
    if len({row["example_id"] for row in selected}) != limit:
        raise ValueError("duplicate training example")
    return selected, {str(p): sha(p) for p in (manifest_path, corpus_path, packets_path)}


def train(args) -> dict:
    from legal.fast_interchange.worker import HotSwapRegistry

    print(json.dumps({"phase": "validating_training_and_readonly_artifacts", "capability": args.capability}), flush=True)
    corpus = validate_path(args.corpus)
    parent = validate_path(args.parent_pack)
    output = validate_path(args.output, output=True)
    contract = getattr(args, "content_contract", COMPACT_CONTRACT_ID)
    rows, pins = load_training(corpus, args.capability, args.limit, device=getattr(args, "device", "cpu"),
                              content_contract=contract)
    registry = HotSwapRegistry.from_dicts(
        root=parent, releases=json.loads((parent / "releases.json").read_text(encoding="utf-8")),
        artifacts=json.loads((parent / "artifacts.json").read_text(encoding="utf-8")),
    )
    if len(registry.releases) != 1:
        raise ValueError("single-capability parent required")
    release = next(iter(registry.releases.values()))
    if release.capability != args.capability:
        raise ValueError("parent capability mismatch")
    binding = registry.bindings[release.release_id]
    binding.verify(parent)
    base_path = parent / binding.base_dir
    if sha(base_path / "model.safetensors") != BASE_SHA256:
        raise ValueError("approved shared base hash mismatch")
    for source in (Path(__file__), ROOT / "scripts/mfl_compact_prompt_research.py",
                   ROOT / "scripts/diagnose_mfl_prompt_framing.py",
                   ROOT / "scripts/train_mfl_adapter_continuation.py",
                   ROOT / "scripts/mfl_research_device.py",
                   parent / "releases.json", parent / "artifacts.json"):
        pins[str(source)] = sha(source)
    device = configure_device(getattr(args, "device", "cpu"), getattr(args, "gpu_uuid", None))
    cpu = device["execution_device"] == "cpu"
    if cpu:
        cpu_training_headroom(initial=True)
    prepare_workspace(output)
    print(json.dumps({"phase": "resource_checks_passed_loading_runtime", "capability": args.capability}), flush=True)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      PYTHONDONTWRITEBYTECODE="1", TOKENIZERS_PARALLELISM="false")
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(2)
    validate_torch_device(torch, device)
    torch.manual_seed(900064 if args.capability == "evidence_review" else 900065)
    report = {
        "schema": "mfl.native-fresh-pilot.v1", "capability": args.capability,
        "status": "running", "input_sha256": pins, "base_sha256": BASE_SHA256,
        "new_base_copies": 0, "continued_failed_adapter": False,
        "production_admitted": False, "quality_qualified": False, "attorney_reviewed": False,
        "authorization_basis": "owner_requested_specialist_model_correction_2026_09_05",
        "scope": "local_fictional_research_only", "real_client_data_used": False,
        "framing": "native_non_thinking_diagnostic_v1", "content": "compact_research",
        "content_contract": contract,
        "execution_device": device["execution_device"], "precision": device["precision"], "cpu_threads": 2,
        "resource_policy": device,
        "initial_memory_guard_bytes": (12 if cpu else 8) * 1024**3, "remaining_memory_guard_bytes": 4 * 1024**3,
        "train_rows": len(rows), "epochs": 1, "batch_size": 1, "peak_learning_rate": 5e-5,
        "rank": 16, "alpha": 32, "dropout": 0, "gradient_checkpointing": True,
        "family_counts": dict(Counter(row["family"] for row in rows)),
        "selected_examples_sha256": packet_digest({"ids": [row["example_id"] for row in rows]}),
        "loss": "answer_only_causal_cross_entropy", "errors": [],
        "answer_head_logits_only": True,
        "wall_time_limit_seconds": 1800,
    }
    write_json(output / "training-run.json", report)
    started = time.monotonic()
    model = optimizer = base = tokenizer = None
    try:
        tokenizer = AutoTokenizer.from_pretrained(base_path, local_files_only=True, trust_remote_code=False)
        base = AutoModelForCausalLM.from_pretrained(
            base_path, local_files_only=True, trust_remote_code=False, use_safetensors=True,
            dtype=(torch.float32 if cpu else torch.bfloat16),
        )
        model = get_peft_model(base, LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )).to(device["execution_device"])
        model.config.use_cache = False
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
        trainable = [p for p in model.parameters() if p.requires_grad]
        if sum(p.numel() for p in trainable) != 10_092_544:
            raise ValueError("unexpected fresh adapter size")
        optimizer = torch.optim.AdamW(trainable, lr=5e-5, weight_decay=0.01)
        order = list(range(len(rows)))
        random.Random(900064).shuffle(order)
        model.train()
        loss_sum = 0.0
        tokens_seen = 0
        for step, index in enumerate(order, 1):
            if time.monotonic() - started > report["wall_time_limit_seconds"]:
                raise TimeoutError("bounded research training time limit reached")
            if cpu:
                cpu_training_headroom()
            else:
                check_gpu_headroom(torch, device)
            row = rows[index]
            prompt_ids = tokenizer(render_native(row["messages"]), add_special_tokens=False).input_ids
            answer_ids = tokenizer(row["response"], add_special_tokens=False).input_ids
            tokens = [*prompt_ids, *answer_ids, tokenizer.eos_token_id]
            if not prompt_ids or not answer_ids or len(tokens) > 1024:
                raise ValueError("exact training token budget exceeded")
            values = torch.tensor([tokens], dtype=torch.long, device=device["execution_device"])
            labels = values.clone()
            labels[:, :len(prompt_ids)] = -100
            optimizer.zero_grad(set_to_none=True)
            rate = learning_rate(step - 1, len(rows), 5e-5)
            for group in optimizer.param_groups:
                group["lr"] = rate
            loss = model(input_ids=values, attention_mask=torch.ones_like(values),
                         **answer_only_head_window(labels, len(prompt_ids))).loss
            if not torch.isfinite(loss).item():
                raise FloatingPointError("nonfinite training loss")
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            if not torch.isfinite(norm).item():
                raise FloatingPointError("nonfinite training gradient")
            optimizer.step()
            loss_sum += float(loss.detach())
            tokens_seen += len(answer_ids) + 1
            report.update(steps=step, supervised_tokens=tokens_seen, loss_mean=loss_sum / step,
                          elapsed_seconds=round(time.monotonic() - started, 3))
            del values, labels, loss, norm
            if step == 1 or step % (16 if len(rows) > 128 else 4) == 0 or step == len(rows):
                write_json(output / "training-run.json", report)
                print(json.dumps({k: report[k] for k in (
                    "capability", "steps", "train_rows", "loss_mean", "elapsed_seconds"
                )}), flush=True)
        if any(not torch.isfinite(p).all().item() for p in trainable):
            raise FloatingPointError("nonfinite trained adapter")
        b_parameters = [p for name, p in model.named_parameters() if ".lora_B." in name]
        if not b_parameters or any(not torch.count_nonzero(p).item() for p in b_parameters):
            raise ValueError("fresh LoRA B parameters must all change from zero initialization")
        report["changed_from_initialization"] = True
        report["nonzero_lora_b_matrices"] = len(b_parameters)
        if not all(sha(Path(path)) == expected for path, expected in pins.items()):
            raise ValueError("training input changed during run")
        binding.verify(parent)
        staging = output / ".final.staging"
        model.save_pretrained(staging, safe_serialization=True)
        report.update(adapter_sha256=sha(staging / "adapter_model.safetensors"),
                      adapter_bytes=(staging / "adapter_model.safetensors").stat().st_size,
                      inputs_unchanged=True, status="completed_research_only")
        staging.replace(output / "final")
    except Exception as exc:
        report["status"] = "failed_no_promotion"
        report["errors"].append(type(exc).__name__ + ": " + str(exc))
    finally:
        del model, optimizer, base, tokenizer
        import gc
        gc.collect()
        if not cpu:
            report["peak_gpu_allocated_bytes"] = torch.cuda.max_memory_allocated()
            torch.cuda.empty_cache()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(output / "training-run.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--parent-pack", type=Path, required=True)
    parser.add_argument("--capability", choices=("evidence_review", "drafting"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, choices=(64, 128, 512), default=64)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--gpu-uuid")
    parser.add_argument("--content-contract", choices=CONTRACTS, default=COMPACT_CONTRACT_ID)
    args = parser.parse_args()
    try:
        with research_lock():
            result = train(args)
    except Exception as exc:
        record_start_failure(args.output, exc, training=True)
        raise SystemExit(2) from exc
    print(json.dumps({k: result[k] for k in ("status", "capability", "elapsed_seconds", "errors")}))
    raise SystemExit(0 if result["status"] == "completed_research_only" else 2)
