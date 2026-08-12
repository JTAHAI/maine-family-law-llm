from __future__ import annotations

import hashlib
import re
from typing import Any

MAX_FINDINGS = 5_000

_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("US_SSN", re.compile(r"(?<!\d)(?:\d{3}-\d{2}-\d{4}|\d{9})(?!\d)"), "[REDACTED_SSN]"),
    ("DATE_OF_BIRTH", re.compile(r"(?i)\b(?:dob|date of birth|born)\s*[:#-]?\s*(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4})"), "[REDACTED_DOB]"),
    ("EMAIL_ADDRESS", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[REDACTED_EMAIL]"),
    ("PHONE_NUMBER", re.compile(r"(?<!\d)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]\d{4}(?!\d)"), "[REDACTED_PHONE]"),
    ("MAINE_DOCKET_NUMBER", re.compile(r"\b(?:[A-Z]{2,5}-)?\d{2,4}-[A-Z]{2,5}-\d{2,6}\b", re.I), "[REDACTED_DOCKET]"),
    ("BANK_ACCOUNT", re.compile(r"(?i)\b(?:account|acct|routing)\s*(?:number|no\.?|#)?\s*[:#-]?\s*\d{6,17}\b"), "[REDACTED_FINANCIAL]"),
    ("STREET_ADDRESS", re.compile(r"\b\d{1,6}\s+[A-Z0-9][A-Z0-9 .'-]{1,80}\s(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Lane|Ln\.?|Drive|Dr\.?|Court|Ct\.?|Way|Boulevard|Blvd\.?)\b", re.I), "[REDACTED_ADDRESS]"),
    ("SEALED_OR_CONFIDENTIAL_LANGUAGE", re.compile(r"(?i)\b(?:sealed|confidential|protective order|in camera|juvenile confidential|not for public disclosure)\b"), "[REDACTED_CONTEXT]"),
    ("GUARDIAN_AD_LITEM_CONTEXT", re.compile(r"(?i)\b(?:guardian ad litem|GAL)\b"), "[REDACTED_GAL]"),
    ("MINOR_CONTEXT", re.compile(r"(?i)\b(?:minor child|minor children|juvenile|child in care|student)\b"), "[REDACTED_MINOR_CONTEXT]"),
    ("SCHOOL_CONTEXT", re.compile(r"(?i)\b(?:school|school district|teacher|principal|counselor|attendance office)\b"), "[REDACTED_SCHOOL_CONTEXT]"),
)


def deterministic_privacy_review(text: str) -> dict[str, Any]:
    text = str(text or "")
    findings: list[dict[str, Any]] = []
    for entity_type, pattern, replacement in _PATTERNS:
        for match in pattern.finditer(text):
            findings.append({
                "entity_type": entity_type,
                "start": match.start(),
                "end": match.end(),
                "score": 1.0,
                "recognizer": "mfl_deterministic",
                "replacement": replacement,
                "text_sha256": hashlib.sha256(match.group(0).encode("utf-8", errors="replace")).hexdigest(),
            })
            if len(findings) >= MAX_FINDINGS:
                break
        if len(findings) >= MAX_FINDINGS:
            break
    findings.sort(key=lambda row: (int(row["start"]), int(row["end"]), str(row["entity_type"])))
    counts: dict[str, int] = {}
    for row in findings:
        counts[str(row["entity_type"])] = counts.get(str(row["entity_type"]), 0) + 1
    return {
        "schema_version": "document_privacy_review_v1",
        "status": "review_required",
        "finding_count": len(findings),
        "finding_counts": counts,
        "findings": findings,
        "complete_detection_guaranteed": False,
        "review_required": True,
        "warning": "Automated privacy detection can miss sensitive information. Human review is required before disclosure or export.",
    }


def merge_privacy_findings(deterministic: dict[str, Any], presidio: dict[str, Any] | None) -> dict[str, Any]:
    combined = [dict(row) for row in deterministic.get("findings") or [] if isinstance(row, dict)]
    deterministic_keys = {
        (str(row.get("entity_type")), int(row.get("start") or 0), int(row.get("end") or 0))
        for row in combined
    }
    presidio_keys: set[tuple[str, int, int]] = set()
    for row in (presidio or {}).get("findings") or []:
        if not isinstance(row, dict):
            continue
        key = (str(row.get("entity_type")), int(row.get("start") or 0), int(row.get("end") or 0))
        presidio_keys.add(key)
        if not any((str(item.get("entity_type")), int(item.get("start") or 0), int(item.get("end") or 0)) == key for item in combined):
            combined.append(dict(row))
    combined.sort(key=lambda row: (int(row.get("start") or 0), int(row.get("end") or 0), str(row.get("entity_type") or "")))
    counts: dict[str, int] = {}
    for row in combined:
        name = str(row.get("entity_type") or "UNKNOWN")
        counts[name] = counts.get(name, 0) + 1
    disagreements = []
    for key in sorted(deterministic_keys ^ presidio_keys):
      disagreements.append({
            "entity_type": key[0],
            "start": key[1],
            "end": key[2],
            "deterministic_present": key in deterministic_keys,
            "presidio_present": key in presidio_keys,
        })
    return {
        "schema_version": "document_privacy_review_v1",
        "status": "review_required",
        "finding_count": len(combined),
        "finding_counts": counts,
        "findings": combined[:MAX_FINDINGS],
        "detectors": ["mfl_deterministic", *( ["presidio"] if presidio and presidio.get("status") == "pass" else [])],
        "presidio_status": (presidio or {}).get("status", "not_run"),
        "deterministic_finding_count": len(deterministic.get("findings") or []),
        "presidio_finding_count": len((presidio or {}).get("findings") or []),
        "disagreements": disagreements,
        "complete_detection_guaranteed": False,
        "review_required": True,
        "warning": "Automated privacy detection can miss sensitive information. Human review is required before disclosure or export.",
    }
