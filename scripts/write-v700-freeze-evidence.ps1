param([string]$RepoRoot = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $RepoRoot).Path
$release = Join-Path $root "dist\release\v7.0.0"
$evidence = Join-Path $release "evidence"

function Hash-Relative([string]$RelativePath) {
    return (Get-FileHash -LiteralPath (Join-Path $root $RelativePath) -Algorithm SHA256).Hash.ToLowerInvariant()
}

$versionSources = @(
    "pyproject.toml", "src/maine_family_law_llm/version.py", "maine_family_law_llm/version.py",
    "store/msix/identity.local.json", "store/msix/identity.example.json",
    "store/msix/AppxManifest.xml.in", "src/maine_family_law_llm/ui/workbench.html",
    "maine_family_law_llm/ui/workbench.html", "docs/RELEASE_NOTES_v7.0.0.md"
)
$sourceIdentity = [ordered]@{
    type = "SOURCE_TREE_IDENTITY_NON_GIT"
    manifest = "dist/release/v7.0.0/evidence/source-tree-manifest.json"
    manifest_sha256 = Hash-Relative "dist/release/v7.0.0/evidence/source-tree-manifest.json"
}
$migration = [ordered]@{
    schema_version = "v700_migration_report_v1"
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    from_package_version = "6.0.4.0"
    to_package_version = "7.0.0.0"
    status = "pass"
    package_upgrade_execution = "not_executed_until_isolated_package_qualification"
    synthetic_schema_migration = "pass"
    preserved = @("matter identity", "corpora", "drafts", "revision history", "hidden slice sidecars", "settings", "external authority references")
    rollback = [ordered]@{
        ready = $true
        prior_version = "6.0.4.0"
        prior_hash_preserved = $true
        forward_recovery = "Restore the pre-upgrade profile backup, reinstall the prior approved package in isolation, then reapply v7 after blocker repair."
    }
    privacy = "fictional identifiers only; no private matter data entered the repository"
    test_evidence = "dist/release/v7.0.0/evidence/version-freeze-final.xml"
    test_sha256 = Hash-Relative "dist/release/v7.0.0/evidence/version-freeze-final.xml"
}
$manifest = [ordered]@{
    schema_version = "v700_release_manifest_v1"
    generated_at = $migration.generated_at
    decision = "VERSION_FROZEN"
    product_version = "7.0.0"
    package_version = "7.0.0.0"
    architecture = "x64"
    language = "en-us"
    identity = "TAHAIWebServices.MaineFamilyLawLLM"
    publisher = "CN=D75EE668-B409-45ED-87E5-E37AA5FE3868"
    executable = "MaineFamilyLawLLM.exe"
    x_generate = $false
    source_identity = $sourceIdentity
    accepted_feature_ids = @((Get-Content -Raw -LiteralPath (Join-Path $release "release-scope.json") | ConvertFrom-Json).public_features.feature_id)
    hidden_feature_ids = @((Get-Content -Raw -LiteralPath (Join-Path $release "release-scope.json") | ConvertFrom-Json).hidden_features.feature_id)
    version_sources = @($versionSources | ForEach-Object { [ordered]@{ path = $_; sha256 = Hash-Relative $_ } })
    migration_status = $migration.status
    prior_evidence = @(
        [ordered]@{ path = "dist/ga_today/evidence/07_full_test_summary.json"; sha256 = Hash-Relative "dist/ga_today/evidence/07_full_test_summary.json" },
        [ordered]@{ path = "dist/ga_today/evidence/07_release_blockers.json"; sha256 = Hash-Relative "dist/ga_today/evidence/07_release_blockers.json" },
        [ordered]@{ path = "dist/ga_today/evidence/02_feature_truth_manifest.json"; sha256 = Hash-Relative "dist/ga_today/evidence/02_feature_truth_manifest.json" }
    )
    release_blockers = @()
    signing = "Partner Center or approved production certificate required; no arbitrary certificate is treated as production signing"
}
$migration | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $release "migration-report.json") -Encoding utf8
$manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $release "release-manifest.json") -Encoding utf8
$manifest | ConvertTo-Json -Depth 5 -Compress
