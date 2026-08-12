"""Offline dependency-floor audit for known security-sensitive packages.

The audit never contacts a package index.  It compares installed versions with
project-maintained minimums selected to exclude known high/moderate advisories
that are relevant to local document parsing and the optional loopback API.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import metadata
import re
from typing import Mapping


class DependencyAuditError(ValueError):
    """Raised when dependency audit input is malformed."""


@dataclass(frozen=True)
class DependencyRule:
    distribution: str
    minimum: str
    group: str
    required: bool
    rationale: str
    advisory_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DependencyFinding:
    distribution: str
    installed: str | None
    minimum: str
    group: str
    status: str
    rationale: str
    advisory_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DependencyAuditReport:
    status: str
    findings: tuple[DependencyFinding, ...]
    checked: int
    blocked: int
    missing_required: int
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checked": self.checked,
            "blocked": self.blocked,
            "missing_required": self.missing_required,
            "note": self.note,
            "findings": [item.to_dict() for item in self.findings],
        }


RULES: tuple[DependencyRule, ...] = (
    DependencyRule(
        "pypdf",
        "6.15.0",
        "core",
        True,
        "Current hardened pypdf floor; excludes known decompression memory-exhaustion and malformed-stream releases.",
        ("GHSA-7hfw-26vp-jp8m", "GHSA-jfx9-29x2-rv3j"),
    ),
    DependencyRule(
        "cryptography",
        "50.0.0",
        "core",
        True,
        "Current cryptography floor used for encrypted matter storage and signed authority updates.",
    ),
    DependencyRule(
        "pypdfium2",
        "5.12.1",
        "core",
        True,
        "Current non-yanked PDFium wrapper release used for bounded local page rendering.",
    ),
    DependencyRule(
        "python-docx",
        "1.2.0",
        "core",
        True,
        "Current DOCX creation and extraction floor used for review-required local exports.",
    ),
    DependencyRule(
        "defusedxml",
        "0.7.1",
        "core",
        True,
        "Hardened XML parser dependency used by the tracked Word editing engine.",
    ),
    DependencyRule(
        "docx-editor",
        "0.7.1",
        "document-editing",
        False,
        "MIT-licensed tracked-change engine with hash-anchored paragraph references, bounded batch operations, and atomic save behavior.",
    ),
    DependencyRule(
        "fastapi",
        "0.139.2",
        "api",
        False,
        "Current FastAPI floor for the optional loopback API stack.",
    ),
    DependencyRule(
        "starlette",
        "1.3.1",
        "api",
        False,
        "Patched Starlette generation; excludes vulnerable Range-header and malformed-Host behavior and includes later StaticFiles path hardening.",
        ("GHSA-7f5h-v6xp-fcq8", "CVE-2026-48710"),
    ),
    DependencyRule(
        "uvicorn",
        "0.51.0",
        "api",
        False,
        "Current Uvicorn floor for the loopback-only local service.",
    ),
    DependencyRule(
        "httpx",
        "0.28.1",
        "api",
        False,
        "Current stable HTTPX floor used by tests and optional local integrations.",
    ),
    DependencyRule(
        "h2",
        "4.4.1",
        "api",
        False,
        "Patched HTTP/2 protocol floor used by the optional local HTTP client stack.",
    ),
    DependencyRule(
        "Pillow",
        "12.3.0",
        "store-build",
        False,
        "Current Pillow floor; excludes historical image-expression and buffer-overflow releases.",
        ("GHSA-8vj2-vxx3-667w", "GHSA-xg8h-j46f-w952"),
    ),
    DependencyRule(
        "PyInstaller",
        "6.21.0",
        "store-build",
        False,
        "Current Windows packaging floor.",
    ),
    DependencyRule(
        "pyinstaller-hooks-contrib",
        "2026.6",
        "store-build",
        False,
        "Pinned hook set used by the Windows build.",
    ),
)


def _version_tuple(value: str) -> tuple[int, ...]:
    if not isinstance(value, str) or not value.strip():
        raise DependencyAuditError("version must be a non-empty string")
    # Security floors use stable numeric releases.  A pre-release such as rc1 is
    # deliberately treated as lower than the corresponding final release.
    match = re.match(r"^\s*(\d+(?:\.\d+)*)", value)
    if not match:
        raise DependencyAuditError(f"unsupported version format: {value!r}")
    nums = tuple(int(part) for part in match.group(1).split("."))
    prerelease = bool(re.search(r"(?:a|b|rc|dev)\d*", value, re.IGNORECASE))
    return nums + ((-1,) if prerelease else (0,))


def version_at_least(installed: str, minimum: str) -> bool:
    left = _version_tuple(installed)
    right = _version_tuple(minimum)
    width = max(len(left), len(right))
    left = left[:-1] + (0,) * (width - len(left)) + (left[-1],)
    right = right[:-1] + (0,) * (width - len(right)) + (right[-1],)
    return left >= right


def installed_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for rule in RULES:
        try:
            versions[rule.distribution] = metadata.version(rule.distribution)
        except metadata.PackageNotFoundError:
            continue
    return versions


def audit_dependency_floors(
    versions: Mapping[str, str] | None = None,
    *,
    include_api: bool = True,
    include_build: bool = False,
    strict_optional: bool = False,
) -> DependencyAuditReport:
    source = dict(installed_versions() if versions is None else versions)
    findings: list[DependencyFinding] = []
    blocked = 0
    missing_required = 0

    for rule in RULES:
        if rule.group == "api" and not include_api:
            continue
        if rule.group == "store-build" and not include_build:
            continue
        installed = source.get(rule.distribution)
        if installed is None:
            if rule.required or strict_optional:
                status = "missing"
                blocked += 1
                if rule.required:
                    missing_required += 1
            else:
                status = "not-installed"
        else:
            try:
                safe = version_at_least(installed, rule.minimum)
            except DependencyAuditError:
                safe = False
            status = "pass" if safe else "blocked"
            if not safe:
                blocked += 1
        findings.append(
            DependencyFinding(
                distribution=rule.distribution,
                installed=installed,
                minimum=rule.minimum,
                group=rule.group,
                status=status,
                rationale=rule.rationale,
                advisory_ids=rule.advisory_ids,
            )
        )

    return DependencyAuditReport(
        status="pass" if blocked == 0 else "fail",
        findings=tuple(findings),
        checked=sum(1 for item in findings if item.installed is not None),
        blocked=blocked,
        missing_required=missing_required,
        note=(
            "Offline floor check only. It does not replace a fresh package-index/advisory scan before a signed release."
        ),
    )
