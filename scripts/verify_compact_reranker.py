"""Compare existing passage-ranker weights on fictional selection cases.

This is a relevance comparison, not admission, claim support, or a calibrated
abstention test. Expected answers never enter the model's inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time

from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_extracts import CompactExtractSelector
from legal.fast_interchange.compact_ranker_process import IsolatedCompactRanker
from legal.fast_interchange.compact_reranker import CompactPassageReranker
from legal.security.strict_json import strict_json_load_path
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT
from scripts.verify_compact_extracts import MATTER, records


def execute(
    output_name: str,
    fixture_name: str,
    *,
    isolated: bool = False,
    candidate="legal-passage-reranker",
):
    if candidate not in {"legal-passage-reranker", "mixedbread-reranker-comparison"}:
        raise ValueError("candidate_not_allowlisted")
    for value, pattern in (
        (output_name, r"reranker-[a-z0-9-]+\.json"),
        (fixture_name, r"extract-selection-[a-z0-9-]+\.json"),
    ):
        if re.fullmatch(pattern, value) is None:
            raise ValueError("repository_local_evidence_required")
    output, fixture_path = OUTPUT / output_name, OUTPUT / fixture_name
    if output.exists() or output.with_suffix(".jsonl").exists():
        raise ValueError("preserve_prior_evidence")
    fixture = strict_json_load_path(fixture_path, max_bytes=64_000, require_object=True)
    assert fixture["fictional_only"] is True and fixture["training_use_permitted"] is False
    scratch = OUTPUT / "scratch"
    for key in ("TEMP", "TMP", "HF_HOME", "TORCH_HOME", "XDG_CACHE_HOME"):
        os.environ[key] = str(scratch)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    files = pinned_inventory(OUTPUT / candidate, "acquisition.json")
    ranker = (
        IsolatedCompactRanker(files, scratch=scratch, research_only=True)
        if isolated
        else CompactPassageReranker(files, research_only=True)
    )
    # Prepare uses only the source/privacy guards, never inference on this worker.
    selector = CompactExtractSelector(None, research_only=True)
    report = {
        "schema_version": "compact_reranker_fictional_comparison_v1",
        "fictional_only": True,
        "training_use_permitted": False,
        "attorney_reviewed": False,
        "production_admitted": False,
        "ga_ready": False,
        "task": "passage_relevance_only",
        "candidate": candidate,
        "abstention_calibrated": False,
        "isolated_process": isolated,
        "desktop_ui_tested": False,
        "frozen_package_tested": False,
        "fixture_name": fixture_name,
        "fixture_sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        "model_bytes": sum(row.bytes for row in files),
        "weights_sha256": next(row.sha256 for row in files if row.path.suffix == ".safetensors"),
        "implementation": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "legal/fast_interchange/compact_extracts.py",
                "legal/fast_interchange/compact_reranker.py",
                "legal/fast_interchange/compact_ranker_process.py",
                "legal/fast_interchange/compact_ranker_worker.py",
                "scripts/verify_compact_reranker.py",
            )
        },
        "cases": [],
        "not_evaluated": [],
        "errors": [],
    }
    try:
        if isolated:
            started = time.monotonic()
            report["warm"] = ranker.warm()
            report["warm_seconds"] = round(time.monotonic() - started, 3)
        for case in fixture["cases"]:
            if case.get("expected_blocker"):
                report["not_evaluated"].append(
                    {"id": case["id"], "reason": "ranker_has_no_calibrated_abstention_threshold"}
                )
                continue
            started = time.monotonic()
            source_rows = records(case)
            plan = selector.prepare(
                question=case["question"], sources=source_rows, matter_id=MATTER
            )
            top_passages, ranked_sources = [], []
            for reference in range(1, len(source_rows) + 1):
                candidates = [span for span in plan.candidates if span.reference == reference]
                passages = [
                    {
                        "source_id": f"fictional-{reference}-{span.candidate_id}",
                        "matter_id": MATTER,
                        "lane": "private_record",
                        "text": span.text,
                    }
                    for span in candidates
                ]
                ranked = ranker.rank(query=case["question"], passages=passages, matter_id=MATTER)
                top = candidates[ranked[0]["source_index"]]
                assert ranked[0]["source_sha256"] == hashlib.sha256(top.text.encode()).hexdigest()
                top_passages.append(top.text)
                ranked_sources.append({"reference": reference, "ranks": ranked})
            row = {
                "id": case["id"],
                "selected_passages": top_passages,
                "expected_passages": case["expected_passages"],
                "passed": top_passages == case["expected_passages"],
                "rankings": ranked_sources,
                "duration_seconds": round(time.monotonic() - started, 3),
            }
            report["cases"].append(row)
            with output.with_suffix(".jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row) + "\n")
            print(
                json.dumps({key: row[key] for key in ("id", "passed", "duration_seconds")}),
                flush=True,
            )
    except Exception as exc:
        report["errors"].append(
            {"type": type(exc).__name__, "code": getattr(exc, "code", "proof_failed")}
        )
    finally:
        ranker.close()
        if isolated:
            report["worker_starts"] = ranker.worker_starts
            report["peak_resident_bytes"] = ranker.peak_resident_bytes
            report["clean_shutdown"] = ranker._process is None
            report["worker_failure"] = ranker.last_failure
        report["summary"] = {
            "relevance_passes": sum(row["passed"] for row in report["cases"]),
            "relevance_cases": len(report["cases"]),
            "not_evaluated_cases": len(report["not_evaluated"]),
            "full_specialist_acceptance": False,
        }
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"summary": report["summary"], "errors": report["errors"]}), flush=True)
    return (
        not report["errors"]
        and len(report["cases"]) + len(report["not_evaluated"]) == len(fixture["cases"])
        and all(row["passed"] for row in report["cases"])
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--fixture-name", default="extract-selection-holdout-v2.json")
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument(
        "--candidate",
        default="legal-passage-reranker",
        choices=["legal-passage-reranker", "mixedbread-reranker-comparison"],
    )
    args = parser.parse_args()
    raise SystemExit(
        0
        if execute(
            args.output_name, args.fixture_name, isolated=args.isolated, candidate=args.candidate
        )
        else 1
    )
