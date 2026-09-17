"""Predeclared fictional QA smoke; not training data or independent legal gold."""

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime

from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_span_process import IsolatedSpanReader
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT, local_path

# Written before inference. Expected answers never enter a worker request.
# No score tuning on these rows; a changed model/policy needs new evaluation.
CASES = (
    (
        "qa-01",
        "When did the courier deliver the envelope?",
        "The courier delivered the envelope on March 6. "
        "The clerk entered the delivery record on March 9.",
        "March 6",
    ),
    (
        "qa-02",
        "When did the clerk enter the delivery record?",
        "The courier delivered the envelope on March 6. "
        "The clerk entered the delivery record on March 9.",
        "March 9",
    ),
    (
        "qa-03",
        "How much did the applicant request?",
        "The applicant requested 175 dollars. The decision approved 120 dollars.",
        "175 dollars",
    ),
    (
        "qa-04",
        "How much did the decision approve?",
        "The applicant requested 175 dollars. The decision approved 120 dollars.",
        "120 dollars",
    ),
    (
        "qa-05",
        "Who reported that the box was empty?",
        "Witness Willow reported that the box was empty. Witness Cedar said it held three folders.",
        "Witness Willow",
    ),
    (
        "qa-06",
        "How many folders did Witness Cedar say the box held?",
        "Witness Willow reported that the box was empty. Witness Cedar said it held three folders.",
        "three",
    ),
    (
        "qa-07",
        "What time is the revised pickup?",
        "The original note listed pickup at 4 p.m. The revised note changed pickup to 6 p.m.",
        "6 p.m.",
    ),
    (
        "qa-08",
        "Where did the fictional receipt place the parcel?",
        "A fictional receipt places the parcel at the south desk, not the north desk.",
        "south desk",
    ),
    (
        "qa-09",
        "What time was the envelope delivered?",
        "The envelope was delivered on March 6. The delivery time was not recorded.",
        None,
    ),
    (
        "qa-10",
        "How much did the decision approve?",
        "The applicant requested 175 dollars. No decision amount appears in this record.",
        None,
    ),
    (
        "qa-11",
        "What was actually inside the box?",
        "Witness Willow reported an empty box. Witness Cedar reported three folders. "
        "Neither account was verified.",
        None,
    ),
    (
        "qa-12",
        "What time did the pickup actually occur?",
        "The revised note scheduled pickup for 6 p.m. There is no record of the actual pickup.",
        None,
    ),
    (
        "qa-13",
        "What did the missing attachment say?",
        "The fictional email refers to an attachment, but the attachment is missing.",
        None,
    ),
    (
        "qa-14",
        "Which statute did the reviewer cite?",
        "The reviewer requested a citation check without identifying a statute.",
        None,
    ),
    (
        "qa-15",
        "When did the clerk enter the delivery record?",
        "The courier delivered the envelope on March 6. The entry date is absent.",
        None,
    ),
    (
        "qa-16",
        "Who verified Witness Cedar's statement?",
        "Witness Cedar said the box held three folders. The statement has not been verified.",
        None,
    ),
)


def execute(run_id):
    if not re.fullmatch(r"[a-z0-9-]{1,20}", run_id):
        raise ValueError("invalid_run_id")
    target = local_path(OUTPUT, f"span-reader-{run_id}.json")
    if target.exists():
        raise ValueError("preserve_prior_evidence")
    worker = IsolatedSpanReader(
        pinned_inventory(OUTPUT / "minilm-span-reader", "acquisition.json"),
        scratch=OUTPUT / "scratch",
        research_only=True,
    )
    report = dict(
        schema="compact_extractive_qa_experiment_v1",
        timestamp=datetime.now(UTC).isoformat(),
        fictional_only=True,
        attorney_reviewed=False,
        independent_human_gold=False,
        training_use_permitted=False,
        production_admitted=False,
        ga_ready=False,
        policy_installed=False,
        no_answer_margin=0,
        max_answer_tokens=32,
        model_sha256=next(r.sha256 for r in worker.files if r.path.suffix == ".safetensors"),
        fixture_sha256=hashlib.sha256(json.dumps(CASES).encode()).hexdigest(),
        implementation={
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "legal/fast_interchange/compact_span_reader.py",
                "legal/fast_interchange/compact_span_process.py",
                "legal/fast_interchange/compact_ranker_worker.py",
                "legal/fast_interchange/compact_ranker_process.py",
                "scripts/verify_compact_span_reader.py",
            )
        },
        rows=[],
        errors=[],
        completed=False,
    )
    started = time.perf_counter()
    try:
        worker.warm()
        report["warm_seconds"] = round(time.perf_counter() - started, 6)
        for case_id, query, context, expected in CASES:
            tick = time.perf_counter()
            row = worker.extract(
                query=query,
                matter_id="fictional-qa",
                passages=[
                    dict(
                        source_id=case_id,
                        matter_id="fictional-qa",
                        lane="private_record",
                        text=context,
                    )
                ],
            )[0]
            report["rows"].append(
                dict(
                    id=case_id,
                    expected=expected,
                    actual=row,
                    exact_match=row["text"] == expected,
                    seconds=round(time.perf_counter() - tick, 6),
                )
            )
        report["completed"] = True
        report["metrics"] = dict(
            total=len(report["rows"]),
            exact_match=sum(r["exact_match"] for r in report["rows"]),
            answerable_exact=sum(
                r["exact_match"] for r in report["rows"] if r["expected"] is not None
            ),
            unanswerable_abstained=sum(
                r["exact_match"] for r in report["rows"] if r["expected"] is None
            ),
            false_answer_acceptances=sum(
                r["actual"]["text"] is not None and not r["exact_match"] for r in report["rows"]
            ),
            # Keep strict match failures, but do not mislabel punctuation-only
            # differences as factual hallucination. Raw outputs remain intact.
            unanswerable_answer_acceptances=sum(
                r["expected"] is None and r["actual"]["text"] is not None for r in report["rows"]
            ),
        )
    except Exception as error:
        report["errors"].append(
            dict(code=getattr(error, "code", "experiment_failed"), kind=type(error).__name__)
        )
        report["worker_failure"] = worker.last_failure
    finally:
        try:
            worker.close()
        except Exception:
            report["completed"] = False
            report["errors"].append(dict(code="owned_worker_cleanup_failed"))
        report.update(
            duration_seconds=round(time.perf_counter() - started, 6),
            worker_stopped=worker._process is None,
            peak_resident_bytes=worker.peak_resident_bytes,
            completed_extract_requests=worker.completed_requests,
        )
        with target.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        print(
            json.dumps(
                {
                    k: report.get(k)
                    for k in ("completed", "metrics", "errors", "worker_failure", "worker_stopped")
                }
            )
        )
    return report["completed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    raise SystemExit(0 if execute(parser.parse_args().run_id) else 1)
