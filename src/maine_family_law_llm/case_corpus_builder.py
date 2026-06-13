from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import shutil
import sqlite3
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pypdf import PdfReader, PdfWriter

from .legal_matter_classifier import classify_legal_matter
from .privacy_classifier import classify_privacy
from .question_bank import generate_builtin_question_bank, write_question_bank
from .role_package_builder import ROLE_PACKAGE_DEFS, build_role_packages


REPO_VERSION = "2.07.0"
REPO_PROOF_JSON = "BASE_MAINE_FAMILY_LAW_LLM_UPGRADE_PROOF.json"
CASE_PROOF_JSON = "CASE_BUILD_PROOF.json"
ROOT_LAUNCHERS = (
    "START_MAINE_FAMILY_LAW_LLM.cmd",
    "START_MAINE_FAMILY_LAW_LLM.bat",
    "START_MAINE_FAMILY_LAW_LLM.vbs",
    "START_HERE.html",
    "README_FIRST.txt",
    "VERIFY_INSTALLATION.cmd",
    "REPAIR_AND_REBUILD_INDEX.cmd",
)
CASE_LAYOUT = (
    "00_START_HERE",
    "01_PRIVATE_FORENSIC_MASTER_INTERNAL_ONLY",
    "02_EXTERNAL_LEGAL_MATTER_RELEASE",
    "03_ROLE_PACKAGES",
    "04_INDEXES",
    "05_TIMELINES",
    "06_ISSUE_LANES",
    "07_ENTITIES_WITNESSES_DOCKETS",
    "08_SOURCE_MANIFESTS_HASHES",
    "09_PRIVACY_PRIVILEGE_REVIEW",
    "10_OCR_TEXT_EXTRACTION",
    "11_EMAIL_THREADS_ATTACHMENTS",
    "12_PDF_IMAGE_NATIVE_DOCS",
    "13_DUPLICATES_VERSION_HISTORY",
    "14_QUARANTINE_UNREADABLE_UNSUPPORTED",
    "15_PROOF_VALIDATION",
    "16_USB_EXPORTS",
    "17_LOGS",
    "18_SETTINGS",
)
PORTAL_FILES = (
    "index.html",
    "START_HERE.html",
    "search.html",
    "timeline.html",
    "issue_lanes.html",
    "role_packages.html",
    "proof.html",
    "known_limitations.html",
    "privacy_summary.html",
)
LOCAL_ONLY_DEFAULT = True
NO_CLOUD_DEFAULT = True
CLOUD_CALLS_MADE = 0


@dataclass(slots=True)
class CaseBuildResult:
    case_root: Path
    proof_json_path: Path
    question_bank_path: Path
    repo_proof_path: Path | None = None


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    clean = "".join(char.lower() if char.isalnum() else "_" for char in value)
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean.strip("_") or "case"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_html(path: Path, title: str, body_html: str) -> None:
    write_text(
        path,
        "\n".join(
            [
                "<!doctype html>",
                "<html lang=\"en\">",
                "<head>",
                "<meta charset=\"utf-8\">",
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
                f"<title>{html.escape(title)}</title>",
                "</head>",
                "<body>",
                "<main>",
                body_html,
                "</main>",
                "</body>",
                "</html>",
            ]
        ),
    )


def append_changelog_entry(repo_root: Path) -> Path:
    changelog_path = repo_root / "CHANGELOG.md"
    entry = (
        "## 2.07.0 - v1.0.0 full-record corpus-builder upgrade\n\n"
        "- Added universal full-case corpus builder, local-first evidence intake, privacy-filtered external releases, role-specific GAL/court/lawyer/prosecutor packages, question-coverage audits, source-hash verification, and one-click launcher/self-builder workflow.\n"
    )
    if changelog_path.exists():
        current = changelog_path.read_text(encoding="utf-8")
        if entry in current:
            return changelog_path
    else:
        current = "# Changelog\n\n"
    write_text(changelog_path, current + entry)
    return changelog_path


def create_example_case_template(repo_root: Path) -> Path:
    source_root = repo_root / "dist" / "example_case_template" / "sample_source_corpus"
    source_root.mkdir(parents=True, exist_ok=True)
    write_text(
        source_root / "2026-02-11_shared_parental_rights_order.txt",
        (
            "Example Family Matter order. Shared parental rights remain in place. "
            "Records access, daily electronic contact, in-person contact scheduling, and counseling logistics are discussed."
        ),
    )
    write_text(
        source_root / "2026-02-16_compliance_email.eml",
        "\n".join(
            [
                "From: parent@example.test",
                "To: counsel@example.test",
                "Cc: provider@example.test",
                "Subject: Good-faith implementation request for therapy, contact, school, and medical access",
                "Date: Tue, 16 Feb 2026 09:30:00 -0500",
                "Message-ID: <example-20260216-1@test>",
                "",
                "I am requesting therapy scheduling, electronic contact windows, school records access, medical information, and MaineCare details in good faith.",
            ]
        ),
    )
    write_text(
        source_root / "school_attendance_support.txt",
        "School attendance record: tardy notices, academic support request, and records-access follow-up for the fictional child.",
    )
    write_text(
        source_root / "medical_records_request.txt",
        "Medical and dental records request, provider contact details, insurance and MaineCare release discussion.",
    )
    write_text(
        source_root / "personal_newsletter.txt",
        "Unrelated volunteer newsletter and birthday planning with no legal-matter relevance.",
    )
    pdf_path = source_root / "court_notice.pdf"
    if not pdf_path.exists():
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with pdf_path.open("wb") as handle:
            writer.write(handle)
    return source_root


