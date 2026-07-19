"""Generate the checked-in FOCAF printable inventory from original public PDFs."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = ROOT / "src" / "maine_family_law_llm" / "resources" / "focaf"
INVENTORY_PATH = RESOURCE_ROOT / "focaf_inventory.json"
REPORT_PATH = ROOT / "docs" / "FOCAF_PRINTABLE_LIBRARY_INVENTORY.md"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _category(filename: str, text: str) -> tuple[str, str, str, str]:
    haystack = f"{filename} {text}".lower()
    if "cumberland" in haystack:
        municipality = filename.split("-")[1].replace("-", " ").title()
        return "Local Cumberland County resources", "Cumberland", municipality, "Families seeking local support contacts"
    if "york-" in filename:
        municipality = filename.split("-")[1].replace("-", " ").title()
        return "Local York County resources", "York", municipality, "Families seeking local support contacts"
    mapping = [
        ("court", "Court-day preparation", "Parents preparing for a court date"),
        ("deadline", "Orders, dates, and deadlines", "Parents tracking orders and dates"),
        ("record", "Records and case organization", "Parents organizing documents"),
        ("binder", "Records and case organization", "Parents organizing documents"),
        ("communication", "Calm communication", "Parents coordinating with another caregiver"),
        ("exchange", "Parenting schedules and exchanges", "Parents planning exchanges"),
        ("routine", "Child routines and wellbeing", "Parents supporting routines across homes"),
        ("school", "School, childcare, counseling, and provider coordination", "Parents and providers coordinating updates"),
        ("provider", "School, childcare, counseling, and provider coordination", "Parents and providers coordinating updates"),
        ("grandparent", "Grandparents and other family helpers", "Grandparents and family helpers"),
        ("teen", "Youth and teen resources", "Teens and parents"),
        ("crisis", "Maine crisis and support contacts", "Families seeking urgent support contacts"),
        ("best-interest", "Best-interest-factor planning", "Parents preparing factual information"),
        ("terms", "Plain-language family-court terms", "Families learning common terms"),
        ("research", "Research and civic materials", "Researchers and civic readers"),
        ("harm", "Professional or policy materials", "Professional or policy readers"),
        ("disparagement", "Professional or policy materials", "Professional or policy readers"),
        ("before-you", "Getting started after service", "Families preparing initial questions"),
    ]
    for keyword, category, audience in mapping:
        if keyword in haystack:
            return category, "", "", audience
    return "Family-facing printables", "", "", "Maine families"


def _kind(filename: str) -> str:
    for keyword, kind in (("checklist", "checklist"), ("tracker", "tracker"), ("worksheet", "worksheet"), ("planner", "planner"), ("card", "card"), ("pack", "packet"), ("guide", "guide")):
        if keyword in filename:
            return kind
    return "printable"


def _summary(text: str, filename: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())[0] if text.strip() else ""
    return sentence[:360].rstrip() or f"Public FOCAF family printable: {filename}."


def main() -> int:
    manifest_rows = {row["FileName"]: row for row in csv.DictReader((RESOURCE_ROOT / "manifest.csv").open(encoding="utf-8"))}
    documents = []
    for pdf_path in sorted(RESOURCE_ROOT.glob("*.pdf")):
        raw = pdf_path.read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest().upper()
        manifest = manifest_rows.get(pdf_path.name, {})
        reader = PdfReader(str(pdf_path))
        pages = []
        headings: list[str] = []
        chunks = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            words = re.findall(r"\w+", text)
            page_headings = [line.strip() for line in text.splitlines() if 3 <= len(line.strip()) <= 100][:4]
            headings.extend(page_headings)
            pages.append({"page_number": page_number, "text": text, "character_count": len(text), "word_count": len(words), "headings": page_headings, "native_text_status": "available" if text else "not_available", "ocr_status": "not_needed" if text else "not_run"})
            for index, start in enumerate(range(0, max(len(text), 1), 900), start=1):
                chunk_text = text[start:start + 1100]
                if chunk_text:
                    chunks.append({"chunk_id": f"{_slug(pdf_path.stem)}-p{page_number}-c{index}", "page_number": page_number, "character_start": start, "character_end": start + len(chunk_text), "text": chunk_text})
        all_text = "\n".join(page["text"] for page in pages)
        category, county, municipality, audience = _category(pdf_path.name, all_text)
        normalized = sorted(set(re.findall(r"[a-z0-9]{3,}", f"{pdf_path.stem} {all_text}".lower())))
        documents.append({
            "document_id": f"focaf-{_slug(pdf_path.stem)}",
            "original_filename": pdf_path.name,
            "display_title": pdf_path.stem.replace("-", " ").replace("_", " ").title(),
            "description": _summary(all_text, pdf_path.name),
            "category": category,
            "intended_audience": audience,
            "likely_use_cases": [category, _kind(pdf_path.name)],
            "family_situation": audience,
            "county": county,
            "municipality": municipality,
            "page_count": len(pages),
            "full_text": all_text,
            "pages": pages,
            "headings": sorted(set(headings))[:30],
            "document_kind": _kind(pdf_path.name),
            "keywords": normalized[:250],
            "source_url": manifest.get("Url", ""),
            "source_hash": actual_hash,
            "manifest_hash": manifest.get("SHA256", ""),
            "manifest_hash_matches": actual_hash == manifest.get("SHA256", ""),
            "resource_lane": "family_printable_secondary_resource",
            "authority_status": "not_legal_authority",
            "parser": {"name": "pypdf", "version": getattr(__import__("pypdf"), "__version__", "unknown")},
            "native_text_status": "available" if all_text else "not_available",
            "ocr_status": "not_needed" if all_text else "not_run",
            "related_document_family": pdf_path.stem.split("-")[0],
            "printability_status": "original_pdf_preserved",
            "warnings": ["Family resource only. Not legal authority, official form, or proof of disputed facts."],
            "extraction_date": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "chunks": chunks,
        })
    payload = {"schema": "maine_family_law_llm.focaf_inventory.v1", "library": "FOCAF public family printables", "authority_status": "not_legal_authority", "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "documents": documents}
    with INVENTORY_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    groups: dict[str, list[dict[str, object]]] = {}
    for document in documents:
        groups.setdefault(str(document["category"]), []).append(document)
    report = ["# FOCAF Printable Library Inventory", "", "This bundled public library contains family-facing resources and selected research/professional materials. It is a secondary resource library, not legal authority or official court forms.", "", f"- PDFs: {len(documents)}", f"- Pages: {sum(int(item['page_count']) for item in documents)}", f"- Native-text PDFs: {sum(1 for item in documents if item['native_text_status'] == 'available')}", ""]
    for category in sorted(groups):
        report.extend([f"## {category}", ""])
        for document in groups[category]:
            report.append(f"- **{document['display_title']}** ({document['page_count']} page(s)): {document['description']}")
        report.append("")
    with REPORT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(report).rstrip() + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
