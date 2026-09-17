"""Frozen-policy, real CPU typed-field diagnostic. No model admission or UI."""

import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import UTC, datetime

from legal.fast_interchange.compact_cpu import pinned_inventory
from legal.fast_interchange.compact_field_review import POLICY, review_field
from legal.fast_interchange.compact_span_process import IsolatedSpanReader
from scripts.acquire_compact_model_candidates import OUTPUT, ROOT, local_path
from scripts.compact_typed_field_challenge import CASES


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate_cases(cases):
    if not isinstance(cases, (list, tuple)) or len(cases) != 24:
        raise ValueError("typed_fixture_size_or_identity_invalid")
    for row in cases:
        if (
            not isinstance(row, (list, tuple))
            or len(row) != 6
            or any(type(x) is not str or not x for x in row[:5])
            or row[1] not in {"clock_time", "calendar_date", "money"}
            or row[2] not in {"source_field", "reported_event"}
            or (row[-1] is not None and (type(row[-1]) is not str or row[-1] not in row[4]))
        ):
            raise ValueError("typed_fixture_row_invalid")
    if len({row[0] for row in cases}) != 24:
        raise ValueError("typed_fixture_size_or_identity_invalid")
    if sum(row[-1] is None for row in cases) != 12:
        raise ValueError("typed_fixture_balance_invalid")


def execute(run_id, *, scoped=False):
    cases, reviewer, policy = CASES, review_field, POLICY
    extra_files = ()
    if scoped is True:
        from legal.fast_interchange.compact_clause_review import POLICY as clause_policy
        from legal.fast_interchange.compact_clause_review import review_clause
        from scripts.compact_clause_field_challenge import CASES as clause_cases

        cases, reviewer, policy = clause_cases, review_clause, clause_policy
        extra_files = (
            "legal/fast_interchange/compact_clause_review.py",
            "scripts/compact_clause_field_challenge.py",
        )
    elif scoped is not False:
        raise ValueError("invalid_scoped_policy")
    if not re.fullmatch(r"[a-z0-9-]{1,20}", run_id):
        raise ValueError("invalid_run_id")
    validate_cases(cases)
    target = local_path(OUTPUT, f"typed-fields-{run_id}.json")
    policy_path = local_path(OUTPUT, f"typed-fields-{run_id}-policy.json")
    if target.exists() or policy_path.exists():
        raise ValueError("preserve_prior_evidence")
    worker = IsolatedSpanReader(
        pinned_inventory(OUTPUT / "minilm-span-reader", "acquisition.json"),
        scratch=OUTPUT / "scratch",
        research_only=True,
    )
    report = dict(
        schema="compact_typed_field_experiment_v1",
        timestamp=datetime.now(UTC).isoformat(),
        fictional_only=True,
        attorney_reviewed=False,
        training_use_permitted=False,
        independent_human_gold=False,
        ga_ready=False,
        production_admitted=False,
        policy_installed=False,
        rows=[],
        errors=[],
        completed=False,
    )
    frozen = dict(
        policy=policy,
        fixture_sha256=digest(cases),
        no_answer_margin=0,
        model_sha256=next(r.sha256 for r in worker.files if r.path.suffix == ".safetensors"),
        implementation={
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "legal/fast_interchange/compact_field_review.py",
                "legal/fast_interchange/compact_span_reader.py",
                "legal/fast_interchange/compact_span_process.py",
                "scripts/compact_typed_field_challenge.py",
                "scripts/verify_compact_typed_fields.py",
                *extra_files,
            )
        },
    )
    with policy_path.open("x", encoding="utf-8") as stream:
        json.dump(frozen, stream, indent=2)
    report["policy_sha256"] = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    started = time.perf_counter()
    try:
        worker.warm()
        report["warm_seconds"] = time.perf_counter() - started
        for case_id, kind, basis, query, context, expected in cases:
            tick = time.perf_counter()
            passage = dict(
                source_id=case_id, matter_id="fictional-field", lane="private_record", text=context
            )
            raw = worker.extract(query=query, passages=[passage], matter_id="fictional-field")[0]
            result = reviewer(
                field_type=kind,
                basis=basis,
                query=query,
                passage=passage,
                matter_id="fictional-field",
                span=raw,
            )
            accepted = result["candidate"]["text"] if result["candidate"] else None
            report["rows"].append(
                dict(
                    id=case_id,
                    field_type=kind,
                    basis=basis,
                    expected=expected,
                    raw=raw,
                    reviewed=result,
                    exact_match=accepted == expected,
                    seconds=time.perf_counter() - tick,
                )
            )
        if hashlib.sha256(policy_path.read_bytes()).hexdigest() != report["policy_sha256"]:
            raise ValueError("frozen_policy_changed")
        rows = report["rows"]
        report["metrics"] = dict(
            cases=len(rows),
            answerable=sum(r["expected"] is not None for r in rows),
            raw_exact_matches=sum(r["raw"]["text"] == r["expected"] for r in rows),
            raw_unanswerable_acceptances=sum(
                r["expected"] is None and r["raw"]["text"] is not None for r in rows
            ),
            reviewed_exact_matches=sum(r["exact_match"] for r in rows),
            correct_answer_coverage=sum(
                r["expected"] is not None and r["exact_match"] for r in rows
            )
            / 12,
            reviewed_unanswerable_acceptances=sum(
                r["expected"] is None and r["reviewed"]["candidate"] is not None for r in rows
            ),
            answerable_wrong_acceptances=sum(
                r["expected"] is not None
                and not r["exact_match"]
                and r["reviewed"]["candidate"] is not None
                for r in rows
            ),
            blocker_counts=dict(Counter(code for r in rows for code in r["reviewed"]["blockers"])),
        )
        report["completed"] = True
    except Exception as error:
        report["errors"].append(
            dict(code=getattr(error, "code", "experiment_failed"), kind=type(error).__name__)
        )
    finally:
        try:
            worker.close()
        except Exception:
            report["completed"] = False
            report["errors"].append(dict(code="worker_cleanup_failed"))
        report.update(
            duration_seconds=time.perf_counter() - started,
            worker_stopped=worker._process is None,
            peak_resident_bytes=worker.peak_resident_bytes,
            completed_requests=worker.completed_requests,
        )
        with target.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        print(
            json.dumps(
                {k: report.get(k) for k in ("completed", "metrics", "errors", "worker_stopped")}
            )
        )
    return report["completed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scoped", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if execute(args.run_id, scoped=args.scoped) else 1)
