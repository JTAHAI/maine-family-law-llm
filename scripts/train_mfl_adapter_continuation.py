"""Continue a local-research LoRA from an audited fictional corpus.

This trainer is intentionally narrow: Qwen3-0.6B, an existing rank-16 PEFT
adapter, exact FAST INTERCHANGE prompt bytes, answer-only loss, one local CUDA
device or a bounded CPU pilot, and no network access. It creates a research checkpoint;
it cannot create a production admission or legal-quality claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import shutil
import sys
import time
from collections import Counter
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CUDA_ALLOCATOR_CONFIG = "expandable_segments:True"
DEFAULT_CUDA_EMPTY_CACHE_EVERY = 64
ATOMIC_RECEIPT_RETRIES = 10
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"required regular file missing: {path}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: object) -> None:
    # Explorer, antivirus, and a status observer can briefly hold a Windows
    # read handle on a receipt.  A progress write must not terminate the
    # actual training job for that transient condition.  Use a process-unique
    # sibling and retry the atomic replacement with a short bounded backoff.
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for attempt in range(ATOMIC_RECEIPT_RETRIES):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt + 1 == ATOMIC_RECEIPT_RETRIES:
                raise
            time.sleep(0.05 * (attempt + 1))


def exact_prompt(instruction: str) -> str:
    messages = json.loads(instruction)
    if not isinstance(messages, list) or not 1 <= len(messages) <= 8:
        raise ValueError("invalid message array")
    rendered: list[str] = []
    for message in messages:
        if (
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or message["role"] not in {"system", "user"}
            or not isinstance(message["content"], str)
            or not message["content"]
        ):
            raise ValueError("invalid fixed-role message")
        rendered.append(f"fi-fixed-role-v1:[{message['role'].upper()}]\\n{message['content']}")
    return "\\n".join(rendered)


def validate_inputs(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from legal.fast_interchange.worker import HotSwapRegistry

    specialist_id = {
        "drafting": "mfl-drafting",
        "evidence_review": "mfl-evidence-review",
    }[args.capability]
    authorization = json.loads(args.authorization.read_text(encoding="utf-8"))
    manifest = json.loads((args.corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    if (
        authorization.get("schema") != "mainely-code.local-research-authorization.v1"
        or authorization.get("specialist_id") != specialist_id
        or authorization.get("local_research_training_authorized") is not True
        or authorization.get("approved_scope")
        != "local_only_research_training_and_evaluation_on_newly_authored_fictional_records"
        or any(
            authorization.get(name) is not False
            for name in (
                "external_rights_authentication_verified",
                "real_client_data_authorized",
                "statutory_training_authorized",
                "production_admitted",
                "rc_complete",
                "promotion_authority",
            )
        )
    ):
        raise ValueError("local research authorization is invalid")
    if (
        sha(args.corpus_dir / "corpus.jsonl") != authorization["corpus_sha256"]
        or sha(args.corpus_dir / "manifest.json") != authorization["corpus_manifest_sha256"]
        or sha(args.base_model / "model.safetensors") != authorization["base_weights_sha256"]
        or manifest.get("corpus_sha256") != authorization["corpus_sha256"]
        or manifest.get("specialist_id") != specialist_id
        or manifest.get("client_data_included") is not False
        or manifest.get("legal_authority_content_included") is not False
        or manifest.get("northstar_assets_included") is not False
    ):
        raise ValueError("authorization content binding mismatch")
    if (
        audit.get("decision") != "technical_integrity_passed_not_training_admitted"
        or audit.get("specialist_id") != specialist_id
        or audit.get("corpus_sha256") != authorization["corpus_sha256"]
        or audit.get("manifest_sha256") != authorization["corpus_manifest_sha256"]
        or audit.get("production_admitted") is not False
        or audit.get("training_authorized") is not False
    ):
        raise ValueError("independent corpus audit mismatch")
    for path, expected in manifest["implementation_sha256"].items():
        if sha(Path(path)) != expected:
            raise ValueError("corpus builder or product consumer changed after audit")

    registry = HotSwapRegistry.from_dicts(
        root=args.parent_pack,
        releases=json.loads((args.parent_pack / "releases.json").read_text(encoding="utf-8")),
        artifacts=json.loads((args.parent_pack / "artifacts.json").read_text(encoding="utf-8")),
    )
    if len(registry.releases) != 1:
        raise ValueError("parent pack must contain exactly one adapter")
    release = next(iter(registry.releases.values()))
    if release.capability != args.capability:
        raise ValueError("parent adapter capability does not match the continuation")
    binding = registry.bindings[release.release_id]
    binding.verify(registry.root)
    parent_adapter = args.parent_pack / binding.adapter_dir
    parent_config = json.loads((parent_adapter / "adapter_config.json").read_text(encoding="utf-8"))
    if parent_config.get("r") != 16 or parent_config.get("lora_alpha") != 32:
        raise ValueError("parent adapter rank/alpha outside the pinned continuation contract")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with (args.corpus_dir / "corpus.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            required = {
                "schema",
                "example_id",
                "instruction",
                "response",
                "rights_class",
                "privacy_class",
                "split",
                "task_family",
                "source_digest",
                "lineage_group",
            }
            if (
                not required <= set(row)
                or row.get("schema") != "mainely-code.sft-example.v1"
                or row["example_id"] in seen
                or row.get("rights_class") != "company_owned"
                or row.get("privacy_class") != "no_client_data"
            ):
                raise ValueError("invalid or duplicate SFT row")
            seen.add(row["example_id"])
            exact_prompt(row["instruction"])
            if not row["response"].endswith("Review required."):
                raise ValueError("review marker missing from training target")
            rows.append(row)
    split_counts = dict(Counter(row["split"] for row in rows))
    validate_split_contract(split_counts, manifest, pilot=bool(getattr(args, "pilot", False)))
    if getattr(args, "pilot", False):
        development_path = args.corpus_dir.parent / "development.json"
        development = json.loads(development_path.read_text(encoding="utf-8"))
        if (
            sha(development_path) != manifest["development_sha256"]
            or development.get("training_use_permitted") is not False
            or len(development.get("cases", [])) != manifest["development_cases"]
        ):
            raise ValueError("pilot development isolation binding mismatch")
    admission = {
        "authorization": authorization,
        "authorization_sha256": sha(args.authorization),
        "audit_sha256": sha(args.audit),
        "corpus_sha256": authorization["corpus_sha256"],
        "base_weights_sha256": authorization["base_weights_sha256"],
        "split_counts": split_counts,
        "scope": "local_research_only",
        "external_rights_authentication_verified": False,
        "promotion_authority": False,
        "parent_release_id": release.release_id,
        "parent_release_fingerprint": release.release_fingerprint,
        "parent_adapter_sha256": sha(parent_adapter / "adapter_model.safetensors"),
    }
    return rows, {"admission": admission, "parent_adapter": parent_adapter}


def learning_rate(step: int, total: int, peak: float) -> float:
    warmup = max(1, int(total * 0.03))
    if step < warmup:
        return peak * (step + 1) / warmup
    progress = (step - warmup) / max(1, total - warmup)
    return peak * 0.5 * (1.0 + math.cos(math.pi * progress))


def valid_cuda_selector(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:[0-9]|[12][0-9]|3[01]|GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})",
            value,
        )
    )


def validate_split_contract(counts: dict, manifest: dict, *, pilot: bool) -> None:
    if counts != manifest.get("split_counts"):
        raise ValueError("training split contract mismatch")
    if pilot:
        if (
            manifest.get("purpose") != "bounded_generalization_pilot"
            or not 64 <= counts.get("train", 0) <= 2_048
            or set(counts) != {"train"}
            or manifest.get("development_cases", 0) < 8
            or not isinstance(manifest.get("development_sha256"), str)
            or len(manifest["development_sha256"]) != 64
        ):
            raise ValueError("audited small-pilot split contract required")
    elif counts.get("train") != 25_600:
        raise ValueError("training split contract mismatch")


def prepare_workspace(output: Path) -> None:
    """Never let a direct trainer invocation create drive-root scratch files."""
    resolved = output.resolve()
    root = (ROOT / "dist").resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("training output must be inside repository dist")
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("training output must be new and cannot traverse a symlink")
    if shutil.disk_usage(ROOT).free < 2 * 1024**3:
        raise ValueError("two GiB training disk reserve required")
    output.mkdir(parents=True)
    for name in (
        "TEMP",
        "TMP",
        "HF_HOME",
        "TORCH_HOME",
        "TORCHINDUCTOR_CACHE_DIR",
        "TRITON_CACHE_DIR",
    ):
        location = output / "scratch" / name.lower()
        location.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(location.resolve())


def select_train_rows(
    rows: list[dict[str, Any]], *, offset: int, limit: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select one explicit, non-overlapping window from the authorized train split.

    A corrective continuation may consume an unused portion of the same
    immutable fictional corpus, but it must never silently repeat the earlier
    window or spill into a held-out split.
    """
    all_train_rows = [row for row in rows if row["split"] == "train"]
    if offset < 0 or limit < 1 or offset + limit > len(all_train_rows):
        raise ValueError("selected training window is outside the authorized train split")
    selected = all_train_rows[offset : offset + limit]
    if len(selected) != limit:
        raise ValueError("selected training window is incomplete")
    return all_train_rows, selected


