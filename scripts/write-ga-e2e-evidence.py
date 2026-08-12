"""Write the evidence-backed GA end-to-end matrix for the fictional matter.

This script is release evidence tooling only.  It does not modify application
features, user matters, or package state.
"""

from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "dist" / "ga_today" / "evidence"
RUNTIME = ROOT / "dist" / "ga_today" / "e2e_runtime"
SCREENSHOTS = EVIDENCE / "screenshots"
FIXTURE_MANIFEST = (
    RUNTIME
    / "fictional_ga_matter_20260811"
    / "fictional_ga_matter_manifest.json"
)
API_PROBE = RUNTIME / "installed_api_probe.json"
MSIX = ROOT / "dist" / "store" / "msix" / "MaineFamilyLawLLM_6.0.4.0_x64.msix"
INSTALLED_EXE = Path(
    r"C:\Program Files\WindowsApps\TAHAIWebServices.MaineFamilyLawLLM_6.0.4.0_x64__k9af96g77tmj4\MaineFamilyLawLLM.exe"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def png_info(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    valid = raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24
    width = height = 0
    if valid:
        width, height = struct.unpack(">II", raw[16:24])
    return {
        "path": portable(path),
        "sha256": sha256(path),
        "bytes": len(raw),
        "png_valid": valid,
        "width": width,
        "height": height,
    }


def journey(
    number: int,
    name: str,
    action: str,
    expected: str,
    actual: str,
    routes: list[str],
    ui_state: str,
    ids: list[str],
    duration_ms: float | None,
    evidence: list[str],
    passed: bool,
    failure: str = "",
) -> dict[str, object]:
    return {
        "journey": number,
        "name": name,
        "action": action,
        "expected_result": expected,
        "actual_result": actual,
        "api_routes": routes,
        "ui_state": ui_state,
        "source_or_artifact_ids": ids,
        "duration_ms": duration_ms,
        "duration_note": (
            "Observed wall time for the principal UI/API action."
            if duration_ms is not None
            else "Not separately instrumented; no duration is inferred."
        ),
        "screenshot_or_dom_evidence": evidence,
        "pass": passed,
        "result": "pass" if passed else "fail",
        "failure_artifact": failure,
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    probe = json.loads(API_PROBE.read_text(encoding="utf-8"))
    probe_by_name = {row["name"]: row for row in probe}

    shots = [png_info(path) for path in sorted(SCREENSHOTS.glob("*.png"))]
    dom_files = [
        {
            "path": portable(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(SCREENSHOTS.glob("*.dom.txt"))
    ]

    active_case_id = "22269581286614e8"
    evidence_build_id = "06ea4e3c9d8b8166764e4ba2"
    document_id = "5d5eedb84cdd4715983b361c51139265"
    revision_id = "375adf477b96457499e6515266faa301"
    pending_revision_id = "1c168c5c7fa740e2a3d83f7e0132608b"
    packet_tokens = [
        "ca316265ef01dcd80d90027a88708350bccbfe1da49e4d3695a4aab385fba901",
        "abfb952f2e93482cc67d3bc33a7122786c428b8c6eb9658210a8b9825510f61d",
        "f58fb1cc5f273e8d947a9aa931c3f9c96fc1bb0a486659fbf755d58fa5cadedf",
    ]

    journeys = [
        journey(1, "Launch healthy workbench", "Launch the installed frozen executable on loopback and open its shipped workbench.", "Workbench loads and runtime health is healthy.", "The shipped workbench loaded, but /api/health returned degraded because product version 6.0.4 and package version 6.0.4.0 fail strict alignment.", ["GET /", "GET /api/health", "GET /api/runtime-diagnostics"], "Workbench rendered; health badge initially reported Offline/unknown and runtime health remained degraded.", [], 3100, ["dist/ga_today/evidence/screenshots/01_frozen_workbench_fictional_matter.png", "dist/ga_today/evidence/screenshots/01_frozen_workbench_fictional_matter.dom.txt"], False, "runtime_health:blocker:version_alignment"),
        journey(2, "Open fictional matter", "Activate the deterministic fictional matter and reload the shipped UI.", "The selected matter is visible in production UI.", "Canonical activation succeeded and Fictional GA Matter 2026 was visible before and after process restart.", ["POST /api/activate-corpus", "GET /api/corpus-library"], "Matter selector shows Fictional GA Matter 2026.", [active_case_id], 900, ["dist/ga_today/evidence/screenshots/01_frozen_workbench_fictional_matter.png", "dist/ga_today/evidence/screenshots/15_frozen_restart_integrity.png"], True),
        journey(3, "Import mixed records", "Register the mixed-record fixture and rebuild its index.", "A user imports the records through the shipped UI and the canonical API indexes them.", "The canonical API indexed 14 root documents and 1 PDF page without parse failures. This was activated/rebuilt through the API fixture harness, not a production-UI import action.", ["POST /api/activate-corpus", "POST /api/corpus-rebuild-index", "GET /api/corpus-inventory"], "Production UI shows the indexed matter but the import action itself was not proven through UI.", [active_case_id, "EV-FICTIONAL_GA-20260811-0001..0014"], 200, ["dist/ga_today/e2e_runtime/fictional_ga_matter_20260811/fictional_ga_matter_manifest.json", "dist/ga_today/e2e_runtime/installed_api_probe.json"], False, "ui_import_not_exercised"),
        journey(4, "Inspect record intelligence", "Inspect hash, parser, OCR, privacy, duplicate/change state, and exact source text.", "All requested intelligence fields are accurate and analysis can run.", "Hash verification, parser state, privacy label, exact text, and immutable-source messaging rendered. OCR was unavailable; the scanned page remained ocr_not_run; exact duplicates were retained as separate canonical evidence IDs; and the document-intelligence consent control could not enable TXT analysis.", ["GET /api/records/inspect/{token}", "GET /api/document-intelligence/status", "POST /api/document-intelligence/analyze", "GET /api/corpus-inventory"], "Verified source inspector works; Structure/OCR/privacy dialog remains disabled for this record.", ["EV-FICTIONAL_GA-20260811-0004", "EV-FICTIONAL_GA-20260811-0005-P0001"], 3400, ["dist/ga_today/evidence/screenshots/05_frozen_private_record_inspector.png", "dist/ga_today/evidence/screenshots/06_frozen_document_intelligence.png"], False, "ocr_unavailable_and_document_intelligence_action_disabled"),
        journey(5, "Ask Maine-law question", "Ask which Maine statute supplies parental-rights best-interest factors.", "A source-backed answer appears with review status.", "The production UI returned a Maine-law answer referencing 19-A M.R.S. § 1653(3), displayed two source cards, and kept Review required visible.", ["POST /ask"], "Answer, citations, evidence controls, and review-required banner visible.", ["19-A-MRS-1653-3"], None, ["dist/ga_today/evidence/screenshots/02_frozen_maine_law_answer.png", "dist/ga_today/evidence/screenshots/02_frozen_maine_law_answer.dom.txt"], True),
        journey(6, "Open exact source", "Open a source card and its quick preview.", "The exact supporting passage is visible with source metadata.", "The official-source quick preview opened to Best interest of child, exposed the official link, and retained review-required language.", ["POST /ask", "GET /sources"], "Exact source preview open in the shipped UI.", ["19-A-MRS-1653-3"], None, ["dist/ga_today/evidence/screenshots/03_frozen_exact_source_preview.png", "dist/ga_today/evidence/screenshots/03_frozen_exact_source_preview.dom.txt"], True),
        journey(7, "Verify citations and quotes", "Verify a valid Maine citation, fake citation, exact quote, and mismatched quote.", "Each fixture receives a deterministic resolution result.", "The UI opened deterministic support verification, but the installed authority generation was unavailable/unverified; it reported blocked, extracted no legal claims, and detected no citation in the rendered answer. Source-level verifier tests passed, but frozen-app verification did not prove the four fixtures.", ["POST /api/authority/verify-answer"], "Verify answer support dialog is blocked and receipt copy is disabled.", ["EV-FICTIONAL_GA-20260811-0014"], 1500, ["dist/ga_today/evidence/screenshots/09_frozen_authority_verification.png", "dist/ga_today/evidence/screenshots/09_frozen_authority_verification.dom.txt"], False, "active_authority_product_unavailable_or_unverified"),
        journey(8, "Build timeline", "Build a source-bound chronology from the fictional matter.", "Timeline is visible in the shipped UI.", "The older evidence-work-product API produced three review-required timeline rows, but the installed UI has no timeline workbench or drill-down for them.", ["POST /api/evidence-work-product/build", "GET /api/evidence-work-product/active"], "No installed timeline UI entry.", [evidence_build_id], probe_by_name["build_evidence_work_product"]["duration_ms"], ["dist/ga_today/e2e_runtime/installed_api_probe.json"], False, "route_only_timeline_not_production_ui_proof"),
        journey(9, "Correct event append-only", "Correct one timeline event and inspect immutable history.", "A corrected event and append-only history are visible.", "The installed package exposes no canonical timeline correction route or production control.", [], "No installed timeline correction UI.", [], None, [], False, "installed_timeline_correction_absent"),
        journey(10, "Review claim coverage", "Review support, contradiction, qualification, and missing context for one claim.", "All four dispositions are usable in the shipped UI.", "The revision-bound review found 3/3 fact strings and retained seven blockers, but extracted zero material legal claims; the evidence API reported zero contradictions. Qualification and missing-context dispositions were not operable end to end.", ["POST /api/document-workspace/documents/{document_id}/review/prepare", "POST /api/evidence-work-product/build"], "Review packet visible with Authority blocked, Claims 0, and seven blockers.", [document_id, revision_id, evidence_build_id], 1800, ["dist/ga_today/evidence/screenshots/12_frozen_unsupported_claim_review.png", "dist/ga_today/evidence/screenshots/12_frozen_unsupported_claim_review.dom.txt"], False, "claim_disposition_workflow_incomplete_in_installed_ui"),
        journey(11, "Inspect coverage and missing records", "Inspect record coverage and the explicit missing attachment.", "The missing attachment appears in coverage UI.", "The evidence packet indexed the EML but produced an empty missing_record_checklist even though the fixture explicitly identifies a missing attachment; no installed coverage UI is present.", ["POST /api/evidence-work-product/build"], "No installed record-coverage/missing-record workbench.", ["EV-FICTIONAL_GA-20260811-0009", evidence_build_id], probe_by_name["build_evidence_work_product"]["duration_ms"], ["dist/ga_today/e2e_runtime/installed_api_probe.json"], False, "missing_attachment_not_detected"),
        journey(12, "Inspect operative order candidate", "Review the amendment and exact modified exchange term without deciding legal status.", "Resolver candidate and exact source term are visible.", "The exact amended term was retrieved and inspected with a hash-verified source. The installed package has no operative-order resolver route or supersession UI, so candidate resolution was not proven.", ["POST /ask", "GET /api/records/inspect/{token}"], "Exact amended term visible; no resolver/supersession workspace.", ["EV-FICTIONAL_GA-20260811-0003", "EV-FICTIONAL_GA-20260811-0004"], None, ["dist/ga_today/evidence/screenshots/04_frozen_private_record_answer.png", "dist/ga_today/evidence/screenshots/05_frozen_private_record_inspector.png"], False, "installed_operative_order_resolver_absent"),
        journey(13, "Create review-required draft", "Create a draft from selected verified authority and evidence.", "A draft is bound to verified authority/evidence and remains review-required.", "A hash-verified private order was imported to a local immutable-source draft and Review required remained visible. Verified authority was unavailable, so the complete authority-plus-evidence acceptance condition was not met.", ["POST /api/document-workspace/import-record", "GET /api/document-workspace/documents/{document_id}"], "Documents & drafting dialog shows original preserved and review required.", [document_id, revision_id, "EV-FICTIONAL_GA-20260811-0004"], 2100, ["dist/ga_today/evidence/screenshots/10_frozen_draft_workspace.png", "dist/ga_today/evidence/screenshots/10_frozen_draft_workspace.dom.txt"], False, "verified_authority_binding_unavailable"),
        journey(14, "Review unsupported claims", "Build a revision-bound review for three fictional unsupported claims.", "Unsupported/citation blockers remain visible and filing readiness stays false.", "The UI built the immutable review packet, reported Authority blocked, Claims 0, seven blockers, and kept the draft not reviewed/not filing-ready.", ["POST /api/document-workspace/documents/{document_id}/review/prepare"], "Seven blockers visible in revision-bound review.", [document_id, revision_id], 1800, ["dist/ga_today/evidence/screenshots/12_frozen_unsupported_claim_review.png", "dist/ga_today/evidence/screenshots/12_frozen_unsupported_claim_review.dom.txt"], True),
        journey(15, "Compare revisions and tracked DOCX", "Propose a fictional edit, compare revisions, and exercise tracked DOCX where supported.", "Diff is shown and supported DOCX tracked review is exercised.", "The shipped UI produced a +3/-2 explicit revision comparison and pending immutable proposal. Tracked DOCX is reported available by the runtime but was not exercised against the DOCX fixture; the active TXT draft correctly disabled that action.", ["POST /api/document-workspace/documents/{document_id}/proposals", "POST /api/document-workspace/documents/{document_id}/docx/tracked-edit"], "Revision diff visible; Create tracked review copy disabled for the TXT draft.", [document_id, pending_revision_id], 1400, ["dist/ga_today/evidence/screenshots/11_frozen_revision_comparison.png", "dist/ga_today/evidence/screenshots/11_frozen_revision_comparison.dom.txt"], False, "supported_docx_tracked_review_not_exercised"),
        journey(16, "Guided form stale warning", "Start a guided form session and expose the stale-form warning.", "A session opens and stale/currentness warning is visible.", "The installed UI reported Catalog unavailable and No verified current forms are available. Its form-build controls stayed disabled, and the installed OpenAPI has no guided form-session route.", ["GET /api/findings-forms/status", "POST /api/findings-forms/complete"], "Findings/forms section disabled because verified authority catalog is unavailable.", ["EV-FICTIONAL_GA-20260811-0013"], None, ["dist/ga_today/evidence/screenshots/12_frozen_unsupported_claim_review.dom.txt"], False, "guided_form_session_unavailable"),
        journey(17, "Open command center", "Open the whole-matter command center.", "Command center loads from production navigation.", "The installed package has no matter-command-center route or production navigation entry.", [], "No installed command-center entry.", [], None, [], False, "installed_command_center_absent"),
        journey(18, "Freeze matter snapshot", "Freeze a whole-matter snapshot.", "Immutable snapshot ID and receipt are visible.", "No installed snapshot route or production control was present.", [], "No installed snapshot control.", [], None, [], False, "installed_snapshot_absent"),
        journey(19, "Generate evidence packet", "Generate a deterministic review-required filing/evidence packet.", "Packet is created with review status and visible blockers.", "The production UI built a reviewed filing packet and explicitly announced that it was built with visible blockers.", ["POST /api/reviewed-filing-packet/documents/{document_id}/build"], "Reviewed filing packet built with visible blockers.", [document_id, *packet_tokens], 2200, ["dist/ga_today/evidence/screenshots/13_frozen_review_packet_blockers.png", "dist/ga_today/evidence/screenshots/13_frozen_review_packet_blockers.dom.txt"], True),
        journey(20, "Inspect packet receipt", "Inspect packet JSON/HTML, receipt, and blocker report.", "Artifact links and blocker counts are visible.", "The UI exposed JSON, HTML, and receipt artifacts; two packet blockers and seven revision-review blockers remained visible.", ["GET /api/reviewed-filing-packet/artifacts/{token}"], "Artifact links and blocker report visible.", packet_tokens, None, ["dist/ga_today/evidence/screenshots/13_frozen_review_packet_blockers.dom.txt"], True),
        journey(21, "Cancel long operation", "Start and cancel a long-running local operation.", "A running job becomes cleanly cancelled with a partial-state receipt.", "OCR start failed closed with HTTP 409 because no Tesseract engine was installed. Cancel returned status idle and cancel_requested false; no operation reached running state, so cancellation was not proven.", ["POST /api/corpus-ocr/start", "POST /api/corpus-ocr/cancel", "GET /api/corpus-ocr/status"], "No running operation was available to cancel.", ["EV-FICTIONAL_GA-20260811-0005"], probe_by_name["ocr_cancel"]["duration_ms"], ["dist/ga_today/e2e_runtime/installed_api_probe.json"], False, "long_running_operation_never_started"),
        journey(22, "Restart integrity", "Terminate the exact installed frozen process, restart it, reload the UI, and inspect state.", "Matter, draft, audit chain, and review state survive restart.", "After process restart, the active fictional matter remained selected; document_count=1, pending_revision_count=1, audit.valid=true with three events; the UI again showed the matter and Review required.", ["GET /api/corpus-library", "GET /api/document-workspace/status", "GET /"], "Fictional GA Matter 2026 and Review required visible after reload.", [active_case_id, document_id, pending_revision_id], 3100, ["dist/ga_today/evidence/screenshots/15_frozen_restart_integrity.png", "dist/ga_today/evidence/screenshots/15_frozen_restart_integrity.dom.txt"], True),
    ]

    passed = sum(1 for row in journeys if row["pass"])
    failed = len(journeys) - passed
    hash_targets = [
        FIXTURE_MANIFEST,
        API_PROBE,
        ROOT / "scripts" / "build-ga-e2e-fictional-matter.py",
        ROOT / "scripts" / "write-ga-e2e-evidence.py",
        MSIX,
        INSTALLED_EXE,
    ]
    artifacts = [
        {
            "path": portable(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in hash_targets
        if path.exists()
    ]

    matrix = {
        "schema_version": "ga_e2e_feature_matrix_v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "decision": "BLOCKED",
        "scope": "canonical GA end-to-end slice; no product features added",
        "git": {
            "available": False,
            "expected_root": str(ROOT),
            "verification": "fatal: not a git repository (or any parent up to mount point)",
            "user_changes_preserved": True,
        },
        "test_environment": {
            "os": "Windows",
            "loopback_url": "http://127.0.0.1:8791/",
            "production_ui": "UI bundled in the installed frozen executable",
            "installed_package": "TAHAIWebServices.MaineFamilyLawLLM_6.0.4.0_x64__k9af96g77tmj4",
            "installed_package_status": "Ok",
            "product_version": "6.0.4",
            "package_version": "6.0.4.0",
            "msix_sha256": "d0b1fd92f32571a92377c6764c198e06c6bd386fecafbd64277aa0904fdc7673",
            "installed_exe_sha256": "909101d07108cd75ef3b19e5ae8c66d5485c6996851ea248dc7a149f3d67963b",
            "network_used": False,
        },
        "fictional_matter": {
            "schema_version": fixture["schema_version"],
            "label": fixture["matter_label"],
            "fictional": fixture["fictional"],
            "private_or_real_data": fixture["private_or_real_data"],
            "record_count": fixture["record_count"],
            "required_fixtures": fixture["required_fixtures"],
            "records": fixture["records"],
            "active_case_id": active_case_id,
        },
        "test_levels": {
            "compile": {"result": "pass", "commands": ["python -m compileall -q legal app src maine_family_law_llm scripts tests", "node --check src\\maine_family_law_llm\\ui\\workbench.js"]},
            "collection": {"result": "pass", "test_files": 301, "collected": 1199},
            "service_and_api": {"result": "pass", "passed": 115, "skipped": 3, "failed": 0, "skip_reasons": ["symlinks unavailable", "Windows symlink privilege is unavailable"]},
            "production_ui": {"result": "fail", "journeys_passed": passed, "journeys_failed": failed, "automation": "Codex in-app Browser against installed frozen UI"},
            "frozen_executable": {"result": "fail", "launch": "pass", "restart": "pass", "runtime_health": "degraded", "health_blockers": ["version_alignment"]},
            "installed_msix": {"result": "fail", "installed": True, "package_status": "Ok", "reinstall_performed": False, "reason": "The installed qualified package was tested in place; E2E and health blockers remain."},
        },
        "journey_summary": {"total": len(journeys), "passed": passed, "failed": failed},
        "journeys": journeys,
        "repairs": [
            "Added a deterministic fictional GA matter generator.",
            "Added canonical release-evidence generation with artifact hashing and PNG validation.",
            "No product behavior was changed; installed-runtime failures remain honestly blocked.",
        ],
        "features_hidden_due_to_failure": [],
        "hidden_feature_note": "No installed-package feature could be safely hidden without rebuilding the package. Missing/disabled surfaces remain release blockers and must not be advertised.",
        "ga_blockers": [row["failure_artifact"] for row in journeys if not row["pass"]],
        "screenshots": shots,
        "dom_evidence": dom_files,
        "artifact_hashes": artifacts,
    }

    matrix_path = EVIDENCE / "03_e2e_feature_matrix.json"
    matrix_path.write_text(json.dumps(matrix, indent=2) + "\n", encoding="utf-8")

    summary_lines = [
        "CANONICAL GA END-TO-END SUMMARY",
        "================================",
        "",
        "Decision: BLOCKED",
        f"Installed package: {matrix['test_environment']['installed_package']} (Status: Ok)",
        "Actual UI: shipped UI loaded by the installed frozen executable",
        f"Fictional matter: {fixture['matter_label']} ({fixture['record_count']} root records; no real/private data)",
        "Network used: false",
        "",
        "Test levels",
        "-----------",
        "Compile: PASS (Python compileall and production workbench.js syntax)",
        "Collection: PASS (1,199 tests in 301 files)",
        "Focused service/API: PASS (115 passed, 3 expected Windows symlink skips, 0 failed)",
        f"Production UI journeys: FAIL ({passed} passed, {failed} failed)",
        "Frozen executable: FAIL overall; launch/restart pass, runtime health degraded",
        "Installed MSIX: FAIL overall; installed status Ok, but E2E blockers remain",
        "",
        "Journey results",
        "---------------",
    ]
    for row in journeys:
        summary_lines.append(
            f"{row['journey']:02d}. {'PASS' if row['pass'] else 'FAIL'} - {row['name']}: {row['actual_result']}"
        )
    summary_lines.extend(
        [
            "",
            "Release blockers",
            "----------------",
            *[f"- {row['journey']:02d} {row['name']}: {row['failure_artifact']}" for row in journeys if not row["pass"]],
            "",
            "No product feature was added, published, uploaded, or self-certified by this slice.",
        ]
    )
    (EVIDENCE / "03_e2e_summary.txt").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )
    print(json.dumps({"matrix": str(matrix_path), "summary": str(EVIDENCE / '03_e2e_summary.txt'), "passed": passed, "failed": failed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
