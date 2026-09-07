"""Bounded offline validation of the unadmitted Evidence Review research pack.

This is intentionally not an admission, legal-quality evaluation, package
qualification, or client-matter workflow.  It loads the supplied local pack
only after the caller explicitly opts into a fictional-record test, sends no
network traffic, and stores a hash of generated text rather than the raw text.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SCOPE = "fictional_evidence_handling_research_only_not_substantive_legal_knowledge"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("research_pack_json_invalid")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cuda-index", type=int, default=0)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--allow-fictional-research", action="store_true")
    args = parser.parse_args()
    if not args.allow_fictional_research:
        parser.error("fictional_research_opt_in_required")
    if not 1 <= args.max_new_tokens <= 256:
        parser.error("max_new_tokens_must_be_between_1_and_256")
    pack = args.pack_root.resolve(strict=True)
    output = args.output.resolve()
    dist_root = (ROOT / "dist").resolve()
    if not output.is_relative_to(dist_root) or output.exists():
        parser.error("output_must_be_new_inside_repository_dist")
    manifest = _read_json(pack / "pack-manifest.json")
    releases = _read_json(pack / "releases.json")
    release_rows = [
        row for row in releases.get("releases", [])
        if isinstance(row, dict) and row.get("capability") == "evidence_review"
    ]
    if (
        manifest.get("production_admitted") is not False
        or manifest.get("attorney_reviewed") is not False
        or manifest.get("scope") != EXPECTED_SCOPE
        or manifest.get("capabilities") != ["evidence_review"]
        or len(release_rows) != 1
    ):
        raise ValueError("fictional_research_pack_scope_invalid")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available() or not 0 <= args.cuda_index < torch.cuda.device_count():
        raise RuntimeError("cuda_runtime_not_available_for_research_validation")
    device = f"cuda:{args.cuda_index}"
    base = pack / "base"
    adapter = pack / "adapters" / "evidence_review"
    prompt = (
        "[USER]\n"
        "Fictional software QA only. Compare exact record one: pickup at 15:20. "
        "Exact record two: pickup at 16:10. State only the difference and say review required."
    )
    started = time.monotonic()
    torch.cuda.set_device(args.cuda_index)
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        base, local_files_only=True, torch_dtype=torch.bfloat16
    ).to(device)
    model = PeftModel.from_pretrained(model, adapter, local_files_only=True)
    model.eval()
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        generated = model.generate(
            **inputs,
            do_sample=False,
            use_cache=True,
            max_new_tokens=args.max_new_tokens,
            return_dict_in_generate=False,
        )
    token_ids = generated[0][inputs["input_ids"].shape[1] :].tolist()
    raw = tokenizer.decode(token_ids, skip_special_tokens=True).strip()
    eos = tokenizer.eos_token_id
    result = {
        "schema_version": "mfl_evidence_research_gpu_validation_v1",
        "scope": "fictional_research_only_not_client_or_legal_use",
        "production_admitted": False,
        "attorney_reviewed": False,
        "raw_model_output_visible": False,
        "network_used": False,
        "release_id": str(release_rows[0].get("release_id") or ""),
        "cuda_index": args.cuda_index,
        "device_name": torch.cuda.get_device_name(args.cuda_index),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "completion_tokens": len(token_ids),
        "maximum_new_tokens": args.max_new_tokens,
        "natural_stop": bool(token_ids and isinstance(eos, int) and token_ids[-1] == eos),
        "output_sha256": sha256(raw.encode("utf-8")).hexdigest(),
        "output_has_both_exact_fictional_values": "15:20" in raw and "16:10" in raw,
        "output_claims_legal_authority": any(
            marker in raw.casefold()
            for marker in ("m.r.s.", "maine law requires", "the court must")
        ),
        "peak_allocated_bytes": int(torch.cuda.max_memory_allocated(args.cuda_index)),
        "review_required": True,
        "release_eligible": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
