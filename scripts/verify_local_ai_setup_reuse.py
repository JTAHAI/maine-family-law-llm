"""Verify consent-bound reuse against existing local models; never download.

State and compact evidence stay under repository dist. Refuses this live drill
unless both engine and pinned model are already installed. Not a cold-install
or legal-quality test.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal.local_ai.installer import InstallService, MODELS, TERMINAL, WindowsBackend
from legal.local_ai.setup import LocalAiSetupStore


def main():
    output = ROOT / "dist/qa/v901-setup"
    output.mkdir(parents=True, exist_ok=True)
    owner = LocalAiSetupStore(root=output / "state", audience="fictional-setup-reuse", encryption_key="fictional-qa-key")
    service = InstallService(WindowsBackend())
    report = {"level": "source_service_real_installed_ollama_and_models", "cold_install_tested": False,
              "legal_quality_certification": False, "checks": []}
    for model in MODELS:
        start = time.monotonic()
        plan = service.prepare(owner, model)
        if not (plan["engine_installed"] and plan["model_installed"] and plan["download_bytes"] == 0):
            raise RuntimeError("reuse drill refuses any download or installation")
        job = service.start(owner, plan["plan_token"], True)["job_id"]
        for _ in range(300):
            result = service.status(owner, job)
            if result["status"] in TERMINAL:
                break
            time.sleep(1)
        else:
            service.cancel(owner, job)
            raise RuntimeError("reuse verification timed out")
        passed = result["status"] == "ready" and not any(
            event["stage"] in {"downloading_engine", "installing_engine", "downloading_model"}
            for event in result["events"])
        report["checks"].append({"model": model, "pass": passed, "seconds": round(time.monotonic()-start, 3),
                                 "plan": plan, "result": result})
        print(json.dumps({"model": model, "pass": passed, "status": result["status"], "error": result["error_code"]}), flush=True)
    report["pass"] = all(row["pass"] for row in report["checks"])
    (output / "live-reuse.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
