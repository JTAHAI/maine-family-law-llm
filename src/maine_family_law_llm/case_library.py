from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CASE_LIBRARY_ENV = "MFL_CASE_LIBRARY_PATH"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def case_library_path() -> Path:
    override = os.environ.get(CASE_LIBRARY_ENV, "").strip()
    if override:
        return Path(override)
    local_appdata = Path(os.environ.get("LOCALAPPDATA") or Path.home())
    return local_appdata / "MaineFamilyLawLLM" / "case_library.json"


def default_case_library() -> dict[str, Any]:
    return {
        "schema": "maine_family_law_llm.case_library.v1",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "active_case_root": "",
        "cases": [],
    }


def load_case_library() -> dict[str, Any]:
    path = case_library_path()
    if not path.exists():
        return default_case_library()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "cases" not in payload or "active_case_root" not in payload:
        return default_case_library()
    return payload


def save_case_library(payload: dict[str, Any]) -> Path:
    path = case_library_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = utc_now()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def describe_case_root(case_root: Path) -> dict[str, Any]:
    resolved = case_root.resolve()
    case_name = resolved.name
    proof_path = resolved / "15_PROOF_VALIDATION" / "CASE_BUILD_PROOF.json"
    indexed_records = 0
    pdf_pages = 0
    if proof_path.exists():
        try:
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            case_name = str(proof.get("case_name") or case_name)
            indexed_records = int(proof.get("total_files_indexed", 0))
            pdf_pages = int(proof.get("total_pdf_pages", 0))
        except Exception:
            pass
    return {
        "label": case_name,
        "case_root": str(resolved),
        "indexed_records": indexed_records,
        "pdf_pages": pdf_pages,
        "exists": resolved.exists(),
    }


def list_registered_case_roots() -> list[dict[str, Any]]:
    payload = load_case_library()
    active = str(payload.get("active_case_root") or "")
    results: list[dict[str, Any]] = []
    for item in payload.get("cases", []):
        case_root = Path(str(item.get("case_root", "")))
        summary = describe_case_root(case_root)
        summary["last_selected_at"] = str(item.get("last_selected_at", ""))
        summary["registered_at"] = str(item.get("registered_at", ""))
        summary["active"] = summary["case_root"] == active
        results.append(summary)
    results.sort(key=lambda row: (not bool(row["active"]), row["label"].lower(), row["case_root"].lower()))
    return results


def prune_missing_case_roots() -> dict[str, Any]:
    payload = load_case_library()
    active = str(payload.get("active_case_root") or "")
    cases = []
    for item in payload.get("cases", []):
        case_root = Path(str(item.get("case_root", "")))
        if case_root.exists():
            cases.append(item)
    payload["cases"] = cases
    if active and not Path(active).exists():
        payload["active_case_root"] = ""
    save_case_library(payload)
    return payload


def register_case_root(case_root: Path, *, label: str | None = None, set_active: bool = True) -> dict[str, Any]:
    payload = load_case_library()
    resolved = str(case_root.resolve())
    now = utc_now()
    cases = list(payload.get("cases", []))
    existing = next((item for item in cases if str(item.get("case_root", "")) == resolved), None)
    if existing is None:
        summary = describe_case_root(Path(resolved))
        cases.append(
            {
                "case_root": resolved,
                "label": label or summary["label"],
                "registered_at": now,
                "last_selected_at": now if set_active else "",
            }
        )
    else:
        existing["label"] = label or existing.get("label") or describe_case_root(Path(resolved))["label"]
        if set_active:
            existing["last_selected_at"] = now
    payload["cases"] = cases
    if set_active:
        payload["active_case_root"] = resolved
    save_case_library(payload)
    return payload


def set_active_case_root(case_root: Path) -> dict[str, Any]:
    return register_case_root(case_root, set_active=True)


def active_case_root() -> Path | None:
    payload = load_case_library()
    active = str(payload.get("active_case_root") or "").strip()
    if not active:
        return None
    path = Path(active)
    return path if path.exists() else None
