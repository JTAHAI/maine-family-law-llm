#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCAN_PATHS = [
    ROOT / "docs" / "outreach",
    ROOT / "docs" / "attorney-review-outreach-plan.md",
    ROOT / "docs" / "reviewer-guide.md",
    ROOT / "docs" / "attorney-sandbox-review-packet.md",
    ROOT / "docs" / "human-review-policy.md",
    ROOT / "docs" / "product-vision.md",
    ROOT / "README.md",
]
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
    "not evidence",
    "unsent",
    "false",
    "invalid evidence",
)
PROHIBITED = {
    "attorney_review_claimed_complete": re.compile(
        r"\b(attorney[- ]review|attorney review evidence)\b.{0,40}\b(complete|completed|received|secured)\b",
        re.I,
    ),
    "outreach_claimed_complete": re.compile(
        r"\boutreach\b.{0,40}\b(complete|completed|sent|done)\b",
        re.I,
    ),
    "pilot_claimed_complete": re.compile(r"\bpilot\b.{0,40}\b(complete|completed|done)\b", re.I),
    "signoff_claimed_complete": re.compile(
        r"\b(legal|security|product|ops) signoff\b.{0,40}\b(complete|completed|done)\b",
        re.I,
    ),
    "ga_claimed_shipped": re.compile(r"\b(GA shipped|GA shipment complete|true GA complete)\b", re.I),
    "emails_claimed_sent": re.compile(r"\b(emails were sent|emails sent|sent emails)\b", re.I),
}


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for path in SCAN_PATHS:
        if path.is_dir():
            files.extend(
                item
                for item in sorted(path.rglob("*"))
                if item.suffix.lower() in {".md", ".csv", ".txt"}
            )
        elif path.is_file():
            files.append(path)
    return files


def _is_boundary_statement(line: str) -> bool:
    lowered = line.lower()
    return any(word in lowered for word in BOUNDARY_WORDS)


def run() -> dict:
    findings = []
    files = _iter_files()
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
        "schema": "maine_family_law_llm.outreach_truthfulness_check.v1",
        "status": "pass" if not findings else "fail",
        "scanned_files": [str(path.relative_to(ROOT)) for path in files],
        "finding_count": len(findings),
        "findings": findings,
        "emails_sent": False,
        "outreach_complete": False,
        "attorney_reviewed": False,
        "production_legal_ready": False,
    }


def main() -> int:
    payload = run()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
