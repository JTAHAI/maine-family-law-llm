"""Use production generation code with an unadmitted adapter and shared local base.

Only small hash-bound diagnostic metadata is created; model files are not copied.
This is a backend-generation test, not admission, desktop E2E or legal certification.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from importlib.metadata import version
from pathlib import Path
from threading import Event

from scripts.train_mfl_adapter_continuation import ROOT, sha, write_json


def evaluation_resources(args, exclusive_check):
    """GPU runs stay exclusive; explicit small CPU diagnostics share no GPU.

    This is a research-runner policy, not a production admission override. The
    CPU option reserves 4 GiB beyond the backend's 8 GiB ceiling, lowers only
    this process's priority, and is never allowed for the full regression.
    """
    if not getattr(args, "shared_host_cpu", False):
        exclusive_check()
        return {"policy": "exclusive_model_workload", "cpu_threads": 4}
    if args.device != "cpu" or args.frozen_regression:
        raise ValueError("shared-host diagnostic requires CPU and development fixtures")
    import psutil

    available = psutil.virtual_memory().available
    if available < 12 * 1024**3:
        raise RuntimeError("shared-host CPU diagnostic requires 12 GiB available RAM")
    if not hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS"):
        raise RuntimeError("shared-host CPU diagnostic is qualified only on Windows")
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    # Set before importing Torch. force_cpu is also passed to the real backend.
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    return {
        "policy": "bounded_shared_host_cpu_development_only",
        "cpu_threads": 2,
        "initial_available_memory_bytes": available,
        "required_initial_available_bytes": 12 * 1024**3,
        "remaining_memory_floor_bytes": 4 * 1024**3,
        "max_cases": 8,
        "priority": "below_normal",
        "gpu_access": False,
        "external_processes_changed": False,
    }


def check_shared_memory(resources):
    if resources["policy"] == "bounded_shared_host_cpu_development_only":
        import psutil

        if psutil.virtual_memory().available < resources["remaining_memory_floor_bytes"]:
            raise RuntimeError("shared-host CPU diagnostic stopped to preserve memory headroom")


def research_registry(parent: Path, adapter: Path, root: Path):
    from legal.fast_interchange.worker import ArtifactInventory, HotSwapRegistry

    for original in (parent, adapter, root):
        if any(
            p.is_symlink() or getattr(p, "is_junction", lambda: False)()
            for p in (original, *original.parents)
        ):
            raise ValueError("linked diagnostic path forbidden")
    parent, adapter, root = parent.resolve(), adapter.resolve(), root.resolve()
    if root != (ROOT / "dist/model-candidates").resolve():
        raise ValueError("diagnostic root must be repository model-candidates")
    if not parent.is_relative_to(root) or not adapter.is_relative_to(root):
        raise ValueError("diagnostic artifacts must stay inside repository model-candidates")
    releases = json.loads((parent / "releases.json").read_text(encoding="utf-8"))
    artifacts = json.loads((parent / "artifacts.json").read_text(encoding="utf-8"))
    old = HotSwapRegistry.from_dicts(root=parent, releases=releases, artifacts=artifacts)
    if len(old.releases) != 1:
        raise ValueError("single specialist parent required")
    old_release = next(iter(old.releases.values()))
    if old_release.capability != "evidence_review":
        raise ValueError("evidence pilot only")
    old.bindings[old_release.release_id].verify(old.root)
    # Preserve source inventories, rebasing paths without moving a single model file.
    binding = copy.deepcopy(artifacts["bindings"][0])
    prefix = parent.relative_to(root).as_posix()
    binding["base_dir"] = prefix + "/" + binding["base_dir"]
    for key in ("base_inventory", "tokenizer_inventory"):
        for item in binding[key]["files"]:
            item["path"] = prefix + "/" + item["path"]
    binding["adapter_dir"] = adapter.relative_to(root).as_posix()
    files = []
    for path in sorted(adapter.rglob("*")):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError("linked diagnostic artifact forbidden")
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha(path),
                }
            )
    config_path = binding["adapter_dir"] + "/adapter_config.json"
    binding["adapter_config"] = next(item for item in files if item["path"] == config_path)
    binding["adapter_inventory"] = {
        "files": [item for item in files if item["path"] != config_path]
    }
    # New diagnostic identity is content-bound and cannot inherit a parent's admission.
    fingerprint = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    identity = "evidence-pilot-" + fingerprint[:20]
    binding.update(release_id=identity, release_fingerprint=fingerprint)
    release = copy.deepcopy(releases["releases"][0])
    release.update(
        release_id=identity,
        model_id=identity,
        release_fingerprint=fingerprint,
        admission="unadmitted_local_research",
        promotion_authority=False,
        review_required=True,
        adapter_config_sha256=binding["adapter_config"]["sha256"],
    )
    for key in ("base_inventory", "tokenizer_inventory", "adapter_inventory"):
        release[key + "_sha256"] = ArtifactInventory.from_dict(binding[key]).digest
    releases["releases"], artifacts["bindings"] = [release], [binding]
    registry = HotSwapRegistry.from_dicts(root=root, releases=releases, artifacts=artifacts)
    registry.bindings[identity].verify(root)
    return registry


def run(args) -> dict:
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("new repository-local diagnostic output required")
    sys.path.insert(0, str(args.model_project / "scripts"))
    from build_mfl_evidence_corpus import EvidenceCase, consumer_prompt_builder
    from evaluate_mfl_evidence_research_v2 import score
    from run_mfl_practical_delivery import check_no_training_process

    resources = evaluation_resources(args, check_no_training_process)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1")
    import torch

    from legal.fast_interchange.admission import Compatibility
    from legal.fast_interchange.worker import TransformersPeftAdapterBackend

    torch.set_num_threads(resources["cpu_threads"])
    registry = research_registry(args.parent_pack, args.adapter, ROOT / "dist/model-candidates")
    release = next(iter(registry.releases.values()))
    binding = registry.bindings[release.release_id]
    baseline_hash = None
    if args.frozen_regression:
        from scripts.run_mfl_specialist_regression import FIXTURES, verify_regression_baseline

        if args.fixtures:
            raise ValueError("cannot substitute fixtures in the canonical regression")
        baseline_hash = verify_regression_baseline(args.model_project, "evidence_review")
        args.fixtures = [
            args.model_project / "data/evaluation" / name for name in FIXTURES["evidence_review"]
        ]
    fixtures = []
    for path in args.fixtures:
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("training_use_permitted") is not False:
            raise ValueError("fixture training-isolation marker required")
        fixtures.extend((path, case) for case in document["cases"])
    if not fixtures or len({(str(path), c["id"]) for path, c in fixtures}) != len(fixtures):
        raise ValueError("nonempty, unique evaluation cases required")
    if args.frozen_regression and len(fixtures) != 104:
        raise ValueError("canonical evidence regression must contain all 104 cases")
    if len(fixtures) > resources.get("max_cases", len(fixtures)):
        raise ValueError("shared-host CPU diagnostic permits at most eight development cases")
    pins = {
        str(path.resolve()): sha(path)
        for path in [
            *args.fixtures,
            Path(__file__),
            ROOT / "legal/fast_interchange/worker.py",
            ROOT / "legal/agent_runtime/runtime.py",
            ROOT / "legal/fast_interchange/specialists.py",
            args.model_project / "scripts/evaluate_mfl_evidence_research_v2.py",
            args.model_project / "scripts/build_mfl_evidence_corpus.py",
        ]
    }
    backend = TransformersPeftAdapterBackend(
        allow_cpu=args.device == "cpu",
        force_cpu=args.device == "cpu",
        cpu_threads=resources["cpu_threads"],
    )
    backend.configure(
        Compatibility(
            runtime_abi="fast_interchange_hotswap_v1",
            **{
                name + "_version": version(name)
                for name in ("torch", "transformers", "peft", "safetensors")
            },
            quantization="fp32" if args.device == "cpu" else "bf16",
            max_context_tokens=2048,
            max_new_tokens=256,
            max_resident_bytes=8 * 1024**3,
            prompt_template_sha256=release.prompt_template_sha256,
        )
    )
    prompt = consumer_prompt_builder(ROOT)
    results, generation_errors, fatal_errors = [], [], []
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        output.with_suffix(".registry.json"),
        {
            "root": str(registry.root),
            "releases": registry.release_document,
            "artifacts": registry.artifact_document,
            "production_admitted": False,
            "model_files_copied": 0,
        },
    )
    started = time.monotonic()
    activation_seconds, peak = None, None
    try:
        check_shared_memory(resources)
        backend.activate(root=registry.root, binding=binding, release=release)
        activation_seconds = time.monotonic() - started
        for path, case in fixtures:
            check_shared_memory(resources)
            packet = EvidenceCase(
                case["id"],
                "evaluation",
                "challenge",
                case["question"],
                tuple(case["sources"]),
                "",
                (),
            )
            start = time.monotonic()
            answer, error = "", None
            backend.clear_context()
            backend.set_cancellation(Event(), start + 300)
            try:
                response = backend.complete(
                    release=release, messages=[{"role": "user", "content": prompt(packet)}]
                )
                answer = response["choices"][0]["message"]["content"]
            except Exception as exc:
                error = type(exc).__name__ + ": " + str(exc)
            finally:
                backend.clear_context()
            result = {
                "case_id": case["id"],
                "fixture": path.name,
                "answer": answer,
                "error": error,
                "seconds": round(time.monotonic() - start, 3),
                **score(case, answer),
            }
            result["mechanical_pass"] &= error is None
            results.append(result)
            write_json(
                output.with_suffix(".progress.json"),
                {"completed": len(results), "total": len(fixtures), "results": results},
            )
            print(json.dumps(result), flush=True)
            if error:
                # A bounded completion failure is a failed case, not permission
                # to leave the rest of a frozen regression unattempted.
                generation_errors.append({"case_id": case["id"], "error": error})
    except Exception as exc:
        fatal_errors.append(type(exc).__name__ + ": " + str(exc))
    finally:
        try:
            backend.clear_context()
            peak = torch.cuda.max_memory_allocated() if args.device == "cuda" else None
        except Exception as exc:
            fatal_errors.append("context cleanup: " + type(exc).__name__)
        finally:
            try:
                backend.close()
            except Exception as exc:
                fatal_errors.append("backend cleanup: " + type(exc).__name__)
    try:
        binding.verify(registry.root)
    except Exception as exc:
        fatal_errors.append("artifact recheck: " + type(exc).__name__)
    unchanged = all(sha(Path(path)) == digest for path, digest in pins.items())
    report = {
        "schema": "mfl.adapter-pilot-generation.v1",
        "passed": sum(r["mechanical_pass"] for r in results),
        "total": len(results),
        "requested": len(fixtures),
        "completed": len(results) == len(fixtures) and not fatal_errors,
        "all_generations_successful": not generation_errors,
        "results": results,
        "generation_errors": generation_errors,
        "fatal_errors": fatal_errors,
        # Retain the legacy aggregate field for downstream readers.
        "errors": [item["error"] for item in generation_errors] + fatal_errors,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "activation_seconds": round(activation_seconds, 3)
        if activation_seconds is not None
        else None,
        "peak_allocated_bytes": peak,
        "artifact_sha256": sha(args.adapter / "adapter_model.safetensors"),
        "input_sha256": pins,
        "inputs_unchanged": unchanged,
        "device": args.device,
        "resource_policy": resources,
        "model_files_copied": 0,
        "production_admitted": False,
        "desktop_e2e": False,
        "attorney_reviewed": False,
        "basis": "production_backend_generation_only_not_legal_quality_certification",
        "evaluation_role": (
            "previously_consulted_frozen_regression"
            if args.frozen_regression
            else "development_experiment_selection_not_final_holdout"
        ),
        "regression_baseline_sha256": baseline_hash,
    }
    write_json(output, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pack", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--fixtures", nargs="+", type=Path, default=[])
    parser.add_argument("--frozen-regression", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--shared-host-cpu", action="store_true")
    report = run(parser.parse_args())
    print(json.dumps({k: report[k] for k in ("passed", "total", "completed", "inputs_unchanged")}))
    raise SystemExit(
        0
        if report["passed"] == report["requested"]
        and report["inputs_unchanged"]
        and report["completed"]
        and report["requested"] > 0
        else 2
    )
