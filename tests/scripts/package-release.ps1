param(
    [string]$Out = "/tmp/maine-family-law-llm-enterprise-hardening-local-resources-release.zip"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root
try {
    python scripts/clean-local-artifacts.py --repo-root $Root | Out-File -FilePath "/tmp/maine-family-law-llm-clean-release-artifacts.log" -Encoding utf8
    python scripts/run-quality-checks.py | Out-File -FilePath "/tmp/maine-family-law-llm-enterprise-hardening-quality.json" -Encoding utf8
    foreach ($Required in @("legal/corpus/source_registry.py", "legal/corpus/source_normalizer.py", "legal/corpus/source_snapshotter.py")) { if (-not (Test-Path $Required)) { throw "Missing required release source file: $Required" } }
    if (Test-Path $Out) { Remove-Item $Out -Force }
    $exclude = @(
        "*.db", "*.sqlite", "*.sqlite3", "*.faiss", "*.bin", "*.pt", "*.pth", "*.safetensors", "*.onnx",
        ".env", "*/.env", "runtime/*", "uploads/*", "vectorstores/*", "corpora/*",
        "official_authority_store/*", "parsed_authority_store/*", "matter_store/*", "eval_store/*",
        "embedding_store/*", "audit_store/*", "model_registry/*", ".local_data/*",
        "__pycache__/*", "*/__pycache__/*", ".pytest_cache/*", ".ruff_cache/*", ".venv/*", "venv/*", "node_modules/*", "dist/*", "build/*", "*.egg-info/*", "enterprise_local_hardening_evidence.json", "enterprise_local_build_plan.json", ".git/*"
    )
    $files = Get-ChildItem -Recurse -File | Where-Object {
        $rel = $_.FullName.Substring((Resolve-Path .).Path.Length + 1).Replace('\\','/')
        -not ($exclude | Where-Object { $rel -like $_ })
    }
    Compress-Archive -Path $files.FullName -DestinationPath $Out -Force
    Write-Output $Out
}
finally {
    Pop-Location
}
