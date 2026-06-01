#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class StepResult:
    name: str
    command: list[str]
    required: bool
    returncode: int | None = None
    status: str = "not_run"
    stdout: str = ""
    stderr: str = ""
    parsed_stdout: Any | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "required": self.required,
            "returncode": self.returncode,
            "status": self.status,
            "stdout": self.stdout[-8000:],
            "stderr": self.stderr[-8000:],
            "parsed_stdout": self.parsed_stdout,
            "error": self.error,
        }


@dataclass
class AuthorityDataProductRun:
    status: str
    generated_at: str
    repo_root: str
    data_root: str
    eval_root: str
    output: str
    steps: list[StepResult] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_manual_actions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "repo_root": self.repo_root,
            "data_root": self.data_root,
            "eval_root": self.eval_root,
            "output": self.output,
            "steps": [step.as_dict() for step in self.steps],
            "blockers": self.blockers,
            "next_manual_actions": self.next_manual_actions,
        }


def _run_step(name: str, command: list[str], *, timeout: int, required: bool) -> StepResult:
    result = StepResult(name=name, command=command, required=required)
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result.returncode = None
        result.status = "blocked"
        result.error = f"timeout after {timeout}s"
        result.stdout = exc.stdout or ""
        result.stderr = exc.stderr or ""
        return result
    result.returncode = completed.returncode
    result.stdout = completed.stdout
    result.stderr = completed.stderr
    result.status = "pass" if completed.returncode == 0 else "blocked"
    try:
        if completed.stdout.strip():
            result.parsed_stdout = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result.parsed_stdout = None
    return result


def _script(name: str) -> str:
    return str(ROOT / "scripts" / name)


