from __future__ import annotations

import hashlib
import html
import json
import os
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from legal.document_intelligence.privacy import deterministic_privacy_review
from legal.evidence.work_product import EvidenceWorkProductStore

SCHEMA_VERSION = "matter_command_center_v1"
ALGORITHM_VERSION = "v1.0.0"
ROOT_FOLDER = "21_MATTER_COMMAND_CENTER"
MAX_RECORDS = 25_000
MAX_NOTE_CHARS = 4_000
MAX_VARIANT_TEXT_CHARS = 1_000
ALLOWED_VARIANTS = {"metadata_only", "redacted", "full"}
ALLOWED_REVIEW_STATUS = {"approve_review", "request_changes", "reject"}
_LOCK = threading.RLock()


class MatterCommandCenterError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class MatterCommandCenterResult:
    status: str
    matter_id: str
    snapshot_id: str
    packet_id: str
    payload: dict[str, Any]
    artifacts: list[dict[str, Any]]
    warnings: list[str]
    blockers: list[str]
    reused_existing_build: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "matter_id": self.matter_id,
            "snapshot_id": self.snapshot_id,
            "packet_id": self.packet_id,
            "payload": self.payload,
            "artifacts": self.artifacts,
            "warnings": sorted(set(self.warnings)),
            "blockers": sorted(set(self.blockers)),
            "reused_existing_build": self.reused_existing_build,
            "review_required": True,
        }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(payload: Any) -> str:
    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _safe_text(value: Any, limit: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _safe_id(value: Any) -> str:
    raw = _safe_text(value, 240)
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in raw).strip("-_.")
    return cleaned or "matter"


def _safe_locator(value: Any) -> str:
    raw = _safe_text(value, 500)
    if not raw:
        return ""
    return Path(raw.replace("\\", "/")).name or raw[:240]


def _record_text(row: dict[str, Any]) -> str:
    for key in ("text", "derived_text", "content", "text_excerpt", "snippet"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.replace("\x00", "")
    return ""


def _normalize_selected(values: Iterable[str] | None) -> set[str]:
    return {str(item).strip()[:256] for item in (values or []) if str(item).strip()}


def _redacted_excerpt(text: str) -> str:
    review = deterministic_privacy_review(text)
    output = text
    for item in sorted(review.get("findings") or [], key=lambda row: (int(row.get("start") or 0), int(row.get("end") or 0)), reverse=True):
        start = max(0, int(item.get("start") or 0))
        end = max(start, int(item.get("end") or 0))
        replacement = str(item.get("replacement") or "[REDACTED]")
        output = output[:start] + replacement + output[end:]
    return output[:MAX_VARIANT_TEXT_CHARS]


def _packet_html(packet: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value or ""))

    included = "".join(
        f"<li><strong>{esc(row['evidence_id'])}</strong> {esc(row.get('title'))} "
        f"<code>{esc(row.get('source_hash') or row.get('text_sha256') or '')}</code></li>"
        for row in packet.get("included_records") or []
    ) or "<li>No included records</li>"
    excluded = "".join(
        f"<li><strong>{esc(row.get('evidence_id') or row.get('title') or 'record')}</strong> - {esc(row.get('reason'))}</li>"
        for row in packet.get("excluded_records") or []
    ) or "<li>No excluded records</li>"
    work_product = packet.get("work_product") or {}
    summary = packet.get("summary") or {}
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>Matter Command Center {esc(packet.get('packet_id'))}</title>"
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#0d1620;color:#f4efe6}main{max-width:1200px;margin:auto;padding:28px}section,article{background:#121d2b;border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:16px;margin:14px 0}code,pre{background:#08111b;border-radius:10px;padding:10px;display:block;overflow:auto}h1,h2,h3{margin-top:0}ul{line-height:1.6}.muted{color:#b4c0cf}</style></head><body><main>"
        f"<p class=\"muted\">Matter command center snapshot · review required · {esc(packet.get('generated_at'))}</p>"
        f"<h1>{esc(packet.get('matter_id'))}</h1>"
        f"<p><strong>Snapshot:</strong> {esc(packet.get('snapshot_id'))} · <strong>Packet:</strong> {esc(packet.get('packet_id'))}</p>"
        f"<section><h2>Summary</h2><pre>{esc(json.dumps(summary, indent=2, sort_keys=True))}</pre></section>"
        f"<section><h2>Included records</h2><ul>{included}</ul></section>"
        f"<section><h2>Excluded records</h2><ul>{excluded}</ul></section>"
        f"<section><h2>Work product</h2><pre>{esc(json.dumps({k: work_product.get(k) for k in ('build_id', 'summary', 'status', 'review_required', 'export_status')}, indent=2, sort_keys=True))}</pre></section>"
        "</main></body></html>"
    )


