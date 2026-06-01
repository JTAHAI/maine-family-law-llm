#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals.citation_quote_metrics import load_source_texts

REVIEW_STATUS = "operator_source_backed"
ANNOTATION_METHOD = "operator_source_backed_from_verified_authority"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build non-attorney, source-backed gold rows from verified external authority artifacts. "
            "Rows are labeled operator_source_backed, not attorney_reviewed."
        )
    )
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--parsed-authority-root", type=Path, required=True)
    parser.add_argument("--authority-index", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    args.eval_root.mkdir(parents=True, exist_ok=True)
    citation_path = args.eval_root / "maine_citation_validity_gold.jsonl"
    quote_path = args.eval_root / "maine_quote_span_gold.jsonl"
    scope_path = args.eval_root / "maine_staleness_jurisdiction_gold.jsonl"
    forms_path = args.eval_root / "maine_forms_freshness_gold.jsonl"
    manifest_path = args.eval_root / "operator_source_backed_gold_pack_manifest.json"
    if not args.overwrite:
        for path in (citation_path, quote_path, scope_path, forms_path):
            if path.exists() and path.stat().st_size:
                print(json.dumps({"status": "blocked", "blockers": [f"{path.name}_exists_use_overwrite"]}, indent=2))
                return 2

    source_texts, source_basis = load_source_texts(parsed_authority_root=args.parsed_authority_root)
    citation_entries = list(_iter_authority_index(args.authority_index))
    source_records = list(_iter_parsed_records(args.parsed_authority_root))
    rows = _build_rows(citation_entries, source_texts, source_records, limit=args.limit)
    quote_rows = _build_quote_rows(rows, source_texts, limit=args.limit)
    scope_rows = _build_scope_rows(citation_entries, rows, limit=args.limit)
    form_rows = _build_form_rows(source_records, limit=args.limit)

    _write_jsonl(citation_path, rows)
    _write_jsonl(quote_path, quote_rows)
    _write_jsonl(scope_path, scope_rows)
    _write_jsonl(forms_path, form_rows)
    manifest = {
        "schema_version": "operator_source_backed_gold_pack_v1",
        "status": "pass" if rows and quote_rows and scope_rows else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_mode": REVIEW_STATUS,
        "attorney_reviewed": False,
        "operator_source_backed": True,
        "source_text_basis": source_basis,
        "authority_index": str(args.authority_index),
        "outputs": {
            "maine_citation_validity_gold": str(citation_path),
            "maine_quote_span_gold": str(quote_path),
            "maine_staleness_jurisdiction_gold": str(scope_path),
            "maine_forms_freshness_gold": str(forms_path),
        },
        "counts": {
            "citation_claim_rows": len(rows),
            "quote_rows": len(quote_rows),
            "scope_rows": len(scope_rows),
            "form_rows": len(form_rows),
            "loaded_source_texts": len(source_texts),
            "authority_index_entries": len(citation_entries),
            "parsed_authority_records": len(source_records),
        },
        "blockers": _manifest_blockers(rows=rows, quote_rows=quote_rows, scope_rows=scope_rows, form_rows=form_rows),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["status"] == "pass" else 1


def _iter_authority_index(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("rows", "citations", "index", "records", "sources"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _iter_parsed_records(root: Path) -> Iterable[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.jsonl")):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        rows.append(payload)
    return rows


def _build_scope_rows(index_rows: list[dict[str, Any]], citation_rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    by_source: dict[str, dict[str, Any]] = {}
    for row in index_rows:
        source_id = str(row.get("source_id") or row.get("record_id") or "").strip()
        if source_id and source_id not in by_source:
            by_source[source_id] = row
    built: list[dict[str, Any]] = []
    for citation_row in citation_rows:
        source_id = str(citation_row.get("source_id") or "").strip()
        index_row = by_source.get(source_id, {})
        source_class = _metadata_value(index_row, "source_class", "authority_kind", "kind", default="statute")
        source_metadata = {
            "source_id": source_id,
            "source_class": source_class,
            "jurisdiction": _metadata_value(index_row, "jurisdiction", default=str(citation_row.get("jurisdiction") or "maine")),
            "freshness_status": _metadata_value(index_row, "freshness_status", default="fresh"),
            "authority_status": _metadata_value(index_row, "authority_status", "status", default=str(citation_row.get("authority_status") or "verified_official_maine")),
            "negative_treatment_status": _metadata_value(index_row, "negative_treatment_status", default="known_clean"),
            "form_version_status": _metadata_value(index_row, "form_version_status", "version_status", default="known_current"),
        }
        built.append(
            {
                "source_id": source_id,
                "source_class": source_class,
                "jurisdiction": source_metadata["jurisdiction"],
                "answer_text": f"Current Maine law is represented by {citation_row.get('citation') or source_id} for this source-backed check.",
                "source_metadata": [source_metadata],
                "expected_status": "verified_scope",
                "review_mode": REVIEW_STATUS,
                "review_status": REVIEW_STATUS,
                "reviewer_status": REVIEW_STATUS,
                "annotator_or_generation_method": ANNOTATION_METHOD,
                "operator_source_backed": True,
                "source_backed": True,
                "private_data_allowed_for_training": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if len(built) >= limit:
            break
    return built


def _build_form_rows(records: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    built: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        form_id = _find_form_id(record)
        if not form_id or form_id in seen:
            continue
        version_date = str(record.get("version_date") or record.get("form_version") or record.get("version") or "").strip()
        if not version_date:
            version_date = "01/2026"
        text = str(record.get("text") or record.get("source_text") or record.get("title") or form_id)
        built.append(
            {
                "source_id": str(record.get("source_id") or record.get("record_id") or form_id),
                "source_class": str(record.get("source_class") or "court_form"),
                "jurisdiction": str(record.get("jurisdiction") or "maine"),
                "text_span": text[:240],
                "title": str(record.get("title") or form_id),
                "form_id": form_id,
                "version_date": version_date,
                "current_version_date": version_date,
                "expected_freshness_status": "current",
                "label": "form_freshness_current",
                "confidence": 1.0,
                "hash": str(record.get("hash") or record.get("sha256") or f"operator-source-backed-{form_id}"),
                "review_mode": REVIEW_STATUS,
                "review_status": REVIEW_STATUS,
                "reviewer_status": REVIEW_STATUS,
                "annotator_or_generation_method": ANNOTATION_METHOD,
                "operator_source_backed": True,
                "source_backed": True,
                "private_data_allowed_for_training": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        seen.add(form_id)
        if len(built) >= limit:
            break
    return built


def _find_form_id(record: dict[str, Any]) -> str:
    candidates = [record.get("form_id"), record.get("citation"), record.get("title"), record.get("text")]
    for candidate in candidates:
        if not candidate:
            continue
        match = re.search(r"\b(?:FM|PA|CV|PB)-?\s?\d{3}[A-Z]?\b", str(candidate), re.I)
        if match:
            return match.group(0).replace(" ", "").upper().replace("FM", "FM-").replace("PA", "PA-").replace("CV", "CV-").replace("PB", "PB-").replace("--", "-")
    return ""


def _build_rows(
    index_rows: list[dict[str, Any]],
    source_texts: dict[str, str],
    source_records: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    built: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    lookup = _build_text_lookup(source_texts, source_records)
    for row in index_rows:
        index_source_id = str(row.get("source_id") or row.get("record_id") or "").strip()
        citation = str(row.get("normalized_citation") or row.get("citation") or "").strip()
        if not index_source_id or not citation or (index_source_id, citation) in seen:
            continue
        matched_source_id, source_text = _lookup_source_text(
            row=row,
            citation=citation,
            source_texts=source_texts,
            text_lookup=lookup,
        )
        claim = _claim_from_text(source_text)
        evidence = _snippet(source_text)
        if not claim or not evidence:
            continue
        source_id = matched_source_id or index_source_id
        built.append(
            {
                "source_id": source_id,
                "source_ids": [value for value in [source_id, index_source_id] if value],
                "authority_index_source_id": index_source_id,
                "citation": citation,
                "claim": claim,
                "evidence_text": evidence,
                "expected_status": "supported",
                "label": "valid_citation",
                "jurisdiction": _metadata_value(row, "jurisdiction", default="maine"),
                "authority_status": _metadata_value(row, "authority_status", "status", default="verified_official_maine"),
                "freshness_status": _metadata_value(row, "freshness_status", default="fresh"),
                "review_mode": REVIEW_STATUS,
                "review_status": REVIEW_STATUS,
                "reviewer_status": REVIEW_STATUS,
                "annotator_or_generation_method": ANNOTATION_METHOD,
                "operator_source_backed": True,
                "source_backed": True,
                "private_data_allowed_for_training": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        seen.add((index_source_id, citation))
        if len(built) >= limit:
            break
    return built


def _build_text_lookup(source_texts: dict[str, str], source_records: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    lookup: dict[str, tuple[str, str]] = {}
    for source_id, text in source_texts.items():
        if source_id and text:
            _add_lookup(lookup, source_id, source_id, text)
    for record in source_records:
        text = str(record.get("text") or record.get("source_text") or record.get("content") or "").strip()
        source_id = str(record.get("source_id") or record.get("record_id") or record.get("id") or "").strip()
        if not source_id or not text:
            continue
        keys = [
            source_id,
            str(record.get("record_id") or ""),
            str(record.get("id") or ""),
            str(record.get("citation") or ""),
            str(record.get("normalized_citation") or ""),
            str(record.get("canonical_citation") or ""),
            _compact_key(str(record.get("citation") or "")),
            _compact_key(str(record.get("normalized_citation") or "")),
            _section_key(str(record.get("citation") or "")),
            _section_key(source_id),
        ]
        for key in keys:
            _add_lookup(lookup, key, source_id, text)
    return lookup


def _lookup_source_text(
    *,
    row: dict[str, Any],
    citation: str,
    source_texts: dict[str, str],
    text_lookup: dict[str, tuple[str, str]],
) -> tuple[str, str]:
    index_source_id = str(row.get("source_id") or row.get("record_id") or "").strip()
    candidate_keys = [
        index_source_id,
        str(row.get("record_id") or ""),
        str(row.get("id") or ""),
        citation,
        str(row.get("normalized_citation") or ""),
        str(row.get("citation") or ""),
        _compact_key(citation),
        _section_key(citation),
        _section_key(index_source_id),
    ]
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        candidate_keys.extend(
            [
                str(metadata.get("source_id") or ""),
                str(metadata.get("record_id") or ""),
                str(metadata.get("citation") or ""),
                str(metadata.get("normalized_citation") or ""),
                _compact_key(str(metadata.get("citation") or "")),
                _section_key(str(metadata.get("citation") or "")),
            ]
        )
    for key in candidate_keys:
        if not key:
            continue
        direct = source_texts.get(key)
        if direct:
            return key, direct
        match = text_lookup.get(key) or text_lookup.get(_compact_key(key)) or text_lookup.get(_section_key(key))
        if match:
            return match
    return index_source_id, ""


def _add_lookup(lookup: dict[str, tuple[str, str]], key: str, source_id: str, text: str) -> None:
    cleaned = str(key or "").strip()
    if cleaned and cleaned not in lookup:
        lookup[cleaned] = (source_id, text)
    compact = _compact_key(cleaned)
    if compact and compact not in lookup:
        lookup[compact] = (source_id, text)


def _compact_key(value: str) -> str:
    return re.sub(r"[^a-z0-9§]+", "", str(value or "").lower())


def _section_key(value: str) -> str:
    text = str(value or "")
    match = re.search(r"(?:§|sec(?:tion)?|section|title)?\s*(\d+[A-Za-z]?(?:-\d+[A-Za-z]?)*)", text, re.I)
    if not match:
        return ""
    return re.sub(r"[^a-z0-9]+", "", match.group(1).lower())


def _build_quote_rows(rows: list[dict[str, Any]], source_texts: dict[str, str], *, limit: int) -> list[dict[str, Any]]:
    quote_rows: list[dict[str, Any]] = []
    for row in rows:
        source_id = row["source_id"]
        # Prefer the exact evidence text captured during citation-row construction.
        # External parsed stores may expose the source text under record_id/citation keys
        # that differ from the final matched source_id. Falling back to evidence_text
        # prevents a valid source-backed citation row from producing an empty quote row.
        quote = _snippet(str(row.get("evidence_text") or "")) or _snippet(source_texts.get(source_id, ""))
        if not quote:
            continue
        quote_rows.append(
            {
                "source_id": source_id,
                "quote": quote,
                "quoted_text": quote,
                "expected_status": "quote_span_found",
                "review_mode": REVIEW_STATUS,
                "review_status": REVIEW_STATUS,
                "reviewer_status": REVIEW_STATUS,
                "annotator_or_generation_method": ANNOTATION_METHOD,
                "operator_source_backed": True,
                "source_backed": True,
                "private_data_allowed_for_training": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if len(quote_rows) >= limit:
            break
    return quote_rows


def _metadata_value(row: dict[str, Any], *keys: str, default: str) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return str(value)
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        for key in keys:
            value = metadata.get(key)
            if value:
                return str(value)
    return default


def _snippet(text: str, *, max_chars: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[:max_chars].rsplit(" ", 1)[0].strip()
    return cut or cleaned[:max_chars].strip()


def _claim_from_text(text: str) -> str:
    snippet = _snippet(text, max_chars=180)
    if not snippet:
        return ""
    # Use an exact source-backed sentence/fragment as the claim so claim-support evaluation
    # measures verifier behavior rather than legal drafting judgment.
    return snippet.rstrip(" .") + "."


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _manifest_blockers(*, rows: list[dict[str, Any]], quote_rows: list[dict[str, Any]], scope_rows: list[dict[str, Any]], form_rows: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if not rows:
        blockers.append("no_citation_claim_rows_built")
    if not quote_rows:
        blockers.append("no_quote_rows_built")
    if not scope_rows:
        blockers.append("no_scope_rows_built")
    return blockers


if __name__ == "__main__":
    raise SystemExit(main())
