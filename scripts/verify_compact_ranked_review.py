"""Real canonical-service shortlists and separate calibration/heldout measurements.

No threshold is installed in the product. Labels and calibration choices never
enter inference. All cases are agent-authored fiction, not attorney gold.
"""

import argparse
import hashlib
import json
import math
import re
import time

from legal.agent_runtime import ContextSource
from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_ranked_review import CompactRankedReview
from legal.fast_interchange.compact_ranker_process import IsolatedCompactRanker
from legal.security.strict_json import strict_json_load_path
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT


def calibration_threshold(rows):
    """Exploratory zero-false-positive calibration rule, not a production policy."""
    negative = [row["top_score"] for row in rows if not row["relevant"]]
    if not negative or any(
        type(score) not in (int, float) or not math.isfinite(score) for score in negative
    ):
        raise ValueError("finite_negative_calibration_required")
    return math.nextafter(max(negative), math.inf)


def metrics(rows, threshold):
    positive = [row for row in rows if row["relevant"]]
    negative = [row for row in rows if not row["relevant"]]
    return {
        "positive_cases": len(positive),
        "negative_cases": len(negative),
        "top1_relevant_cases": sum(row["top1_relevant"] for row in positive),
        "all_requested_passages_in_top3": sum(row["all_relevant_in_top3"] for row in positive),
        "recall_at3": sum(row["recall_at3"] for row in positive) / len(positive)
        if positive
        else None,
        "experimental_threshold": threshold,
        "experimental_false_accepts": sum(row["top_score"] >= threshold for row in negative),
        "experimental_positive_abstentions": sum(row["top_score"] < threshold for row in positive),
        "experimental_wrong_top1_accepts": sum(
            row["top_score"] >= threshold and not row["top1_relevant"] for row in positive
        ),
        "threshold_is_not_production_policy": True,
    }


def execute(output_name):
    if re.fullmatch(r"ranked-review-quality-[a-z0-9-]+\.json", output_name) is None:
        raise ValueError("repository_evidence_name_required")
    output = OUTPUT / output_name
    if output.exists():
        raise ValueError("preserve_prior_evidence")
    fixture_path = OUTPUT / "ranker-calibration-and-heldout-v1.json"
    data = strict_json_load_path(fixture_path, max_bytes=64000, require_object=True)
    assert (
        data["fictional_only"]
        and not data["training_use_permitted"]
        and not data["attorney_reviewed"]
    )
    all_ids = [case["id"] for split in ("calibration", "test") for case in data[split]]
    assert len(set(all_ids)) == len(all_ids)
    # Freeze expected labels now, before loading any weights or measuring scores.
    fixture_hash = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    files = pinned_inventory(OUTPUT / "legal-passage-reranker", "acquisition.json")
    worker = IsolatedCompactRanker(files, scratch=OUTPUT / "scratch", research_only=True)
    service = CompactRankedReview(worker, research_only=True)
    report = {
        "schema_version": "compact_ranked_review_quality_v1",
        "fictional_only": True,
        "training_use_permitted": False,
        "attorney_reviewed": False,
        "fixture_sha256": fixture_hash,
        "data_basis": data["basis"],
        "production_admitted": False,
        "ga_ready": False,
        "production_ui_tested": False,
        "frozen_package_tested": False,
        "threshold_installed": False,
        "weights_sha256": next(r.sha256 for r in files if r.path.name == "model.safetensors"),
        "implementation_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "legal/fast_interchange/compact_ranked_review.py",
                "legal/fast_interchange/ranked_evidence_output.py",
                "scripts/verify_compact_ranked_review.py",
            )
        },
        "calibration": [],
        "test": [],
        "errors": [],
    }
    started = time.monotonic()
    try:
        worker.warm()
        report["warm_seconds"] = round(time.monotonic() - started, 3)
        for split in ("calibration", "test"):
            if split == "test":
                threshold = calibration_threshold(report["calibration"])
                report["threshold_frozen_before_test"] = threshold
            for case in data[split]:
                before = time.monotonic()
                assert len(case["sentences"]) >= 6  # top3 must exclude some passages
                source = ContextSource(
                    case["id"],
                    "private_record",
                    "Fictional quality fixture",
                    " ".join(case["sentences"]),
                    metadata={"matter_id": "fictional-ranker-quality"},
                )
                plan = service.prepare(
                    question=case["query"], sources=(source,), matter_id="fictional-ranker-quality"
                )
                assert [row.text for row in plan.extract.candidates] == case["sentences"]
                result = service.run(
                    plan,
                    approved_sha256=plan.approval_sha256,
                    sources=(source,),
                    matter_id="fictional-ranker-quality",
                )
                ranks = result["rankings"][0]["ranks"]
                top3 = [row["source_index"] for row in ranks[:3]]
                relevant = case["relevant"]
                row = {
                    "id": case["id"],
                    "relevant": relevant,
                    "top3": top3,
                    "top1_relevant": ranks[0]["source_index"] in relevant,
                    "all_relevant_in_top3": bool(relevant) and set(relevant).issubset(top3),
                    "recall_at3": len(set(relevant).intersection(top3)) / len(relevant)
                    if relevant
                    else None,
                    "top_score": ranks[0]["relevance_score"],
                    "rankings": ranks,
                    "source_spans": result["source_spans"],
                    "answer": result["answer"],
                    "relevance_stated_as_unknown": "relevance is unknown" in result["answer"],
                    "absence_not_inferred": "cannot establish" in result["answer"],
                    "duration_seconds": round(time.monotonic() - before, 3),
                }
                report[split].append(row)
                print(
                    json.dumps(
                        {
                            key: row[key]
                            for key in ("id", "top3", "top1_relevant", "duration_seconds")
                        }
                    ),
                    flush=True,
                )
        assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == fixture_hash
        report["metrics"] = {
            split: metrics(report[split], threshold) for split in ("calibration", "test")
        }
        report["measurement_completed"] = True
    except Exception as exc:
        report["errors"].append(
            {"type": type(exc).__name__, "code": getattr(exc, "code", "proof_failed")}
        )
    finally:
        worker.close()
        report.update(
            clean_shutdown=worker._process is None,
            worker_starts=worker.worker_starts,
            rank_requests=worker.completed_requests,
            peak_resident_bytes=worker.peak_resident_bytes,
            duration_seconds=round(time.monotonic() - started, 3),
        )
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"metrics": report.get("metrics"), "errors": report["errors"]}), flush=True)
    test = report.get("metrics", {}).get("test", {})
    return bool(
        report.get("measurement_completed")
        and not report["errors"]
        and test.get("experimental_false_accepts") == 0
        and test.get("experimental_positive_abstentions") == 0
        and test.get("experimental_wrong_top1_accepts") == 0
        and test.get("all_requested_passages_in_top3") == test.get("positive_cases")
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-name", required=True)
    raise SystemExit(0 if execute(parser.parse_args().output_name) else 1)
