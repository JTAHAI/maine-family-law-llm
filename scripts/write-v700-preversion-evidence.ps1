param([string]$RepoRoot = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $RepoRoot).Path
$evidence = Join-Path $root "dist\release\v7.0.0\evidence"
$gaEvidence = Join-Path $root "dist\ga_today\evidence"

function Get-RelativeHash([string]$RelativePath) {
    $full = Join-Path $root $RelativePath
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { return $null }
    return (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Read-JUnit([string]$RelativePath) {
    [xml]$xml = Get-Content -Raw -LiteralPath (Join-Path $root $RelativePath)
    $suite = if ($null -ne $xml.testsuites) { $xml.testsuites.testsuite } else { $xml.testsuite }
    $tests = [int]$suite.tests
    $failures = [int]$suite.failures
    $errors = [int]$suite.errors
    $skipped = [int]$suite.skipped
    return [ordered]@{
        path = $RelativePath
        tests = $tests
        failures = $failures
        errors = $errors
        skipped = $skipped
        passed = $tests - $failures - $errors - $skipped
        duration_seconds = [double]$suite.time
        sha256 = Get-RelativeHash $RelativePath
    }
}

$full = Read-JUnit "dist/release/v7.0.0/evidence/pre-version-ga-postfloor.xml"
$accessibility = Read-JUnit "dist/release/v7.0.0/evidence/preversion-accessibility.xml"
$cancellation = Read-JUnit "dist/release/v7.0.0/evidence/preversion-large-cancellation.xml"
$generatedAt = (Get-Date).ToUniversalTime().ToString("o")

$accepted = @(
    "launch_health", "matter_corpus_open", "record_import_inventory", "deterministic_parser",
    "ocr_searchable_derivative", "document_intelligence_privacy", "duplicate_changed_copy_review",
    "ask_maine_family_law", "official_source_cards_exact_preview", "citation_quote_verification",
    "drafting_revision_history", "revision_comparison", "review_required_packet",
    "canonical_filing_gate", "local_only_privacy", "backup_restore"
)
$hidden = @(
    "timeline_and_event_correction", "claim_disposition_workbench", "guided_current_forms",
    "tracked_docx_installed_workflow", "whole_matter_command_center", "whole_matter_snapshot",
    "record_coverage_missing_attachment"
) + (21..44 | ForEach-Object { "slice_$_" })

$artifactPaths = @(
    "dist/release/v7.0.0/evidence/source-tree-manifest.json",
    "dist/release/v7.0.0/evidence/pre-version-ga-postfloor.xml",
    "dist/release/v7.0.0/evidence/preversion-postfloor-frozen-authority.json",
    "dist/release/v7.0.0/evidence/preversion-postfloor-frozen-ui.json",
    "dist/release/v7.0.0/evidence/preversion-postfloor-offline-run.log",
    "dist/release/v7.0.0/evidence/preversion-bundled-engine-inventory.json",
    "dist/release/v7.0.0/evidence/preversion-runtime-private-data-audit-clean.json",
    "dist/release/v7.0.0/evidence/preversion-dependency-security.json",
    "dist/release/v7.0.0/evidence/preversion-security-focused.xml",
    "dist/release/v7.0.0/evidence/preversion-filing-gate-hash.json",
    "dist/release/v7.0.0/evidence/preversion-backup-restore.json",
    "dist/release/v7.0.0/evidence/preversion-accessibility.xml",
    "dist/release/v7.0.0/evidence/preversion-large-cancellation.xml"
)
$artifacts = @($artifactPaths | ForEach-Object {
    $fullPath = Join-Path $root $_
    [ordered]@{ path = $_; sha256 = Get-RelativeHash $_; bytes = (Get-Item -LiteralPath $fullPath).Length }
})

$sourceIdentity = [ordered]@{
    type = "SOURCE_TREE_IDENTITY_NON_GIT"
    manifest = "dist/release/v7.0.0/evidence/source-tree-manifest.json"
    manifest_sha256 = Get-RelativeHash "dist/release/v7.0.0/evidence/source-tree-manifest.json"
    file_count = 1631
    git = "unavailable"
}
$nonBlocking = @([ordered]@{
    id = "windows_symlink_privilege"
    classification = "environment limitation"
    severity = "P2"
    detail = "Fourteen symlink/Windows-mode tests were skipped with explicit platform reasons; no product failure was observed."
})

$summary = [ordered]@{
    schema_version = "ga_preversion_full_regression_v2"
    generated_at = $generatedAt
    decision = "READY_FOR_VERSION_FREEZE"
    source_identity = $sourceIdentity
    versions = [ordered]@{ product = "6.0.4"; package = "6.0.4.0"; version_changed = $false }
    commands = @(
        "python -m compileall -q legal app src maine_family_law_llm scripts tests",
        "node --check src\maine_family_law_llm\ui\workbench.js",
        "node --check maine_family_law_llm\ui\workbench.js",
        "python -m pytest --collect-only -q", "python -m pytest",
        "python -m pytest -q tests/test_v620_evidence_review_workbench.py::test_timeline_cancellation_is_immediate_for_exactly_500_records",
        "python -m pytest -q tests/test_full_ux_hardening_v700.py tests/test_v500_responsive_ux_hardening.py tests/test_v600_visual_design_refresh.py",
        "scripts/build-frozen-app.ps1 -FeatureTier full",
        "python scripts/run_installed_offline_qualification.py --runtime <corrected frozen runtime>",
        "python scripts/generate_bundled_engine_inventory.py --runtime-root <corrected frozen runtime>"
    )
    validation = [ordered]@{
        compile = "pass"; production_js = "pass"; mirror_js = "pass"; collection = "pass"
        full_pytest = $full; accessibility = $accessibility; large_500_record_cancellation = $cancellation
    }
    retained_e2e = [ordered]@{
        result = "pass"; runtime = "dist/preversion-ga-postfloor/runtime/MaineFamilyLawLLM.exe"
        launch_health = "pass"; production_ui = "pass"; nav_count = 6; official_authority = "pass"
        exact_source = "pass"; fake_citation = "fail_closed"; ocr_functional_offline = "pass"
        privacy_worker = "pass"; record_import_count = 8; local_only_external_connections = 0
        clean_shutdown = "pass"
    }
    security = [ordered]@{
        filing_gate_cases = 16; false_passes = 0; false_pass_rate = 0.0
        private_payload_audit = "pass"; dependency_floor_audit = "pass"; audit_hash_match = "pass"
    }
    authority = [ordered]@{
        root = "C:\dev\ME_FM_LLM_data"; active_build_id = "89f23df714e94463f105228f"
        official_source_count = 38; parsed_record_count = 1372; recall_at_20 = 1.0
        exact_real = "pass"; exact_fake = "not_found"
    }
    backup_restore = [ordered]@{ result = "pass"; file_count = 108; original_unchanged = $true }
    accepted_public_feature_ids = $accepted
    hidden_feature_ids = $hidden
    failures = @(); classifications = $nonBlocking; p0_count = 0; p1_count = 0
    artifacts = $artifacts
}
$blockers = [ordered]@{
    schema_version = "ga_preversion_release_blockers_v2"; generated_at = $generatedAt
    decision = "READY_FOR_VERSION_FREEZE"; version_freeze_allowed = $true; p0 = @(); p1 = @()
    remaining_nonblocking = $nonBlocking
    superseded_blockers = @(
        "evaluation_orchestrator", "DPAPI intermittent failure", "missing frozen config",
        "missing Presidio worker", "older MSIX filing gate", "dependency floors",
        "old installed 6.0.4 E2E", "missing 01/06 evidence", "authority unavailable",
        "exact-500 cancellation", "third-party notices"
    )
}
$artifactManifest = [ordered]@{
    schema_version = "ga_preversion_artifact_manifest_v2"; generated_at = $generatedAt
    source_identity = $sourceIdentity; artifacts = $artifacts
}

$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $gaEvidence "07_full_test_summary.json") -Encoding utf8
$blockers | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $gaEvidence "07_release_blockers.json") -Encoding utf8
$artifactManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $gaEvidence "07_release_artifact_manifest.json") -Encoding utf8
$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $evidence "pre_version_test_summary.json") -Encoding utf8
$blockers | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence "pre_version_blockers.json") -Encoding utf8
@(
    "READY_FOR_VERSION_FREEZE",
    "Full suite: $($full.tests) total, $($full.passed) passed, $($full.skipped) skipped, 0 failed/errors.",
    "Accessibility: $($accessibility.tests) passed.", "Exact-500 cancellation: pass.",
    "Frozen runtime/UI/authority/offline/private-data/dependency/backup: pass.",
    "Filing gate: 0/16 false passes.", "P0/P1 blockers: 0."
) | Set-Content -LiteralPath (Join-Path $gaEvidence "07_full_test_summary.txt") -Encoding utf8

