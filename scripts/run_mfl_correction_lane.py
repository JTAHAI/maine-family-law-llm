"""Supervise Evidence then Drafting correction, with durable fail-closed evidence.

All generated files stay in one new repository-local dist directory. External
model inputs are read-only. This lane never grants production/model admission,
changes a version, publishes, or packages an MSIX.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CAPABILITIES = ("evidence_review", "drafting")
# The qualified RTX 3060 completes the continuations with bf16 and gradient
# checkpointing, but batch four has a measured out-of-memory failure during
# backward recomputation.  Keep the lane deliberately conservative: every
# run records the effective batch size in its immutable training identity.
SAFE_BF16_BATCH_SIZE = 2


def write_json(path: Path, value: object) -> None:
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pending.replace(path)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def completed_training(path: Path) -> bool:
    value = json.loads(path.read_text(encoding="utf-8"))
    identity = value.get("identity")
    if not isinstance(identity, dict):
        return False
    batch_size = identity.get("batch_size")
    if not isinstance(batch_size, int) or batch_size < 1:
        return False
    expected_steps = 12_800 // batch_size
    return (
        value.get("status") == "completed-local-research-only"
        and value.get("production_admitted") is False
        and value.get("train_examples") == 12_800
        and value.get("examples_seen") == 12_800
        and value.get("epochs") == 1
        and value.get("step") == expected_steps
    )


def completed_pack(path: Path) -> bool:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value.get("run_complete") is True and value.get("production_admitted") is False


def passed_regression(path: Path) -> bool:
    value = json.loads(path.read_text(encoding="utf-8"))
    return (
        value.get("decision") == "LOCAL_RESEARCH_QUALITY_PASS"
        and value.get("failures") == []
        and value.get("quality", {}).get("quality_gate_passed") is True
        and value.get("production_admitted") is False
    )


def selected_specifications(capabilities: tuple[str, ...]) -> tuple[tuple[object, ...], ...]:
    """Return the explicit research lanes requested by the operator.

    A failed Evidence candidate must be repairable without silently launching
    the separate Drafting GPU job or consuming its disk budget.
    """

    specifications = (
        ("evidence_review", "evidence-r0012b", 2026090112,
         None,
         "package_mfl_research.py"),
        ("drafting", "drafting-r0004b", 2026090104,
         ROOT / "dist/model-candidates/drafting-r0003/drafting-r0003-final",
         "package_mfl_practical_research.py"),
    )
    requested = set(capabilities)
    result = tuple(row for row in specifications if row[0] in requested)
    if len(result) != len(requested):
        raise ValueError("correction_capability_selection_invalid")
    return result


def run_child(command: list[str], *, timeout: int, **kwargs) -> subprocess.CompletedProcess:
    """Keep our process tree alive until its deadline, then terminate only it.

    Windows venv launchers can own a second Python process. Killing only the
    launcher would leave GPU work running and collide with the next candidate.
    """
    with subprocess.Popen(command, **kwargs) as child:
        try:
            returncode = child.wait(timeout=timeout)
        except BaseException:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=30, check=False,
                )
            else:
                child.kill()
            child.wait(timeout=30)
            raise
    return subprocess.CompletedProcess(command, returncode)


def execute_stage(
    name: str,
    command: list[str],
    *,
    output: Path,
    environment: dict[str, str],
    completion: Path,
    validate: Callable[[Path], bool],
    timeout: int,
) -> bool:
    started = datetime.now(UTC)
    record: dict = {
        "stage": name,
        "command": command,
        "started_at": started.isoformat(),
        "status": "running",
        "completion": str(completion),
        "script_sha256": digest(Path(command[2])),
    }
    status = output / f"{name}.json"
    log = output / f"{name}.log"
    write_json(status, record)
    print(json.dumps({"stage": name, "status": "running"}), flush=True)
    try:
        with log.open("w", encoding="utf-8") as stream:
            result = run_child(
                command,
                cwd=ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
        record["returncode"] = result.returncode
        if result.returncode:
            record.update(status="failed", error="command_nonzero_exit")
        elif not completion.is_file() or not validate(completion):
            record.update(status="failed", error="completion_record_missing_or_invalid")
        else:
            record.update(status="passed", completion_sha256=digest(completion))
    except Exception as exc:
        record.update(status="failed", error=type(exc).__name__)
    finally:
        record["duration_seconds"] = (datetime.now(UTC) - started).total_seconds()
        if log.is_file():
            record["log_sha256"] = digest(log)
        write_json(status, record)
        print(json.dumps({"stage": name, "status": record["status"]}), flush=True)
    return record["status"] == "passed"


def run(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    is_resume = bool(args.resume)
    if not output.is_relative_to((ROOT / "dist").resolve()):
        raise ValueError("lane_output_must_be_inside_repository_dist")
    if is_resume:
        if not output.is_dir() or not (output / "lane-status.json").is_file():
            raise ValueError("resume_output_must_be_an_existing_lane_inside_repository_dist")
    elif output.exists():
        raise ValueError("lane_output_must_be_new_inside_repository_dist")
    if shutil.disk_usage(ROOT).free < 8 * 1024**3:
        raise ValueError("eight_gib_disk_headroom_required")
    python = str(args.python.resolve(strict=True))
    project = args.model_project.resolve(strict=True)
    base = project / "artifacts/base_models/Qwen3-0.6B"
    output.mkdir(parents=True, exist_ok=is_resume)
    environment = os.environ.copy()
    for key in (
        "TEMP", "TMP", "HF_HOME", "TRANSFORMERS_CACHE", "TORCH_HOME",
        "TORCHINDUCTOR_CACHE_DIR", "TRITON_CACHE_DIR",
    ):
        folder = output / "scratch" / key.lower()
        folder.mkdir(parents=True, exist_ok=True)
        environment[key] = str(folder)
    environment.update(
        HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1", TOKENIZERS_PARALLELISM="false",
    )
    status = output / "lane-status.json"
    if is_resume:
        state = json.loads(status.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("production_admitted") is not False:
            raise ValueError("resume_lane_status_invalid")
        state.pop("finished_at", None)
        state["resumed_at"] = datetime.now(UTC).isoformat()
        state["resume_count"] = int(state.get("resume_count", 0)) + 1
        state["status"] = "running"
        state["supervisor_pid"] = os.getpid()
    else:
        state = {
            "schema": "mfl.correction-lane.v1",
            "status": "running",
            "started_at": datetime.now(UTC).isoformat(),
            "supervisor_pid": os.getpid(),
            "capabilities": {},
            "production_admitted": False,
            "attorney_reviewed": False,
            "in_app_e2e_passed": False,
            "store_ready": False,
        }
    write_json(status, state)
    for capability, candidate, seed, parent, packager in selected_specifications(args.capabilities):
        # The evidence parent is supplied from the same read-only model project
        # chosen on the command line; no other project path becomes a runtime
        # dependency or output destination.
        if capability == "evidence_review":
            parent = project / "artifacts/mfl_fast_interchange/evidence-r0010-corrective-final"
        if not isinstance(parent, Path):
            raise ValueError("correction_parent_pack_invalid")
        source = ROOT / "dist/model-candidates" / candidate
        target = output / capability
        target.mkdir(exist_ok=is_resume)
        training = target / "training"
        pack = target / f"{candidate}-b{SAFE_BF16_BATCH_SIZE}-final"
        regression = target / "regression"
        state["active_capability"] = capability
        state["capabilities"][capability] = "training"
        write_json(status, state)
        stages = (
            ("train", ROOT / "scripts/train_mfl_adapter_continuation.py", [
                "--authorization", str(source / "research-authorization.json"),
                "--corpus-dir", str(source / "corpus"),
                "--audit", str(source / "corpus-audit.json"),
                "--base-model", str(base), "--parent-pack", str(parent),
                "--output", str(training), "--capability", capability,
                "--batch-size", str(SAFE_BF16_BATCH_SIZE), "--train-limit", "12800",
                "--learning-rate", "0.00006", "--seed", str(seed),
                "--cuda-visible-device", "0", "--precision", "bf16",
                "--gradient-checkpointing",
            ], training / "training-run.json", completed_training, 6 * 3600),
            ("package", project / "scripts" / packager, [
                "--run", str(training), "--checkpoint", str(training / "final"),
                "--base", str(base), "--output", str(pack),
            ], pack / "pack-manifest.json", completed_pack, 900),
            ("regression", ROOT / "scripts/run_mfl_specialist_regression.py", [
                "--capability", capability, "--pack", str(pack),
                "--corpus-dir", str(source / "corpus"),
                "--model-project", str(project), "--python", python,
                "--output", str(regression), "--device", "cuda",
                "--precision", "bf16", "--cuda-visible-device", "0",
            ], regression / "regression-summary.json", passed_regression, 3 * 3600),
        )
        for name, script, tail, completion, validate, timeout in stages:
            state["active_stage"] = name
            write_json(status, state)
            if is_resume and completion.is_file() and validate(completion):
                print(json.dumps({"stage": name, "status": "reused_valid_completion"}), flush=True)
                continue
            if not execute_stage(
                name, [python, "-B", str(script), *tail], output=target,
                environment=environment, completion=completion, validate=validate,
                timeout=timeout,
            ):
                state["capabilities"][capability] = f"blocked_{name}"
                # A completed quality failure may be followed by independent
                # Drafting work; infrastructure/training failure must not
                # start another GPU job after an uncertain child shutdown.
                if name != "regression" or not completion.is_file():
                    state.update(status="blocked", finished_at=datetime.now(UTC).isoformat())
                    write_json(status, state)
                    return 1
                break
        else:
            state["capabilities"][capability] = "local_research_quality_pass"
        write_json(status, state)
    passed = all(value == "local_research_quality_pass" for value in state["capabilities"].values())
    state.update(
        status="local_research_quality_pass_e2e_pending" if passed else "blocked",
        finished_at=datetime.now(UTC).isoformat(),
    )
    write_json(status, state)
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Reuse only completed stages whose receipts still pass validation; "
            "never retrain them."
        ),
    )
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument(
        "--capabilities",
        nargs="+",
        choices=CAPABILITIES,
        default=list(CAPABILITIES),
        help="Run only the named independent fictional research lanes (default: both).",
    )
    args = parser.parse_args()
    args.capabilities = tuple(dict.fromkeys(args.capabilities))
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
