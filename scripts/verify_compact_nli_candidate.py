"""Bounded, fictional-only NLI qualification. No production factory or admission.

Expected labels stay in the host evaluation fixture, never in model input. Scores
describe text relations; they cannot authenticate a source or verify legal facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from threading import Thread

import psutil

from legal.fast_interchange.admission import canonical
from legal.fast_interchange.compact_cpu import (
    MAX_RESIDENT_BYTES,
    _WindowsWorkerJob,
    pinned_inventory,
)
from legal.fast_interchange.compact_network_guard import PythonNetworkGuard
from legal.fast_interchange.snapshot import validate_safetensors
from legal.security.strict_json import strict_json_load_path, strict_json_loads
from scripts.acquire_compact_model_candidates import CATALOG, OUTPUT, ROOT

LABELS = ("contradiction", "entailment", "neutral")
# Deliberately small agent-authored software challenge, NOT legal gold or training data.
CASES = (
    (
        "e01",
        "The fictional clerk received the packet on Monday.",
        "The packet was received on Monday.",
        "entailment",
    ),
    (
        "e02",
        "A fictional message says the cost worksheet is missing from the enclosure.",
        "A message reports a missing cost worksheet.",
        "entailment",
    ),
    (
        "e03",
        "The fictional court order directs the exchange to occur at the library.",
        "The order names the library as the exchange location.",
        "entailment",
    ),
    (
        "e04",
        "The fictional note contains an allegation by Parent A that Parent B was late.",
        "Parent A alleged that Parent B was late.",
        "entailment",
    ),
    (
        "e05",
        "The fictional amended order replaces the original Friday time with Saturday at noon.",
        "The amended order sets Saturday at noon instead of Friday.",
        "entailment",
    ),
    (
        "e06",
        "The fictional receipt identifies Folder A as delivered and Folder B as undelivered.",
        "Folder B is marked undelivered.",
        "entailment",
    ),
    (
        "e07",
        "The fictional calendar lists a hearing on May 3 and a separate meeting on May 5.",
        "The hearing and meeting have different dates.",
        "entailment",
    ),
    (
        "e08",
        "The fictional email promises to send the missing attachment tomorrow.",
        "The sender promised a future attachment delivery.",
        "entailment",
    ),
    (
        "n01",
        "The fictional email says Parent A delivered a packet on Monday.",
        "Parent B delivered a packet on Monday.",
        "neutral",
    ),
    (
        "n02",
        "A fictional private note alleges that Parent B missed an exchange.",
        "A court found that Parent B missed an exchange.",
        "neutral",
    ),
    (
        "n03",
        "The fictional sender promises to deliver the attachment tomorrow.",
        "The attachment has been delivered.",
        "neutral",
    ),
    (
        "n04",
        "The fictional log records that an envelope was received.",
        "The envelope contained every requested document.",
        "neutral",
    ),
    (
        "n05",
        "The fictional calendar lists a hearing on May 3 and a meeting on May 5.",
        "The hearing was cancelled.",
        "neutral",
    ),
    (
        "n06",
        "The fictional screenshot contains the words 'I sent the payment'.",
        "The bank completed the payment.",
        "neutral",
    ),
    (
        "n07",
        "The fictional witness says the vehicle was blue.",
        "The witness's account is accurate.",
        "neutral",
    ),
    (
        "n08",
        "The fictional order states an exchange location at the library.",
        "That order is currently operative and has not been amended.",
        "neutral",
    ),
    (
        "c01",
        "The fictional receipt explicitly says the attachment was not delivered.",
        "The attachment was delivered.",
        "contradiction",
    ),
    (
        "c02",
        "The fictional order requires the single exchange on Saturday, not Friday.",
        "That single exchange is required on Friday.",
        "contradiction",
    ),
    (
        "c03",
        "The fictional record says Parent A, not Parent B, received the sole packet.",
        "Parent B received the sole packet.",
        "contradiction",
    ),
    (
        "c04",
        "The fictional clerk cancelled the May 3 hearing.",
        "The May 3 hearing was not cancelled.",
        "contradiction",
    ),
    (
        "c05",
        "The fictional order expressly makes no finding about whether the payment was late.",
        "The order found that the payment was late.",
        "contradiction",
    ),
    (
        "c06",
        "The fictional inventory contains exactly two folders and no other folders.",
        "The inventory contains three folders.",
        "contradiction",
    ),
    (
        "c07",
        "The fictional amended order says the former location no longer applies.",
        "The amended order keeps the former location applicable.",
        "contradiction",
    ),
    (
        "c08",
        "The fictional report labels the note as an unverified allegation, not a court finding.",
        "The report labels the note as a court finding.",
        "contradiction",
    ),
)


def fixture(challenge="baseline24"):
    if challenge == "attribution36":
        from scripts.compact_nli_attribution_challenge import cases

        return cases()
    if challenge != "baseline24":
        raise ValueError("unknown_fictional_challenge")
    return [{"id": i, "premise": p, "hypothesis": h, "expected": e} for i, p, h, e in CASES]


def input_pair(case):
    """Only the two texts enter inference, never expected labels or case IDs."""
    return case["premise"], case["hypothesis"]


def score_rows(rows, cases=None):
    selected = fixture() if cases is None else cases
    if not isinstance(selected, list) or not 1 <= len(selected) <= 128:
        raise ValueError("invalid_nli_fixture")
    expected = {case["id"]: case for case in selected}
    if len(expected) != len(selected):
        raise ValueError("invalid_nli_fixture")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("incomplete_nli_output")
    seen, scored = set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "probabilities", "seconds"}:
            raise ValueError("invalid_nli_output")
        if not isinstance(row["id"], str):
            raise ValueError("invalid_nli_output")
        case = expected.get(row["id"])
        values = row["probabilities"]
        if (
            case is None
            or row["id"] in seen
            or not isinstance(values, list)
            or len(values) != 3
            or any(
                type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
                for x in values
            )
            or abs(sum(values) - 1) > 1e-5
            or type(row["seconds"]) not in (int, float)
            or not math.isfinite(row["seconds"])
            or row["seconds"] < 0
        ):
            raise ValueError("invalid_nli_output")
        seen.add(row["id"])
        predicted = LABELS[max(range(3), key=lambda i: values[i])]
        scored.append(
            {**case, **row, "predicted": predicted, "pass": predicted == case["expected"]}
        )
    correct = sum(row["pass"] for row in scored)
    return {
        "cases": scored,
        "correct": correct,
        "total": len(scored),
        "synthetic_challenge_passed": correct == len(scored),
        "false_entailments": sum(
            row["predicted"] == "entailment" and row["expected"] != "entailment" for row in scored
        ),
        "false_contradictions": sum(
            row["predicted"] == "contradiction" and row["expected"] != "contradiction"
            for row in scored
        ),
        "confusion_matrix": {
            actual: {
                predicted: sum(
                    row["expected"] == actual and row["predicted"] == predicted for row in scored
                )
                for predicted in LABELS
            }
            for actual in LABELS
        },
        "probabilities_are_not_calibrated_truth_confidence": True,
        "ga_ready": False,
    }


def qualification_exit_code(report):
    if report["errors"]:
        return 2
    return 0 if report.get("metrics", {}).get("synthetic_challenge_passed") is True else 1


def validate_worker_result(result, fixture_hash):
    # The worker supplies measurements, never authority to overwrite host status.
    if not isinstance(result, dict) or set(result) != {
        "rows",
        "load_seconds",
        "peak_rss_bytes",
        "torch_version",
        "network_attempt_detected",
        "fixture_sha256",
    }:
        raise ValueError("candidate_worker_envelope_invalid")
    if (
        result["fixture_sha256"] != fixture_hash
        or result["network_attempt_detected"] is not False
        or type(result["load_seconds"]) not in (int, float)
        or not math.isfinite(result["load_seconds"])
        or result["load_seconds"] < 0
        or type(result["peak_rss_bytes"]) is not int
        or not 0 < result["peak_rss_bytes"] <= MAX_RESIDENT_BYTES
        or not isinstance(result["torch_version"], str)
        or re.fullmatch(r"[0-9][0-9A-Za-z.+_-]{0,63}", result["torch_version"]) is None
    ):
        raise ValueError("candidate_worker_envelope_invalid")
    return result


def child(challenge="baseline24"):
    """Only called in the suspended/job-bound child. Imports are local and offline."""
    phase, guard = "guard", None
    try:
        guard = PythonNetworkGuard()
        cases = fixture(challenge)
        root = OUTPUT / "text-relation-nli"
        selected = CATALOG["text-relation-nli"]
        receipt = strict_json_load_path(root / "acquisition.json", max_bytes=20000)
        if (
            receipt["revision"] != selected["revision"]
            or receipt["source"] != selected["repo"]
            or set(p.name for p in root.iterdir()) != set(selected["files"]) | {"acquisition.json"}
        ):
            raise ValueError("candidate_inventory_invalid")
        files = pinned_inventory(root, "acquisition.json")
        if (
            next(r.sha256 for r in files if r.path.suffix == ".safetensors")
            != selected["weights_sha256"]
        ):
            raise ValueError("candidate_weights_invalid")
        with ExitStack() as locks, redirect_stdout(sys.stderr):
            phase = "artifact_verification"
            for row in files:
                row.lock(locks)
            config = strict_json_load_path(root / "config.json", max_bytes=20000)
            if config["id2label"] != dict(enumerate(LABELS)) and config["id2label"] != {
                str(i): v for i, v in enumerate(LABELS)
            }:
                raise ValueError("candidate_labels_invalid")
            if config["model_type"] != "deberta-v2" or config["num_hidden_layers"] != 6:
                raise ValueError("candidate_architecture_invalid")
            for row in files:
                if row.path.suffix == ".json":
                    data = strict_json_load_path(
                        row.path, max_bytes=12_000_000, max_items=1_000_000
                    )
                    if any(data.get(k) for k in ("auto_map", "auto_mapping", "trust_remote_code")):
                        raise ValueError("remote_code_forbidden")
            validate_safetensors(root / "model.safetensors", maximum_bytes=600_000_000)
            phase = "runtime_import"
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            torch.set_num_threads(2)
            phase, start = "model_load", time.monotonic()
            tokenizer = AutoTokenizer.from_pretrained(
                root, local_files_only=True, trust_remote_code=False, use_fast=True
            )
            if not tokenizer.is_fast:
                raise ValueError("fast_tokenizer_required")
            model = (
                AutoModelForSequenceClassification.from_pretrained(
                    root,
                    local_files_only=True,
                    trust_remote_code=False,
                    use_safetensors=True,
                )
                .cpu()
                .eval()
            )
            load_seconds = time.monotonic() - start
            rows = []
            with torch.inference_mode():
                for case in cases:
                    phase, start = "score", time.monotonic()
                    tokens = tokenizer(*input_pair(case), truncation=False, return_tensors="pt")
                    if tokens["input_ids"].shape[1] > 512:
                        raise ValueError("candidate_input_too_long")
                    logits = model(**tokens).logits
                    if tuple(logits.shape) != (1, 3) or not torch.isfinite(logits).all():
                        raise ValueError("candidate_output_invalid")
                    rows.append(
                        {
                            "id": case["id"],
                            "probabilities": torch.softmax(logits, dim=-1)[0].tolist(),
                            "seconds": round(time.monotonic() - start, 6),
                        }
                    )
            guard.check()
            mem = psutil.Process().memory_info()
            result = {
                "rows": rows,
                "load_seconds": load_seconds,
                "peak_rss_bytes": getattr(mem, "peak_wset", mem.rss),
                "torch_version": torch.__version__,
                "network_attempt_detected": guard.denied,
                "fixture_sha256": hashlib.sha256(canonical(cases)).hexdigest(),
            }
        encoded = canonical(result)
        if len(encoded) > 64000:
            raise ValueError("candidate_output_too_large")
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
        return 0
    except Exception as error:
        result = {
            "error": {
                "phase": phase,
                "kind": type(error).__name__,
                "network_denied": bool(guard and guard.denied),
            }
        }
        sys.stdout.write(json.dumps(result))
        return 1


def execute(run_id, challenge="baseline24"):
    cases = fixture(challenge)
    if not re.fullmatch(r"[a-z0-9-]{1,24}", run_id):
        raise ValueError("candidate_evidence_id_invalid")
    target = OUTPUT / f"nli-quality-{run_id}.json"
    if target.exists():
        raise ValueError("preserve_prior_evidence")
    if os.name != "nt" or psutil.virtual_memory().available < MAX_RESIDENT_BYTES + 1024**3:
        raise ValueError("candidate_windows_and_memory_required")
    scratch = OUTPUT / "nli-scratch"
    for part in (scratch, *scratch.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError("candidate_link_forbidden")
    scratch.mkdir(exist_ok=True)
    env = {
        k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE"}
    }
    env.update(
        {
            k: str(scratch)
            for k in (
                "TEMP",
                "TMP",
                "HF_HOME",
                "TORCH_HOME",
                "XDG_CACHE_HOME",
                "USERPROFILE",
                "APPDATA",
                "LOCALAPPDATA",
            )
        }
    )
    env.update(
        PATH=str(Path(psutil.Process().exe()).parent),
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        HF_HUB_DISABLE_PROGRESS_BARS="1",
        CUDA_VISIBLE_DEVICES="",
        USERNAME="mfl-fictional-nli",
        OMP_NUM_THREADS="2",
        TOKENIZERS_PARALLELISM="false",
    )
    report = {
        "schema_version": "compact_nli_quality_v1",
        "fictional_only": True,
        "training_use_permitted": False,
        "attorney_reviewed": False,
        "production_admitted": False,
        "production_ui_tested": False,
        "frozen_package_tested": False,
        "ga_ready": False,
        "fixture_sha256": hashlib.sha256(canonical(cases)).hexdigest(),
        "challenge": challenge,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_frozen_before_inference": True,
        "candidate": CATALOG["text-relation-nli"],
        "errors": [],
    }
    process = job = reader = None
    received = []
    started = time.monotonic()
    try:
        job = _WindowsWorkerJob()
        bootstrap = (
            "import site,sys;site.addsitedir(sys.argv[1]);sys.path.insert(0,sys.argv[2]);"
            "from scripts.verify_compact_nli_candidate import child;"
            "raise SystemExit(child(sys.argv[3]))"
        )
        process = subprocess.Popen(
            [
                psutil.Process().exe(),
                "-I",
                "-B",
                "-c",
                bootstrap,
                str(Path(sys.prefix) / "Lib/site-packages"),
                str(ROOT),
                challenge,
            ],
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW | 0x00000004,
        )
        job.attach_and_resume(process)
        reader = Thread(target=lambda: received.append(process.stdout.read(64001)), daemon=True)
        reader.start()
        while process.poll() is None:
            if time.monotonic() - started > 120:
                raise TimeoutError("candidate_deadline")
            if received and len(received[0]) > 64000:
                raise ValueError("candidate_output_too_large")
            if psutil.virtual_memory().available < 1024**3:
                raise MemoryError("candidate_headroom")
            time.sleep(0.05)
        reader.join(5)
        if reader.is_alive() or not received or len(received[0]) > 64000:
            raise ValueError("candidate_output_incomplete")
        result = strict_json_loads(received[0], max_bytes=64000, require_object=True)
        report["worker_exit_code"] = process.returncode
        if process.returncode != 0 or "error" in result:
            report["errors"].append(result.get("error", {"kind": "worker_failed"}))
        else:
            measured = validate_worker_result(result, report["fixture_sha256"])
            report["metrics"] = score_rows(measured["rows"], cases)
            report.update(measured)
            if challenge == "attribution36":
                report["partition_metrics"] = {
                    split: score_rows(
                        [row for row in measured["rows"] if row["id"].startswith(split + "-")],
                        [case for case in cases if case["split"] == split],
                    )
                    for split in ("cal", "eval")
                }
                report["calibration_or_threshold_tuning_performed"] = False
            inventory = strict_json_load_path(OUTPUT / "text-relation-nli/acquisition.json")
            report["model_files_bytes"] = inventory["total_bytes"]
            report["selected_runtime_plus_model_bytes"] = (
                inventory["total_bytes"] + CATALOG["text-relation-nli"]["selected_runtime_bytes"]
            )
            report["runtime_closure_qualified"] = False
    except Exception as error:
        report["errors"].append({"kind": type(error).__name__})
    finally:
        if job:
            job.close()
        if process:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            if reader:
                reader.join(5)
            process.stdout.close()
            handle = getattr(process, "_handle", None)
            if handle:
                handle.Close()
        report["owned_worker_stopped"] = process is None or process.poll() is not None
        report["seconds"] = round(time.monotonic() - started, 3)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "evidence": str(target.relative_to(ROOT)),
                "errors": report["errors"],
                "metrics": {k: v for k, v in report.get("metrics", {}).items() if k != "cases"},
            }
        )
    )
    return qualification_exit_code(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--challenge", choices=("baseline24", "attribution36"), default="baseline24"
    )
    args = parser.parse_args()
    raise SystemExit(execute(args.run_id, args.challenge))
