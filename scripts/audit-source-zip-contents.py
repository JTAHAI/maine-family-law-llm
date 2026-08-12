#!/usr/bin/env python3
"""Verify that a source release ZIP did not drop required repo evidence artifacts.

This is intentionally narrower than the release tree artifact audit: it checks the
finished ZIP file so broad packaging exclusions cannot silently remove machine-
audited source evidence that the formal GA tracker depends on.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZipFile

REQUIRED_RELEASE_PATHS = {
    "openapi.json",
    "docs/api-contract-test-report.json",
    "docs/ui-completion-report.json",
    "docs/model_registry_admission_report.json",
    "docs/llm_injection_red_team_report.json",
    "docs/enterprise-security-test-report.json",
    "docs/governance-compliance-packet-report.json",
    "docs/sre-reliability-report.json",
    "configs/maine_true_ga_pass_tracker.json",
    "configs/maine_ga_pass_evidence_requirements.json",
}

PROHIBITED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "official_authority_store",
    "parsed_authority_store",
    "embedding_store",
    "matter_store",
    "eval_store",
    "audit_store",
    "model_registry",
    "runtime",
    "uploads",
    "vectorstores",
    "corpora",
    "models",
    "weights",
}

PROHIBITED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".faiss",
    ".bin",
    ".pt",
    ".pth",
    ".onnx",
    ".safetensors",
    ".gguf",
}

ALLOWED_PDF_PREFIXES = {
    "src/maine_family_law_llm/resources/focaf/",
    "maine_family_law_llm/resources/focaf/",
}


def _strip_archive_root(name: str) -> str:
    """Remove a recognized release directory without case-sensitive coupling.

    Historical builders used both underscore and hyphen separators and changed
    capitalization over time.  Audit the repository-relative path, not the
    cosmetic name of the top-level folder in the ZIP.
    """
    clean = name.rstrip("/")
    parts = Path(clean).parts
    if len(parts) <= 1:
        return clean
    root = parts[0].casefold()
    if (
        root == "me_fm_llm"
        or root.startswith("me_fm_llm_v")
        or root.startswith("maine-family-law-llm_v")
        or root.startswith("maine-family-law-llm-v")
    ):
        return "/".join(parts[1:])
    return clean


def audit(zip_path: Path) -> dict:
    blockers: list[str] = []
    with ZipFile(zip_path) as zf:
        names = {name for name in zf.namelist() if not name.endswith("/")}
    normalized = {_strip_archive_root(name) for name in names}
    missing = sorted(REQUIRED_RELEASE_PATHS - normalized)
    blockers.extend(f"missing_required_release_path:{path}" for path in missing)

    prohibited: list[str] = []
    for path in sorted(normalized):
        if not path:
            continue
        parts = set(Path(path).parts)
        suffix = Path(path).suffix.lower()
        allowed_public_pdf = suffix == ".pdf" and any(path.startswith(prefix) for prefix in ALLOWED_PDF_PREFIXES)
        if parts & PROHIBITED_PARTS or suffix in PROHIBITED_SUFFIXES or (suffix == ".pdf" and not allowed_public_pdf):
            prohibited.append(path)
    blockers.extend(f"prohibited_release_zip_entry:{path}" for path in prohibited[:50])

    return {
        "schema": "maine_family_law_llm.source_zip_content_audit.v1",
        "zip_path": str(zip_path),
        "status": "pass" if not blockers else "fail",
        "safe_to_package": not blockers,
        "required_count": len(REQUIRED_RELEASE_PATHS),
        "missing_required_paths": missing,
        "prohibited_entry_count": len(prohibited),
        "allowed_public_pdf_count": sum(1 for path in normalized if Path(path).suffix.lower() == ".pdf" and any(path.startswith(prefix) for prefix in ALLOWED_PDF_PREFIXES)),
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()
    report = audit(args.zip_path)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