def _command_plan(
    *,
    data_root: Path,
    eval_root: Path,
    previous_manifest: Path | None,
    timeout: float,
    delay: float,
    max_retries: int,
    strict_content_type: bool,
    skip_ingest: bool,
    max_targets: int | None,
    build_followup_targets: bool,
    ingest_followup_targets: bool,
    max_derived_targets: int | None,
    derived_batch_size: int,
    derived_batch_timeout: int,
    require_direct_authority: bool,
    require_retrieval_smoke: bool,
    retrieval_top_k: int,
    retrieval_min_case_count: int,
    retrieval_min_recall_at_20: float,
    retrieval_max_case_count: int | None,
    require_gold_eval_pack: bool,
    require_release_metrics: bool,
    reviewer: list[str],
    single_review: bool,
) -> list[tuple[str, list[str], bool]]:
    py = sys.executable
    manifest = data_root / "official_authority_store" / "source_manifest.json"
    derived_targets = data_root / "official_authority_store" / "derived_authority_targets.json"
    queue = eval_root / "gold_annotation_queue.jsonl"
    csv_queue = eval_root / "gold_annotation_queue.csv"
    gold_manifest = eval_root / "gold_eval_pack_manifest.json"
    release_metrics = eval_root / "release_metrics_evidence.json"
    plan: list[tuple[str, list[str], bool]] = []
    if not skip_ingest:
        ingest = [
            py,
            _script("ingest-maine-authority.py"),
            "--data-root",
            str(data_root),
            "--timeout",
            str(timeout),
            "--delay",
            str(delay),
            "--max-retries",
            str(max_retries),
        ]
        if strict_content_type:
            ingest.append("--strict-content-type")
        if max_targets is not None:
            ingest.extend(["--max-targets", str(max_targets)])
        plan.append(("ingest_official_authority", ingest, True))
    parsed_audit_cmd = [py, _script("audit-parsed-authority-store.py"), "--data-root", str(data_root)]
    # When second-wave follow-up ingestion is requested, the first parsed store is
    # expected to contain mostly index/reference records. Do not require direct
    # section/form/opinion records until after derived targets are built, fetched
    # with --append-existing-manifest, and the parsed store is rebuilt.
    if require_direct_authority and not ingest_followup_targets:
        parsed_audit_cmd.append("--require-direct-authority")
    plan.extend(
        [
            ("audit_authority_build", [py, _script("audit-authority-build.py"), "--data-root", str(data_root)], True),
            ("build_parsed_authority_store", [py, _script("build-parsed-authority-store.py"), "--data-root", str(data_root)], True),
            ("audit_parsed_authority_store", parsed_audit_cmd, True),
        ]
    )
    if build_followup_targets:
        followup_cmd = [py, _script("build-authority-followup-targets.py"), "--data-root", str(data_root)]
        if max_derived_targets is not None:
            followup_cmd.extend(["--max-targets", str(max_derived_targets)])
        plan.append(("build_authority_followup_targets", followup_cmd, True))
    if ingest_followup_targets:
        followup_ingest = [
            py,
            _script("ingest-derived-authority-targets.py"),
            "--data-root",
            str(data_root),
            "--target-catalog",
            str(derived_targets),
            "--timeout",
            str(timeout),
            "--delay",
            str(delay),
            "--max-retries",
            str(max_retries),
            "--batch-size",
            str(derived_batch_size),
            "--batch-timeout",
            str(derived_batch_timeout),
            "--append-existing-manifest",
        ]
        if strict_content_type:
            followup_ingest.append("--strict-content-type")
        if max_derived_targets is not None:
            followup_ingest.extend(["--max-targets", str(max_derived_targets)])
        plan.append(("ingest_derived_authority_targets", followup_ingest, True))
        plan.append(("rebuild_parsed_authority_store", [py, _script("build-parsed-authority-store.py"), "--data-root", str(data_root)], True))
        re_audit_cmd = [py, _script("audit-parsed-authority-store.py"), "--data-root", str(data_root), "--require-direct-authority"]
        plan.append(("reaudit_parsed_authority_store", re_audit_cmd, True))
    plan.extend(
        [
            (
                "build_source_update_report",
                [
                    py,
                    _script("build-source-update-report.py"),
                    "--data-root",
                    str(data_root),
                ]
                + (["--previous-manifest", str(previous_manifest)] if previous_manifest else []),
                True,
            ),
            ("build_authority_layer", [py, _script("build-authority-layer.py"), "--data-root", str(data_root)], True),
            ("build_retrieval_indexes", [py, _script("build-retrieval-indexes.py"), "--data-root", str(data_root)], True),
            (
                "audit_retrieval_indexes",
                [py, _script("audit-retrieval-indexes.py"), "--data-root", str(data_root)]
                + (["--require-direct-lookups"] if require_direct_authority else []),
                True,
            ),
            (
                "run_retrieval_smoke_eval",
                [
                    py,
                    _script("run-retrieval-smoke-eval.py"),
                    "--data-root",
                    str(data_root),
                    "--eval-root",
                    str(eval_root),
                    "--top-k",
                    str(retrieval_top_k),
                    "--min-case-count",
                    str(retrieval_min_case_count),
                    "--min-recall-at-20",
                    str(retrieval_min_recall_at_20),
                ]
                + (["--max-case-count", str(retrieval_max_case_count)] if retrieval_max_case_count is not None else [])
                + ["--progress-interval", "5"],
                require_retrieval_smoke,
            ),
            (
                "triage_retrieval_failures",
                [py, _script("triage-retrieval-failures.py"), "--data-root", str(data_root), "--eval-root", str(eval_root)],
                False,
            ),
        ]
    )
    queue_cmd = [
        py,
        _script("build-gold-annotation-queue.py"),
        "--manifest",
        str(manifest),
        "--output",
        str(queue),
        "--csv-output",
        str(csv_queue),
    ]
    for item in reviewer:
        queue_cmd.extend(["--reviewer", item])
    if single_review:
        queue_cmd.append("--single-review")
    plan.append(("build_gold_annotation_queue", queue_cmd, False))
    plan.append(("audit_gold_annotation_queue", [py, _script("audit-gold-annotation-queue.py"), "--queue", str(queue)], False))

    gold_manifest_cmd = [
        py,
        _script("build-gold-eval-pack-manifest.py"),
        "--eval-root",
        str(eval_root),
        "--output",
        str(gold_manifest),
    ]
    gold_audit_cmd = [py, _script("audit-gold-eval-pack.py"), "--eval-root", str(eval_root)]
    if require_gold_eval_pack:
        gold_manifest_cmd.append("--require-ready")
        gold_audit_cmd.append("--require-ready")
    plan.append(("build_gold_eval_pack_manifest", gold_manifest_cmd, require_gold_eval_pack))
    plan.append(("audit_gold_eval_pack", gold_audit_cmd, require_gold_eval_pack))

    release_metrics_cmd = [
        py,
        _script("run-release-metrics-evidence.py"),
        "--eval-root",
        str(eval_root),
        "--output",
        str(release_metrics),
    ]
    if require_release_metrics:
        release_metrics_cmd.append("--require-ready")
    plan.append(("build_release_metrics_evidence", release_metrics_cmd, require_release_metrics))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the external Maine authority data-product pipeline for Pass 19+ evidence."
    )
    parser.add_argument("--data-root", type=Path, required=True, help="External data root; must be outside the repo.")
    parser.add_argument("--eval-root", type=Path, default=None, help="External eval root. Defaults to <data-root>/eval_store.")
    parser.add_argument("--output", type=Path, default=None, help="Evidence JSON path. Defaults to <data-root>/authority_data_product_run.json.")
    parser.add_argument("--previous-manifest", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--strict-content-type", action="store_true")
    parser.add_argument("--skip-ingest", action="store_true", help="Use an existing official_authority_store/source_manifest.json.")
    parser.add_argument("--max-targets", type=int, default=None, help="Optional cap for first-wave smoke/debug runs; omit for production.")
    parser.add_argument(
        "--skip-followup-targets",
        action="store_true",
        help="Do not derive second-wave section/rule/form/opinion targets from parsed indexes.",
    )
    parser.add_argument(
        "--ingest-followup-targets",
        action="store_true",
        help="After deriving targets, fetch the second-wave direct authority targets too.",
    )
    parser.add_argument("--max-derived-targets", type=int, default=None, help="Optional cap for second-wave target derivation/ingest smoke runs.")
    parser.add_argument("--derived-batch-size", type=int, default=75, help="Second-wave ingest batch size for resumable direct-authority ingestion.")
    parser.add_argument("--derived-batch-timeout", type=int, default=600, help="Per-batch timeout for second-wave direct-authority ingestion.")
    parser.add_argument(
        "--require-direct-authority",
        action="store_true",
        help="Block if parsed authority contains only indexes/references instead of direct sections/forms/opinions.",
    )
    parser.add_argument(
        "--require-retrieval-smoke",
        action="store_true",
        help="Make the measured retrieval smoke eval a required release gate instead of advisory evidence.",
    )
    parser.add_argument("--retrieval-top-k", type=int, default=20)
    parser.add_argument("--retrieval-min-case-count", type=int, default=1)
    parser.add_argument("--retrieval-min-recall-at-20", type=float, default=0.9)
    parser.add_argument(
        "--retrieval-max-case-count",
        type=int,
        default=None,
        help="Bound retrieval smoke cases. Defaults inside the smoke runner to max(25, --retrieval-min-case-count).",
    )
    parser.add_argument(
        "--require-gold-eval-pack",
        action="store_true",
        help="Require attorney-reviewed gold eval minimums before the harness can pass.",
    )
    parser.add_argument(
        "--require-release-metrics",
        action="store_true",
        help="Require measured release metrics evidence and passing release gates.",
    )
    parser.add_argument("--step-timeout", type=int, default=7200)
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--reviewer", action="append", default=[])
    parser.add_argument("--single-review", action="store_true")
    parser.add_argument("--plan-only", action="store_true", help="Print the command plan without executing it.")
    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()
    eval_root = (args.eval_root or (data_root / "eval_store")).expanduser().resolve()
    output = (args.output or (data_root / "authority_data_product_run.json")).expanduser().resolve()

    try:
        data_root.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise SystemExit("Refusing to build external authority data product inside the source repository.")

    plan = _command_plan(
        data_root=data_root,
        eval_root=eval_root,
        previous_manifest=args.previous_manifest,
        timeout=args.timeout,
        delay=args.delay,
        max_retries=args.max_retries,
        strict_content_type=args.strict_content_type,
        skip_ingest=args.skip_ingest,
        max_targets=args.max_targets,
        build_followup_targets=not args.skip_followup_targets,
        ingest_followup_targets=args.ingest_followup_targets,
        max_derived_targets=args.max_derived_targets,
        derived_batch_size=args.derived_batch_size,
        derived_batch_timeout=args.derived_batch_timeout,
        require_direct_authority=args.require_direct_authority,
        require_retrieval_smoke=args.require_retrieval_smoke,
        retrieval_top_k=args.retrieval_top_k,
        retrieval_min_case_count=args.retrieval_min_case_count,
        retrieval_min_recall_at_20=args.retrieval_min_recall_at_20,
        retrieval_max_case_count=args.retrieval_max_case_count,
        require_gold_eval_pack=args.require_gold_eval_pack,
        require_release_metrics=args.require_release_metrics,
        reviewer=args.reviewer,
        single_review=args.single_review,
    )
    if args.plan_only:
        print(
            json.dumps(
                {
                    "status": "pass",
                    "mode": "plan_only",
                    "data_root": str(data_root),
                    "eval_root": str(eval_root),
                    "steps": [
                        {"name": name, "command": command, "required": required}
                        for name, command, required in plan
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    eval_root.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    steps: list[StepResult] = []
    blockers: list[str] = []
    for name, command, required in plan:
        step = _run_step(name, command, timeout=args.step_timeout, required=required)
        steps.append(step)
        if step.status != "pass" and required:
            blockers.append(name)
            if not args.continue_on_failure:
                break

    optional_failures = [step.name for step in steps if step.status != "pass" and not step.required]
    status = "pass" if not blockers else "blocked"
    run = AuthorityDataProductRun(
        status=status,
        generated_at=datetime.now(timezone.utc).isoformat(),
        repo_root=str(ROOT),
        data_root=str(data_root),
        eval_root=str(eval_root),
        output=str(output),
        steps=steps,
        blockers=blockers,
        next_manual_actions=[
            "Run again without --max-targets for production coverage." if args.max_targets is not None else "Keep source snapshots and indexes in the external data root.",
            "Promote generated annotation rows only after attorney review; seed/fixture rows do not count as GA evidence.",
            "Run with --ingest-followup-targets after the first-wave index snapshots parse cleanly; this fetches direct section/rule/form/opinion targets in resumable chunks.",
            "Use --require-direct-authority for the Pass 20/23 handoff once follow-up targets are ingested; index-only parsed stores and empty lookup artifacts should not be treated as retrieval-ready.",
            "Use --require-retrieval-smoke with explicit thresholds before treating Pass 24 measured retrieval evidence as a release gate.",
            "Use --require-gold-eval-pack only after attorney-reviewed JSONL minimums are met; generated annotation queues are not gold evidence.",
            "Use --require-release-metrics only after task-specific evaluators produce measured metrics from real gold files.",
            "Resolve any required-step blockers before claiming Pass 19+ complete.",
        ] + ([f"Optional steps failed: {', '.join(optional_failures)}"] if optional_failures else []),
    )
    output.write_text(json.dumps(run.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(run.as_dict(), indent=2, sort_keys=True))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
