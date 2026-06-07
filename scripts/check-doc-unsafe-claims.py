#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_ROOT = ROOT / "docs"
SCAN_FILES = [ROOT / "README.md", *sorted(DOC_ROOT.rglob("*.md"))]
EXCLUDED_PARTS = {
    "external-evidence",
    "sample-evidence",
}
BOUNDARY_WORDS = (
    "do not",
    "does not",
    "not ",
    "no ",
    "without",
    "unless",
    "must not",
    "cannot",
    "blocked",
    "remain open",
    "required",
    "prohibited",
    "unsafe",
    "false",
    "invalid",
    "not evidence",
)
PROHIBITED = {
    "enterprise_legal_ga_complete": re.compile(
        r"\b(enterprise legal GA complete|production legal GA complete|true GA complete)\b",
        re.I,
    ),
    "filing_ready_by_default": re.compile(r"\bfiling[- ]ready by default\b", re.I),
    "no_attorney_review_needed": re.compile(r"\bno attorney review needed\b", re.I),
    "guaranteed_legal_accuracy": re.compile(r"\bguaranteed legal accuracy\b", re.I),
    "replaces_attorney": re.compile(r"\b(replaces an attorney|replaces attorney|substitute for attorney)\b", re.I),
    "legal_advice_to_public": re.compile(r"\blegal advice to the public\b", re.I),
    "guaranteed_outcome": re.compile(r"\b(you will win|guaranteed outcome)\b", re.I),
    "ga_shipped": re.compile(r"\bGA shipped\b", re.I),
}


def _included(path: Path) -> bool:
    rel_parts = set(path.relative_to(ROOT).parts)
    return not rel_parts.intersection(EXCLUDED_PARTS)


def _is_boundary_statement(line: str) -> bool:
    lowered = line.lower()
    return any(word in lowered for word in BOUNDARY_WORDS)


def run() -> dict:
    files = [path for path in SCAN_FILES if path.is_file() and _included(path)]
    findings = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _is_boundary_statement(line):
                continue
            for finding, pattern in PROHIBITED.items():
                if pattern.search(line):
                    findings.append(
                        {
                            "finding": finding,
                            "path": str(path.relative_to(ROOT)),
                            "line": number,
                            "text": line.strip(),
                        }
                    )
    return {
        "schema": "maine_family_law_llm.doc_unsafe_claims_check.v1",
        "status": "pass" if not findings else "fail",
        "scanned_files": [str(path.relative_to(ROOT)) for path in files],
        "finding_count": len(findings),
        "findings": findings,
        "production_legal_ready": False,
    }


def main() -> int:
    payload = run()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
