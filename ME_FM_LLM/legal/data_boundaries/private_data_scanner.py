from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PrivateDataFinding:
    kind: str
    path: str
    detail: str


@dataclass(frozen=True)
class PrivateDataScanResult:
    ok: bool
    findings: list[PrivateDataFinding]


SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
DOB_RE = re.compile(r"\b(?:DOB|date of birth)\s*[:\-]?\s*\d{1,2}/\d{1,2}/\d{2,4}\b", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)")
MINOR_RE = re.compile(r"\b(?:minor child|juvenile|guardian ad litem|GAL|date of birth|SSN)\b", re.IGNORECASE)
SECRET_RE = re.compile(
    r"\b(?:api[_-]?key|secret[_-]?key|client[_-]?secret|private[_-]?key|password|token)\b\s*[:=]",
    re.IGNORECASE,
)

TEXT_SUFFIXES = {".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".py", ".ts", ".tsx", ".sh", ".ps1"}


def scan_text(text: str, path: str = "<memory>") -> list[PrivateDataFinding]:
    checks = [
        ("ssn", SSN_RE),
        ("date_of_birth", DOB_RE),
        ("email", EMAIL_RE),
        ("phone", PHONE_RE),
        ("juvenile_or_sensitive_family_marker", MINOR_RE),
        ("secret_marker", SECRET_RE),
    ]
    findings: list[PrivateDataFinding] = []
    for kind, pattern in checks:
        if pattern.search(text):
            findings.append(PrivateDataFinding(kind=kind, path=path, detail="pattern matched"))
    return findings


def scan_path(path: Path | str, *, include_source_code: bool = False) -> PrivateDataScanResult:
    root = Path(path)
    findings: list[PrivateDataFinding] = []
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]

    for file_path in files:
        if file_path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if not include_source_code and file_path.suffix.lower() in {".py", ".ts", ".tsx", ".sh", ".ps1"}:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(text, path=file_path.as_posix()))

    return PrivateDataScanResult(ok=not findings, findings=findings)
