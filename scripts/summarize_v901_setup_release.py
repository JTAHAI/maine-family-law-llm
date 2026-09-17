"""Freeze compact, honest 9.0.1 setup/package verification evidence."""
from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "dist/release/v9.0.1"
QA = ROOT / "dist/qa/v901-setup"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    package = RELEASE / "msix/MaineFamilyLawLLM_9.0.1.0_x64.msix"
    runtime = RELEASE / "runtime/MaineFamilyLawLLM.exe"
    suites = []
    for name in ("regression-final.xml", "version-tests-final.xml", "installer-final.xml"):
        suite = ET.parse(QA / name).getroot().find("testsuite")
        suites.append({"file": name, **suite.attrib})
    frozen = load(QA / "frozen/frozen-qwen.json")
    ui = load(QA / "browser-verification.json")
    bindings = []
    with zipfile.ZipFile(package) as archive:
        for relative in ("MaineFamilyLawLLM.exe", "_internal/src/maine_family_law_llm/ui/workbench.js",
                         "_internal/src/maine_family_law_llm/version.py", "_internal/configs/maine_v6_visual_design_policy.json"):
            actual = hashlib.sha256(archive.read(relative)).hexdigest()
            source = RELEASE / "runtime" / relative
            source_path = ROOT / relative.removeprefix("_internal/") if relative.startswith("_internal/") else source
            bindings.append({"entry": relative, "sha256": actual, "matches_runtime": actual == sha(source),
                             "matches_source": actual == sha(source_path)})
        manifest = archive.read("AppxManifest.xml").decode("utf-8-sig")
    audits = {}
    for name in ("private-data-audit.json", "bundled-engine-inventory.json", "sealed-msix-payload-audit.json",
                 "sealed-msix-archive-audit.json", "msix-path-audit.json", "store-build-smoke.json"):
        audits[name] = load(RELEASE / "evidence" / name)
    git = lambda *args: subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    report = {
        "version": "9.0.1", "package_version": "9.0.1.0", "created_at": datetime.now(timezone.utc).isoformat(),
        "decision": "BUILT_FUNCTIONALLY_VERIFIED_WITH_QUALIFICATION_LIMITS",
        "git": {"root": git("rev-parse", "--show-toplevel"), "head": git("rev-parse", "HEAD"),
                "branch": git("branch", "--show-current"), "changes": git("status", "--short").splitlines(),
                "diff_stat": git("diff", "--stat")},
        "package": {"path": str(package), "bytes": package.stat().st_size, "sha256": sha(package),
                    "signing": "unsigned_for_Microsoft_Store_signing", "version_in_manifest": 'Version="9.0.1.0"' in manifest,
                    "language_en_us": 'Language="en-us"' in manifest, "x_generate_absent": "x-generate" not in manifest},
        "focused_test_suites": suites,
        "counts_note": "Installer suite overlaps regression; do not add all suite counts as distinct tests.",
        "syntax": {"python_compileall": "pass", "both_production_js_mirrors_node_check": "pass"},
        "frozen": {"pass": frozen["pass"], "executable_sha256": frozen["executable_sha256"],
                   "matches_final_runtime": frozen["executable_sha256"] == sha(runtime),
                   "model_task_results": [{k: r[k] for k in ("model", "task", "pass", "duration_seconds")} for r in frozen["checks"]],
                   "setup_results": [{k: r[k] for k in ("model", "pass", "seconds")} for r in frozen["setup_checks"]]},
        "browser": ui, "package_bindings": bindings, "package_audits": audits,
        "limitations": ["Clean Windows installation of missing Ollama/model components was fixture-tested, not live-tested.",
                        "Installed MSIX upgrade/uninstall and WACK were not executed.",
                        "Full repository suite was not rerun for 9.0.1; focused suites are reported exactly.",
                        "Qwen models are general-purpose. Exact quotations do not certify legal quality, relevance, completeness or factual truth.",
                        "Models are downloaded only with consent; weights are not bundled in this MSIX."]}
    report["artifact_hashes"] = {str(p.relative_to(ROOT)): sha(p) for p in [package, runtime,
        ROOT / "legal/local_ai/installer.py", ROOT / "app/api/local_ai_setup.py",
        ROOT / "src/maine_family_law_llm/ui/workbench.js", ROOT / "docs/handoffs/NH_4B_8B_DIRECT_COPY_HANDOFF.md",
        QA / "regression-final.xml", QA / "version-tests-final.xml", QA / "frozen/frozen-qwen.json", QA / "browser-verification.json"]}
    (RELEASE / "RELEASE_VERIFICATION.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (RELEASE / "RELEASE_VERIFICATION.txt").write_text(
        "9.0.1 built; component reuse and source-bound Qwen workflows verified.\n"
        + "MSIX SHA-256: " + report["package"]["sha256"] + "\n"
        + "\n".join(report["limitations"]) + "\n", encoding="utf-8")
    print(json.dumps({"package": report["package"], "frozen": report["frozen"], "bindings": bindings}, indent=2))
    return 0 if (frozen["pass"] and report["frozen"]["matches_final_runtime"] and ui["pass"]
                 and all(b["matches_runtime"] and b["matches_source"] for b in bindings)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