def _packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Matter Command Center",
        "",
        f"- Matter ID: `{packet.get('matter_id')}`",
        f"- Snapshot ID: `{packet.get('snapshot_id')}`",
        f"- Packet ID: `{packet.get('packet_id')}`",
        f"- Generated: `{packet.get('generated_at')}`",
        f"- Variant: `{packet.get('variant')}`",
        f"- Review required: `{packet.get('review_required')}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(packet.get("summary") or {}, indent=2, sort_keys=True),
        "```",
        "",
        "## Included Records",
    ]
    for row in packet.get("included_records") or []:
        lines.append(f"- `{row['evidence_id']}` {row.get('title') or ''}")
    lines.extend(["", "## Excluded Records"])
    for row in packet.get("excluded_records") or []:
        lines.append(f"- `{row.get('evidence_id') or row.get('title') or 'record'}` {row.get('reason')}")
    return "\n".join(lines) + "\n"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise MatterCommandCenterError("command_center_record_unavailable", "The command-center record is unavailable.", status_code=404)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MatterCommandCenterError("command_center_record_invalid", "The command-center record is invalid.", status_code=409)
    return payload


class MatterCommandCenterStore:
    def __init__(self, case_root: str | Path):
        self.case_root = Path(case_root).expanduser().resolve()
        if not self.case_root.is_dir():
            raise MatterCommandCenterError("case_root_unavailable", "The active matter is unavailable.", status_code=404)
        self.root = self.case_root / ROOT_FOLDER
        self.snapshots = self.root / "snapshots"
        self.packets = self.root / "packets"
        self.history = self.root / "packet_review_history.jsonl"
        self.health_history_path = self.root / "health_history.jsonl"
        self.active_snapshot_pointer = self.root / "ACTIVE_SNAPSHOT.json"
        self.active_packet_pointer = self.root / "ACTIVE_PACKET.json"
        for folder in (self.root, self.snapshots, self.packets):
            if folder.exists() and folder.is_symlink():
                raise MatterCommandCenterError("command_center_symlink_refused", "A symlinked command-center directory was refused.", status_code=409)
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._work_product = EvidenceWorkProductStore(self.case_root)

    def _record_rows(
        self,
        records: Sequence[dict[str, Any]],
        *,
        selected_record_ids: Iterable[str] | None = None,
        variant: str = "metadata_only",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        selected = _normalize_selected(selected_record_ids)
        included: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        warnings: list[str] = []
        seen: set[str] = set()
        for raw in records[:MAX_RECORDS]:
            if not isinstance(raw, dict):
                continue
            evidence_id = _safe_text(raw.get("evidence_id") or raw.get("source_id"), 256)
            parent_id = _safe_text(raw.get("parent_evidence_id"), 256)
            if not evidence_id:
                excluded.append({"reason": "missing_evidence_id"})
                continue
            if evidence_id in seen:
                excluded.append({"evidence_id": evidence_id, "reason": "duplicate_evidence_id"})
                continue
            if selected and evidence_id not in selected and parent_id not in selected:
                excluded.append({"evidence_id": evidence_id, "reason": "outside_selected_scope"})
                continue
            text = _record_text(raw)
            if not text:
                warnings.append(f"record_text_missing:{evidence_id}")
            source_hash = _safe_text(raw.get("source_hash") or raw.get("sha256"), 64).lower()
            if source_hash and len(source_hash) != 64:
                warnings.append(f"invalid_source_hash:{evidence_id}")
                source_hash = ""
            text_sha256 = _sha(text.encode("utf-8"))
            text_excerpt = _safe_text(text, MAX_VARIANT_TEXT_CHARS)
            row = {
                "evidence_id": evidence_id,
                "parent_evidence_id": parent_id,
                "title": _safe_text(raw.get("title") or raw.get("subject") or evidence_id, 300),
                "source_type": _safe_text(raw.get("source_type") or raw.get("document_type") or "record", 120),
                "source_locator": _safe_locator(raw.get("source_locator") or raw.get("source_path") or raw.get("filename") or raw.get("title")),
                "source_hash": source_hash,
                "text_sha256": text_sha256,
                "page_number": max(0, int(raw.get("page_number") or 0)),
                "issue_lanes": list(raw.get("issue_lanes") or raw.get("issue_tags") or []) if isinstance(raw.get("issue_lanes") or raw.get("issue_tags"), list) else [],
                "privacy_status": _safe_text(raw.get("privacy_status"), 80),
                "parser_status": _safe_text(raw.get("parser_status"), 80),
                "ocr_status": _safe_text(raw.get("ocr_status"), 80),
                "canonical_evidence_id": _safe_text(raw.get("canonical_evidence_id") or raw.get("canonical_document_key") or evidence_id, 256),
                "record_state": "included",
                "review_required": True,
            }
            if variant == "full":
                row["text_excerpt"] = text_excerpt
            elif variant == "redacted":
                row["text_excerpt_redacted"] = _redacted_excerpt(text)
            included.append(row)
            seen.add(evidence_id)
        return included, excluded, warnings

    def _fingerprint(self, matter_id: str, included: Sequence[dict[str, Any]], excluded: Sequence[dict[str, Any]], *, variant: str, selected_record_ids: Sequence[str]) -> str:
        return _sha(
            {
                "schema_version": SCHEMA_VERSION,
                "algorithm_version": ALGORITHM_VERSION,
                "matter_id": matter_id,
                "variant": variant,
                "selected_record_ids": list(sorted({str(item).strip() for item in selected_record_ids if str(item).strip()})),
                "included": [
                    {
                        "evidence_id": row["evidence_id"],
                        "source_hash": row.get("source_hash") or "",
                        "text_sha256": row.get("text_sha256") or "",
                        "canonical_evidence_id": row.get("canonical_evidence_id") or "",
                    }
                    for row in included
                ],
                "excluded": [
                    {
                        "evidence_id": row.get("evidence_id") or "",
                        "reason": row.get("reason") or "",
                    }
                    for row in excluded
                ],
            }
        )

    def _snapshot_path(self, snapshot_id: str) -> Path:
        return self.snapshots / f"{snapshot_id}.json"

    def _packet_root(self, packet_id: str) -> Path:
        return self.packets / packet_id

    def _packet_paths(self, packet_id: str) -> tuple[Path, Path, Path]:
        root = self._packet_root(packet_id)
        return root / "packet.json", root / "packet.html", root / "receipt.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8", newline="\n")
        os.chmod(temp, 0o600)
        os.replace(temp, path)

    def _activate(self, snapshot_id: str, packet_id: str) -> None:
        self._write_json(
            self.active_snapshot_pointer,
            {
                "schema_version": "active_matter_command_center_snapshot_v1",
                "snapshot_id": snapshot_id,
                "activated_at": _utc_now(),
            },
        )
        self._write_json(
            self.active_packet_pointer,
            {
                "schema_version": "active_matter_command_center_packet_v1",
                "packet_id": packet_id,
                "activated_at": _utc_now(),
            },
        )

    def _current_fingerprint(self, records: Sequence[dict[str, Any]]) -> str:
        rows = []
        for raw in records[:MAX_RECORDS]:
            if not isinstance(raw, dict):
                continue
            evidence_id = _safe_text(raw.get("evidence_id") or raw.get("source_id"), 256)
            if not evidence_id:
                continue
            text = _record_text(raw)
            rows.append(
                {
                    "evidence_id": evidence_id,
                    "source_hash": _safe_text(raw.get("source_hash") or raw.get("sha256"), 64).lower(),
                    "text_sha256": _sha(text.encode("utf-8")),
                    "canonical_evidence_id": _safe_text(raw.get("canonical_evidence_id") or raw.get("canonical_document_key") or evidence_id, 256),
                }
            )
        return _sha(rows)

    def freeze_snapshot(
        self,
        matter_id: str,
        records: Sequence[dict[str, Any]],
        *,
        selected_record_ids: Sequence[str] | None = None,
        variant: str = "metadata_only",
        approved: bool = False,
        note: str = "",
    ) -> dict[str, Any]:
        if not approved:
            raise MatterCommandCenterError("snapshot_approval_required", "Explicit approval is required before freezing a matter snapshot.", status_code=409)
        normalized_variant = str(variant or "metadata_only").strip().lower()
        if normalized_variant not in ALLOWED_VARIANTS:
            raise MatterCommandCenterError("invalid_snapshot_variant", "Unsupported snapshot variant.", status_code=400)
        selected = list(selected_record_ids or [])
        included, excluded, warnings = self._record_rows(records, selected_record_ids=selected, variant=normalized_variant)
        if not included:
            raise MatterCommandCenterError("no_selected_records", "No indexed records were available for the snapshot.", status_code=404)
        snapshot_fingerprint = self._fingerprint(matter_id, included, excluded, variant=normalized_variant, selected_record_ids=selected)
        snapshot_id = snapshot_fingerprint[:24]
        snapshot_path = self._snapshot_path(snapshot_id)
        current_fingerprint = self._current_fingerprint(records)
        if snapshot_path.exists():
            existing = _read_json(snapshot_path)
            if existing.get("snapshot_sha256") and existing.get("snapshot_sha256") != _sha({key: value for key, value in existing.items() if key != "snapshot_sha256"}):
                raise MatterCommandCenterError("snapshot_tampered", "The stored snapshot failed verification.", status_code=409)
            self._write_json(
                self.active_snapshot_pointer,
                {"schema_version": "active_matter_command_center_snapshot_v1", "snapshot_id": snapshot_id, "activated_at": _utc_now()},
            )
            return existing
        snapshot = {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "matter_id": _safe_id(matter_id),
            "snapshot_id": snapshot_id,
            "snapshot_fingerprint": snapshot_fingerprint,
            "generated_at": _utc_now(),
            "variant": normalized_variant,
            "selected_record_ids": sorted({str(item).strip() for item in selected if str(item).strip()}),
            "included_records": included,
            "excluded_records": excluded,
            "coverage": {
                "record_count": len(included),
                "excluded_record_count": len(excluded),
                "with_text_count": sum(1 for row in included if row.get("text_sha256")),
                "with_source_hash_count": sum(1 for row in included if row.get("source_hash")),
                "privacy_flag_count": sum(1 for row in included if row.get("privacy_status")),
                "source_types": sorted({str(row.get("source_type") or "") for row in included if row.get("source_type")}),
                "issue_lanes": sorted({lane for row in included for lane in row.get("issue_lanes") or [] if lane}),
            },
            "full_record_coverage": {
                "selected_scope": bool(selected),
                "current_record_fingerprint": current_fingerprint,
                "record_fingerprint_match": True,
                "stale_snapshot": False,
            },
            "review_required": True,
            "export_status": "review_required",
            "notes": _safe_text(note, MAX_NOTE_CHARS),
            "warnings": sorted(set(warnings)),
        }
        snapshot["snapshot_sha256"] = _sha({key: value for key, value in snapshot.items() if key != "snapshot_sha256"})
        self._write_json(snapshot_path, snapshot)
        self._write_json(
            snapshot_path.with_name(f"{snapshot_id}.receipt.json"),
            {
                "schema_version": "matter_command_center_snapshot_receipt_v1",
                "snapshot_id": snapshot_id,
                "matter_id": snapshot["matter_id"],
                "snapshot_sha256": snapshot["snapshot_sha256"],
                "snapshot_fingerprint": snapshot_fingerprint,
                "included_record_ids": [row["evidence_id"] for row in included],
                "excluded_records": excluded,
                "generated_at": snapshot["generated_at"],
                "review_required": True,
            },
        )
        self._write_json(
            self.active_snapshot_pointer,
            {"schema_version": "active_matter_command_center_snapshot_v1", "snapshot_id": snapshot_id, "activated_at": _utc_now()},
        )
        return snapshot

    def _latest_snapshot_id(self) -> str:
        if self.active_snapshot_pointer.exists():
            try:
                payload = _read_json(self.active_snapshot_pointer)
                snapshot_id = _safe_text(payload.get("snapshot_id"), 64)
                if snapshot_id:
                    return snapshot_id
            except MatterCommandCenterError:
                pass
        snapshots = sorted(self.snapshots.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        return snapshots[0].stem if snapshots else ""

    def _snapshot_payload(self, snapshot_id: str) -> dict[str, Any]:
        return _read_json(self._snapshot_path(snapshot_id))

    def _stale_status(self, snapshot: dict[str, Any], records: Sequence[dict[str, Any]]) -> tuple[bool, list[str]]:
        current = self._current_fingerprint(records)
        snapshot_fp = str(snapshot.get("full_record_coverage", {}).get("current_record_fingerprint") or "")
        current_ids = {str(row.get("evidence_id") or "") for row in snapshot.get("included_records") or [] if str(row.get("evidence_id") or "")}
        # Compare the same explicit scope used to freeze the snapshot. Selecting
        # a parent record also includes its derived pages; comparing that scoped
        # set to every active-matter record made every partial snapshot stale
        # immediately. The whole-matter fingerprint above still detects any
        # source change, including records outside the selected export scope.
        active_rows, _excluded, _warnings = self._record_rows(
            records,
            selected_record_ids=snapshot.get("selected_record_ids") or [],
            variant=str(snapshot.get("variant") or "metadata_only"),
        )
        active_ids = {str(row["evidence_id"]) for row in active_rows}
        blockers: list[str] = []
        if current != snapshot_fp:
            blockers.append("matter_snapshot_source_changed")
        if current_ids != active_ids:
            blockers.append("matter_snapshot_scope_changed")
        return bool(blockers), blockers

    def build_evidence_packet(
        self,
        matter_id: str,
        records: Sequence[dict[str, Any]],
        *,
        selected_record_ids: Sequence[str] | None = None,
        snapshot_id: str = "",
        variant: str = "metadata_only",
        approved: bool = False,
        note: str = "",
    ) -> dict[str, Any]:
        if not approved:
            raise MatterCommandCenterError("packet_approval_required", "Explicit approval is required before exporting an evidence packet.", status_code=409)
        snapshot = self.freeze_snapshot(
            matter_id,
            records,
            selected_record_ids=selected_record_ids,
            variant=variant,
            approved=True,
            note=note,
        )
        if snapshot_id and snapshot_id != snapshot["snapshot_id"]:
            raise MatterCommandCenterError("packet_snapshot_mismatch", "The requested snapshot does not match the frozen matter snapshot.", status_code=409)
        selected_ids = snapshot.get("selected_record_ids") or []
        selected = selected_ids if selected_ids else [row["evidence_id"] for row in snapshot.get("included_records") or []]
        work_product = self._work_product.build(records, selected_evidence_ids=selected)
        stale, stale_reasons = self._stale_status(snapshot, records)
        packet_payload = {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "matter_id": snapshot["matter_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "variant": str(variant or "metadata_only").strip().lower(),
            "generated_at": _utc_now(),
            "selected_record_ids": list(selected),
            "included_records": snapshot.get("included_records") or [],
            "excluded_records": snapshot.get("excluded_records") or [],
            "coverage": snapshot.get("coverage") or {},
            "snapshot": snapshot,
            "work_product": work_product.packet,
            "stale_snapshot_detected": stale,
            "stale_reasons": stale_reasons,
            "review_required": True,
        }
        packet_id = _sha(packet_payload)[:24]
        packet_root = self._packet_root(packet_id)
        packet_json, packet_html, receipt_path = self._packet_paths(packet_id)
        if packet_json.exists():
            existing = _read_json(packet_json)
            if existing.get("packet_sha256") and existing.get("packet_sha256") != _sha({key: value for key, value in existing.items() if key != "packet_sha256"}):
                raise MatterCommandCenterError("packet_tampered", "The stored packet failed verification.", status_code=409)
            self._write_json(self.active_packet_pointer, {"schema_version": "active_matter_command_center_packet_v1", "packet_id": packet_id, "activated_at": _utc_now()})
            return existing
        packet_root.mkdir(parents=True, exist_ok=True)
        packet_payload["packet_id"] = packet_id
        packet_payload["packet_sha256"] = _sha({key: value for key, value in packet_payload.items() if key != "packet_sha256"})
        receipt = {
            "schema_version": "matter_command_center_packet_receipt_v1",
            "matter_id": snapshot["matter_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "packet_id": packet_id,
            "packet_sha256": packet_payload["packet_sha256"],
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "variant": packet_payload["variant"],
            "included_record_ids": [row["evidence_id"] for row in packet_payload["included_records"]],
            "excluded_records": packet_payload["excluded_records"],
            "work_product_build_id": work_product.build_id,
            "work_product_sha256": work_product.packet.get("packet_sha256"),
            "review_required": True,
            "generated_at": packet_payload["generated_at"],
        }
        receipt["receipt_sha256"] = _sha({key: value for key, value in receipt.items() if key != "receipt_sha256"})
        self._write_json(packet_json, packet_payload)
        packet_html.write_text(_packet_html(packet_payload), encoding="utf-8", newline="\n")
        os.chmod(packet_html, 0o600)
        self._write_json(receipt_path, receipt)
        packet_md = packet_root / "packet.md"
        packet_md.write_text(_packet_markdown(packet_payload), encoding="utf-8", newline="\n")
        os.chmod(packet_md, 0o600)
        self._activate(snapshot["snapshot_id"], packet_id)
        return packet_payload | {"receipt": receipt, "work_product_result": work_product.as_dict()}

    def list_packets(self, matter_id: str | None = None) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for packet_root in sorted((path for path in self.packets.iterdir() if path.is_dir()), key=lambda path: path.stat().st_mtime, reverse=True):
            packet_json = packet_root / "packet.json"
            if not packet_json.is_file() or packet_json.is_symlink():
                continue
            payload = _read_json(packet_json)
            if matter_id and str(payload.get("matter_id") or "") != _safe_id(matter_id):
                continue
            receipt = _read_json(packet_root / "receipt.json") if (packet_root / "receipt.json").is_file() else {}
            rows.append(
                {
                    "packet_id": payload.get("packet_id") or packet_root.name,
                    "matter_id": payload.get("matter_id"),
                    "snapshot_id": payload.get("snapshot_id"),
                    "variant": payload.get("variant"),
                    "generated_at": payload.get("generated_at"),
                    "record_count": len(payload.get("included_records") or []),
                    "stale_snapshot_detected": bool(payload.get("stale_snapshot_detected")),
                    "packet_sha256": payload.get("packet_sha256"),
                    "receipt_sha256": receipt.get("receipt_sha256"),
                    "review_required": True,
                }
            )
        return {"schema_version": "matter_command_center_packet_list_v1", "packets": rows, "count": len(rows), "review_required": True}

    def _health_state(
        self,
        matter_id: str,
        records: Sequence[dict[str, Any]],
        *,
        snapshot: dict[str, Any] | None,
        stale: bool,
        stale_reasons: Sequence[str],
        packet_list: Sequence[dict[str, Any]],
        latest_packet_id: str,
    ) -> dict[str, Any]:
        included, _excluded, inventory_warnings = self._record_rows(records, variant="metadata_only")
        blockers: list[dict[str, Any]] = []

        def add(
            blocker_id: str,
            *,
            severity: str,
            title: str,
            detail: str,
            action_id: str,
            action_label: str,
            record_ids: Sequence[str] = (),
        ) -> None:
            blockers.append(
                {
                    "blocker_id": blocker_id,
                    "severity": severity,
                    "title": title,
                    "detail": detail,
                    "record_ids": sorted({str(item) for item in record_ids if str(item)})[:100],
                    "corrective_action": {
                        "action_id": action_id,
                        "label": action_label,
                        "scope": "active_matter_only",
                        "review_required": True,
                    },
                    "review_required": True,
                }
            )

        if not snapshot:
            add(
                "no_frozen_snapshot",
                severity="attention",
                title="No review snapshot has been frozen",
                detail="Freeze an explicit active-matter record scope before relying on a packet comparison.",
                action_id="freeze_review_snapshot",
                action_label="Freeze a new review snapshot",
            )
        if stale:
            for reason in sorted(set(stale_reasons)):
                add(
                    reason,
                    severity="attention",
                    title="Frozen snapshot no longer matches the active matter",
                    detail="Review the changed scope and freeze a new snapshot before using the old packet as current.",
                    action_id="review_scope_and_refreeze",
                    action_label="Review scope and freeze a replacement snapshot",
                )
        if not packet_list:
            add(
                "no_evidence_packet",
                severity="attention",
                title="No evidence packet has been built",
                detail="A packet is not available for handoff or comparison until a reviewed snapshot is selected and built.",
                action_id="build_review_required_packet",
                action_label="Build a review-required evidence packet",
            )
        missing_hashes = [row["evidence_id"] for row in included if not row.get("source_hash")]
        if missing_hashes:
            add(
                "source_hash_missing",
                severity="attention",
                title="Some active-matter records lack a source hash",
                detail="Inspect these records before treating them as provenance-bound evidence.",
                action_id="inspect_record_provenance",
                action_label="Inspect record provenance",
                record_ids=missing_hashes,
            )
        privacy_review = [
            row["evidence_id"]
            for row in included
            if str(row.get("privacy_status") or "").strip()
            and str(row.get("privacy_status") or "").strip().lower() not in {"pass", "cleared", "reviewed"}
        ]
        if privacy_review:
            add(
                "privacy_review_required",
                severity="attention",
                title="Some records retain a privacy-review status",
                detail="Review privacy findings before selecting these records for a shareable or full-content work product.",
                action_id="review_record_privacy",
                action_label="Review record privacy status",
                record_ids=privacy_review,
            )
        parser_review = [
            row["evidence_id"]
            for row in included
            if any(
                str(row.get(field) or "").strip().lower() not in {"", "pass", "complete", "not_required"}
                for field in ("parser_status", "ocr_status")
            )
        ]
        if parser_review:
            add(
                "parser_or_ocr_review_required",
                severity="attention",
                title="Some records have parser or OCR review signals",
                detail="Inspect the original record and the local extraction before relying on derived text.",
                action_id="inspect_parser_or_ocr_result",
                action_label="Inspect parser or OCR result",
                record_ids=parser_review,
            )
        if latest_packet_id:
            packet_reviews = self.review_history(latest_packet_id).get("history") or []
            if not packet_reviews:
                add(
                    "latest_packet_review_not_recorded",
                    severity="attention",
                    title="The latest evidence packet has no recorded reviewer decision",
                    detail="A generated packet remains review-required until a reviewer records an outcome.",
                    action_id="record_packet_reviewer_decision",
                    action_label="Record a packet reviewer decision",
                )
        warning_ids = [str(item).split(":", 1)[-1] for item in inventory_warnings if ":" in str(item)]
        return {
            "schema_version": "matter_command_center_health_v1",
            "matter_id": _safe_id(matter_id),
            "record_count": len(included),
            "packet_count": len(packet_list),
            "latest_packet_id": latest_packet_id,
            "snapshot_id": str(snapshot.get("snapshot_id") or "") if snapshot else "",
            "stale_snapshot_detected": bool(stale),
            "blockers": blockers,
            "blocker_count": len(blockers),
            "inventory_warning_record_ids": sorted(set(warning_ids))[:100],
            "review_required": True,
            "health_status": "attention_required" if blockers else "review_required_no_known_blocker",
        }

    def _load_health_history(self, matter_id: str) -> list[dict[str, Any]]:
        if not self.health_history_path.exists():
            return []
        if self.health_history_path.is_symlink():
            raise MatterCommandCenterError("command_center_health_history_symlink_refused", "The command-center health history was refused.", status_code=409)
        rows: list[dict[str, Any]] = []
        previous_entry_sha256 = "0" * 64
        for line in self.health_history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MatterCommandCenterError("command_center_health_history_invalid", "The command-center health history is invalid.", status_code=409) from exc
            if not isinstance(row, dict):
                raise MatterCommandCenterError("command_center_health_history_invalid", "The command-center health history is invalid.", status_code=409)
            entry_sha256 = str(row.get("entry_sha256") or "")
            expected_entry_sha256 = _sha({key: value for key, value in row.items() if key != "entry_sha256"})
            if (
                not entry_sha256
                or entry_sha256 != expected_entry_sha256
                or str(row.get("previous_entry_sha256") or "") != previous_entry_sha256
            ):
                raise MatterCommandCenterError("command_center_health_history_tampered", "The command-center health history failed verification.", status_code=409)
            previous_entry_sha256 = entry_sha256
            if str(row.get("matter_id") or "") == _safe_id(matter_id):
                rows.append(row)
        return rows

    def _record_health_state(self, health: dict[str, Any]) -> list[dict[str, Any]]:
        matter_id = str(health.get("matter_id") or "")
        previous = self._load_health_history(matter_id)
        fingerprint_payload = {key: value for key, value in health.items() if key not in {"observed_at", "health_id", "state_sha256", "entry_sha256"}}
        fingerprint = _sha(fingerprint_payload)
        if previous and str(previous[-1].get("state_sha256") or "") == fingerprint:
            return previous
        entry = {
            **fingerprint_payload,
            "health_id": fingerprint[:24],
            "observed_at": _utc_now(),
            "state_sha256": fingerprint,
            "previous_entry_sha256": str(previous[-1].get("entry_sha256") or "0" * 64) if previous else "0" * 64,
        }
        entry["entry_sha256"] = _sha(entry)
        if self.health_history_path.exists() and self.health_history_path.is_symlink():
            raise MatterCommandCenterError("command_center_health_history_symlink_refused", "The command-center health history was refused.", status_code=409)
        with self.health_history_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False))
            handle.write("\n")
        os.chmod(self.health_history_path, 0o600)
        return [*previous, entry]

    def health_history(self, matter_id: str) -> dict[str, Any]:
        rows = self._load_health_history(matter_id)
        return {
            "schema_version": "matter_command_center_health_history_v1",
            "matter_id": _safe_id(matter_id),
            "history": rows[-100:],
            "count": len(rows),
            "review_required": True,
        }

    def command_center(self, matter_id: str, records: Sequence[dict[str, Any]]) -> dict[str, Any]:
        latest_snapshot_id = self._latest_snapshot_id()
        snapshot = self._snapshot_payload(latest_snapshot_id) if latest_snapshot_id else None
        latest_packet_id = ""
        if self.active_packet_pointer.exists():
            try:
                latest_packet_id = _safe_text(_read_json(self.active_packet_pointer).get("packet_id"), 64)
            except MatterCommandCenterError:
                latest_packet_id = ""
        stale = False
        stale_reasons: list[str] = []
        if snapshot:
            stale, stale_reasons = self._stale_status(snapshot, records)
        packet_list = self.list_packets(matter_id).get("packets", [])
        health = self._health_state(
            matter_id,
            records,
            snapshot=snapshot,
            stale=stale,
            stale_reasons=stale_reasons,
            packet_list=packet_list,
            latest_packet_id=latest_packet_id,
        )
        health_history = self._record_health_state(health)
        return {
            "schema_version": SCHEMA_VERSION,
            "matter_id": _safe_id(matter_id),
            "latest_snapshot_id": latest_snapshot_id,
            "latest_packet_id": latest_packet_id,
            "snapshot": snapshot,
            "stale_snapshot_detected": stale,
            "stale_reasons": stale_reasons,
            "packet_list": packet_list,
            "health": health,
            "health_history": health_history[-100:],
            "review_required": True,
        }

    def packet(self, packet_id: str) -> dict[str, Any]:
        packet_json, _packet_html, receipt_path = self._packet_paths(packet_id)
        payload = _read_json(packet_json)
        if payload.get("packet_sha256") != _sha({key: value for key, value in payload.items() if key != "packet_sha256"}):
            raise MatterCommandCenterError("packet_tampered", "The packet failed its integrity check.", status_code=409)
        payload["receipt"] = _read_json(receipt_path)
        return payload

    def receipt(self, packet_id: str) -> dict[str, Any]:
        _packet_json, _packet_html, receipt_path = self._packet_paths(packet_id)
        return _read_json(receipt_path)

    def compare_packets(self, left_packet_id: str, right_packet_id: str) -> dict[str, Any]:
        left = self.packet(left_packet_id)
        right = self.packet(right_packet_id)
        left_ids = {str(row.get("evidence_id") or "") for row in left.get("included_records") or []}
        right_ids = {str(row.get("evidence_id") or "") for row in right.get("included_records") or []}
        return {
            "schema_version": "matter_command_center_packet_compare_v1",
            "left_packet_id": left_packet_id,
            "right_packet_id": right_packet_id,
            "left_snapshot_id": left.get("snapshot_id"),
            "right_snapshot_id": right.get("snapshot_id"),
            "same_packet": left.get("packet_sha256") == right.get("packet_sha256"),
            "same_record_scope": left_ids == right_ids,
            "added_record_ids": sorted(right_ids - left_ids),
            "removed_record_ids": sorted(left_ids - right_ids),
            "review_required": True,
        }

    def review_packet(
        self,
        packet_id: str,
        *,
        reviewer_name: str,
        reviewer_role: str,
        review_status: str,
        note: str = "",
        approved: bool = False,
    ) -> dict[str, Any]:
        if not approved:
            raise MatterCommandCenterError("packet_review_approval_required", "Explicit approval is required before recording a packet review.", status_code=409)
        normalized_status = str(review_status or "").strip().lower()
        if normalized_status not in ALLOWED_REVIEW_STATUS:
            raise MatterCommandCenterError("invalid_packet_review_status", "Unsupported review status.", status_code=400)
        packet = self.packet(packet_id)
        entry = {
            "schema_version": "matter_command_center_packet_review_v1",
            "review_id": uuid.uuid4().hex,
            "packet_id": packet_id,
            "matter_id": packet.get("matter_id"),
            "snapshot_id": packet.get("snapshot_id"),
            "reviewer_name": _safe_text(reviewer_name, 160),
            "reviewer_role": _safe_text(reviewer_role, 80),
            "review_status": normalized_status,
            "note": _safe_text(note, MAX_NOTE_CHARS),
            "created_at": _utc_now(),
            "previous_entry_sha256": "",
            "review_required": True,
        }
        history_rows: list[dict[str, Any]] = []
        if self.history.exists():
            for line in self.history.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                history_rows.append(json.loads(line))
        previous = str(history_rows[-1].get("entry_sha256") or "0" * 64) if history_rows else "0" * 64
        entry["previous_entry_sha256"] = previous
        entry["entry_sha256"] = _sha({key: value for key, value in entry.items() if key != "entry_sha256"})
        with self.history.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, sort_keys=True, ensure_ascii=False))
            handle.write("\n")
        return entry

    def review_history(self, packet_id: str | None = None) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        if self.history.exists():
            for line in self.history.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if packet_id and str(row.get("packet_id") or "") != packet_id:
                    continue
                rows.append(row)
        return {
            "schema_version": "matter_command_center_packet_review_history_v1",
            "packet_id": packet_id or "",
            "history": rows,
            "count": len(rows),
            "review_required": True,
        }

    def verify(self, packet_id: str | None = None) -> dict[str, Any]:
        target_packet_id = packet_id or (
            _safe_text(_read_json(self.active_packet_pointer).get("packet_id"), 64) if self.active_packet_pointer.exists() else ""
        )
        if not target_packet_id:
            return {"status": "blocked", "blockers": ["no_command_center_builds"], "review_required": True}
        if packet_id:
            packet = self.packet(packet_id)
        else:
            packet = self.packet(target_packet_id)
        blockers: list[str] = []
        if packet.get("packet_sha256") and packet.get("packet_sha256") != _sha({key: value for key, value in packet.items() if key != "packet_sha256"}):
            blockers.append("packet_content_hash_mismatch")
        return {
            "status": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "packet_id": packet.get("packet_id") or packet_id or "",
            "review_required": True,
        }