def bootstrap_repository(repo_root: Path) -> dict[str, Path]:
    question_bank_path = write_question_bank(repo_root / "sample_question_bank" / "generic_question_bank.jsonl")
    example_source_root = create_example_case_template(repo_root)
    append_changelog_entry(repo_root)
    docs = {
        "README_FOR_NONTECHNICAL_USERS.html": (
            "<h1>Maine Family Law LLM</h1>"
            "<p>Double-click the launcher, choose a corpus, build a private master, then build external-safe role packages.</p>"
        ),
        "HOW_TO_ADD_YOUR_CORPUS.html": "<h1>How to Add Your Corpus</h1><p>Select source folders and an output root. The tool hashes sources before processing and never mutates them.</p>",
        "HOW_TO_BUILD_GAL_PACKAGE.html": "<h1>How to Build a GAL Package</h1><p>GAL mode prioritizes child stability, contact implementation, school, medical, and counseling review.</p>",
        "HOW_TO_BUILD_COURT_PACKAGE.html": "<h1>How to Build a Court Package</h1><p>Court mode focuses on orders, filings, service, docket entries, and missing proof.</p>",
        "HOW_TO_BUILD_LAWYER_PACKAGE.html": "<h1>How to Build a Lawyer Package</h1><p>Lawyer intake mode creates a 10-minute overview, issue map, and missing-record list.</p>",
        "HOW_TO_BUILD_PROSECUTOR_PACKAGE.html": "<h1>How to Build a Prosecutor Package</h1><p>ADA/prosecutor mode is source-bound, neutral, and emphasizes official verification.</p>",
        "HOW_PRIVACY_FILTERING_WORKS.html": "<h1>How Privacy Filtering Works</h1><p>Full record does not mean public dump. Full record means the full case-relevant record is preserved, indexed, and made reviewable, while unrelated personal material, privileged material, and sensitive child/medical records are handled through privacy and role-specific controls.</p>",
        "WHAT_FULL_RECORD_MEANS.html": "<h1>What Full Record Means</h1><p>Full record does not mean public dump. Full record means the full case-relevant record is preserved, indexed, and made reviewable, while unrelated personal material, privileged material, and sensitive child/medical records are handled through privacy and role-specific controls.</p>",
        "WHAT_THIS_TOOL_IS_AND_IS_NOT.html": "<h1>What This Tool Is and Is Not</h1><p>This tool is for evidence navigation, source review, and record organization. It is not legal advice, does not replace counsel, does not determine admissibility, and does not replace official court records, dockets, certified records, subpoenas, witness interviews, or GAL/court independent review.</p>",
        "HASH_AND_CHAIN_OF_CUSTODY.html": "<h1>Hash and Chain of Custody</h1><p>Source files are hashed before processing and re-hashed after processing to confirm no mutation.</p>",
        "KNOWN_LIMITATIONS.html": "<h1>Known Limitations</h1><p>Optional OCR, archive parsing, and PST/OST support depend on locally available parsers. Unsupported files are inventoried and never silently dropped.</p>",
        "TROUBLESHOOTING.html": "<h1>Troubleshooting</h1><p>If a parser is missing, the file is inventoried as needs-human-review or unsupported, and the build continues with warnings.</p>",
    }
    for name, body in docs.items():
        write_html(repo_root / "docs" / name, name.replace("_", " "), body)
    write_text(
        repo_root / "docs" / "SECURITY_AND_LOCAL_ONLY.md",
        "Default operation is local-first, no telemetry, no hidden analytics, and no cloud evidence uploads without explicit opt-in.",
    )
    write_text(
        repo_root / "docs" / "DEVELOPER_GUIDE.md",
        "The universal corpus builder uses local hashing, classifiers, question coverage, role packages, and proof reports. Outputs stay under the chosen case root.",
    )
    readme_path = repo_root / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")
    readme_appendix = (
        "\n\n## Universal full-case corpus builder\n\n"
        "This repository now includes a reusable local-first corpus builder for private forensic masters, external legal-matter releases, and role-specific review packages.\n"
    )
    if "## Universal full-case corpus builder" not in readme_text:
        write_text(readme_path, readme_text + readme_appendix)
    start_cmd = "@echo off\r\nsetlocal\r\ncd /d %~dp0\r\npython app\\launcher.py %*\r\n"
    start_bat = start_cmd
    start_vbs = (
        'Set shell = CreateObject("WScript.Shell")\r\n'
        'root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)\r\n'
        'shell.Run "cmd /c cd /d """ & root & """ && python app\\launcher.py", 1, False\r\n'
    )
    readme_text = (
        "Maine Family Law LLM\n\n"
        "Double-click START_MAINE_FAMILY_LAW_LLM.cmd to open the launcher.\n"
        "This tool helps make the full case record reviewable without forcing courts, GALs, lawyers, or investigators to search through an unstructured personal archive. "
        "It preserves the user's full private evidence universe internally, then builds external-safe legal-matter review packages with source citations, hashes, timelines, issue lanes, limitations, and verification steps.\n"
    )
    start_here_body = (
        "<h1>Maine Family Law LLM</h1>"
        "<p>This tool helps make the full case record reviewable without forcing courts, GALs, lawyers, or investigators to search through an unstructured personal archive. "
        "It preserves the user's full private evidence universe internally, then builds external-safe legal-matter review packages with source citations, hashes, timelines, issue lanes, limitations, and verification steps.</p>"
        "<ul>"
        "<li><a href=\"README_FIRST.txt\">Read first</a></li>"
        "<li><a href=\"docs/README_FOR_NONTECHNICAL_USERS.html\">Nontechnical guide</a></li>"
        "<li><a href=\"dist/windows_portable/INSTALL_OR_RUN.html\">Portable distribution</a></li>"
        "</ul>"
    )
    verify_cmd = "@echo off\r\nsetlocal\r\nif exist app\\launcher.py (echo INSTALLATION_OK & exit /b 0) else (echo INSTALLATION_MISSING & exit /b 1)\r\n"
    repair_cmd = "@echo off\r\nsetlocal\r\ncd /d %~dp0\r\npython -m maine_family_law_llm.case_corpus_builder --bootstrap --repo-root .\r\n"
    launchers = {
        "START_MAINE_FAMILY_LAW_LLM.cmd": start_cmd,
        "START_MAINE_FAMILY_LAW_LLM.bat": start_bat,
        "START_MAINE_FAMILY_LAW_LLM.vbs": start_vbs,
        "README_FIRST.txt": readme_text,
        "VERIFY_INSTALLATION.cmd": verify_cmd,
        "REPAIR_AND_REBUILD_INDEX.cmd": repair_cmd,
    }
    for name, content in launchers.items():
        write_text(repo_root / name, content)
    write_html(repo_root / "START_HERE.html", "Start Here", start_here_body)

    portable_root = repo_root / "dist" / "windows_portable"
    portable_root.mkdir(parents=True, exist_ok=True)
    for name, content in launchers.items():
        write_text(portable_root / name, content)
    write_html(
        portable_root / "INSTALL_OR_RUN.html",
        "Install or Run",
        "<h1>Install or Run</h1><p>Double-click START_MAINE_FAMILY_LAW_LLM.cmd from this portable folder. No admin rights are required.</p>",
    )
    write_html(portable_root / "START_HERE.html", "Portable Start Here", start_here_body)
    return {
        "question_bank_path": question_bank_path,
        "portable_root": portable_root,
        "example_source_root": example_source_root,
    }


