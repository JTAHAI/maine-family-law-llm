#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python scripts/clean-local-artifacts.py --repo-root "$ROOT" >/tmp/maine-family-law-llm-clean-release-artifacts.log
python scripts/run-quality-checks.py >/tmp/maine-family-law-llm-enterprise-hardening-quality.json
python scripts/clean-local-artifacts.py --repo-root "$ROOT" >/tmp/maine-family-law-llm-clean-release-artifacts-after-quality.log
PYTHONDONTWRITEBYTECODE=1 python scripts/audit-release-artifacts.py --repo-root "$ROOT" --require-ready >/tmp/maine-family-law-llm-release-artifact-audit.json
PYTHONDONTWRITEBYTECODE=1 python scripts/doctor-local-repo.py --repo-root "$ROOT" --json >/tmp/maine-family-law-llm-doctor-release.json
test -f legal/corpus/source_registry.py
test -f legal/corpus/source_normalizer.py
test -f legal/corpus/source_snapshotter.py

OUT="${1:-/tmp/maine-family-law-llm-post-ga-test-readiness-release.zip}"
rm -f "$OUT"

# Deterministic builder exclusions include: *.db *.sqlite *.sqlite3 *.faiss *.bin *.pt *.pth *.safetensors *.onnx,
# .env, runtime/*, uploads/*, vectorstores/*, corpora/*, official_authority_store/*,
# parsed_authority_store/*, matter_store/*, eval_store/*, embedding_store/*, audit_store/*,
# model_registry/*, .local_data/*, __pycache__/*, .pytest_cache/*, .ruff_cache/*,
# .venv/*, node_modules/*, dist/*, build/*, *.egg-info/*, smoke_evidence*.json,
# source_sbom.json, source_release_lock.json, enterprise_local_hardening_evidence.json,
# enterprise_local_build_plan.json, enterprise_preflight_report.json,
# offline_validation_pack_report.json, public_release_readiness.json, release_provenance.json, .git/*.
PYTHONDONTWRITEBYTECODE=1 python scripts/build-deterministic-source-release.py \
  --repo-root "$ROOT" \
  --output "$OUT" \
  --archive-root ME_FM_LLM >/tmp/maine-family-law-llm-deterministic-source-release.json

PYTHONDONTWRITEBYTECODE=1 python scripts/audit-source-zip-contents.py "$OUT" >/tmp/maine-family-law-llm-source-zip-content-audit.json

echo "$OUT"
