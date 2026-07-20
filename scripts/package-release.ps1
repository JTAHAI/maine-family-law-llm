param(
    [string]$Out = "/tmp/maine-family-law-llm-enterprise-hardening-local-resources-release.zip"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root
try {
    python scripts/clean-local-artifacts.py --repo-root $Root | Out-File -FilePath "/tmp/maine-family-law-llm-clean-release-artifacts.log" -Encoding utf8
    python scripts/run-quality-checks.py | Out-File -FilePath "/tmp/maine-family-law-llm-enterprise-hardening-quality.json" -Encoding utf8
    python scripts/clean-local-artifacts.py --repo-root $Root | Out-File -FilePath "/tmp/maine-family-law-llm-clean-release-artifacts-after-quality.log" -Encoding utf8
    $env:PYTHONDONTWRITEBYTECODE = "1"
    python scripts/audit-release-artifacts.py --repo-root $Root --require-ready | Out-File -FilePath "/tmp/maine-family-law-llm-release-artifact-audit.json" -Encoding utf8
    python scripts/doctor-local-repo.py --repo-root $Root --json | Out-File -FilePath "/tmp/maine-family-law-llm-doctor-release.json" -Encoding utf8
    foreach ($Required in @("legal/corpus/source_registry.py", "legal/corpus/source_normalizer.py", "legal/corpus/source_snapshotter.py")) { if (-not (Test-Path $Required)) { throw "Missing required release source file: $Required" } }
    if (Test-Path $Out) { Remove-Item $Out -Force }
    # Deterministic builder excludes *.db, *.sqlite, *.sqlite3, *.faiss, *.bin, *.pt, *.pth,
    # *.safetensors, *.onnx, .env, runtime/*, uploads/*, vectorstores/*, corpora/*,
    # official_authority_store/*, parsed_authority_store/*, matter_store/*, eval_store/*,
    # embedding_store/*, audit_store/*, model_registry/*, .local_data/*, __pycache__/*,
    # .pytest_cache/*, .ruff_cache/*, .venv/*, venv/*, node_modules/*, dist/*, build/*,
    # *.egg-info/*, smoke_evidence*.json, source_sbom.json, source_release_lock.json,
    # enterprise_local_hardening_evidence.json, enterprise_local_build_plan.json, and .git/*.
    python scripts/build-deterministic-source-release.py --repo-root $Root --output $Out --archive-root ME_FM_LLM | Out-File -FilePath "/tmp/maine-family-law-llm-deterministic-source-release.json" -Encoding utf8
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python scripts/audit-source-zip-contents.py $Out | Out-File -FilePath "/tmp/maine-family-law-llm-source-zip-content-audit.json" -Encoding utf8
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output $Out
}
finally {
    Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue
    Pop-Location
}