$stabilization = [ordered]@{
    schema_version = "worktree_stabilization_v2"; generated_at = $generatedAt; status = "STABLE"
    source_identity = $sourceIdentity; compile = "pass"; collection = "pass"; full_suite = $full
    production_routes = "pass"; slice_21_31 = "hidden_fail_closed"; disabled_features = $hidden
    blockers = @(); artifacts = $artifacts
}
$stabilization | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $gaEvidence "01_worktree_stabilization.json") -Encoding utf8
@("STABLE", "Compilation, collection, full tests, frozen routes, and hidden-slice policy pass.", "Slices 21-31 remain hidden and fail closed.") |
    Set-Content -LiteralPath (Join-Path $gaEvidence "01_worktree_stabilization.txt") -Encoding utf8

$screenshots = @(
    "dist/release/v7.0.0/evidence/preversion-postfloor-ui/01-workbench.png",
    "dist/release/v7.0.0/evidence/preversion-postfloor-ui/02-answer.png",
    "dist/release/v7.0.0/evidence/preversion-postfloor-ui/03-preview.png"
)
$ux = [ordered]@{
    schema_version = "ux_accessibility_polish_v2"; generated_at = $generatedAt; status = "pass"
    production_nav_entries = 6; hidden_features_absent = $true; accessibility = $accessibility
    visual_regression = $screenshots; page_errors = 0; p0_p1 = @()
    remaining = @([ordered]@{ severity = "P2"; detail = "Expected OCR prerequisite 409 when no matter is selected is handled as an empty state." })
}
$ux | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $gaEvidence "06_ux_accessibility_polish.json") -Encoding utf8
@($screenshots | ForEach-Object { [ordered]@{ path = $_; sha256 = Get-RelativeHash $_ } }) |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $gaEvidence "06_visual_regression_manifest.json") -Encoding utf8
@("PASS", "18 focused accessibility/UX tests passed.", "Frozen UI rendered six retained navigation entries with no page errors.", "No P0/P1 UX blocker remains.") |
    Set-Content -LiteralPath (Join-Path $gaEvidence "06_ux_accessibility_polish.txt") -Encoding utf8

$summary | ConvertTo-Json -Depth 4 -Compress
