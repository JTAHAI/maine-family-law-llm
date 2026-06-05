param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string]$Version = "2.06.0",
  [string]$Label = "family_justice_workbench",
  [string]$OutputRoot = "D:\dev"
)

$ErrorActionPreference = "Stop"

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$stage = Join-Path $OutputRoot "ME_FM_LLM_zip_stage_$stamp"
$zip = Join-Path $OutputRoot "ME_FM_LLM_v$Version`_$Label`_$stamp.zip"

$excludedDirs = @(
  ".git", ".venv", "venv", "env", "node_modules", "dist", "build", "coverage",
  "reports", "archive", "historical-docs", ".sentinel", "__pycache__",
  ".pytest_cache", ".ruff_cache", ".mfl_work", "ME_FM_LLM_data",
  "official_authority_store", "parsed_authority_store", "embedding_store", "eval_store",
  "audit_store", "model_registry", "vector_store", "vector_stores", "models", "weights"
)

$excludedFiles = @(
  "*.pyc", "*.pyo", ".DS_Store", "Thumbs.db", ".env", ".env.*", "env.prod",
  "env.production", "prod.env", "production.env", "*.sqlite", "*.sqlite3", "*.db",
  "*.bin", "*.safetensors", "*.pt", "*.pth", "*.onnx", "*.gguf"
)

Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null

robocopy $RepoRoot $stage /MIR /XD $excludedDirs /XF $excludedFiles | Out-Host
if ($LASTEXITCODE -gt 7) {
  throw "robocopy failed with exit code $LASTEXITCODE"
}

Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force
$hash = Get-FileHash $zip -Algorithm SHA256

[pscustomobject]@{
  version = $Version
  label = $Label
  repo_root = $RepoRoot
  stage = $stage
  zip = $zip
  sha256 = $hash.Hash
} | ConvertTo-Json -Depth 4
