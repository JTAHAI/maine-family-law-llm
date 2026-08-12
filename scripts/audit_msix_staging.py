from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


INVALID_WINDOWS_CHARS = set('<>:"|?*')
RESERVED_DOS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CLOCK$",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def _load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_key(path_text: str) -> str:
    return unicodedata.normalize("NFC", path_text).casefold()


def _validate_component(component: str) -> list[str]:
    issues: list[str] = []
    if component in {"", ".", ".."}:
        issues.append("dot_or_empty_segment")
        return issues
    if any(ch in INVALID_WINDOWS_CHARS for ch in component):
        issues.append("invalid_windows_character")
    if component.endswith(" "):
        issues.append("trailing_space")
    if component.endswith("."):
        issues.append("trailing_period")
    stem = component.split(".", 1)[0].rstrip(" .").upper()
    if stem in RESERVED_DOS_NAMES:
        issues.append("reserved_dos_device_name")
    if ":" in component:
        issues.append("alternate_data_stream_syntax")
    return issues


def _collect_makeappx_log(log_path: Path | None) -> dict[str, Any]:
    if log_path is None or not log_path.exists():
        return {"available": False}
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    processing = [line for line in lines if line.startswith("Processing ")]
    final_success = processing[-1] if processing else ""
    failing_line = ""
    for line in reversed(lines):
        if "error:" in line.lower() or "Failure at" in line:
            failing_line = line
            break
    return {
        "available": True,
        "final_successfully_ingested_line": final_success,
        "last_error_line": failing_line,
        "line_count": len(lines),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-root", required=True)
    parser.add_argument("--manifest-input", required=True)
    parser.add_argument("--sealed-manifest", default="")
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--map-output", required=True)
    parser.add_argument("--makeappx-log", default="")
    args = parser.parse_args()

    stage_root = Path(args.stage_root).resolve()
    manifest = _load_manifest(Path(args.manifest_input))
    sealed = _load_manifest(Path(args.sealed_manifest)) if args.sealed_manifest else None
    files = manifest["files"]
    if sealed is not None:
        files = [
            {
                "source_path": "",
                "package_relative_path": row["path"],
                "destination_path": str(stage_root / str(row["path"]).replace("/", os.sep)),
            }
            for row in sealed["files"]
        ]
    issues: list[dict[str, Any]] = []
    destination_entries: list[tuple[str, str]] = []
    casefold_destinations: Counter[str] = Counter()
    nfc_destinations: Counter[str] = Counter()
    seen_paths: set[str] = set()
    first_offender: dict[str, Any] | None = None

    for entry in files:
        source_path = Path(entry["source_path"]) if entry["source_path"] else None
        package_relative_path = str(entry["package_relative_path"]).replace("\\", "/")
        destination_path = Path(entry["destination_path"])
        source_length = len(str(source_path)) if source_path else 0
        package_length = len(package_relative_path)
        entry_issues: list[str] = []
        if source_path is not None and not source_path.exists():
            entry_issues.append("source_disappeared")
        if not destination_path.exists():
            entry_issues.append("destination_missing")
        if not destination_path.is_file():
            entry_issues.append("non_regular_destination")
        if source_path is not None and source_path.is_symlink():
            entry_issues.append("symlink_source")
        if destination_path.is_symlink():
            entry_issues.append("symlink_destination")
        if any(part in {"", ".", ".."} for part in Path(package_relative_path).parts):
            entry_issues.append("dot_or_empty_segment")
        for component in Path(package_relative_path).parts:
            entry_issues.extend(_validate_component(component))
        if Path(package_relative_path).is_absolute():
            entry_issues.append("absolute_package_destination")
        if "\\" in package_relative_path:
            entry_issues.append("backslash_in_package_destination")
        if "//" in package_relative_path:
            entry_issues.append("doubled_separator")
        if re.search(r"(?<!^)[A-Za-z]:", package_relative_path):
            entry_issues.append("alternate_data_stream_syntax")
        destination_key = package_relative_path.casefold()
        normalized_key = _normalize_key(package_relative_path)
        casefold_destinations[destination_key] += 1
        nfc_destinations[normalized_key] += 1
        destination_entries.append((package_relative_path, str(source_path or "")))
        if package_relative_path in seen_paths:
            entry_issues.append("duplicate_destination")
        seen_paths.add(package_relative_path)
        if source_length > 240:
            entry_issues.append("long_source_path")
        if package_length > 200:
            entry_issues.append("long_package_path")
        if entry_issues and first_offender is None:
            first_offender = {
                "source_path": str(source_path or ""),
                "package_relative_path": package_relative_path,
                "issues": sorted(set(entry_issues)),
            }
        issues.append(
            {
                "source_path": str(source_path),
                "package_relative_path": package_relative_path,
                "source_path_length": source_length,
                "package_relative_path_length": package_length,
                "issues": sorted(set(entry_issues)),
            }
        )

    duplicate_casefold = [path for path, count in casefold_destinations.items() if count > 1]
    duplicate_nfc = [path for path, count in nfc_destinations.items() if count > 1]
    missing_from_stage = []
    for entry in files:
        if not Path(entry["destination_path"]).exists():
            missing_from_stage.append(entry["package_relative_path"])
    # MakeAppx receives AppxManifest.xml through /m; it must be sealed and audited
    # with the payload, but must not also appear in the [Files] mapping section.
    map_lines = [
        f"\"{entry['destination_path']}\" \"{entry['package_relative_path']}\""
        for entry in sorted(files, key=lambda row: str(row["package_relative_path"]).casefold())
        if str(entry["package_relative_path"]).replace("\\", "/").casefold() != "appxmanifest.xml"
    ]
    map_path = Path(args.map_output)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text("[Files]\n" + "\n".join(map_lines) + "\n", encoding="utf-8")

    payload = {
        "schema_version": "msix_path_audit_v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "stage_root": str(stage_root),
        "package_root": str(stage_root / "package"),
        "file_count": len(files),
        "issues": issues,
        "duplicate_casefold_destinations": duplicate_casefold,
        "duplicate_nfc_destinations": duplicate_nfc,
        "missing_from_stage": missing_from_stage,
        "first_offending_entry": first_offender,
        "makeappx_log_summary": _collect_makeappx_log(Path(args.makeappx_log) if args.makeappx_log else None),
        "status": "pass"
        if not any(row["issues"] for row in issues) and not duplicate_casefold and not duplicate_nfc and not missing_from_stage
        else "fail",
    }

    audit_path = Path(args.audit_output)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
