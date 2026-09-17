"""Fictional frozen-process acceptance, with optional browser inspection window.

Uses installed local Qwen weights; never downloads or modifies them. All QA
state stays in one explicit repository-dist workspace. This is not an MSIX
installation or a legal-quality evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import time
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8879)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--verify-setup-reuse", action="store_true", help="Also exercise consent-bound setup; refuse any download")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "dist") or output == ROOT / "dist":
        parser.error("output must be a dedicated repository dist child")
    runtime = args.runtime.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=True)
    profile = output / "profile"
    case = output / "Fictional Family Demonstration"
    files = case / "02_PRIVATE_FORENSIC_MASTER" / "files"
    files.mkdir(parents=True, exist_ok=True)
    records = []
    for i, text in enumerate(
        [
            "Fictional parent A proposes an exchange at 3:00 p.m. "
            "No acceptance is recorded. A requested receipt is missing.",
            "Fictional parent B proposes an exchange at 4:00 p.m. "
            "No acceptance is recorded. This is not a court finding.",
        ],
        1,
    ):
        path = files / f"DEMO-{i}.txt"
        path.write_text(text, encoding="utf-8")
        records.append(
            {
                "evidence_id": f"DEMO-{i}",
                "title": f"Fictional exchange proposal {i}",
                "source_type": "txt",
                "source_locator": path.name,
                "source_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
                "private_copy_relpath": path.relative_to(case).as_posix(),
                "text_content": text,
                "text_excerpt": text,
                "parser_status": "available",
            }
        )
    indexes = case / "04_INDEXES"
    indexes.mkdir(exist_ok=True)
    (indexes / "private_search_index.json").write_text(json.dumps(records), encoding="utf-8")
    proof = case / "15_PROOF_VALIDATION" / "CASE_BUILD_PROOF.json"
    proof.parent.mkdir(exist_ok=True)
    proof.write_text(
        json.dumps(
            {"case_name": case.name, "total_files_indexed": len(records), "total_pdf_pages": 0}
        ),
        encoding="utf-8",
    )
    library = profile / "MaineFamilyLawLLM" / "case_library.json"
    library.parent.mkdir(parents=True, exist_ok=True)
    library.write_text(
        json.dumps(
            {
                "schema": "maine_family_law_llm.case_library.v1",
                "active_case_root": str(case),
                "cases": [{"case_root": str(case), "label": case.name}],
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "LOCALAPPDATA": str(profile),
            "MFL_RUNTIME_MODE": "store",
            "MFL_AUTHORITY_DATA_ROOT": str(output / "empty-authority"),
            "MFL_RUNTIME_STATE_ROOT": str(output / "state"),
            "MFL_IDEMPOTENCY_STATE_ROOT": str(output / "idempotency"),
            "MFL_VAULT_KEY_ROOT": str(output / "vault"),
            "MFL_LOCAL_AI_STATE_ROOT": str(output / "local-ai-setup"),
            "TEMP": str(output),
            "TMP": str(output),
            "PYTHONDONTWRITEBYTECODE": "1",
            "MFL_LOCAL_API_INSTANCE_ID": secrets.token_hex(32),
        }
    )
    for key in list(env):
        if key.startswith(("MFL_FAST_INTERCHANGE", "MAINE_FAST_INTERCHANGE", "SENTINEL_")):
            env.pop(key)
    base = f"http://127.0.0.1:{args.port}"
    headers = {
        "Content-Type": "application/json",
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "local-desktop",
        "X-MFLL-Client-Session": secrets.token_hex(24),
    }
    opener = build_opener(ProxyHandler({}))

    def request(path, body=None):
        req = Request(
            base + path,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        with opener.open(req, timeout=180) as response:
            if (
                path == "/api/health"
                and response.headers.get("X-MFL-Service-Instance")
                != env["MFL_LOCAL_API_INSTANCE_ID"]
            ):
                raise RuntimeError("refusing_non_owned_local_service")
            return json.loads(response.read())

    process = subprocess.Popen(
        [str(runtime), "--serve-local-api", "--port", str(args.port)],
        cwd=runtime.parent,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    report = {
        "level": "frozen_executable_canonical_api_real_ollama",
        "fixture": "fictional_only",
        "installed_msix_test": False,
        "legal_quality_certification": False,
        "checks": [],
        "setup_checks": [],
        "executable_sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
    }
    try:
        for _ in range(90):
            try:
                health = request("/api/health")
                if health:
                    break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError("frozen process exited") from None
                time.sleep(1)
        else:
            raise RuntimeError("frozen health timeout")
        report["health"] = health
        print(json.dumps({"stage": "frozen_ready", "url": base, "pid": process.pid}), flush=True)
        answer = request(
            "/ask", {"question": "Find mentions of exchange", "search_mode": "my_records"}
        )
        refs = answer.get("local_agent_source_refs", [])
        if len(refs) != 2:
            (output / "ask-diagnostic.json").write_text(
                json.dumps(answer, indent=2), encoding="utf-8"
            )
            raise RuntimeError("fictional search did not supply two exact references")
        for model in ("qwen3:4b", "qwen3:8b"):
            if args.verify_setup_reuse:
                setup_started = time.monotonic()
                plan = request("/api/local-ai/installation/prepare", {"model": model})
                if not (plan["engine_installed"] and plan["model_installed"] and plan["download_bytes"] == 0):
                    raise RuntimeError("frozen reuse drill refuses any download or reinstall")
                job = request("/api/local-ai/installation/start", {"plan_token": plan["plan_token"], "user_confirmed": True})
                for _ in range(240):
                    state = request("/api/local-ai/installation/jobs/" + job["job_id"])
                    if state["status"] in {"ready", "failed", "cancelled", "interrupted"}:
                        break
                    time.sleep(1)
                passed = state["status"] == "ready" and not any(
                    e["stage"] in {"installing_engine", "downloading_engine", "downloading_model"}
                    for e in state["events"])
                report["setup_checks"].append({"model": model, "pass": passed, "plan": plan, "result": state,
                                               "seconds": round(time.monotonic() - setup_started, 3)})
                print(json.dumps({"stage": "setup_reuse", "model": model, "pass": passed}), flush=True)
                if not passed:
                    (output / "frozen-qwen.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                    raise RuntimeError("frozen setup reuse did not pass")
            for task in ("evidence_review", "drafting"):
                body = {
                    "question": (
                        "Review both proposed exchange times and the requested missing receipt. "
                        "Preserve all qualifications and do not infer agreement."
                    )
                    if task == "evidence_review"
                    else (
                        "Draft working material about both proposed exchange times and the "
                        "requested missing receipt. Preserve qualifications; do not infer "
                        "agreement or a court finding."
                    ),
                    "matter_id": answer["local_agent_matter_id"],
                    "source_refs": refs,
                    "task": task,
                    "provider": "curated_ollama_reasoning",
                    "model": model,
                    "endpoint": "http://127.0.0.1:11434",
                }
                start = time.monotonic()
                preview = request("/api/local-agent/preview", body)
                result = request(
                    "/api/local-agent/run",
                    {
                        **body,
                        "run_id": preview["context_manifest"]["run_id"],
                        "source_refs": preview["source_refs"],
                        "approval_token": preview["approval_token"],
                        "approved_manifest_sha256": preview["context_manifest"]["manifest_sha256"],
                    },
                )
                passed = (
                    result["status"] == "completed_review_required"
                    and result["review_required"]
                    and result["provenance_receipt"]["citation_refs"] == [1, 2]
                    and result["model"]["admission"]["execution_policy_revision"]
                    == "qwen-source-review-v6"
                    and result["output_grounding"]["quoted_text_checked"] is True
                    and result["output_grounding"]["factual_claims_verified"] is False
                    and "requested receipt is missing" in result["answer"]
                    and "No receipt requested" not in result["answer"]
                )
                report["checks"].append(
                    {
                        "model": model,
                        "task": task,
                        "pass": passed,
                        "duration_seconds": round(time.monotonic() - start, 3),
                        "result": result,
                    }
                )
                print(json.dumps({"model": model, "task": task, "pass": passed}), flush=True)
        report["pass"] = all(row["pass"] for row in report["checks"] + report["setup_checks"])
        (output / "frozen-qwen.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.serve:
            print("Browser inspection available at " + base, flush=True)
            while process.poll() is None:
                time.sleep(1)
        return 0 if report["pass"] else 1
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)


if __name__ == "__main__":
    raise SystemExit(main())