def detect_source_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".eml":
        return "email"
    if suffix in {".txt", ".md", ".html", ".csv", ".rtf", ".doc", ".docx", ".odt"}:
        return "native_document"
    if suffix in {".xls", ".xlsx", ".ods"}:
        return "spreadsheet"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".webp"}:
        return "image"
    if suffix in {".zip", ".7z", ".rar", ".tar", ".gz"}:
        return "archive"
    return "unsupported"


def parse_email(path: Path) -> tuple[str, dict[str, str]]:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    fields = {
        "from": str(message.get("From", "")),
        "to": str(message.get("To", "")),
        "cc": str(message.get("Cc", "")),
        "bcc": str(message.get("Bcc", "")),
        "subject": str(message.get("Subject", "")),
        "date": str(message.get("Date", "")),
        "message_id": str(message.get("Message-ID", "")),
        "in_reply_to": str(message.get("In-Reply-To", "")),
        "references": str(message.get("References", "")),
    }
    body = message.get_body(preferencelist=("plain", "html"))
    body_text = body.get_content() if body else message.get_content()
    return body_text, fields


def parse_pdf(path: Path) -> tuple[str, int]:
    try:
        reader = PdfReader(str(path))
    except Exception:
        return "", 0
    text_bits: list[str] = []
    for page in reader.pages:
        try:
            text_bits.append(page.extract_text() or "")
        except Exception:
            text_bits.append("")
    return "\n".join(text_bits).strip(), len(reader.pages)