def training_device(args: argparse.Namespace) -> str:
    device = getattr(args, "device", "cuda")
    if device == "cuda":
        return "cuda:0"
    if (
        device != "cpu"
        or not args.pilot
        or args.precision != "fp32"
        or args.batch_size != 1
        or not 64 <= args.train_limit <= 128
        or not args.gradient_checkpointing
    ):
        raise ValueError("CPU training requires a 64-128-row FP32 checkpointed batch-one pilot")
    return "cpu"


def cpu_training_headroom(*, initial: bool = False) -> None:
    import psutil

    required = (12 if initial else 4) * 1024**3
    if psutil.virtual_memory().available < required:
        raise RuntimeError("CPU training stopped to preserve available memory headroom")
    if initial:
        if not hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS"):
            raise RuntimeError("CPU training pilot is qualified only on Windows")
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)


def train(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists():
        raise ValueError("continuation output must be a new directory")
    device = training_device(args)
    cpu = device == "cpu"
    if cpu:
        cpu_training_headroom(initial=True)
    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_PROGRESS_BARS="1",
        PYTHONDONTWRITEBYTECODE="1",
        CUDA_VISIBLE_DEVICES="-1" if cpu else str(args.cuda_visible_device),
    )
    # This continuation is deliberately bounded for modest consumer GPUs.  The
    # RTX 3060 lane can otherwise retain fragmented free blocks across many
    # gradient-checkpointed steps and fail late with CUDA OOM even though its
    # peak allocated memory is below device capacity.  Set this before torch
    # is imported so PyTorch can grow allocations in place where supported.
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = CUDA_ALLOCATOR_CONFIG
    rows, inputs = validate_inputs(args)
    prepare_workspace(args.output)
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(2 if cpu else 4)
    tokenizer = AutoTokenizer.from_pretrained(
        args.base_model, local_files_only=True, trust_remote_code=False
    )
    if type(tokenizer.eos_token_id) is not int:
        raise ValueError("tokenizer EOS is unavailable")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    dtype = torch.bfloat16 if args.precision == "bf16" else torch.float32
    if args.precision == "bf16" and not torch.cuda.is_bf16_supported():
        raise ValueError("selected CUDA device does not support BF16 continuation")
    base = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        local_files_only=True,
        trust_remote_code=False,
        use_safetensors=True,
        dtype=dtype,
    )
    model = PeftModel.from_pretrained(
        base,
        inputs["parent_adapter"],
        is_trainable=True,
    ).to(device)
    model.config.use_cache = False
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    if sum(parameter.numel() for parameter in trainable) != 10_092_544:
        raise ValueError("unexpected trainable adapter parameter count")
    optimizer = torch.optim.AdamW(trainable, lr=args.learning_rate, weight_decay=0.01)
    all_train_rows, train_rows = select_train_rows(
        rows, offset=args.train_offset, limit=args.train_limit
    )
    selected_examples_sha256 = hashlib.sha256(
        "\n".join(row["example_id"] for row in train_rows).encode("utf-8")
    ).hexdigest()
    total_steps = math.ceil(len(train_rows) / args.batch_size) * args.epochs
    identity = {
        **inputs,
        "parent_adapter": str(inputs["parent_adapter"].resolve()),
        "trainer_sha256": sha(Path(__file__).resolve()),
        "base_config_sha256": sha(args.base_model / "config.json"),
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "rank": 16,
        "alpha": 32,
        "learning_rate": args.learning_rate,
        "precision": args.precision,
        "load_in_4bit": False,
        "gradient_checkpointing": args.gradient_checkpointing,
        "cuda_allocator": os.environ["PYTORCH_CUDA_ALLOC_CONF"],
        "prompt_format": "mfl_fixed_role_v1",
        "loss": "exact_answer_only_causal_cross_entropy",
        "continuation": True,
        "bounded_pilot": bool(getattr(args, "pilot", False)),
        "quality_qualification": False,
        "execution_device": device,
        "cpu_threads": 2 if cpu else 4,
        "authorized_train_examples": len(all_train_rows),
        "train_offset": args.train_offset,
        "selected_train_examples": len(train_rows),
        "selected_examples_sha256": selected_examples_sha256,
    }
    write_json(args.output / "run-identity.json", identity)
    started = time.monotonic()
    step = 0
    examples_seen = 0
    supervised_tokens = 0
    loss_sum = 0.0
    model.train()
    for epoch in range(args.epochs):
        order = list(range(len(train_rows)))
        random.Random(args.seed + epoch).shuffle(order)
        for start in range(0, len(order), args.batch_size):
            if cpu:
                cpu_training_headroom()
            selected = [train_rows[index] for index in order[start : start + args.batch_size]]
            sequences: list[list[int]] = []
            prompt_lengths: list[int] = []
            for row in selected:
                prompt_ids = tokenizer(
                    exact_prompt(row["instruction"]),
                    add_special_tokens=False,
                    truncation=False,
                ).input_ids
                answer_ids = tokenizer(
                    row["response"], add_special_tokens=False, truncation=False
                ).input_ids
                tokens = [*prompt_ids, *answer_ids, tokenizer.eos_token_id]
                if not prompt_ids or not answer_ids or len(tokens) > 1024:
                    raise ValueError("training sequence violates exact token budget")
                sequences.append(tokens)
                prompt_lengths.append(len(prompt_ids))
            encoded = tokenizer.pad({"input_ids": sequences}, padding=True, return_tensors="pt").to(
                device
            )
            labels = encoded.input_ids.clone()
            for index, prompt_length in enumerate(prompt_lengths):
                labels[index, :prompt_length] = -100
            labels[encoded.attention_mask == 0] = -100
            count = int((labels != -100).sum().item())
            optimizer.zero_grad(set_to_none=True)
            rate = learning_rate(step, total_steps, args.learning_rate)
            for group in optimizer.param_groups:
                group["lr"] = rate
            autocast = (
                torch.autocast(device_type="cuda", dtype=torch.bfloat16)
                if args.precision == "bf16"
                else nullcontext()
            )
            with autocast:
                loss = model(**encoded, labels=labels).loss
            if not bool(torch.isfinite(loss).item()):
                raise FloatingPointError("non-finite continuation loss")
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            if not bool(torch.isfinite(norm).item()):
                raise FloatingPointError("non-finite continuation gradient")
            optimizer.step()
            step += 1
            examples_seen += len(selected)
            supervised_tokens += count
            loss_value = float(loss.detach().float().cpu())
            loss_sum += loss_value
            # Drop the final references from this step before the next
            # checkpointed backward pass.  This does not change gradients or
            # the deterministic data order, but keeps the allocator healthy
            # on 6-GB devices.  Emptying the cache only returns unreferenced
            # blocks; active tensors remain protected by PyTorch.
            del encoded, labels, norm, loss
            if not cpu and step % args.cuda_empty_cache_every == 0:
                torch.cuda.empty_cache()
            if step == 1 or step % 10 == 0 or step == total_steps:
                progress = {
                    "event": "continuation_progress",
                    "step": step,
                    "total_steps": total_steps,
                    "examples_seen": examples_seen,
                    "supervised_tokens": supervised_tokens,
                    "loss": loss_value,
                    "loss_mean": loss_sum / step,
                    "learning_rate": rate,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "device": "cpu" if cpu else torch.cuda.get_device_name(0),
                    "peak_allocated_mib": None
                    if cpu
                    else round(torch.cuda.max_memory_allocated() / 1024**2, 2),
                    "reserved_mib": None
                    if cpu
                    else round(torch.cuda.memory_reserved() / 1024**2, 2),
                }
                write_json(args.output / "progress.json", progress)
                print(json.dumps(progress), flush=True)

    staging = args.output / ".final.staging"
    model.save_pretrained(staging, safe_serialization=True, selected_adapters=["default"])
    saved_adapter = staging / "adapter_model.safetensors"
    parent_hash = inputs["admission"]["parent_adapter_sha256"]
    adapter_hash = sha(saved_adapter)
    if adapter_hash == parent_hash:
        raise FloatingPointError("continuation adapter did not change")
    checkpoint = {
        "schema": "mfl.research-training-checkpoint.v1",
        "step": step,
        "examples_seen": examples_seen,
        "supervised_tokens": supervised_tokens,
        "loss_sum": loss_sum,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "identity": identity,
        "adapter_sha256": adapter_hash,
        "research_only": True,
        "production_admitted": False,
        "rc_complete": False,
        "promotion_authority": False,
    }
    write_json(staging / "checkpoint.json", checkpoint)
    staging.replace(args.output / "final")
    result = {
        "schema": "mainely-code.training-run.v1",
        "status": "completed-local-research-only",
        "run_purpose": (f"user_authorized_fictional_{args.capability}_generalization_research"),
        "specialist_id": inputs["admission"]["authorization"]["specialist_id"],
        "base_model_path": str(args.base_model.resolve()),
        "dataset_path": str((args.corpus_dir / "corpus.jsonl").resolve()),
        "dataset_sha256": inputs["admission"]["corpus_sha256"],
        "train_examples": len(train_rows),
        "examples_seen": examples_seen,
        "epochs": args.epochs,
        "step": step,
        "supervised_tokens": supervised_tokens,
        "loss_sum": loss_sum,
        "elapsed_seconds": checkpoint["elapsed_seconds"],
        "identity": identity,
        "runtime": {
            "device": "cpu" if cpu else torch.cuda.get_device_name(0),
            "precision": args.precision,
            "peak_allocated_mib": None
            if cpu
            else round(torch.cuda.max_memory_allocated() / 1024**2, 2),
        },
        "adapter_sha256": adapter_hash,
        "parent_adapter_sha256": parent_hash,
        "research_authorization": inputs["admission"],
        "training_admission": None,
        "completed_at": datetime.now(UTC).isoformat(),
        "production_admitted": False,
        "rc_complete": False,
        "promotion_authority": False,
    }
    write_json(args.output / "training-run.json", result)
    print(json.dumps({"event": "continuation_complete", **result}), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--parent-pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--capability",
        choices=("drafting", "evidence_review"),
        default="drafting",
    )
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=6e-5)
    parser.add_argument("--seed", type=int, default=2026090104)
    parser.add_argument("--cuda-visible-device", default="0")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--precision", choices=("bf16", "fp32"), default="bf16")
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument(
        "--cuda-empty-cache-every", type=int, default=DEFAULT_CUDA_EMPTY_CACHE_EVERY
    )
    parser.add_argument("--train-limit", type=int, default=12_800)
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Require an audited 64–2048-row pilot manifest; never qualifies release.",
    )
    parser.add_argument(
        "--train-offset",
        type=int,
        default=0,
        help="First row of the authorized train split for a non-overlapping continuation.",
    )
    args = parser.parse_args()
    if (
        args.epochs != 1
        or not 1 <= args.batch_size <= 16
        or not 0 < args.learning_rate <= 1e-4
        or not valid_cuda_selector(args.cuda_visible_device)
        or not 1 <= args.cuda_empty_cache_every <= 10_000
        or not (64 if args.pilot else 3_200)
        <= args.train_limit
        <= (2_048 if args.pilot else 25_600)
        or not 0 <= args.train_offset < 25_600
        or args.train_offset + args.train_limit > 25_600
    ):
        parser.error("bounded continuation configuration is invalid")
    train(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
