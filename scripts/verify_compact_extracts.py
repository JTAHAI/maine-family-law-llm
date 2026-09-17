"""Real CPU source-ID selection with non-training fictional challenge fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from threading import Event, Thread

from legal.agent_runtime import ContextSource
from legal.agent_runtime.providers import LocalModelError
from legal.fast_interchange.compact_cpu import CompactCpuWorker, pinned_inventory
from legal.fast_interchange.compact_extracts import CompactExtractSelector
from legal.security.strict_json import strict_json_load_path
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT

MATTER = "fictional-compact-extract-review"


def records(case):
    return tuple(
        ContextSource(
            f"fictional-{case['id']}-{i}",
            "private_record",
            "Fictional record",
            text,
            metadata={"matter_id": MATTER},
        )
        for i, text in enumerate(case["sources"], 1)
    )


def execute(output_name: str, fixture_name: str = "extract-selection-cases-v1.json"):
    output = OUTPUT / output_name
    if output.parent.resolve() != OUTPUT.resolve() or not output_name.endswith(".json"):
        raise ValueError("repository_local_evidence_path_required")
    if output.exists() or output.with_suffix(".jsonl").exists():
        raise ValueError("preserve_prior_evidence")
    if re.fullmatch(r"extract-selection-[a-z0-9-]+\.json", fixture_name) is None:
        raise ValueError("repository_local_fixture_required")
    fixture_path = OUTPUT / fixture_name
    fixture = strict_json_load_path(fixture_path, max_bytes=64_000, require_object=True)
    assert fixture["fictional_only"] is True and fixture["training_use_permitted"] is False
    scratch = OUTPUT / "scratch"
    for key in ("TEMP", "TMP", "HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME"):
        os.environ[key] = str(scratch)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    model = next(
        row
        for row in pinned_inventory(OUTPUT / "qwen3-compact-comparison", "acquisition.json")
        if row.path.suffix == ".gguf"
    )
    worker = CompactCpuWorker(
        model=model,
        engine=pinned_inventory(OUTPUT / "cpu-runtime", "engine-inventory.json"),
        scratch=scratch,
        research_only=True,
        threads=2,
    )
    selector = CompactExtractSelector(worker, research_only=True)
    report = {
        "schema_version": "mfl_real_compact_extract_proof_v1",
        "fictional_only": True,
        "training_use_permitted": False,
        "attorney_reviewed": False,
        "production_admitted": False,
        "ga_ready": False,
        "canonical_api_tested": False,
        "desktop_ui_tested": False,
        "frozen_package_tested": False,
        "task": "source_passage_selection_not_drafting",
        "model_sha256": model.sha256,
        "model_bytes": model.bytes,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "fixture_name": fixture_name,
        "implementation": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "legal/fast_interchange/compact_cpu.py",
                "legal/fast_interchange/compact_extracts.py",
                "legal/fast_interchange/evidence_output.py",
                "scripts/verify_compact_extracts.py",
            )
        },
        "cases": [],
        "errors": [],
    }
    try:
        for case in fixture["cases"]:
            started = time.monotonic()
            row = {
                "id": case["id"],
                "passed": False,
                "expected_blocker": case.get("expected_blocker"),
                "expected_passages": case.get("expected_passages"),
                "expected_native_requests": case.get("expected_native_requests", 0)
                if case.get("expected_blocker")
                else 1,
            }
            before = worker.completed_requests
            try:
                sources = records(case)
                plan = selector.prepare(
                    question=case["question"], sources=sources, matter_id=MATTER
                )
                row["candidate_counts"] = [len(r) for r in plan.choices]
                result = selector.run(
                    plan, approved_sha256=plan.approval_sha256, sources=sources, matter_id=MATTER
                )
                row["result"] = result
                actual = [
                    sources[s["reference"] - 1].text[s["start_offset"] : s["end_offset"]]
                    for s in result["source_spans"]
                ]
                row["selected_passages"] = actual
                row["passed"] = (
                    not case.get("expected_blocker") and actual == case["expected_passages"]
                )
            except LocalModelError as exc:
                row["error_code"] = exc.code
                row["passed"] = (
                    exc.code == case.get("expected_blocker")
                    and worker.completed_requests - before == row["expected_native_requests"]
                )
            row["duration_seconds"] = round(time.monotonic() - started, 3)
            row["native_requests"] = worker.completed_requests - before
            report["cases"].append(row)
            with output.with_suffix(".jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row) + "\n")
            print(
                json.dumps(
                    {
                        key: row[key]
                        for key in ("id", "passed", "duration_seconds", "native_requests")
                    }
                ),
                flush=True,
            )

        # A real in-flight grammar-constrained request is canceled, consumes its
        # approval, closes the owned process, then a fresh approved run restarts.
        sources = records(fixture["cases"][0])
        plan = selector.prepare(
            question=fixture["cases"][0]["question"], sources=sources, matter_id=MATTER
        )
        dispatched, outcome = Event(), []
        original_post = worker._post

        def observed_post(route, payload):
            if route == "/v1/chat/completions":
                dispatched.set()
            return original_post(route, payload)

        worker._post = observed_post

        def invoke():
            try:
                selector.run(
                    plan, approved_sha256=plan.approval_sha256, sources=sources, matter_id=MATTER
                )
                outcome.append("completed_before_cancel")
            except LocalModelError as exc:
                outcome.append(exc.code)

        thread = Thread(target=invoke, daemon=True)
        thread.start()
        assert dispatched.wait(15), "real grammar request was not dispatched"
        selector.cancel()
        thread.join(timeout=10)
        worker._post = original_post
        report["cancellation"] = {
            "outcome": outcome,
            "thread_drained": not thread.is_alive(),
            "owned_worker_stopped": worker._process is None,
        }
        assert outcome == ["fast_interchange_generation_canceled"] and not thread.is_alive()
        try:
            selector.run(
                plan, approved_sha256=plan.approval_sha256, sources=sources, matter_id=MATTER
            )
        except LocalModelError as exc:
            report["cancellation"]["replay_code"] = exc.code
        assert (
            report["cancellation"]["replay_code"]
            == "fast_interchange_compact_extract_approval_consumed"
        )
        new_plan = selector.prepare(
            question=fixture["cases"][0]["question"], sources=sources, matter_id=MATTER
        )
        restarted = selector.run(
            new_plan, approved_sha256=new_plan.approval_sha256, sources=sources, matter_id=MATTER
        )
        report["restart"] = {
            "passed": bool(restarted["source_spans"]),
            "choices": restarted["choices"],
        }
    except Exception as exc:
        report["errors"].append(
            {"type": type(exc).__name__, "code": getattr(exc, "code", "proof_failed")}
        )
    finally:
        worker.close()
        report["clean_shutdown"] = worker._process is None
        report["peak_native_resident_bytes"] = worker.peak_resident_bytes
        report["completed_native_requests"] = worker.completed_requests
        report["erased_context_tokens"] = worker.erased_tokens
        positive = [r for r in report["cases"] if not r["expected_blocker"]]
        negative = [
            r
            for r in report["cases"]
            if r["expected_blocker"] and not r["expected_native_requests"]
        ]
        abstention = [
            r for r in report["cases"] if r["expected_blocker"] and r["expected_native_requests"]
        ]
        report["summary"] = {
            "relevance_passes": sum(r["passed"] for r in positive),
            "relevance_cases": len(positive),
            "blocked_before_inference_passes": sum(r["passed"] for r in negative),
            "blocked_before_inference_cases": len(negative),
            "no_relevant_passage_passes": sum(r["passed"] for r in abstention),
            "no_relevant_passage_cases": len(abstention),
            "full_specialist_acceptance": False,
        }
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"summary": report["summary"], "errors": report["errors"]}), flush=True)
    return (
        not report["errors"]
        and len(report["cases"]) == len(fixture["cases"])
        and all(row["passed"] for row in report["cases"])
        and report.get("restart", {}).get("passed") is True
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--fixture-name", default="extract-selection-cases-v1.json")
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.output_name, args.fixture_name) else 1)