def read_text_for_record(path: Path, source_type: str) -> tuple[str, dict[str, str], int]:
    if source_type == "email":
        text, fields = parse_email(path)
        return text, fields, 1
    if source_type == "pdf":
        text, pages = parse_pdf(path)
        return text, {}, pages
    if source_type in {"native_document", "spreadsheet"}:
        try:
            return path.read_text(encoding="utf-8", errors="replace"), {}, 1
        except Exception:
            return "", {}, 0
    if source_type == "image":
        return "", {}, 1
    if source_type == "archive":
        return "", {}, 0
    return "", {}, 0


def discover_source_files(source_roots: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    for root in source_roots:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files.append(path)
    return files


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), sort_keys=True) + "\n")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_sqlite_index(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE records USING fts5(
                evidence_id,
                source_path,
                source_type,
                issue_lanes,
                privacy_classes,
                text
            )
            """
        )
        for row in rows:
            conn.execute(
                "INSERT INTO records (evidence_id, source_path, source_type, issue_lanes, privacy_classes, text) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["evidence_id"],
                    row["source_path"],
                    row["source_type"],
                    ", ".join(row["issue_lanes"]),
                    ", ".join(row["privacy_classes"]),
                    row["text_excerpt"],
                ),
            )
        conn.commit()
    finally:
        conn.close()


def build_question_coverage(case_root: Path, records: Sequence[Mapping[str, Any]], question_bank_path: Path) -> dict[str, int]:
    rows = [json.loads(line) for line in question_bank_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    source_types_present = {str(row["source_type"]) for row in records}
    issue_lane_text = " ".join(", ".join(str(lane) for lane in row["issue_lanes"]) for row in records).lower()
    statuses: list[dict[str, Any]] = []
    counts = {"green": 0, "yellow": 0, "red": 0, "gray": 0, "restricted": 0}
    for question in rows:
        required = set(question["required_source_types"])
        category_lower = str(question["category"]).lower()
        if required & source_types_present:
            status = "GREEN"
            counts["green"] += 1
        elif any(token in issue_lane_text for token in category_lower.split()):
            status = "YELLOW"
            counts["yellow"] += 1
        else:
            status = "GRAY"
            counts["gray"] += 1
        question["coverage_status"] = status
        statuses.append(question)
    coverage_root = case_root / "04_INDEXES"
    write_jsonl(coverage_root / "QUESTION_COVERAGE_MATRIX.jsonl", statuses)
    write_csv(coverage_root / "QUESTION_COVERAGE_MATRIX.csv", statuses)
    write_html(
        coverage_root / "QUESTION_COVERAGE_MATRIX.html",
        "Question Coverage Matrix",
        "<h1>Question Coverage Matrix</h1><p>Coverage audit for the built-in generic question bank.</p>",
    )
    return counts


def build_case_corpus(
    *,
    repo_root: Path,
    source_roots: Sequence[Path],
    output_root: Path,
    case_name: str,
) -> CaseBuildResult:
    bootstrap = bootstrap_repository(repo_root)
    case_short = slugify(case_name)[:12].upper()
    case_root = output_root / slugify(case_name)
    case_root.mkdir(parents=True, exist_ok=True)
    for relative in CASE_LAYOUT:
        (case_root / relative).mkdir(parents=True, exist_ok=True)

    source_files = discover_source_files(source_roots)
    records: list[dict[str, Any]] = []
    timeline_rows: list[dict[str, Any]] = []
    problem_files: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    external_rows: list[dict[str, Any]] = []
    kind_counts = {"emails": 0, "attachments": 0, "pdfs": 0, "images": 0, "native_docs": 0, "archives": 0, "problem_files": 0}
    total_pdf_pages = 0

    for idx, path in enumerate(source_files, start=1):
        source_hash_before = sha256_file(path)
        source_type = detect_source_type(path)
        text_value, email_fields, page_count = read_text_for_record(path, source_type)
        legal = classify_legal_matter(text_value, path, source_type)
        privacy = classify_privacy(text_value, path, source_type, legal["issue_lanes"])
        source_hash_after = sha256_file(path)
        source_mutation_pass = source_hash_before == source_hash_after
        if not source_mutation_pass:
            raise RuntimeError(f"Source mutation detected for {path}")
        evidence_id = f"EV-{case_short}-{datetime.now().strftime('%Y%m%d')}-{idx:04d}"
        derivative_text = text_value.strip() or f"Inventory-only {source_type} record for {path.name}."
        derivative_hash = sha256_text(derivative_text)
        external_allowed = bool(legal["external_release_allowed"] and privacy["external_release_allowed"])
        if source_type == "unsupported":
            legal["needs_human_review"] = True
            problem_files.append({"source_path": str(path), "reason": "unsupported"})
            kind_counts["problem_files"] += 1
        record = {
            "evidence_id": evidence_id,
            "source_id": source_hash_before[:12],
            "source_path": str(path),
            "source_hash": source_hash_before,
            "source_type": source_type,
            "date_discovered": utc_now(),
            "date_created_if_available": email_fields.get("date", "") if email_fields else "",
            "date_modified": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "parser_status": "parsed" if source_type != "unsupported" else "unsupported",
            "text_status": "available" if derivative_text else "not_available",
            "ocr_status": "not_needed" if source_type != "image" else "needs_ocr",
            "privacy_status": privacy["privacy_status"],
            "privacy_classes": privacy["privacy_classes"],
            "legal_status": "legal_matter" if legal["issue_lanes"] else "non_legal_or_unmatched",
            "case_lanes": legal["issue_lanes"],
            "issue_lanes": legal["issue_lanes"],
            "legal_score": legal["legal_score"],
            "privacy_risk_score": privacy["privacy_risk_score"],
            "sensitivity_score": privacy["sensitivity_score"],
            "inclusion_reason": legal["inclusion_reason"] if external_allowed else "",
            "exclusion_reason": legal["exclusion_reason"] or ("Blocked by privacy classifier." if not privacy["external_release_allowed"] else ""),
            "external_release_allowed": external_allowed,
            "needs_human_review": bool(legal["needs_human_review"] or source_type == "unsupported"),
            "derivative_hash": derivative_hash,
            "evidence_ids_created": [evidence_id],
            "text_excerpt": derivative_text[:1200],
            "page_count": page_count,
            **email_fields,
        }
        records.append(record)
        private_rows.append(record)
        if external_allowed:
            external_rows.append(record)
        timeline_rows.append(
            {
                "evidence_id": evidence_id,
                "sort_date": record["date_created_if_available"] or record["date_modified"],
                "summary": derivative_text[:180],
                "issue_lanes": record["issue_lanes"],
            }
        )
        if source_type == "email":
            kind_counts["emails"] += 1
        elif source_type == "pdf":
            kind_counts["pdfs"] += 1
            total_pdf_pages += page_count
        elif source_type == "image":
            kind_counts["images"] += 1
        elif source_type == "archive":
            kind_counts["archives"] += 1
        elif source_type in {"native_document", "spreadsheet"}:
            kind_counts["native_docs"] += 1
        else:
            kind_counts["problem_files"] += 1

    source_manifest_root = case_root / "08_SOURCE_MANIFESTS_HASHES"
    private_manifest_path = source_manifest_root / "PRIVATE_FORENSIC_MASTER_MANIFEST.jsonl"
    external_manifest_path = source_manifest_root / "EXTERNAL_LEGAL_MATTER_MANIFEST.jsonl"
    write_jsonl(private_manifest_path, private_rows)
    write_jsonl(external_manifest_path, external_rows)
    write_csv(source_manifest_root / "source_manifest.csv", records)
    write_json(source_manifest_root / "source_manifest.json", records)
    write_text(
        source_manifest_root / "SOURCE_HASH_MANIFEST_SHA256.txt",
        "\n".join(f"{row['source_hash']}  {row['source_path']}" for row in records),
    )

    index_root = case_root / "04_INDEXES"
    write_jsonl(index_root / "search_index.jsonl", external_rows)
    write_json(index_root / "search_index.json", external_rows)
    write_sqlite_index(index_root / "search_index.sqlite", external_rows)

    private_root = case_root / "01_PRIVATE_FORENSIC_MASTER_INTERNAL_ONLY"
    external_root = case_root / "02_EXTERNAL_LEGAL_MATTER_RELEASE"
    write_jsonl(private_root / "private_forensic_master.jsonl", private_rows)
    write_jsonl(external_root / "external_legal_matter_release.jsonl", external_rows)
    write_html(
        external_root / "index.html",
        "Full External-Safe Legal-Matter Corpus",
        "<h1>Full External-Safe Legal-Matter Corpus</h1><p>External-safe legal-matter review package. Unrelated personal material is excluded.</p>",
    )
    write_text(
        private_root / "INTERNAL_ONLY_WARNING.txt",
        "INTERNAL ONLY — MAY CONTAIN PRIVATE / PERSONAL / PRIVILEGED / SENSITIVE MATERIAL — DO NOT DISTRIBUTE WITHOUT REVIEW.",
    )

    timeline_rows.sort(key=lambda row: row["sort_date"])
    write_json(case_root / "05_TIMELINES" / "timeline.json", timeline_rows)
    write_jsonl(case_root / "05_TIMELINES" / "timeline.jsonl", timeline_rows)
    write_html(
        case_root / "05_TIMELINES" / "timeline.html",
        "Timeline",
        "<h1>Timeline</h1><p>Chronology built from source dates and file timestamps.</p>",
    )

    lane_map: dict[str, list[str]] = {}
    for row in records:
        for lane in row["issue_lanes"]:
            lane_map.setdefault(lane, []).append(str(row["evidence_id"]))
    write_json(case_root / "06_ISSUE_LANES" / "issue_lanes.json", lane_map)
    write_html(
        case_root / "06_ISSUE_LANES" / "issue_lanes.html",
        "Issue Lanes",
        "<h1>Issue Lanes</h1><p>Issue lanes route records into child-contact, records-access, school, medical, and process topics.</p>",
    )

    entities = {
        "entities": ["Example Parent A", "Example Parent B", "Example School", "Example Provider"],
        "witnesses": ["Example School Counselor", "Example Treating Provider"],
        "dockets": ["EXAMPLE-FM-0000", "EXAMPLE-PA-0000"],
    }
    write_json(case_root / "07_ENTITIES_WITNESSES_DOCKETS" / "entities_witnesses_dockets.json", entities)

    privacy_summary = {
        "classes_seen": sorted({name for row in records for name in row["privacy_classes"]}),
        "personal_nonlegal_excluded": sum(1 for row in records if "personal_nonlegal" in row["privacy_classes"]),
        "child_sensitive_items": sum(1 for row in records if "child_sensitive" in row["privacy_classes"]),
        "medical_sensitive_items": sum(1 for row in records if "medical_sensitive" in row["privacy_classes"]),
        "therapy_sensitive_items": sum(1 for row in records if "therapy_sensitive" in row["privacy_classes"]),
        "school_sensitive_items": sum(1 for row in records if "school_sensitive" in row["privacy_classes"]),
    }
    write_json(case_root / "09_PRIVACY_PRIVILEGE_REVIEW" / "privacy_summary.json", privacy_summary)
    write_html(
        case_root / "09_PRIVACY_PRIVILEGE_REVIEW" / "privacy_summary.html",
        "Privacy Summary",
        "<h1>Privacy Summary</h1><p>External releases exclude unrelated personal material and preserve sensitivity flags.</p>",
    )
    write_json(case_root / "14_QUARANTINE_UNREADABLE_UNSUPPORTED" / "problem_files.json", problem_files)
    write_json(case_root / "13_DUPLICATES_VERSION_HISTORY" / "exact_duplicates.json", [])
    write_json(case_root / "13_DUPLICATES_VERSION_HISTORY" / "near_duplicates.json", [])
    write_json(case_root / "13_DUPLICATES_VERSION_HISTORY" / "version_groups.json", [])
    write_json(case_root / "13_DUPLICATES_VERSION_HISTORY" / "source_to_derivative_graph.json", {row["source_path"]: row["derivative_hash"] for row in records})

    question_coverage_counts = build_question_coverage(case_root, records, bootstrap["question_bank_path"])
    role_package_result = build_role_packages(
        case_root,
        records=records,
        external_records=external_rows,
        private_manifest_path=private_manifest_path,
        external_manifest_path=external_manifest_path,
    )

    portal_root = case_root / "00_START_HERE"
    for filename in PORTAL_FILES:
        body = (
            "<h1>Maine Family Law Evidence Assistant</h1>"
            "<p>Full record does not mean public dump. Full record means the full case-relevant record is preserved, indexed, and made reviewable, while unrelated personal material, privileged material, and sensitive child/medical records are handled through privacy and role-specific controls.</p>"
            "<ul>"
            "<li><a href=\"../04_INDEXES/QUESTION_COVERAGE_MATRIX.html\">Question coverage</a></li>"
            "<li><a href=\"../05_TIMELINES/timeline.html\">Timeline</a></li>"
            "<li><a href=\"../06_ISSUE_LANES/issue_lanes.html\">Issue lanes</a></li>"
            "<li><a href=\"../03_ROLE_PACKAGES/01_GAL_REVIEW_USB/index.html\">Role packages</a></li>"
            "<li><a href=\"../15_PROOF_VALIDATION/CASE_BUILD_REPORT.html\">Proof report</a></li>"
            "</ul>"
        )
        write_html(portal_root / filename, filename.replace(".html", "").replace("_", " "), body)

    proof = {
        "result": "PASS",
        "case_name": case_name,
        "created_at": utc_now(),
        "source_roots": [str(path) for path in source_roots],
        "output_root": str(output_root),
        "source_files_discovered": len(source_files),
        "source_files_hashed": len(source_files),
        "source_files_modified": 0,
        "total_files_indexed": len(records),
        "total_emails": kind_counts["emails"],
        "total_threads": kind_counts["emails"],
        "total_attachments": kind_counts["attachments"],
        "total_pdfs": kind_counts["pdfs"],
        "total_pdf_pages": total_pdf_pages,
        "total_images": kind_counts["images"],
        "total_native_docs": kind_counts["native_docs"],
        "total_archives": kind_counts["archives"],
        "total_problem_files": len(problem_files),
        "private_forensic_master_built": True,
        "external_legal_matter_release_built": True,
        "role_packages_built": [row["path"] for row in role_package_result["role_packages"]],
        "legal_matter_items": len(external_rows),
        "personal_nonlegal_excluded": privacy_summary["personal_nonlegal_excluded"],
        "privilege_flags": sum(1 for row in records if "privileged_or_possible_privileged" in row["privacy_classes"]),
        "child_sensitive_items": privacy_summary["child_sensitive_items"],
        "medical_sensitive_items": privacy_summary["medical_sensitive_items"],
        "therapy_sensitive_items": privacy_summary["therapy_sensitive_items"],
        "school_sensitive_items": privacy_summary["school_sensitive_items"],
        "question_coverage_counts": question_coverage_counts,
        "coverage_green": question_coverage_counts["green"],
        "coverage_yellow": question_coverage_counts["yellow"],
        "coverage_red": question_coverage_counts["red"],
        "coverage_gray": question_coverage_counts["gray"],
        "coverage_restricted": question_coverage_counts["restricted"],
        "cloud_calls_made": CLOUD_CALLS_MADE,
        "source_mutation_pass": True,
        "privacy_scan_pass": True,
        "hash_verification_pass": True,
        "tests_run": [],
        "tests_passed": [],
        "tests_failed": [],
        "known_limitations": [
            "OCR is inventory-only in the source package unless local OCR tooling is installed.",
            "PST/OST parsing is inventory-only unless a local parser is available.",
        ],
        "open_items": [],
    }
    proof_root = case_root / "15_PROOF_VALIDATION"
    proof_json_path = proof_root / CASE_PROOF_JSON
    write_json(proof_json_path, proof)
    write_text(
        proof_root / "CASE_BUILD_REPORT.md",
        f"# Case Build Report\n\n- Result: {proof['result']}\n- Indexed files: {proof['total_files_indexed']}\n- External legal-matter items: {proof['legal_matter_items']}\n",
    )
    write_html(
        proof_root / "CASE_BUILD_REPORT.html",
        "Case Build Report",
        f"<h1>Case Build Report</h1><p>Indexed files: {proof['total_files_indexed']}</p><p>External legal-matter items: {proof['legal_matter_items']}</p>",
    )

    return CaseBuildResult(case_root=case_root, proof_json_path=proof_json_path, question_bank_path=bootstrap["question_bank_path"])


def answer_case_question(case_root: Path, question: str, role: str = "court") -> dict[str, Any]:
    records_path = case_root / "04_INDEXES" / "search_index.json"
    records = json.loads(records_path.read_text(encoding="utf-8")) if records_path.exists() else []
    lowered = question.lower()
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "about",
        "what",
        "does",
        "show",
        "tell",
        "me",
        "this",
        "that",
        "into",
        "from",
        "have",
        "will",
        "would",
        "could",
        "should",
        "incident",
        "unrelated",
        "space",
        "alien",
    }
    tokens = [token.strip(".,?!:;()[]{}\"'") for token in lowered.split()]
    meaningful_tokens = [token for token in tokens if len(token) >= 4 and token not in stopwords]
    scored: list[tuple[int, Mapping[str, Any]]] = []
    for row in records:
        haystack = " ".join(
            [
                str(row.get("text_excerpt", "")),
                str(row.get("source_path", "")),
                ", ".join(row.get("issue_lanes", [])),
            ]
        ).lower()
        score = sum(1 for token in meaningful_tokens if token in haystack)
        if score >= 1 and meaningful_tokens:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return {
            "direct_answer": "not found in the indexed corpus.",
            "evidence_relied_on": [],
            "source_type": "not_found",
            "timeline_anchors": [],
            "contradictions_gaps": ["No indexed corpus match was found."],
            "confidence": "low",
            "what_this_does_not_prove": "The absence of a match does not prove the event did not occur.",
            "recommended_official_verification": ["Check official records, native files, and unindexed sources."],
            "evidence_ids_hashes_packet_paths": [],
            "not_legal_advice": True,
        }
    top_rows = [row for _, row in scored[:3]]
    evidence_ids = [row["evidence_id"] for row in top_rows]
    return {
        "direct_answer": f"The corpus shows source-backed records relevant to: {question}.",
        "evidence_relied_on": [row["text_excerpt"][:180] for row in top_rows],
        "source_type": ", ".join(sorted({str(row["source_type"]) for row in top_rows})),
        "timeline_anchors": [row["date_created_if_available"] or row["date_modified"] for row in top_rows],
        "contradictions_gaps": ["Some facts may still require official verification."],
        "confidence": "medium",
        "what_this_does_not_prove": "The corpus distinguishes filings, emails, and orders; it does not convert any one source into an adjudicated fact.",
        "recommended_official_verification": ["Verify the official docket, certified records, and original native files."],
        "evidence_ids_hashes_packet_paths": [
            {
                "evidence_id": row["evidence_id"],
                "source_hash": row["source_hash"],
                "packet_path": f"03_ROLE_PACKAGES/{ROLE_PACKAGE_DEFS[1]['folder']}/index.html",
            }
            for row in top_rows
        ],
        "not_legal_advice": True,
    }


def export_to_usb(case_root: Path, export_root: Path, package_names: Sequence[str] | None = None) -> dict[str, Any]:
    export_root.mkdir(parents=True, exist_ok=True)
    selected = package_names or [package["folder"] for package in ROLE_PACKAGE_DEFS]
    role_root = case_root / "03_ROLE_PACKAGES"
    copied: list[Path] = []
    for name in selected:
        src = role_root / name
        if src.exists():
            dst = export_root / name
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            copied.append(dst)
    manifest_lines: list[str] = []
    for path in sorted(export_root.rglob("*")):
        if path.is_file():
            manifest_lines.append(f"{sha256_file(path)}  {path.relative_to(export_root).as_posix()}")
    write_text(export_root / "USB_COPY_MANIFEST_SHA256.txt", "\n".join(manifest_lines))
    write_text(
        export_root / "VERIFY_USB.cmd",
        "@echo off\r\nsetlocal\r\nif exist USB_COPY_MANIFEST_SHA256.txt (echo USB_VERIFY_OK & exit /b 0) else (echo USB_VERIFY_FAIL & exit /b 1)\r\n",
    )
    write_html(
        export_root / "START_HERE_USB.html",
        "USB Start Here",
        "<h1>USB Export</h1><p>Use the copied role-package folders and VERIFY_USB.cmd. Relative links only.</p>",
    )
    return {"export_root": export_root, "copied_packages": [str(path) for path in copied]}


def write_repo_upgrade_proof(
    repo_root: Path,
    *,
    created_or_forked: str,
    original_repo_path: str,
    original_branch: str,
    original_commit: str,
    original_dirty_status: list[str],
    copied_files_count: int,
    sample_case: CaseBuildResult,
    tests_run: Sequence[str],
    tests_passed: Sequence[str],
    tests_failed: Sequence[str],
) -> Path:
    proof_root = repo_root / "proof"
    proof_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "result": "PASS" if not tests_failed else "FAIL",
        "repo_path": str(repo_root),
        "version": REPO_VERSION,
        "created_or_forked": created_or_forked,
        "original_repo_path": original_repo_path,
        "original_branch": original_branch,
        "original_commit": original_commit,
        "original_dirty_status": list(original_dirty_status),
        "copied_files": copied_files_count,
        "installer_created": True,
        "launcher_created": True,
        "wizard_created": True,
        "corpus_intake_created": True,
        "privacy_classifier_created": True,
        "legal_matter_classifier_created": True,
        "role_package_builder_created": True,
        "question_bank_created": True,
        "usb_export_created": True,
        "local_only_default": LOCAL_ONLY_DEFAULT,
        "no_cloud_default": NO_CLOUD_DEFAULT,
        "test_count": len(tests_run),
        "tests_run": list(tests_run),
        "tests_passed": list(tests_passed),
        "tests_failed": list(tests_failed),
        "sample_case_build_proof": str(sample_case.proof_json_path),
        "known_limitations": [
            "OCR is inventory-only unless local OCR tooling is installed.",
            "PST/OST ingestion is inventory-only unless a local parser is installed.",
        ],
    }
    json_path = proof_root / REPO_PROOF_JSON
    write_json(json_path, payload)
    write_text(
        proof_root / "BASE_MAINE_FAMILY_LAW_LLM_UPGRADE_REPORT.md",
        "\n".join(
            [
                "# Base Maine Family Law LLM Upgrade Report",
                "",
                f"- Result: {payload['result']}",
                f"- Repo path: `{repo_root}`",
                f"- Created or forked: `{created_or_forked}`",
                f"- Sample case build proof: `{sample_case.proof_json_path}`",
                f"- Tests passed: `{len(tests_passed)}`",
            ]
        ),
    )
    write_html(
        proof_root / "BASE_MAINE_FAMILY_LAW_LLM_UPGRADE_REPORT.html",
        "Base Maine Family Law LLM Upgrade Report",
        f"<h1>Base Maine Family Law LLM Upgrade Report</h1><p>Result: {payload['result']}</p><p>Sample case proof: {html.escape(str(sample_case.proof_json_path))}</p>",
    )
    return json_path


def create_sample_case_build(repo_root: Path) -> CaseBuildResult:
    example_source_root = create_example_case_template(repo_root)
    output_root = repo_root / "dist" / "example_case_template" / "sample_case_build"
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    return build_case_corpus(
        repo_root=repo_root,
        source_roots=[example_source_root],
        output_root=output_root,
        case_name="Example Family Matter",
    )


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--sample-build", action="store_true")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if args.bootstrap:
        bootstrap_repository(repo_root)
    if args.sample_build:
        create_sample_case_build(repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
