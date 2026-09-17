"""Freeze factual local v9 acceptance evidence; never infer legal/Store certification."""

from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "dist/qa/v9-qwen"
RELEASE = ROOT / "dist/release/v9.0.0"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    package = RELEASE / "msix/MaineFamilyLawLLM_9.0.0.0_x64.msix"
    suites, repaired = {}, set()
    repair_reports = {
        "research-environment-junit.xml",
        "migration-repair-junit.xml",
        "assignment-repair-junit.xml",
        "unit-junit.xml",
        "version-final-junit.xml",
        "shipment-followup-junit.xml",
        "restore-layout-junit.xml",
    }
    for path in sorted(QA.glob("*junit.xml")):
        cases = list(ET.parse(path).getroot().iter("testcase"))
        failures, skips, passed = [], [], []
        for case in cases:
            identity = f"{case.get('classname')}::{case.get('name')}"
            if case.find("failure") is not None or case.find("error") is not None:
                failures.append(identity)
            elif case.find("skipped") is not None:
                skips.append({"test": identity, "reason": case.find("skipped").get("message")})
            else:
                passed.append(identity)
        suites[path.name] = {
            "tests": len(cases),
            "passed": len(passed),
            "failures": failures,
            "skips": skips,
            "sha256": sha(path),
        }
        if path.name in repair_reports:
            repaired.update(passed)
    full = read(QA / "full-regression/summary.json")
    original_failures = [test for batch in full["batches"] for test in batch.get("failures", [])]
    unresolved = sorted(set(original_failures) - repaired)
    frozen = read(QA / "frozen/frozen-qwen.json")
    browser = read(QA / "media/browser-verification.json")
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "dirty_worktree": True,
        "package": {
            "path": str(package),
            "bytes": package.stat().st_size,
            "sha256": sha(package),
            "version": "9.0.0.0",
            "signing": "unsigned_for_store_submission",
        },
        "test_reports": suites,
        "full_regression": {
            "original_status": full["status"],
            "collected": full["collected"],
            "totals": full.get("totals"),
            "seconds": full.get("seconds"),
            "original_failures": original_failures,
            "verified_by_separate_followup": sorted(set(original_failures) & repaired),
            "unresolved": unresolved,
            "source_snapshot_predates_final_quotation_only_drafting": True,
            "final_changed_path_coverage": [
                "unit-junit.xml",
                "live-junit.xml",
                "version-final-junit.xml",
                "restore-layout-junit.xml",
                "frozen/frozen-qwen.json",
            ],
            "single_clean_full_suite_claimed": False,
        },
        "frozen_checks": [
            {key: row[key] for key in ("model", "task", "pass", "duration_seconds")}
            for row in frozen["checks"]
        ],
        "browser": browser,
        "cleanup": read(QA / "cleanup-status.json"),
        "package_audits": {
            name: read(RELEASE / "evidence" / name).get("status")
            for name in (
                "private-data-audit.json",
                "sealed-msix-archive-audit.json",
                "package-size-budget.json",
            )
        },
        "known_boundaries": [
            "General Qwen weights unchanged; no Maine-law specialist qualification "
            "or legal-quality certification.",
            "Evidence and drafting select exact source quotations, "
            "not autonomous factual/legal conclusions.",
            "Model relevance, completeness and factual truth remain unverified; "
            "human source review is required.",
            "Short selected passages only; no silent context truncation or whole-corpus inference.",
            "Ollama and 4B/8B weights are separate installations, not MSIX payloads.",
            "Closing Qwen review discards the UI result but does not cancel engine generation; "
            "a bounded timeout applies.",
            "Fresh installed-MSIX upgrade and WACK were not executed in this run.",
        ],
        "store_ga_decision": "STORE_GA_NOT_EVALUATED",
        "enterprise_ga_decision": "ENTERPRISE_GA_NOT_EVALUATED",
        "repairs": [
            "Explicit Qwen non-thinking template; strict completed/model-bound responses "
            "and bounded context.",
            "Source-quote reconstruction prevents the observed no-receipt-requested fabrication "
            "from being displayed.",
            "Approval binds requested route as well as effective model, task, matter, "
            "session and sources.",
            "GPU headroom includes system reserve; keep_alive=0 releases residency "
            "after each request.",
            "Review dialog defaults to curated 4B/8B route while preserving explicit "
            "saved preferences.",
            "Two audit tests now use the application vault-key resolver rather than "
            "assuming an environment key.",
            "Current version expectations, local package identity, design metadata and shipment "
            "policy aligned to 9.0.0 without altering historical release scope manifests.",
            "Saved-context restore notice is collapsed inside the chat scroller; it no longer "
            "creates a fourth grid row that obscures the conversation.",
        ],
    }
    coverage_complete = (
        bool(full.get("totals"))
        and full["totals"]["tests"] == full["collected"]
        and all(batch.get("coverage_matches_collection") for batch in full["batches"])
    )
    final_tests_pass = all(
        suites[name]["tests"] and not suites[name]["failures"]
        for name in ("unit-junit.xml", "live-junit.xml", "security-junit.xml")
    )
    report["local_acceptance"] = (
        "PASS_BOUNDED_WORKFLOWS"
        if coverage_complete
        and final_tests_pass
        and not unresolved
        and frozen["pass"]
        and browser["pass"]
        and all(value == "pass" for value in report["package_audits"].values())
        else "BLOCKED_OR_INCOMPLETE"
    )
    (RELEASE / "RELEASE_VERIFICATION.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    scope = read(ROOT / "configs/v900_release_scope.json")
    scope["decision"] = report["local_acceptance"]
    scope["public_feature_claims_status"] = "usable_with_limitations"
    scope["verification_report"] = "RELEASE_VERIFICATION.json"
    scope["package_sha256"] = sha(package)
    scope["scope_verified_in_this_run"] = ["optional_local_qwen_source_review"]
    scope["existing_scope_recertified"] = False
    (RELEASE / "release-scope.json").write_text(
        json.dumps(scope, indent=2) + "\n", encoding="utf-8"
    )
    summary = [
        "# v9.0.0 local verification",
        "",
        report["local_acceptance"],
        "",
        f"MSIX: {package.name} ({package.stat().st_size:,} bytes)",
        f"SHA-256: {sha(package)}",
        "",
        "## Evidence",
        "",
        f"Full regression original result: {full['status']}; totals: {full.get('totals')}",
        "Original failures with separate passing follow-up: "
        f"{len(set(original_failures) & repaired)}",
        f"Unresolved failures: {len(unresolved)}",
        f"Frozen real-model checks: {sum(r['pass'] for r in frozen['checks'])}/4",
        f"Browser checks: {browser}",
        "",
        "## Limits",
        "",
    ]
    summary.extend("- " + item for item in report["known_boundaries"])
    summary.extend(
        [
            "",
            "No blanket GA, Store certification, or legal-quality certification is claimed.",
            "Original regression failures remain in full-regression/summary.json; "
            "follow-up reports are separate.",
        ]
    )
    (RELEASE / "RELEASE_VERIFICATION.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    package.with_suffix(".msix.sha256").write_text(
        f"{sha(package)}  {package.name}\n", encoding="ascii"
    )
    paths = [
        RELEASE / "RELEASE_VERIFICATION.json",
        RELEASE / "RELEASE_VERIFICATION.md",
        RELEASE / "release-scope.json",
        package,
        *sorted((RELEASE / "evidence").glob("*.json")),
        *sorted(QA.glob("*junit.xml")),
        QA / "full-regression/summary.json",
        QA / "frozen/frozen-qwen.json",
        QA / "cleanup-status.json",
        *sorted((QA / "media").glob("*")),
    ]
    (RELEASE / "RELEASE_ARTIFACT_MANIFEST.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": str(path.relative_to(ROOT)),
                        "bytes": path.stat().st_size,
                        "sha256": sha(path),
                    }
                    for path in paths
                    if path.is_file()
                ],
                "private_data": "fictional_QA_only_no_private_profiles_in_submission",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "local_acceptance": report["local_acceptance"],
                "unresolved": unresolved,
                "package_sha256": sha(package),
            }
        )
    )


if __name__ == "__main__":
    main()
