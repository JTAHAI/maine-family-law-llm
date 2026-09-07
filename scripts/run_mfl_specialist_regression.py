"""Run one specialist against internal splits and every frozen wording suite.

The external model project is treated as read-only.  All caches, journals and
reports are forced into a new directory under this repository's ignored dist/.
Only the independent frozen reports feed the strict quality decision.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.security.durable_io import atomic_write_bytes  # noqa: E402
from legal.security.strict_json import strict_json_load_path  # noqa: E402
from scripts.bounded_evaluation_process import run_bounded  # noqa: E402
from scripts.summarize_mfl_specialist_quality import sha256_file, summarize  # noqa: E402

FIXTURES = {
    "drafting": (
        "mfl_drafting_out_of_template_v1.json",
        "mfl_drafting_fresh_wording_v2.json",
    ),
    "evidence_review": (
        "mfl_evidence_out_of_template_v1.json",
        "mfl_evidence_fresh_wording_v2.json",
        "mfl_evidence_fresh_wording_v3_corrective_r0004.json",
        "mfl_evidence_fresh_wording_v4_corrective_r0005.json",
        "mfl_evidence_post_training_r0007_v1.json",
        "mfl_evidence_post_training_r0008_v1.json",
        "mfl_evidence_post_training_r0009_v1.json",
        "mfl_evidence_post_training_r0010_v1.json",
    ),
}
MINIMUM_FROZEN_CASES = {"drafting": 22, "evidence_review": 104}


def verify_regression_baseline(model_project: Path, capability: str) -> str:
    """Pin the consulted regression inputs before inference, not just afterward."""
    path = ROOT / "configs" / "mfl_specialist_regression_baseline.json"
    baseline = strict_json_load_path(path, require_object=True)
    if baseline.get("schema_version") != "mfl_specialist_regression_baseline_v1":
        raise ValueError("regression_baseline_invalid")
    evaluation = evaluator(model_project, capability)
    if sha256_file(evaluation) != baseline["evaluators"].get(evaluation.name):
        raise ValueError("regression_evaluator_not_pinned")
    for name in FIXTURES[capability]:
        fixture = model_project / "data" / "evaluation" / name
        expected = baseline["fixtures"].get(name)
        if not expected or sha256_file(fixture) != expected["sha256"]:
            raise ValueError("regression_fixture_not_pinned")
        cases = strict_json_load_path(fixture, require_object=True).get("cases", [])
        if [row.get("id") for row in cases] != expected["case_ids"]:
            raise ValueError("regression_case_inventory_mismatch")
    return sha256_file(path)


def evaluator(model_project: Path, capability: str) -> Path:
    name = (
        "evaluate_mfl_practical_research_v2.py"
        if capability == "drafting"
        else "evaluate_mfl_evidence_research_v2.py"
    )
    return (model_project / "scripts" / name).resolve(strict=True)


def run(args: argparse.Namespace) -> dict[str, Any]:
    from legal.fast_interchange.worker import HotSwapRegistry
    from legal.security.strict_json import strict_json_load_path

    baseline_hash = verify_regression_baseline(
        args.model_project.resolve(strict=True), args.capability
    )
    pack = args.pack.resolve(strict=True)
    registry = HotSwapRegistry.from_dicts(
        root=pack,
        releases=strict_json_load_path(pack / "releases.json", require_object=True),
        artifacts=strict_json_load_path(pack / "artifacts.json", require_object=True),
    )
    selected = [item for item in registry.releases.values() if item.capability == args.capability]
    if len(selected) != 1:
        raise ValueError("evaluation_candidate_capability_invalid")
    release = selected[0]
    registry.bindings[release.release_id].verify(pack)
    pack_hash = sha256_file(pack / "pack-manifest.json")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "dist").resolve()) or output.exists():
        raise ValueError("specialist_regression_output_must_be_new_inside_repository_dist")
    output.mkdir(parents=True)
    environment = os.environ.copy()
    for name, relative in {
        "TEMP": "temporary",
        "TMP": "temporary",
        "HF_HOME": "hf",
        "TRANSFORMERS_CACHE": "transformers",
        "TORCH_HOME": "torch",
    }.items():
        path = output / relative
        path.mkdir(exist_ok=True)
        environment[name] = str(path)
    environment.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    if args.cuda_visible_device:
        environment["CUDA_VISIBLE_DEVICES"] = args.cuda_visible_device
    evaluation = evaluator(args.model_project, args.capability)
    common = [
        str(args.python.resolve(strict=True)),
        "-B",
        str(evaluation),
        "--pack",
        str(args.pack.resolve(strict=True)),
        "--family-repo",
        str(ROOT),
        "--corpus-dir",
        str(args.corpus_dir.resolve(strict=True)),
        "--device",
        args.device,
        "--precision",
        args.precision,
        "--engine",
        "family-worker",
    ]
    if args.capability == "drafting":
        common.extend(("--capability", "drafting"))
    commands: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    abort = False

    def invoke(name: str, tail: list[str]) -> Path:
        nonlocal abort
        report = output / "reports" / f"{name}.json"
        report.parent.mkdir(exist_ok=True)
        command = [*common, "--output", str(report), *tail]
        started = datetime.now(UTC)
        completed = run_bounded(
            command,
            cwd=ROOT,
            env=environment,
            timeout_seconds=args.command_timeout,
        )
        record = {
            "name": name,
            "command": command,
            **completed,
            "started_at": started.isoformat(),
            "duration_seconds": (datetime.now(UTC) - started).total_seconds(),
            "report": str(report),
        }
        commands.append(record)
        abort = completed["timed_out"] or completed["cleanup_failed"]
        if (
            completed["returncode"] != 0
            or completed["timed_out"]
            or completed["cleanup_failed"]
            or not report.is_file()
        ):
            failures.append(
                {
                    "name": name,
                    "code": "evaluation_command_failed",
                    "returncode": completed["returncode"],
                }
            )
        atomic_write_bytes(
            output / "progress.json",
            json.dumps(
                {
                    "status": "blocked" if abort else "running",
                    "baseline_sha256": baseline_hash,
                    "commands": commands,
                    "failures": failures,
                },
                indent=2,
            ).encode("utf-8"),
        )
        print(json.dumps({"evaluation": name, "returncode": completed["returncode"]}), flush=True)
        return report

    for suite in ("development", "test", "challenge"):
        if abort:
            break
        invoke(f"internal-{suite}", ["--suite", suite, "--limit", str(args.internal_limit)])
    frozen: list[Path] = []
    fixture_root = args.model_project.resolve(strict=True) / "data" / "evaluation"
    for name in FIXTURES[args.capability]:
        if abort:
            break
        fixture = (fixture_root / name).resolve(strict=True)
        frozen.append(
            invoke(
                f"frozen-{fixture.stem}", ["--suite", "out-of-template", "--fixtures", str(fixture)]
            )
        )

    try:
        if (
            verify_regression_baseline(args.model_project.resolve(strict=True), args.capability)
            != baseline_hash
        ):
            raise ValueError("regression_baseline_changed")
    except (OSError, ValueError):
        failures.append({"code": "regression_inputs_changed_during_run"})
    quality = None
    if all(path.is_file() for path in frozen):
        quality = summarize(
            args.capability,
            frozen,
            minimum_cases=MINIMUM_FROZEN_CASES[args.capability],
            expected_pack_manifest_sha256=pack_hash,
            expected_release_fingerprint=release.release_fingerprint,
        )
        if failures:
            quality["quality_gate_passed"] = False
            quality["runnable_research_only"] = False
            quality["decision"] = "BLOCKED"
            quality["failures"].extend(failures)
        (output / "quality-status.json").write_text(
            json.dumps(quality, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if not quality["quality_gate_passed"]:
            failures.append({"code": "strict_frozen_quality_gate_failed"})
    result = {
        "schema_version": "mfl_specialist_regression_run_v1",
        "observed_at": datetime.now(UTC).isoformat(),
        "capability": args.capability,
        "regression_baseline_sha256": baseline_hash,
        "dataset_basis": "consulted_fictional_regression_not_blind_holdout",
        "pack": str(args.pack.resolve(strict=True)),
        "corpus_dir": str(args.corpus_dir.resolve(strict=True)),
        "external_model_project_read_only": str(args.model_project.resolve(strict=True)),
        "commands": commands,
        "quality": quality,
        "failures": failures,
        "decision": "LOCAL_RESEARCH_QUALITY_PASS" if not failures else "BLOCKED",
        "production_admitted": False,
        "attorney_reviewed": False,
        "legal_use_approved": False,
    }
    (output / "regression-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability", choices=tuple(FIXTURES), required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--precision", choices=("bf16", "fp32"), default="bf16")
    parser.add_argument("--cuda-visible-device", default="")
    parser.add_argument("--internal-limit", type=int, default=29)
    parser.add_argument("--command-timeout", type=int, default=1200)
    args = parser.parse_args()
    if not 1 <= args.internal_limit <= 320:
        parser.error("internal_limit_must_be_1_through_320")
    if not 1 <= args.command_timeout <= 7200:
        parser.error("command_timeout_must_be_1_through_7200")
    result = run(args)
    print(json.dumps({"decision": result["decision"], "output": str(args.output.resolve())}))
    return 0 if result["decision"] == "LOCAL_RESEARCH_QUALITY_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
