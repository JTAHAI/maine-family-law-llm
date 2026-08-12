from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any, Mapping, Sequence


ROLE_PACKAGE_DEFS: tuple[dict[str, str], ...] = (
    {
        "folder": "01_GAL_REVIEW_USB",
        "title": "GAL Review Package",
        "description": "Child-focused review with contact, school, medical, and counseling context.",
    },
    {
        "folder": "02_COURT_REVIEW_USB",
        "title": "Court Review Package",
        "description": "Orders, filings, docket, service, and source-navigation materials.",
    },
    {
        "folder": "03_LAWYER_INTAKE_USB",
        "title": "Lawyer Intake Package",
        "description": "10-minute overview, issue map, top exhibits, and missing-record list.",
    },
    {
        "folder": "04_ADA_PROSECUTOR_CONTEXT_USB",
        "title": "ADA / Prosecutor / Investigator Package",
        "description": "Neutral criminal-context review with communications scope and official-verification list.",
    },
    {
        "folder": "05_FULL_EXTERNAL_SAFE_LEGAL_MATTER_USB",
        "title": "Full External-Safe Legal-Matter Package",
        "description": "Everything case-relevant and privacy-cleared for external review.",
    },
    {
        "folder": "06_PRIVATE_FORENSIC_MASTER_INTERNAL_ONLY_USB",
        "title": "Private Forensic Master Internal Only",
        "description": "Internal-only full evidence universe with privacy and privilege flags.",
    },
)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_html(path: Path, title: str, body_html: str) -> None:
    _write_text(
        path,
        "\n".join(
            [
                "<!doctype html>",
                "<html lang=\"en\">",
                "<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>"
                + html.escape(title)
                + "</title></head>",
                "<body><main>",
                body_html,
                "</main></body></html>",
            ]
        ),
    )


def _relative_href(from_path: Path, to_path: Path) -> str:
    return os.path.relpath(to_path, start=from_path.parent).replace("\\", "/")


def build_role_packages(
    case_root: Path,
    *,
    records: Sequence[Mapping[str, Any]],
    external_records: Sequence[Mapping[str, Any]],
    private_manifest_path: Path,
    external_manifest_path: Path,
) -> dict[str, Any]:
    role_root = case_root / "03_ROLE_PACKAGES"
    role_root.mkdir(parents=True, exist_ok=True)
    built: list[dict[str, str]] = []
    for package in ROLE_PACKAGE_DEFS:
        package_root = role_root / package["folder"]
        package_root.mkdir(parents=True, exist_ok=True)
        title = package["title"]
        package_records = external_records
        if package["folder"].startswith("06_"):
            package_records = records
        package_page = package_root / "index.html"
        evidence_ids = [str(row["evidence_id"]) for row in package_records[:25]]
        linked_rows = []
        for row in package_records[:30]:
            detail_relpath = str(row.get("detail_page_relpath", ""))
            detail_href = _relative_href(package_page, case_root / detail_relpath) if detail_relpath else ""
            file_relpath = str(row.get("external_copy_relpath") or row.get("private_copy_relpath") or "")
            file_href = _relative_href(package_page, case_root / file_relpath) if file_relpath else ""
            linked_rows.append(
                {
                    "evidence_id": str(row.get("evidence_id", "")),
                    "title": str(row.get("subject") or row.get("title") or row.get("evidence_id", "")),
                    "date": str(row.get("date_created_if_available") or row.get("date_modified") or ""),
                    "issue_lanes": ", ".join(row.get("issue_lanes", [])) or "none tagged",
                    "detail_href": detail_href,
                    "file_href": file_href,
                }
            )
        _write_text(
            package_root / "README.txt",
            "\n".join(
                [
                    title,
                    package["description"],
                    "",
                    "This package is source-bound and review-required.",
                    f"Evidence examples: {', '.join(evidence_ids[:8]) if evidence_ids else 'No records yet.'}",
                ]
            ),
        )
        _write_html(
            package_page,
            title,
            "\n".join(
                [
                    f"<h1>{html.escape(title)}</h1>",
                    f"<p>{html.escape(package['description'])}</p>",
                    "<p>This package is for evidence navigation, source review, and role-specific review.</p>",
                    "<p><a href=\""
                    + html.escape(_relative_href(package_page, case_root / "00_START_HERE" / "search.html"))
                    + "\">Open search portal</a> · <a href=\""
                    + html.escape(_relative_href(package_page, case_root / "15_PROOF_VALIDATION" / "CASE_BUILD_REPORT.html"))
                    + "\">Open proof report</a></p>",
                    "<ul>",
                    *[
                        (
                            "<li>"
                            + (
                                f"<a href=\"{html.escape(row['detail_href'])}\">{html.escape(row['title'])}</a>"
                                if row["detail_href"]
                                else f"<code>{html.escape(row['evidence_id'])}</code>"
                            )
                            + f" <small>{html.escape(row['date'])}</small> · {html.escape(row['issue_lanes'])}"
                            + (
                                f" · <a href=\"{html.escape(row['file_href'])}\">open file</a>"
                                if row["file_href"]
                                else ""
                            )
                            + "</li>"
                        )
                        for row in linked_rows[:12]
                    ],
                    "</ul>",
                ]
            ),
        )
        if package["folder"].startswith("01_"):
            _write_html(
                package_root / "child_focused_index.html",
                "GAL child-focused index",
                "<h1>Child-Focused Index</h1><p>Child stability, contact implementation, school, medical, and counseling sources.</p>",
            )
        if package["folder"].startswith("02_"):
            _write_html(
                package_root / "docket_filing_service_index.html",
                "Court docket / filing / service index",
                "<h1>Court Docket / Filing / Service Index</h1><p>Prepared, served, submitted, accepted, entered, rejected, and ruled-on status lines.</p>",
            )
        if package["folder"].startswith("03_"):
            _write_html(
                package_root / "10_minute_case_overview.html",
                "10-minute case overview",
                "<h1>10-Minute Case Overview</h1><p>Issue map, urgent deadlines, top exhibits, missing records, and next review steps.</p>",
            )
        if package["folder"].startswith("04_"):
            _write_html(
                package_root / "context_and_verification.html",
                "ADA / Prosecutor context and verification list",
                "\n".join(
                    [
                        "<h1>Context and Verification</h1>",
                        "<p>This package is source-bound, neutral, and not a personal attack packet.</p>",
                        "<ul>",
                        "<li>Check official criminal docket and conditions.</li>",
                        "<li>Verify family/PFA overlap and communications scope.</li>",
                        "<li>Review possible exculpatory or context-bearing records.</li>",
                        "</ul>",
                    ]
                ),
            )
        if package["folder"].startswith("05_"):
            _write_text(package_root / "external_release_manifest.txt", str(external_manifest_path))
        if package["folder"].startswith("06_"):
            _write_text(
                package_root / "INTERNAL_ONLY_WARNING.txt",
                "INTERNAL ONLY — MAY CONTAIN PRIVATE / PERSONAL / PRIVILEGED / SENSITIVE MATERIAL — DO NOT DISTRIBUTE WITHOUT REVIEW.",
            )
            _write_text(package_root / "private_master_manifest.txt", str(private_manifest_path))
        built.append({"title": title, "path": str(package_root)})

    return {"role_packages": built, "root": str(role_root)}
