"""Hash-bound Windows App Certification Kit result discovery and parsing."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

_WACK_ROOTS = (Path(r"C:\Program Files (x86)\Windows Kits\10\App Certification Kit"), Path(r"C:\Program Files\Windows Kits\10\App Certification Kit"))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_wack() -> dict[str, Any]:
    candidates = [root / "appcert.exe" for root in _WACK_ROOTS]
    executable = next((item for item in candidates if item.is_file()), None)
    return {"available": executable is not None, "executable": str(executable) if executable else "", "searched": [str(item) for item in candidates]}


def _find_report(output_root: Path) -> Path | None:
    if not output_root.is_dir():
        return None
    # A previously generated wack-result.json is a summary, not a native
    # certification report. Never let it certify itself on a later invocation.
    reports = [path for path in output_root.rglob("*.xml") if path.is_file() and not path.is_symlink()]
    return reports[0] if len(reports) == 1 else None


def _classify_xml(payload: bytes) -> tuple[list[dict[str, str]], list[dict[str, str]], int]:
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("wack_report_declarations_not_allowed")
    root = ElementTree.fromstring(payload)
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    passed_tests = 0
    for node in root.iter():
        attrs = {str(key).split("}")[-1].lower(): str(value).strip() for key, value in node.attrib.items()}
        text = " ".join(part.strip() for part in node.itertext() if part.strip())[:500]
        basis = " ".join([node.tag.split("}")[-1], *attrs.values(), text]).lower()
        row = {"node": node.tag.split("}")[-1][:120], "id": attrs.get("id") or attrs.get("name") or "", "message": attrs.get("message") or text[:300]}
        if row["node"].lower() in {"test", "testresult"}:
            outcome = str(attrs.get("status") or attrs.get("result") or "").lower()
            if outcome in {"pass", "passed"}:
                passed_tests += 1
            else:
                failures.append({**row, "message": "test_result_failed_incomplete_or_unrecognized"})
        if re.search(r"\b(fail\w*|error\w*|not.?pass\w*)\b", basis):
            failures.append(row)
        elif re.search(r"\bwarn(ing)?\b", basis):
            warnings.append(row)
    return failures[:100], warnings[:100], passed_tests


def parse_wack_report(*, package: str | Path, output_root: str | Path, execution_status: str, reason: str = "") -> dict[str, Any]:
    package_path = Path(package).resolve()
    root = Path(output_root).resolve()
    tool = discover_wack()
    report_path = _find_report(root)
    report_hash = ""
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    parser_error = ""
    passed_tests = 0
    if report_path:
        try:
            with report_path.open("rb") as handle:
                payload = handle.read(32 * 1024 * 1024 + 1)
            if len(payload) > 32 * 1024 * 1024:
                raise ValueError("wack_report_too_large")
            report_hash = hashlib.sha256(payload).hexdigest()
            failures, warnings, passed_tests = _classify_xml(payload)
        except Exception as exc:  # noqa: BLE001
            parser_error = type(exc).__name__
    status = str(execution_status or "not_run").strip().lower()
    blockers: list[str] = []
    if not package_path.is_file():
        blockers.append("package_unavailable")
    if status not in {"completed", "pass"}:
        blockers.append(f"wack_execution:{status or 'not_run'}")
    if not report_path:
        blockers.append("wack_report_missing")
    if parser_error:
        blockers.append("wack_report_unparseable")
    if failures:
        blockers.append("wack_failures_present")
    if not passed_tests:
        blockers.append("wack_explicit_passed_tests_missing")
    return {
        "schema_version": "wack_qualification_v1",
        "generated_at": _now(),
        "status": "pass" if not blockers else "blocked",
        "execution_status": status or "not_run",
        "reason": str(reason or "")[:500],
        "package": {"file_name": package_path.name, "sha256": sha256_file(package_path) if package_path.is_file() else ""},
        "tool": tool,
        "report": {"file_name": report_path.name if report_path else "", "sha256": report_hash, "parser_error": parser_error, "passed_test_count": passed_tests, "failure_count": len(failures), "warning_count": len(warnings), "failures": failures, "warnings": warnings},
        "blockers": blockers,
        "review_required": True,
        "store_release_blocked": bool(blockers),
    }


__all__ = ["discover_wack", "parse_wack_report", "sha256_file"]
