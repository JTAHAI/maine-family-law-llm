"""Offline, bounded framing ablation; never admits or changes a serving model.

Compare a pinned specialist and its unchanged shared base using identical input
content with legacy framing and a hard-coded Qwen non-thinking chat frame. This
is experiment-selection evidence, not a final holdout or production E2E test.
No downloaded chat-template code is executed and no model files are copied.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import re
import time
from types import SimpleNamespace

from scripts.evaluate_mfl_adapter_pilot import check_shared_memory, evaluation_resources
from scripts.train_mfl_adapter_continuation import ROOT, exact_prompt, sha, write_json
from scripts.mfl_compact_prompt_research import COMPACT_CONTRACT_ID, CONTRACTS
from scripts.mfl_research_device import (
    configure_device, validate_torch_device, check_gpu_headroom, research_lock, record_start_failure,
)


def render_native(messages: list[dict[str, str]]) -> str:
    # Validate the same limited roles as training. Never run tokenizer Jinja.
    exact_prompt(json.dumps(messages))
    parts = []
    for message in messages:
        # Source text cannot manufacture chat token IDs/role boundaries. The
        # diagnostic preserves an auditable visible escape instead of deletion.
        content = message["content"].replace("<|", "\\u003c|")
        parts.append(f"<|im_start|>{message['role']}\n{content}<|im_end|>\n")
    return "".join(parts) + "<|im_start|>assistant\n<think>\n\n</think>\n\n"


def load_cases(path: Path, capability: str) -> list[dict]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if (
        fixture.get("schema") != "mfl.framing-diagnostic.v1"
        or fixture.get("training_use_permitted") is not False
        or fixture.get("fictional_only") is not True
        or fixture.get("evaluation_role") != "development_not_final_holdout"
    ):
        raise ValueError("fictional, training-isolated development fixture required")
    cases = [c for c in fixture["cases"] if c.get("capability") == capability]
    if not 1 <= len(cases) <= 8 or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("one to eight unique diagnostic cases required")
    for case in cases:
        if (
            not isinstance(case.get("question"), str) or not case["question"]
            or not isinstance(case.get("sources"), list)
            or not all(isinstance(s, str) and s for s in case["sources"])
            or not isinstance(case.get("expected_semantics"), list)
            or not case["expected_semantics"]
        ):
            raise ValueError("diagnostic case contract invalid")
    return cases


def consumer_messages(case: dict) -> list[dict[str, str]]:
    from legal.agent_runtime.contracts import ContextSource
    from legal.agent_runtime.runtime import LocalAgentRuntime

    runtime = LocalAgentRuntime(SimpleNamespace(
        provider_id="fast_interchange_local", model_binding={"capability": case["capability"]}
    ))
    sources = tuple(ContextSource(
        source_id=f"{case['id']}-source-{index}", lane="private_record",
        title="Fictional diagnostic record; not a real matter", text=text,
        locator=f"fictional block {index}", authority_status="unverified_fixture",
        freshness_status="unknown",
    ) for index, text in enumerate(case["sources"], 1))
    return [{"role": "user", "content": runtime._build_prompt(case["question"], sources, [])}]


def validate_path(path: Path, *, output: bool = False) -> Path:
    if any(p.is_symlink() or getattr(p, "is_junction", lambda: False)()
           for p in (path, *path.parents)):
        raise ValueError("linked diagnostic path forbidden")
    resolved = path.resolve()
    if not resolved.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("diagnostic inputs and outputs must remain in repository dist")
    if output and resolved.exists():
        raise ValueError("diagnostic output must be new; preserve prior evidence")
    return resolved


def experiment_modes(args) -> tuple[str, tuple[str, ...]]:
    content = getattr(args, "content", "production")
    native_only = getattr(args, "native_only", False)
    if content not in {"production", "compact_research"}:
        raise ValueError("unknown diagnostic content contract")
    if content == "compact_research" and not native_only:
        raise ValueError("compact research uses explicit native-only comparison")
    return content, (("native_non_thinking_diagnostic_v1",) if native_only else (
        "fixed_v1", "native_non_thinking_diagnostic_v1"
    ))


def weight_placement(device: str, *, direct: bool) -> dict:
    if direct and device != "cuda:0":
        raise ValueError("direct weight placement is an explicit CUDA-only experiment")
    return {"device_map": {"": device}} if direct else {}


def model_modes(args) -> tuple[bool, ...]:
    base_only = getattr(args, "base_only", False)
    adapter_only = getattr(args, "adapter_only", False)
    if base_only and adapter_only:
        raise ValueError("base-only and adapter-only are mutually exclusive")
    return (False,) if base_only else ((True,) if adapter_only else (False, True))


def prepare_model(raw, adapter: Path, device: str, *, base_only: bool):
    if base_only:
        # Reuse the verified base directly: no adapter import, load or copies.
        return raw.to(device).eval()
    from peft import PeftModel

    return PeftModel.from_pretrained(raw, adapter, is_trainable=False).to(device).eval()


def adapter_context(model, *, with_adapter: bool, base_only: bool):
    return nullcontext() if base_only or with_adapter else model.disable_adapter()


def generation_outcome(results: list[dict], requested: int, failures: list[str]) -> dict:
    complete = sum(row.get("complete") is True and row.get("error") is None
                   and isinstance(row.get("answer"), str)
                   and bool(row["answer"].strip()) for row in results)
    return {
        "attempted_generations": len(results),
        "completed_generations": complete,
        "run_completed": requested > 0 and len(results) == requested
        and complete == requested and not failures,
    }


def run(args) -> dict:
    from legal.fast_interchange.worker import HotSwapRegistry

    print(json.dumps({"phase": "validating_readonly_artifacts", "capability": args.capability}), flush=True)
    output = validate_path(args.output, output=True)
    parent = validate_path(args.parent_pack)
    adapter = validate_path(args.adapter)
    fixtures = validate_path(args.fixtures)
    cases = load_cases(fixtures, args.capability)
    content_mode, framings = experiment_modes(args)
    adapter_modes = model_modes(args)
    base_only = adapter_modes == (False,)
    message_builder = consumer_messages
    if content_mode == "compact_research":
        from scripts.mfl_compact_prompt_research import compact_messages
        message_builder = lambda case: compact_messages(case, contract=getattr(args, "content_contract", COMPACT_CONTRACT_ID))
    registry = HotSwapRegistry.from_dicts(
        root=parent,
        releases=json.loads((parent / "releases.json").read_text(encoding="utf-8")),
        artifacts=json.loads((parent / "artifacts.json").read_text(encoding="utf-8")),
    )
    if len(registry.releases) != 1:
        raise ValueError("single specialist parent required")
    release = next(iter(registry.releases.values()))
    if release.capability != args.capability:
        raise ValueError("capability mismatch")
    binding = registry.bindings[release.release_id]
    binding.verify(parent)
    base = parent / binding.base_dir
    pins = {str(path): sha(path) for path in (
        fixtures, Path(__file__), ROOT / "scripts/train_mfl_adapter_continuation.py",
        ROOT / "scripts/evaluate_mfl_adapter_pilot.py", ROOT / "legal/agent_runtime/runtime.py",
        ROOT / "legal/fast_interchange/specialists.py", ROOT / "legal/fast_interchange/worker.py",
        parent / "releases.json", parent / "artifacts.json",
        adapter / "adapter_model.safetensors", adapter / "adapter_config.json",
        ROOT / "scripts/mfl_research_device.py",
    )}
    if content_mode == "compact_research":
        compact_source = ROOT / "scripts/mfl_compact_prompt_research.py"
        pins[str(compact_source)] = sha(compact_source)
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = output.parent / "scratch"
    scratch.mkdir(exist_ok=True)
    for name in ("TEMP", "TMP", "HF_HOME", "TORCH_HOME", "TORCHINDUCTOR_CACHE_DIR", "TRITON_CACHE_DIR"):
        os.environ[name] = str(scratch)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      PYTHONDONTWRITEBYTECODE="1", TOKENIZERS_PARALLELISM="false")
    device = configure_device(getattr(args, "device", "cpu"), getattr(args, "gpu_uuid", None))
    resources = (evaluation_resources(
        SimpleNamespace(shared_host_cpu=True, device="cpu", frozen_regression=False), lambda: None,
    ) if device["execution_device"] == "cpu" else device)
    print(json.dumps({"phase": "resource_checks_passed_loading_runtime", "capability": args.capability}), flush=True)
    import psutil
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList

    torch.set_num_threads(resources["cpu_threads"])
    validate_torch_device(torch, device)
    placement = weight_placement(device["execution_device"], direct=getattr(args, "direct_gpu_placement", False))
    torch.manual_seed(900001)
    results, failures = [], []
    started = time.monotonic()
    model = tokenizer = raw = None
    report = {
        "schema": "mfl.framing-ablation.v1", "capability": args.capability,
        "resource_policy": resources, "input_sha256": pins,
        "production_admitted": False, "production_contract_changed": False,
        "desktop_e2e": False, "attorney_reviewed": False, "legal_quality_qualified": False,
        "evaluation_role": "development_not_final_holdout", "model_files_copied": 0,
        "content_mode": content_mode, "framings": framings,
        "content_contract": (getattr(args, "content_contract", COMPACT_CONTRACT_ID)
                             if content_mode == "compact_research" else "production"),
        "adapter_only": adapter_modes == (True,),
        "base_only": base_only,
        "adapter_loaded": False,
        "unchanged_base_evaluated": False,
        "base_ablation_requested": len(adapter_modes) == 2,
        "base_ablation_performed": False,
        "direct_gpu_weight_placement": bool(placement),
        "cases": len(cases), "requested_generations": len(adapter_modes) * len(framings) * len(cases),
        "results": results, "errors": failures,
        "semantic_scoring": "requires_reading_raw_answers_not_keyword_certification",
    }
    peak_rss = 0
    try:
        tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True, trust_remote_code=False)
        if any(tokenizer.convert_tokens_to_ids(s) != value for s, value in (
            ("<|im_start|>", 151644), ("<|im_end|>", 151645),
        )):
            raise ValueError("unrecognized native token contract")
        raw = AutoModelForCausalLM.from_pretrained(
            base, local_files_only=True, trust_remote_code=False,
            use_safetensors=True, dtype=(torch.float32 if device["execution_device"] == "cpu" else torch.bfloat16),
            **placement,
        )
        model = prepare_model(raw, adapter, device["execution_device"], base_only=base_only)
        report["adapter_loaded"] = not base_only
        report["activation_seconds"] = round(time.monotonic() - started, 3)
        for case in cases:
            messages = message_builder(case)
            for framing in framings:
                prompt = (exact_prompt(json.dumps(messages)) if framing == "fixed_v1"
                          else render_native(messages))
                for with_adapter in adapter_modes:
                    check_shared_memory(resources)
                    check_gpu_headroom(torch, device)
                    start = time.monotonic()
                    deadline = start + 180

                    class Deadline(StoppingCriteria):
                        def __call__(self, input_ids, scores, **kwargs):
                            check_shared_memory(resources)
                            check_gpu_headroom(torch, device)
                            if time.monotonic() > deadline:
                                raise TimeoutError("bounded diagnostic generation timeout")
                            return False

                    answer, error, complete, count = "", None, False, 0
                    try:
                        encoded = tokenizer(prompt, return_tensors="pt", truncation=False).to(device["execution_device"])
                        prompt_count = encoded.input_ids.shape[1]
                        if not 1 <= prompt_count <= 2048:
                            raise ValueError("exact context token budget exceeded")
                        with adapter_context(model, with_adapter=with_adapter, base_only=base_only), torch.no_grad():
                            generated = model.generate(
                                **encoded, do_sample=False, use_cache=True,
                                cache_implementation="dynamic", return_dict_in_generate=False,
                                temperature=None, top_p=None, top_k=None, max_new_tokens=256,
                                stopping_criteria=StoppingCriteriaList([Deadline()]),
                            )[0][prompt_count:]
                        token_ids = generated.tolist()
                        count = len(token_ids)
                        eos = model.generation_config.eos_token_id
                        eos = [eos] if isinstance(eos, int) else eos
                        complete = bool(token_ids) and count < 256 and token_ids[-1] in eos
                        answer = tokenizer.decode(generated, skip_special_tokens=True).strip()
                        # Raw partial answers are evidence only; NEVER served to users.
                        del encoded, generated
                    except Exception as exc:
                        error = type(exc).__name__ + ": " + str(exc)
                    peak_rss = max(peak_rss, psutil.Process().memory_info().rss)
                    row = {
                        "case_id": case["id"], "framing": framing, "adapter_enabled": with_adapter,
                        "answer": answer, "error": error, "complete": complete,
                        "output_tokens": count, "review_required_visible": answer.endswith("Review required."),
                        "reference_indexes": re.findall(r"\[(\d+)\]", answer),
                        "expected_semantics": case["expected_semantics"],
                        "seconds": round(time.monotonic() - start, 3),
                    }
                    results.append(row)
                    write_json(output.with_suffix(".progress.json"), report)
                    print(json.dumps({k: row[k] for k in (
                        "case_id", "framing", "adapter_enabled", "complete", "seconds", "error"
                    )}), flush=True)
    except Exception as exc:
        failures.append(type(exc).__name__ + ": " + str(exc))
    finally:
        del model, tokenizer, raw
        import gc
        gc.collect()
        if device["execution_device"] != "cpu":
            report["peak_gpu_allocated_bytes"] = torch.cuda.max_memory_allocated()
            torch.cuda.empty_cache()
    try:
        binding.verify(parent)
        report["inputs_unchanged"] = all(sha(Path(p)) == digest for p, digest in pins.items())
    except Exception as exc:
        report["inputs_unchanged"] = False
        failures.append("input recheck: " + type(exc).__name__)
    report.update(elapsed_seconds=round(time.monotonic() - started, 3), peak_cpu_rss_bytes=peak_rss,
                  **generation_outcome(results, report["requested_generations"], failures))
    report["unchanged_base_evaluated"] = any(
        row["adapter_enabled"] is False and row["complete"] and row["error"] is None
        and bool(row["answer"].strip()) for row in results
    )
    report["base_ablation_performed"] = report["base_ablation_requested"] and report["run_completed"]
    write_json(output, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-pack", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--capability", choices=("evidence_review", "drafting"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--content", choices=("production", "compact_research"), default="production")
    parser.add_argument("--native-only", action="store_true")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--gpu-uuid")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--adapter-only", action="store_true",
                      help="Explicit candidate-only retest; does not claim a repeated base ablation")
    mode.add_argument("--base-only", action="store_true",
                      help="Unchanged-base control; the adapter is provenance only, not loaded or evaluated")
    parser.add_argument("--direct-gpu-placement", action="store_true",
                        help="Unqualified research memory experiment; startup/reserve guards remain mandatory")
    parser.add_argument("--content-contract", choices=CONTRACTS, default=COMPACT_CONTRACT_ID)
    args = parser.parse_args()
    try:
        with research_lock():
            result = run(args)
    except Exception as exc:
        record_start_failure(args.output, exc, training=False)
        raise SystemExit(2) from exc
    raise SystemExit(0 if result["run_completed"] and result["inputs_unchanged"] else 2)
