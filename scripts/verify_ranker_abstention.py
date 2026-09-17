"""One frozen-cutoff research experiment; never installs a ranking policy.

An answer-bearing label means the requested concrete field is provided. A
negative passage can still be useful context. This experiment must NOT hide
negative context or turn a high relevance score into a factual finding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from datetime import UTC, datetime

from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_ranker_process import IsolatedCompactRanker
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT, local_path
from scripts.compact_ranker_abstention_challenge import CALIBRATION, EVALUATION


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate_fixture(calibration, evaluation):
    seen = set()
    for prefix, rows in (("cal-", calibration), ("eval-", evaluation)):
        if len(rows) != 16:
            raise ValueError("challenge_partition_size_invalid")
        for row in rows:
            if (
                len(row) != 5
                or not row[0].startswith(prefix)
                or row[0] in seen
                or any(not isinstance(s, str) or not 1 <= len(s) <= 600 for s in row[:4])
                or (row[4] is not None and (type(row[4]) is not int or row[4] not in (0, 1)))
            ):
                raise ValueError("challenge_row_invalid")
            seen.add(row[0])
        if sum(row[4] is None for row in rows) != 8:
            raise ValueError("challenge_partition_balance_invalid")
    # Exact input overlap would contaminate a supposedly held-out partition.
    if {tuple(r[1:4]) for r in calibration} & {tuple(r[1:4]) for r in evaluation}:
        raise ValueError("challenge_partition_overlap")


def freeze_cutoff(calibration):
    if not calibration or any(not r["id"].startswith("cal-") for r in calibration):
        raise ValueError("only_calibration_rows_allowed")
    if any(
        type(r["score"]) not in (float, int) or not math.isfinite(r["score"]) for r in calibration
    ):
        raise ValueError("calibration_score_invalid")
    unsafe = [r["score"] for r in calibration if r["expected"] is None or r["top"] != r["expected"]]
    if not unsafe:
        raise ValueError("negative_calibration_required")
    # Most permissive threshold above every observed calibration false answer.
    # This intentionally may reject all answers; never relax to force usefulness.
    cutoff = math.nextafter(max(unsafe), math.inf)
    if not math.isfinite(cutoff):
        raise ValueError("finite_cutoff_unavailable")
    return cutoff


def metrics(rows, cutoff):
    if not math.isfinite(cutoff):
        raise ValueError("cutoff_invalid")
    accepted = [r for r in rows if r["score"] >= cutoff]
    false = [r for r in accepted if r["expected"] is None or r["top"] != r["expected"]]
    positives = sum(r["expected"] is not None for r in rows)
    return {
        "cases": len(rows),
        "answerable": positives,
        "accepted": len(accepted),
        "false_answer_acceptances": len(false),
        "correct_answer_acceptances": len(accepted) - len(false),
        "correct_answer_coverage": (len(accepted) - len(false)) / positives if positives else None,
        "false_acceptance_case_ids": [r["id"] for r in false],
        "raw_top1_answerable_correct": sum(
            r["expected"] is not None and r["expected"] == r["top"] for r in rows
        ),
        "abstained": len(rows) - len(accepted),
    }


def execute(run_id):
    if re.fullmatch(r"[a-z0-9-]{1,20}", run_id) is None:
        raise ValueError("challenge_id_invalid")
    validate_fixture(CALIBRATION, EVALUATION)
    target = local_path(OUTPUT, f"ranker-abstention-{run_id}.json")
    frozen = local_path(OUTPUT, f"ranker-abstention-{run_id}-cutoff.json")
    if target.exists() or frozen.exists():
        raise ValueError("preserve_prior_evidence")
    worker = IsolatedCompactRanker(
        pinned_inventory(OUTPUT / "legal-passage-reranker", "acquisition.json"),
        scratch=OUTPUT / "scratch",
        research_only=True,
    )
    report = {
        "schema": "ranker_answer_bearing_cutoff_experiment_v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "fictional_only": True,
        "training_use_permitted": False,
        "attorney_reviewed": False,
        "independent_human_gold": False,
        "ga_ready": False,
        "production_admitted": False,
        "policy_installed": False,
        "fixture_sha256": digest([CALIBRATION, EVALUATION]),
        "target": (
            "requested concrete field or attributed statement, "
            "not factual truth or all useful context"
        ),
        "selection": (
            "cutoff above largest calibration negative or wrong-answer score; no evaluation tuning"
        ),
        "model_sha256": next(r.sha256 for r in worker.files if r.path.name == "model.safetensors"),
        "implementation": {
            n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest()
            for n in (
                "scripts/verify_ranker_abstention.py",
                "scripts/compact_ranker_abstention_challenge.py",
                "legal/fast_interchange/compact_reranker.py",
                "legal/fast_interchange/compact_ranker_process.py",
            )
        },
        "partitions": {},
        "errors": [],
    }
    started = time.perf_counter()
    try:
        worker.warm()
        report["warm_seconds"] = round(time.perf_counter() - started, 6)
        for partition, fixture in (("calibration", CALIBRATION), ("evaluation", EVALUATION)):
            if partition == "evaluation":
                selection = {
                    "cutoff": freeze_cutoff(report["partitions"]["calibration"]),
                    "calibration_results_sha256": digest(report["partitions"]["calibration"]),
                    "fixture_sha256": report["fixture_sha256"],
                    "policy_installed": False,
                }
                with frozen.open("x", encoding="utf-8") as stream:
                    json.dump(selection, stream, indent=2)
                frozen_hash = hashlib.sha256(frozen.read_bytes()).hexdigest()
                report["frozen_cutoff"] = selection
            rows = report["partitions"][partition] = []
            for case in fixture:
                call_started = time.perf_counter()
                ranked = worker.rank(
                    query=case[1],
                    matter_id="fictional-answerability",
                    passages=[
                        {
                            "source_id": f"passage-{i}",
                            "matter_id": "fictional-answerability",
                            "lane": "private_record",
                            "text": text,
                        }
                        for i, text in enumerate(case[2:4])
                    ],
                )
                rows.append(
                    dict(
                        id=case[0],
                        expected=case[4],
                        top=ranked[0]["source_index"],
                        score=ranked[0]["relevance_score"],
                        scores=[
                            dict(index=r["source_index"], score=r["relevance_score"])
                            for r in ranked
                        ],
                        seconds=round(time.perf_counter() - call_started, 6),
                    )
                )
            print(json.dumps({"partition": partition, "completed": len(rows)}), flush=True)
        assert hashlib.sha256(frozen.read_bytes()).hexdigest() == frozen_hash
        report["cutoff_sha256"] = frozen_hash
        report["metrics"] = {
            p: metrics(rows, selection["cutoff"]) for p, rows in report["partitions"].items()
        }
        report["completed"] = True
    except Exception as error:
        report["completed"] = False
        report["errors"].append(
            dict(code=getattr(error, "code", "challenge_failed"), kind=type(error).__name__)
        )
    finally:
        try:
            worker.close()
        except Exception:
            report["completed"] = False
            report["errors"].append({"code": "owned_worker_cleanup_failed", "kind": "CleanupError"})
        report.update(
            duration_seconds=round(time.perf_counter() - started, 6),
            peak_resident_bytes=worker.peak_resident_bytes,
            worker_stopped=worker._process is None,
            completed_rank_requests=worker.completed_requests,
        )
        with target.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        print(
            json.dumps(
                {k: report.get(k) for k in ("completed", "metrics", "errors", "worker_stopped")}
            ),
            flush=True,
        )
    return report["completed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    raise SystemExit(0 if execute(parser.parse_args().run_id) else 1)
