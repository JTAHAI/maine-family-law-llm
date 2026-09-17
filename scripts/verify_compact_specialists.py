"""Real CPU model + production host-boundary proof using fictional fixtures only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from threading import Thread

from legal.agent_runtime import ContextSource, LocalAgentRunRequest, LocalAgentRuntime
from legal.agent_runtime.providers import LocalModelError
from legal.fast_interchange.compact_cpu import (
    CompactCpuWorker,
    CompactResearchClient,
    pinned_inventory,
)
from legal.fast_interchange.compact_reranker import CompactPassageReranker
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


def evidence_summary(report):
    rows = report["results"]
    return {
        "cases_executed": len(rows),
        "host_status_counts": dict(Counter(row["host"]["status"] for row in rows)),
        "model_transport_completed": sum(bool(row["raw_answer"]) for row in rows),
        "full_feature_acceptance_passes": 0,
        "semantic_review_required": True,
        "quote_binding_is_not_semantic_quality": True,
    }


def run(
    output: Path,
    *,
    smoke: bool = False,
    fixture_path: Path | None = None,
    candidate: str = "qwen-drafting-base",
    reasoning_budget: int = 0,
):
    if output.exists() or not output.resolve().is_relative_to(OUTPUT.resolve()):
        raise ValueError("new_compact_evidence_path_required")
    scratch = OUTPUT / "scratch"
    scratch.mkdir(exist_ok=True)
    for key in ("TEMP", "TMP", "HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME"):
        os.environ[key] = str(scratch)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONDONTWRITEBYTECODE="1")
    if candidate not in {"qwen-drafting-base", "qwen3-compact-comparison"}:
        raise ValueError("candidate_not_in_research_catalog")
    model_files = pinned_inventory(OUTPUT / candidate, "acquisition.json")
    engine_files = pinned_inventory(OUTPUT / "cpu-runtime", "engine-inventory.json")
    model = next(r for r in model_files if r.path.suffix == ".gguf")
    worker = CompactCpuWorker(
        model=model,
        engine=engine_files,
        scratch=scratch,
        research_only=True,
        threads=2,
        reasoning_budget=reasoning_budget,
    )
    report = {
        "schema_version": "mfl_compact_real_cpu_proof_v1",
        "fictional_only": True,
        "trained_specialist_adapters": False,
        "production_admitted": False,
        "ga_ready": False,
        "desktop_ui_tested": False,
        "frozen_package_tested": False,
        "model_sha256": model.sha256,
        "model_bytes": model.bytes,
        "candidate": candidate,
        "threads": 2,
        "generation_profile": worker.generation_profile,
        "reasoning_budget": reasoning_budget,
        "max_new_tokens": worker.completion_limit,
        "results": [],
        "errors": [],
        "fixtures": [],
    }
    report["implementation"] = [
        {"path": path, "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
        for path in (
            "legal/fast_interchange/compact_cpu.py",
            "legal/fast_interchange/compact_reranker.py",
            "legal/agent_runtime/runtime.py",
            "scripts/verify_compact_specialists.py",
        )
    ]
    journal = output.with_suffix(".jsonl")
    if journal.exists():
        raise ValueError("new_compact_evidence_path_required")
    try:
        worker.start()
        report["startup_seconds"] = worker.start_seconds
        # Native health is public; generation and state controls must require the secret.
        with worker._session.post(
            worker._endpoint + "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "READY"}]},
            timeout=3,
        ) as r:
            report["unauthenticated_generation_denied"] = r.status_code == 401
        report["native_engine_health"] = True
        paths = (
            [fixture_path]
            if fixture_path
            else [
                ROOT / "dist/model-candidates/framing-v9-20260906" / name
                for name in ("diagnostic-cases.json", "adversarial-cases.json")
            ]
        )
        for path in paths:
            if not path.resolve().is_relative_to((ROOT / "dist").resolve()):
                raise ValueError("fictional_fixture_must_be_repository_local")
            fixture = json.loads(path.read_text(encoding="utf-8"))
            if (
                fixture.get("fictional_only") is not True
                or fixture.get("training_use_permitted") is not False
            ):
                raise ValueError("fictional_fixture_required")
            report["fixtures"].append(
                {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            )
            cases = fixture["cases"]
            if smoke:
                cases = [
                    next(r for r in cases if r["capability"] == cap)
                    for cap in ("evidence_review", "drafting")
                ]
            for case in cases:
                started = time.monotonic()
                client = CompactResearchClient(worker, case["capability"])
                runtime = LocalAgentRuntime(client)
                sources = tuple(
                    ContextSource(
                        source_id=f"fictional-{case['id']}-{i}",
                        lane="private_record",
                        title=f"Fictional record {i}",
                        text=text,
                        locator=f"paragraph {i}",
                        metadata={"matter_id": "fictional-compact-ga"},
                    )
                    for i, text in enumerate(case["sources"], 1)
                )
                manifest, _, _ = runtime.preview(
                    question=case["question"], sources=sources, run_id=case["id"]
                )
                result = runtime.run(
                    LocalAgentRunRequest(
                        question=case["question"],
                        sources=sources,
                        approved_manifest_sha256=manifest.manifest_sha256,
                        matter_id="fictional-compact-ga",
                        run_id=case["id"],
                        manifest_created_at=manifest.created_at,
                    )
                )
                row = {
                    "id": case["id"],
                    "capability": case["capability"],
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "raw_answer": client.last_raw_response,
                    "expected_semantics": case["expected_semantics"],
                    "semantic_review": "pending_human_or_agent_inspection_not_automatic_pass",
                    "host": result.to_dict(),
                }
                report["results"].append(row)
                with journal.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row) + "\n")
                print(
                    json.dumps(
                        {
                            "id": case["id"],
                            "status": result.status,
                            "seconds": row["duration_seconds"],
                            "raw_answer": client.last_raw_response,
                        }
                    ),
                    flush=True,
                )
        cancellation = []

        def long_request():
            try:
                worker.complete(
                    [{"role": "user", "content": "Count from 1 to 2000, one number per line."}]
                )
                cancellation.append("unexpected_completion")
            except LocalModelError as exc:
                cancellation.append(exc.code)

        thread = Thread(target=long_request)
        thread.start()
        time.sleep(0.3)
        worker.cancel()
        thread.join(timeout=8)
        report["cancellation"] = {
            "worker_joined": not thread.is_alive(),
            "outcomes": cancellation,
            "owned_process_stopped": worker._process is None,
        }
        if thread.is_alive():
            worker.close()
            raise ValueError("cancellation_did_not_finish")
        worker.start()
        report["restart_answer"] = worker.complete(
            [{"role": "user", "content": "Reply with READY only."}]
        )
        report["peak_native_resident_bytes"] = worker.peak_resident_bytes
        report["completed_native_requests"] = worker.completed_requests
        report["erased_context_tokens"] = worker.erased_tokens
    except Exception as exc:
        report["errors"].append(getattr(exc, "code", type(exc).__name__))
        raise
    finally:
        worker.close()
        report["clean_shutdown"] = worker._process is None
        report["summary"] = evidence_summary(report)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    passages = [
        {
            "source_id": f"fictional-passage-{i}",
            "text": text,
            "matter_id": "fictional-compact-ga",
            "lane": "private_record",
        }
        for i, text in enumerate(
            [
                "The fictional agreement permits termination with thirty days written notice.",
                "The fictional agreement sets payment at two hundred dollars per month.",
                "The fictional review packet includes a note that the attachment was not received.",
            ]
        )
    ]
    reranker = CompactPassageReranker(
        pinned_inventory(OUTPUT / "legal-passage-reranker", "acquisition.json"), research_only=True
    )
    started = time.monotonic()
    try:
        ranks = reranker.rank(
            query="What notice must be given to terminate the agreement?",
            passages=passages,
            matter_id="fictional-compact-ga",
        )
    except Exception as exc:
        report["errors"].append(getattr(exc, "code", type(exc).__name__))
        report["reranker"] = {"status": "failed", "top_result_correct": False}
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise
    finally:
        reranker.close()
    report["reranker"] = {
        "ranks": ranks,
        "expected_first_source": "fictional-passage-0",
        "top_result_correct": ranks[0]["source_id"] == "fictional-passage-0",
        "seconds": round(time.monotonic() - started, 3),
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({k: v for k, v in report.items() if k not in {"results", "fixtures"}}, indent=2)
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--fixture", type=Path)
    p.add_argument(
        "--candidate",
        choices=["qwen-drafting-base", "qwen3-compact-comparison"],
        default="qwen-drafting-base",
    )
    p.add_argument("--reasoning-budget", type=int, choices=[0, 256], default=0)
    args = p.parse_args()
    run(
        args.output,
        smoke=args.smoke,
        fixture_path=args.fixture,
        candidate=args.candidate,
        reasoning_budget=args.reasoning_budget,
    )


if __name__ == "__main__":
    main()
