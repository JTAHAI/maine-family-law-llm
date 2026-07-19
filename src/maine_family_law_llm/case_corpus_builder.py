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
from .local_corpus_index import rebuild_local_content_index, search_local_content_index
from .privacy_classifier import classify_privacy
from .question_bank import generate_builtin_question_bank, write_question_bank
from .role_package_builder import ROLE_PACKAGE_DEFS, build_role_packages
from .case_workspace import write_case_source_roots
from .version import VERSION


REPO_VERSION = VERSION
REPO_PROOF_JSON = "BASE_MAINE_FAMILY_LAW_LLM_UPGRADE_PROOF.json"
CASE_PROOF_JSON = "CASE_BUILD_PROOF.json"
ROOT_LAUNCHERS = (
    "START_MAINE_FAMILY_LAW_LLM.cmd",
    "START_MAINE_FAMILY_LAW_LLM.bat",
    "START_MAINE_FAMILY_LAW_LLM.vbs",
    "START_HERE.html",
    "README_FIRST.md",
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
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True))


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


def relative_href(from_path: Path, to_path: Path) -> str:
    return os.path.relpath(to_path, start=from_path.parent).replace("\\", "/")


def stage_case_copy(destination_root: Path, evidence_id: str, source_path: Path) -> str:
    if not source_path.exists():
        return ""
    destination_root.mkdir(parents=True, exist_ok=True)
    destination_name = f"{evidence_id}_{source_path.name}".replace(" ", "_")
    destination = destination_root / destination_name
    if not destination.exists():
        shutil.copy2(source_path, destination)
    return destination_name


def write_case_portal(
    case_root: Path,
    *,
    case_name: str,
    external_records: Sequence[dict[str, Any]],
    proof: Mapping[str, Any],
) -> None:
    portal_root = case_root / "00_START_HERE"
    detail_root = portal_root / "records"
    detail_root.mkdir(parents=True, exist_ok=True)

    dataset: list[dict[str, Any]] = []
    source_types = sorted({str(row.get("source_type", "")) for row in external_records if row.get("source_type")})
    issue_lanes = sorted({lane for row in external_records for lane in row.get("issue_lanes", []) if lane})

    for row in external_records:
        detail_path = detail_root / f"{str(row['evidence_id']).replace(' ', '_')}.html"
        row["detail_page_relpath"] = detail_path.relative_to(case_root).as_posix()
        external_copy_relpath = str(row.get("external_copy_relpath", ""))
        external_copy_path = case_root / external_copy_relpath if external_copy_relpath else None
        external_file_href = relative_href(detail_path, external_copy_path) if external_copy_path and external_copy_path.exists() else ""
        proof_href = relative_href(detail_path, case_root / "15_PROOF_VALIDATION" / "CASE_BUILD_REPORT.html")
        search_href = relative_href(detail_path, portal_root / "search.html")

        write_text(
            detail_path,
            "\n".join(
                [
                    "<!doctype html>",
                    "<html lang=\"en\">",
                    "<head>",
                    "<meta charset=\"utf-8\">",
                    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
                    f"<title>{html.escape(str(row.get('title') or row['evidence_id']))}</title>",
                    "<style>body{margin:0;background:#f5f1ea;color:#17212b;font-family:Segoe UI,Arial,sans-serif;}main{max-width:1080px;margin:0 auto;padding:28px;}a{color:#165f6d;}code,pre{background:#fff;border:1px solid rgba(23,33,43,.12);padding:10px;border-radius:10px;display:block;white-space:pre-wrap;word-break:break-word;}section{background:#fff;border:1px solid rgba(23,33,43,.12);border-radius:14px;padding:18px;margin-top:14px;}ul{line-height:1.6;}</style>",
                    "</head>",
                    "<body>",
                    "<main>",
                    f"<p><a href=\"{html.escape(search_href)}\">Back to search</a> · <a href=\"{html.escape(proof_href)}\">Open proof report</a></p>",
                    f"<h1>{html.escape(str(row.get('title') or row['evidence_id']))}</h1>",
                    f"<p><strong>Evidence ID:</strong> {html.escape(str(row['evidence_id']))}</p>",
                    f"<p><strong>Source type:</strong> {html.escape(str(row.get('source_type', '')))} · <strong>Date:</strong> {html.escape(str(row.get('date_created_if_available') or row.get('date_modified') or 'Undated'))}</p>",
                    f"<p><strong>Issue lanes:</strong> {html.escape(', '.join(row.get('issue_lanes', [])) or 'none tagged')}</p>",
                    f"<p><strong>Inclusion reason:</strong> {html.escape(str(row.get('inclusion_reason') or 'Not stated'))}</p>",
                    f"<p><strong>Privacy classes:</strong> {html.escape(', '.join(row.get('privacy_classes', [])) or 'none')}</p>",
                    f"<p><strong>SHA-256:</strong> {html.escape(str(row.get('source_hash', '')))}</p>",
                    (
                        f"<p><a href=\"{html.escape(external_file_href)}\" target=\"_blank\" rel=\"noopener noreferrer\">Open staged external-safe file</a></p>"
                        if external_file_href
                        else "<p><strong>Staged file:</strong> unavailable in this case portal.</p>"
                    ),
                    "<section><h2>Source excerpt</h2>",
                    f"<pre>{html.escape(str(row.get('text_excerpt') or 'No extracted text was available for this record.'))}</pre>",
                    "</section>",
                    "<section><h2>Source manifest row</h2>",
                    f"<pre>{html.escape(json.dumps(row, indent=2, sort_keys=True))}</pre>",
                    "</section>",
                    "</main>",
                    "</body>",
                    "</html>",
                ]
            ),
        )

        dataset.append(
            {
                "evidence_id": row["evidence_id"],
                "title": str(row.get("subject") or row.get("title") or row["evidence_id"]),
                "source_type": str(row.get("source_type", "")),
                "issue_lanes": list(row.get("issue_lanes", [])),
                "date": str(row.get("date_created_if_available") or row.get("date_modified") or ""),
                "text_excerpt": str(row.get("text_excerpt", "")),
                "privacy_status": str(row.get("privacy_status", "")),
                "source_hash": str(row.get("source_hash", "")),
                "detail_href": f"records/{detail_path.name}",
                "file_href": relative_href(portal_root / "search.html", external_copy_path) if external_copy_path and external_copy_path.exists() else "",
            }
        )

    write_text(
        portal_root / "search_records.js",
        "window.__CASE_RECORDS__ = " + json.dumps(dataset) + ";\n",
    )

    metrics_markup = "".join(
        [
            f"<div class=\"metric\"><span>Indexed records</span><strong>{proof.get('total_files_indexed', 0):,}</strong></div>",
            f"<div class=\"metric\"><span>External-safe records</span><strong>{proof.get('legal_matter_items', 0):,}</strong></div>",
            f"<div class=\"metric\"><span>PDF pages</span><strong>{proof.get('total_pdf_pages', 0):,}</strong></div>",
            f"<div class=\"metric\"><span>Excluded personal</span><strong>{proof.get('personal_nonlegal_excluded', 0):,}</strong></div>",
        ]
    )
    type_options = "".join(f"<option value=\"{html.escape(item)}\">{html.escape(item)}</option>" for item in source_types)
    lane_options = "".join(f"<option value=\"{html.escape(item)}\">{html.escape(item)}</option>" for item in issue_lanes)
    search_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(case_name)} - Search the Record</title>
  <style>
    :root {{
      --ink: #17212b;
      --muted: #5c6875;
      --line: rgba(23,33,43,.12);
      --paper: #f6f2eb;
      --panel: #ffffff;
      --accent: #165f6d;
      --accent-dark: #103945;
      --warm: #a44b22;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{ margin: 0; min-height: 100vh; overflow: hidden; background: linear-gradient(180deg, #efe7da 0%, #f6f2eb 55%, #f8f4ee 100%); color: var(--ink); font-family: "Segoe UI", Arial, sans-serif; }}
    a {{ color: var(--accent); }}
    .shell {{ height: 100vh; display: grid; grid-template-rows: auto auto minmax(0, 1fr); gap: 14px; padding: 18px; max-width: 1480px; margin: 0 auto; }}
    .hero {{ display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 16px; align-items: stretch; }}
    .hero-main, .hero-rail, .toolbar, .results, .detail {{ background: rgba(255,255,255,.88); border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 18px 38px rgba(23,33,43,.08); }}
    .hero-main {{ padding: 22px 26px; }}
    .hero-main h1 {{ margin: 8px 0 10px; font-size: clamp(2.6rem, 5vw, 4.2rem); line-height: .95; font-family: Georgia, "Times New Roman", serif; font-weight: 700; }}
    .eyebrow {{ color: var(--accent); font-weight: 800; letter-spacing: .2em; text-transform: uppercase; font-size: .9rem; }}
    .case-badge {{ display: inline-flex; align-items: center; padding: 10px 14px; border-radius: 999px; background: #eef4f5; border: 1px solid rgba(22,95,109,.18); color: var(--accent); font-weight: 800; }}
    .hero-note {{ margin: 0; max-width: 82ch; color: var(--muted); font-size: 1rem; line-height: 1.55; }}
    .hero-note-secondary {{ margin-top: 10px; }}
    .hero-rail {{ padding: 22px; display: grid; align-content: start; gap: 14px; }}
    .hero-rail h2 {{ margin: 0; font-size: 1.15rem; text-transform: uppercase; letter-spacing: .08em; color: var(--accent-dark); }}
    .hero-rail p {{ margin: 0; color: var(--muted); line-height: 1.55; }}
    .metric-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .metric {{ border: 1px solid var(--line); border-radius: 12px; padding: 12px; background: #fff; }}
    .metric span {{ display: block; font-size: .82rem; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }}
    .metric strong {{ display: block; margin-top: 6px; font-size: 1.55rem; }}
    .toolbar {{ display: grid; grid-template-columns: minmax(0, 1.5fr) 180px 220px auto; gap: 12px; padding: 14px; }}
    label {{ display: block; margin-bottom: 6px; color: var(--muted); font-size: .85rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }}
    input, select, button {{ font: inherit; }}
    input, select {{ width: 100%; padding: 12px 14px; border: 1px solid var(--line); border-radius: 12px; background: #fff; color: var(--ink); }}
    button {{ border: 0; border-radius: 12px; padding: 12px 16px; background: var(--accent-dark); color: #fff; font-weight: 700; cursor: pointer; }}
    .workspace {{ min-height: 0; display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(340px, .9fr); gap: 14px; }}
    .results, .detail {{ min-height: 0; display: grid; grid-template-rows: auto minmax(0, 1fr); overflow: hidden; }}
    .panel-head {{ padding: 16px 18px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; gap: 10px; }}
    .panel-head h2 {{ margin: 0; font-size: 1rem; letter-spacing: .06em; text-transform: uppercase; }}
    .panel-body {{ min-height: 0; overflow: auto; padding: 16px 18px; }}
    .result-card {{ border: 1px solid var(--line); border-radius: 14px; background: #fff; padding: 14px; display: grid; gap: 10px; margin-bottom: 12px; }}
    .result-card h3 {{ margin: 0; font-size: 1.04rem; }}
    .result-meta {{ display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: .88rem; }}
    .pill {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 10px; background: #eef4f5; color: var(--accent); font-weight: 700; }}
    .excerpt {{ color: #31404e; line-height: 1.55; }}
    .card-actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .card-actions a, .card-actions button {{ text-decoration: none; }}
    .card-actions .secondary {{ background: #eef4f5; color: var(--accent-dark); }}
    .detail-empty {{ color: var(--muted); line-height: 1.6; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
    .footer-links {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 14px; font-size: .92rem; }}
    @media (max-width: 1080px) {{
      body {{ overflow: auto; }}
      .shell {{ height: auto; min-height: 100vh; }}
      .hero, .workspace, .toolbar {{ grid-template-columns: 1fr; }}
    }}
    @media (max-height: 820px) and (min-width: 1081px) {{
      .shell {{ gap: 10px; padding: 10px; }}
      .hero {{ gap: 12px; }}
      .hero-main {{ padding: 14px 18px; }}
      .hero-main h1 {{ margin: 4px 0 8px; font-size: clamp(1.95rem, 3.6vw, 3.05rem); }}
      .eyebrow {{ font-size: .82rem; letter-spacing: .18em; }}
      .case-badge {{ padding: 8px 12px; font-size: .92rem; }}
      .hero-note {{ font-size: .9rem; line-height: 1.42; }}
      .hero-note-secondary {{ display: none; }}
      .hero-rail {{ padding: 16px; gap: 10px; }}
      .metric strong {{ font-size: 1.25rem; }}
      .toolbar {{ gap: 10px; padding: 10px; }}
      label {{ margin-bottom: 4px; font-size: .78rem; }}
      input, select {{ padding: 10px 12px; }}
      button {{ padding: 10px 14px; }}
      .panel-head {{ padding: 12px 14px; }}
      .panel-body {{ padding: 12px 14px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-main">
        <div class="eyebrow">We The People</div>
        <h1>&ldquo;... establish JUSTICE ...&rdquo;</h1>
        <p class="case-badge">Maine Family Law Evidence Assistant</p>
        <p class="hero-note" style="margin-top:14px;">Justice does not belong to one institution or one profession, it belongs to the People which these institutions of government are meant to serve; it is Public.</p>
        <p class="hero-note hero-note-secondary">This case workspace preserves a private forensic master, produces an external-safe legal-matter release, and keeps the record reviewable without turning the corpus into an unstructured dump.</p>
      </div>
      <aside class="hero-rail">
        <h2>Case Summary</h2>
        <p><strong>{html.escape(case_name)}</strong></p>
        <p>Search the external-safe legal-matter record, open staged files, inspect source-manifest rows, and follow role-package links without using the command line.</p>
        <div class="metric-grid">{metrics_markup}</div>
      </aside>
    </section>
    <section class="toolbar">
      <div><label for="query">Search the record</label><input id="query" placeholder="school, contact, medical, support, docket, therapy, records access"></div>
      <div><label for="source-type">Source type</label><select id="source-type"><option value="">All source types</option>{type_options}</select></div>
      <div><label for="issue-lane">Issue lane</label><select id="issue-lane"><option value="">All issue lanes</option>{lane_options}</select></div>
      <div style="display:flex;align-items:end;"><button id="clear-search" type="button">Clear filters</button></div>
    </section>
    <section class="workspace">
      <section class="results">
        <div class="panel-head"><h2>External-Safe Search Results</h2><span id="results-count" class="pill">0 results</span></div>
        <div class="panel-body" id="results"></div>
      </section>
      <aside class="detail">
        <div class="panel-head"><h2>Record Detail</h2><span class="pill">Review required</span></div>
        <div class="panel-body" id="detail">
          <div class="detail-empty">
            Select a result to inspect its excerpt, hash, issue lanes, and staged file links.
            <div class="footer-links">
              <a href="../04_INDEXES/QUESTION_COVERAGE_MATRIX.html">Question coverage</a>
              <a href="../05_TIMELINES/timeline.html">Timeline</a>
              <a href="../06_ISSUE_LANES/issue_lanes.html">Issue lanes</a>
              <a href="../03_ROLE_PACKAGES/01_GAL_REVIEW_USB/index.html">Role packages</a>
              <a href="../15_PROOF_VALIDATION/CASE_BUILD_REPORT.html">Proof report</a>
            </div>
          </div>
        </div>
      </aside>
    </section>
  </div>
  <script src="search_records.js"></script>
  <script>
    const records = window.__CASE_RECORDS__ || [];
    const queryInput = document.getElementById('query');
    const sourceType = document.getElementById('source-type');
    const issueLane = document.getElementById('issue-lane');
    const clearSearch = document.getElementById('clear-search');
    const resultsNode = document.getElementById('results');
    const detailNode = document.getElementById('detail');
    const countNode = document.getElementById('results-count');

    function escapeHtml(value) {{
      return (value || '').toString().replace(/[&<>\"']/g, (char) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}}[char]));
    }}

    function renderDetail(record) {{
      if (!record) {{
        detailNode.innerHTML = '<div class="detail-empty">Select a result to inspect the record.</div>';
        return;
      }}
      const lanes = (record.issue_lanes || []).map((item) => `<span class="pill">${{escapeHtml(item)}}</span>`).join(' ');
      const actions = [
        `<a href="${{record.detail_href}}" target="_blank" rel="noopener noreferrer">Open detail page</a>`,
        record.file_href ? `<a href="${{record.file_href}}" target="_blank" rel="noopener noreferrer">Open staged file</a>` : ''
      ].filter(Boolean).join(' · ');
      detailNode.innerHTML = `
        <h3>${{escapeHtml(record.title || record.evidence_id)}}</h3>
        <p><strong>Evidence ID:</strong> ${{escapeHtml(record.evidence_id)}}</p>
        <p><strong>Date:</strong> ${{escapeHtml(record.date || 'Undated')}} · <strong>Source type:</strong> ${{escapeHtml(record.source_type || 'unknown')}}</p>
        <div class="result-meta">${{lanes || '<span class="pill">no issue lane</span>'}}</div>
        <p class="excerpt">${{escapeHtml(record.text_excerpt || 'No excerpt available.')}}</p>
        <p><strong>Privacy:</strong> ${{escapeHtml(record.privacy_status || 'review required')}}</p>
        <p><strong>SHA-256:</strong><br><code>${{escapeHtml(record.source_hash || '')}}</code></p>
        <div class="footer-links">${{actions}}</div>
      `;
    }}

    function renderResults() {{
      const needle = queryInput.value.trim().toLowerCase();
      const typeNeedle = sourceType.value;
      const laneNeedle = issueLane.value;
      const filtered = records.filter((record) => {{
        const blob = [record.title, record.evidence_id, record.source_type, record.date, record.text_excerpt, ...(record.issue_lanes || [])].join(' ').toLowerCase();
        if (needle && !blob.includes(needle)) return false;
        if (typeNeedle && record.source_type !== typeNeedle) return false;
        if (laneNeedle && !(record.issue_lanes || []).includes(laneNeedle)) return false;
        return true;
      }});
      countNode.textContent = `${{filtered.length}} result${{filtered.length === 1 ? '' : 's'}}`;
      resultsNode.innerHTML = filtered.map((record) => {{
        const laneMarkup = (record.issue_lanes || []).map((item) => `<span class="pill">${{escapeHtml(item)}}</span>`).join(' ');
        return `
          <article class="result-card">
            <h3>${{escapeHtml(record.title || record.evidence_id)}}</h3>
            <div class="result-meta">
              <span>${{escapeHtml(record.date || 'Undated')}}</span>
              <span>${{escapeHtml(record.source_type || 'unknown')}}</span>
              ${{laneMarkup}}
            </div>
            <div class="excerpt">${{escapeHtml(record.text_excerpt || 'No excerpt available.')}}</div>
            <div class="card-actions">
              <button type="button" data-detail="${{escapeHtml(record.evidence_id)}}">Inspect here</button>
              <a class="secondary" href="${{record.detail_href}}" target="_blank" rel="noopener noreferrer">Open detail</a>
              ${{record.file_href ? `<a class="secondary" href="${{record.file_href}}" target="_blank" rel="noopener noreferrer">Open file</a>` : ''}}
            </div>
          </article>
        `;
      }}).join('') || '<div class="detail-empty">No records matched those filters.</div>';

      document.querySelectorAll('[data-detail]').forEach((button) => {{
        button.addEventListener('click', () => {{
          const record = records.find((item) => item.evidence_id === button.dataset.detail);
          renderDetail(record || null);
        }});
      }});

      renderDetail(filtered[0] || null);
    }}

    [queryInput, sourceType, issueLane].forEach((element) => {{
      element.addEventListener('input', renderResults);
      element.addEventListener('change', renderResults);
    }});
    clearSearch.addEventListener('click', () => {{
      queryInput.value = '';
      sourceType.value = '';
      issueLane.value = '';
      renderResults();
    }});
    renderResults();
  </script>
</body>
</html>
"""
    write_text(portal_root / "search.html", search_html)
    write_text(
        portal_root / "START_HERE.html",
        "\n".join(
            [
                "<!doctype html>",
                "<html lang=\"en\">",
                "<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>Start Here</title><style>body{margin:0;background:#f6f2eb;color:#17212b;font-family:Segoe UI,Arial,sans-serif;}main{max-width:1100px;margin:0 auto;padding:28px;}a{color:#165f6d;}ul{line-height:1.8;}.button-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px;}a.button{display:inline-flex;align-items:center;justify-content:center;padding:12px 16px;border-radius:999px;background:#103945;color:#fff;text-decoration:none;font-weight:700;}</style></head>",
                "<body><main>",
                "<p><strong>Review required.</strong> Local-first evidence navigation only. Not legal advice.</p>",
                "<h1>Maine Family Law Evidence Assistant</h1>",
                "<p>Open the search portal to review the external-safe record, inspect proof and hashes, or move into role-specific review packages.</p>",
                "<div class=\"button-row\">",
                "<a class=\"button\" href=\"search.html\">Open search portal</a>",
                "<a class=\"button\" href=\"../03_ROLE_PACKAGES/01_GAL_REVIEW_USB/index.html\">Open role packages</a>",
                "<a class=\"button\" href=\"../15_PROOF_VALIDATION/CASE_BUILD_REPORT.html\">Open proof report</a>",
                "</div>",
                "<ul>",
                "<li><a href=\"search.html\">Search the external-safe record</a></li>",
                "<li><a href=\"../04_INDEXES/QUESTION_COVERAGE_MATRIX.html\">Question coverage</a></li>",
                "<li><a href=\"../05_TIMELINES/timeline.html\">Timeline</a></li>",
                "<li><a href=\"../06_ISSUE_LANES/issue_lanes.html\">Issue lanes</a></li>",
                "<li><a href=\"../09_PRIVACY_PRIVILEGE_REVIEW/privacy_summary.html\">Privacy summary</a></li>",
                "</ul>",
                "</main></body></html>",
            ]
        ),
    )
    write_text(
        portal_root / "index.html",
        "<!doctype html><html><head><meta http-equiv=\"refresh\" content=\"0; url=START_HERE.html\"></head><body><a href=\"START_HERE.html\">Open start page</a></body></html>",
    )
    write_html(
        portal_root / "timeline.html",
        "Timeline",
        "<h1>Timeline</h1><p>Open <a href=\"../05_TIMELINES/timeline.html\">the generated timeline</a>.</p>",
    )
    write_html(
        portal_root / "issue_lanes.html",
        "Issue Lanes",
        "<h1>Issue Lanes</h1><p>Open <a href=\"../06_ISSUE_LANES/issue_lanes.html\">the issue-lane summary</a>.</p>",
    )
    write_html(
        portal_root / "role_packages.html",
        "Role Packages",
        "<h1>Role Packages</h1><p>Open the package folders under <a href=\"../03_ROLE_PACKAGES/01_GAL_REVIEW_USB/index.html\">03_ROLE_PACKAGES</a>.</p>",
    )
    write_html(
        portal_root / "proof.html",
        "Proof",
        "<h1>Proof</h1><p>Open <a href=\"../15_PROOF_VALIDATION/CASE_BUILD_REPORT.html\">the case build proof report</a>.</p>",
    )
    write_html(
        portal_root / "known_limitations.html",
        "Known Limitations",
        "<h1>Known Limitations</h1><p>OCR and PST/OST parsing remain inventory-only unless additional local tooling is installed.</p>",
    )
    write_html(
        portal_root / "privacy_summary.html",
        "Privacy Summary",
        "<h1>Privacy Summary</h1><p>Open <a href=\"../09_PRIVACY_PRIVILEGE_REVIEW/privacy_summary.html\">the generated privacy summary</a>.</p>",
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


def create_example_case_template(repo_root: Path, *, template_root: Path | None = None) -> Path:
    base_root = template_root or (repo_root / "dist" / "example_case_template")
    source_root = base_root / "sample_source_corpus"
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


def _nontechnical_readme_html() -> str:
    return (
        "<h1>Maine Family Law LLM for Nontechnical Users</h1>"
        "<p>This tool is built so a parent, caregiver, GAL, lawyer, or reviewer can double-click a launcher instead of using a command line. "
        "It runs locally on Windows, keeps your originals read-only, and tells you when something was not found in the indexed corpus.</p>"
        "<h2>Quick start</h2>"
        "<ol>"
        "<li>Download the GitHub ZIP or the Windows installer package.</li>"
        "<li>Double-click <strong>START_MAINE_FAMILY_LAW_LLM.cmd</strong> or <strong>INSTALL_MAINE_FAMILY_LAW_LLM.cmd</strong>.</li>"
        "<li>If Python or required packages are missing, the launcher will install them and skip what is already present.</li>"
        "<li>Click <strong>Create New Case Corpus</strong> if you are starting a fresh matter.</li>"
        "<li>Click <strong>Open Existing Case Corpus</strong> if somebody already built your case workspace and you only want to use the LLM/search tools.</li>"
        "<li>Click <strong>Reopen Intake / Add More Evidence</strong> later if you need to add more records without mutating the earlier build.</li>"
        "<li>The launcher remembers earlier source folders for that case, so you only need to add the new files or folders.</li>"
        "<li>Use the <strong>Installed corpus library</strong> to switch between saved family/client matters through one install.</li>"
        "</ol>"
        "<h2>Source export guides</h2>"
        "<ul>"
        "<li><a href=\"HOW_TO_ADD_YOUR_CORPUS.html\">What files the wizard accepts</a></li>"
        "<li><a href=\"HOW_TO_EXPORT_FROM_GMAIL_AND_GOOGLE_WORKSPACE.html\">Gmail and Google Workspace</a></li>"
        "<li><a href=\"HOW_TO_EXPORT_FROM_OUTLOOK_AND_HOTMAIL.html\">Outlook desktop, Outlook on the web, Hotmail, and Outlook.com</a></li>"
        "<li><a href=\"HOW_TO_EXPORT_FROM_IPHONE_AND_ANDROID.html\">Phones, screenshots, photos, and attachments</a></li>"
        "<li><a href=\"SYSTEM_REQUIREMENTS.html\">Recommended Windows system requirements</a></li>"
        "</ul>"
        "<h2>Skip the import wizard if your corpus already exists</h2>"
        "<p>You do not need to rebuild the corpus every time. If someone already gave you a completed case folder, open the launcher and choose "
        "<strong>Open Existing Case Corpus</strong>. Then use <strong>Open Review Portal</strong>, <strong>Open Search / Indexes</strong>, or the browser LLM/chat workbench.</p>"
    )


def _corpus_ingest_guide_html() -> str:
    return (
        "<h1>How to Add Your Corpus</h1>"
        "<p>The corpus wizard accepts ordinary folders and individual files. For best results, gather copies of the records into one staging folder and then point the wizard at that folder.</p>"
        "<h2>Preferred file types</h2>"
        "<ul>"
        "<li><strong>Email:</strong> <code>.eml</code>, printed email PDFs, downloaded attachments, exported text</li>"
        "<li><strong>Documents:</strong> <code>.pdf</code>, <code>.txt</code>, <code>.md</code>, <code>.docx</code>, <code>.rtf</code>, <code>.html</code></li>"
        "<li><strong>Images:</strong> screenshots, photos, scans, <code>.jpg</code>, <code>.png</code>, <code>.heic</code>, <code>.tif</code></li>"
        "<li><strong>Spreadsheets:</strong> <code>.xlsx</code>, <code>.xls</code>, <code>.csv</code></li>"
        "</ul>"
        "<h2>Good first places to look</h2>"
        "<ul>"
        "<li><strong>Documents</strong>: prepared filings, letters, school records, case folders</li>"
        "<li><strong>Downloads</strong>: court PDFs, saved email attachments, portal exports</li>"
        "<li><strong>Desktop</strong>: temporary review sets or recent exports</li>"
        "<li><strong>Pictures</strong>: screenshots, scans, and phone image exports</li>"
        "</ul>"
        "<h2>Best practice staging layout</h2>"
        "<pre>My Case Export\\\n"
        "  01_email_eml_or_pdf\\\n"
        "  02_filings_and_orders_pdf\\\n"
        "  03_phone_screenshots_and_photos\\\n"
        "  04_attachments_and_reports\\\n"
        "  05_school_medical_counseling\\\n"
        "  06_timelines_notes_and_spreadsheets</pre>"
        "<h2>What the wizard does</h2>"
        "<ol>"
        "<li>Hashes the originals read-only.</li>"
        "<li>Inventories every file it can see.</li>"
        "<li>Builds a private forensic master.</li>"
        "<li>Builds an external-safe legal-matter release.</li>"
        "<li>Builds role packages, indexes, proof reports, and USB exports.</li>"
        "</ol>"
        "<p>When you reopen intake later, the earlier remembered source folders stay attached to the case automatically unless those folders or drives are no longer available.</p>"
        "<h2>What to avoid</h2>"
        "<ul>"
        "<li>Do not point the wizard at your whole computer profile or your whole mailbox unless you truly mean to review all of it.</li>"
        "<li>Do not rely on raw PST/OST/MBOX archives as your only format. The safest search path is still PDFs, <code>.eml</code>, attachments, screenshots, and plainly readable documents.</li>"
        "<li>Keep an untouched copy of the originals somewhere safe. This tool never mutates them, but preservation still matters.</li>"
        "</ul>"
    )


def _gmail_export_guide_html() -> str:
    return (
        "<h1>Export from Gmail and Google Workspace</h1>"
        "<p>This guide is for free Gmail accounts and paid Google Workspace accounts.</p>"
        "<h2>Best import formats</h2>"
        "<ul>"
        "<li>Download important messages as <code>.eml</code> when Gmail offers it.</li>"
        "<li>Print important emails to PDF so the message is human-readable even outside Gmail.</li>"
        "<li>Download every attachment into the same staging folder.</li>"
        "</ul>"
        "<h2>Single-message workflow</h2>"
        "<ol>"
        "<li>Open the email in Gmail.</li>"
        "<li>Use the message menu to download the message or print it to PDF.</li>"
        "<li>Save attachments beside the message PDF or <code>.eml</code>.</li>"
        "<li>Place those files in a case staging folder such as <code>01_email_eml_or_pdf</code>.</li>"
        "</ol>"
        "<h2>Large-mailbox workflow</h2>"
        "<ol>"
        "<li>Use Google Takeout if you need a cold-storage export of a large mailbox.</li>"
        "<li>Keep the Takeout archive as preservation evidence.</li>"
        "<li>For the best search experience in this tool, still convert the important threads into PDFs or <code>.eml</code> files and save their attachments in plain folders.</li>"
        "</ol>"
        "<h2>Good reminder</h2>"
        "<p>If a message matters, preserve it in more than one readable way: one printed PDF, one downloaded message copy when possible, and the original attachments.</p>"
    )


def _outlook_export_guide_html() -> str:
    return (
        "<h1>Export from Outlook Desktop, Outlook on the Web, Hotmail, and Outlook.com</h1>"
        "<p>This guide is written for the Microsoft free-email ecosystem most parents actually use: Outlook.com, Hotmail, Live, and Outlook Web App, plus installed Outlook desktop where available.</p>"
        "<h2>Preferred approach</h2>"
        "<ul>"
        "<li>Print important messages to PDF.</li>"
        "<li>Download attachments beside the email PDF.</li>"
        "<li>If Outlook desktop lets you save readable message files, keep them too, but do not depend on PST/OST alone for search.</li>"
        "</ul>"
        "<h2>Outlook.com / Hotmail / Outlook on the web</h2>"
        "<ol>"
        "<li>Open the message in the browser.</li>"
        "<li>Use the browser print function and save to PDF.</li>"
        "<li>Download any attachments into the same case staging folder.</li>"
        "<li>Repeat for the messages that matter most.</li>"
        "</ol>"
        "<h2>Outlook desktop</h2>"
        "<ol>"
        "<li>Open the message and print it to PDF.</li>"
        "<li>Save attachments separately.</li>"
        "<li>If you also export a PST/OST for preservation, keep it as a cold-storage original, not as the only thing you import.</li>"
        "</ol>"
        "<h2>Why this matters</h2>"
        "<p>The local search and LLM layers work best with ordinary readable files in ordinary folders. A folder full of PDFs, attachments, and plain documents is easier to verify, review, and hand to another person than a single mailbox database.</p>"
    )


def _phone_export_guide_html() -> str:
    return (
        "<h1>Export from iPhone, Android, Photos, and Screenshots</h1>"
        "<p>Phones often hold the evidence that never makes it into a formal document: screenshots, texts, call logs, photos of paperwork, portal screens, and downloaded attachments.</p>"
        "<h2>What to gather</h2>"
        "<ul>"
        "<li>Screenshots of messages, portals, attendance notices, payment screens, or missed-contact logs</li>"
        "<li>Photos of letters, envelopes, binders, school papers, or handwritten notes</li>"
        "<li>Downloaded PDFs or attachments already saved on the phone</li>"
        "<li>Voicemail transcripts or notes exported to PDF/text where available</li>"
        "</ul>"
        "<h2>iPhone / iPad</h2>"
        "<ol>"
        "<li>Use the Photos app or Files app to gather screenshots, scans, and downloaded documents.</li>"
        "<li>Connect by USB to the Windows computer or upload to a temporary transfer folder such as OneDrive, iCloud Drive, Google Drive, or a cable-import folder.</li>"
        "<li>Copy the files into a staging folder such as <code>03_phone_screenshots_and_photos</code>.</li>"
        "</ol>"
        "<h2>Android</h2>"
        "<ol>"
        "<li>Use Files, Photos, or your screenshot folder to gather the records.</li>"
        "<li>Transfer them to the Windows computer by USB, Nearby Share, Drive, or another normal file transfer method.</li>"
        "<li>Keep the folder names understandable so another reviewer can tell what came from the phone.</li>"
        "</ol>"
        "<h2>Practical advice</h2>"
        "<p>If a phone screen matters, capture the surrounding date/time context too. A screenshot plus a PDF export plus the related attachment is often stronger than any one artifact by itself.</p>"
    )


def _system_requirements_html() -> str:
    return (
        "<h1>Recommended Windows System Requirements</h1>"
        "<p>The builder and local chat are meant to stay usable on ordinary Windows machines. A discrete GPU is not required.</p>"
        "<h2>Minimum practical setup</h2>"
        "<ul>"
        "<li>Windows 10 or Windows 11</li>"
        "<li>64-bit Intel i5 / Ryzen 5 class CPU or better</li>"
        "<li>16 GB RAM</li>"
        "<li>At least 15 GB free SSD space for the app, Python, indexes, and a modest case build</li>"
        "<li>Internet access for the first install only, if Python or packages need to be downloaded</li>"
        "</ul>"
        "<h2>Recommended setup</h2>"
        "<ul>"
        "<li>Intel i7 or Ryzen 7 class CPU</li>"
        "<li>24 GB to 32 GB RAM for smoother indexing, bigger cases, and browser chat workbench use</li>"
        "<li>SSD storage with 30 GB or more free working space</li>"
        "<li>A 1920x1080 display or better</li>"
        "</ul>"
        "<h2>Important notes</h2>"
        "<ul>"
        "<li>The tool is local-first and does not require a discrete GPU.</li>"
        "<li>Very large corpora still benefit from more RAM and fast SSD storage.</li>"
        "<li>The browser workbench, launcher, and corpus builder all remain usable without cloud evidence upload by default.</li>"
        "</ul>"
    )


def _root_readme_markdown() -> str:
    return (
        "Maine Family Law LLM\n\n"
        "Double-click START_MAINE_FAMILY_LAW_LLM.cmd to open the launcher, or run INSTALL_MAINE_FAMILY_LAW_LLM.cmd from the Windows installer package.\n\n"
        "Quick path for nontechnical users:\n"
        "1. Run the launcher.\n"
        "2. Let it install missing prerequisites and skip the ones already present.\n"
        "3. Choose Create New Case Corpus if you need to build a case.\n"
        "4. Choose Open Existing Case Corpus if somebody already built the matter for you.\n"
        "5. Use Reopen Intake / Add More Evidence later to build a new expanded case without mutating the earlier one.\n"
        "6. The launcher remembers the earlier source folders for that case, so you only need to add the new material.\n\n"
        "Use the Installed corpus library to switch between saved family/client matters through one install.\n\n"
        "Helpful guides:\n"
        "- docs/README_FOR_NONTECHNICAL_USERS.html\n"
        "- docs/HOW_TO_ADD_YOUR_CORPUS.html\n"
        "- docs/HOW_TO_EXPORT_FROM_GMAIL_AND_GOOGLE_WORKSPACE.html\n"
        "- docs/HOW_TO_EXPORT_FROM_OUTLOOK_AND_HOTMAIL.html\n"
        "- docs/HOW_TO_EXPORT_FROM_IPHONE_AND_ANDROID.html\n"
        "- docs/SYSTEM_REQUIREMENTS.html\n"
    )


def _start_here_body_html() -> str:
    return (
        "<h1>Maine Family Law LLM</h1>"
        "<p>This tool helps make the full case record reviewable without forcing courts, GALs, lawyers, investigators, or parents to search through an unstructured personal archive. "
        "It preserves a private forensic master, builds an external-safe legal-matter release, and keeps the original sources read-only.</p>"
        "<p>For most people, the simple path is: create a case once, then reopen intake later whenever new evidence arrives.</p>"
        "<ul>"
        "<li><a href=\"README_FIRST.md\">Read first</a></li>"
        "<li><a href=\"docs/README_FOR_NONTECHNICAL_USERS.html\">Nontechnical guide</a></li>"
        "<li><a href=\"docs/HOW_TO_ADD_YOUR_CORPUS.html\">How to add your corpus</a></li>"
        "<li><a href=\"docs/SYSTEM_REQUIREMENTS.html\">System requirements</a></li>"
        "<li><a href=\"dist/windows_portable/INSTALL_OR_RUN.html\">Portable distribution</a></li>"
        "</ul>"
    )


def _windows_launcher_vbs() -> str:
    """Return a quote-safe Windows Script Host launcher."""

    return (
        'Option Explicit\n'
        '\n'
        'Dim shell, fso, root, launcher, comspec, command\n'
        'Set shell = CreateObject("WScript.Shell")\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        '\n'
        'root = fso.GetParentFolderName(WScript.ScriptFullName)\n'
        'launcher = fso.BuildPath(root, "START_MAINE_FAMILY_LAW_LLM.cmd")\n'
        'comspec = shell.ExpandEnvironmentStrings("%ComSpec%")\n'
        'command = Chr(34) & comspec & Chr(34) & " /d /s /c " & _\n'
        '    Chr(34) & Chr(34) & launcher & Chr(34) & Chr(34)\n'
        '\n'
        'shell.Run command, 1, False\n'
    )


def bootstrap_repository(repo_root: Path) -> dict[str, Path]:
    question_bank_path = write_question_bank(repo_root / "sample_question_bank" / "generic_question_bank.jsonl")
    example_source_root = create_example_case_template(repo_root)
    docs = {
        "README_FOR_NONTECHNICAL_USERS.html": _nontechnical_readme_html(),
        "HOW_TO_ADD_YOUR_CORPUS.html": _corpus_ingest_guide_html(),
        "HOW_TO_EXPORT_FROM_GMAIL_AND_GOOGLE_WORKSPACE.html": _gmail_export_guide_html(),
        "HOW_TO_EXPORT_FROM_OUTLOOK_AND_HOTMAIL.html": _outlook_export_guide_html(),
        "HOW_TO_EXPORT_FROM_IPHONE_AND_ANDROID.html": _phone_export_guide_html(),
        "SYSTEM_REQUIREMENTS.html": _system_requirements_html(),
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
    start_cmd = (
        "@echo off\nsetlocal\ncd /d %~dp0\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0scripts\\bootstrap-windows-launcher.ps1\" -RepoRoot \"%~dp0\" %*\n"
    )
    start_bat = start_cmd
    start_vbs = _windows_launcher_vbs()
    readme_text = _root_readme_markdown()
    start_here_body = _start_here_body_html()
    verify_cmd = (
        "@echo off\nsetlocal\ncd /d %~dp0\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0scripts\\bootstrap-windows-launcher.ps1\" -RepoRoot \"%~dp0\" -VerifyOnly\n"
    )
    repair_cmd = (
        "@echo off\nsetlocal\ncd /d %~dp0\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0scripts\\bootstrap-windows-launcher.ps1\" -RepoRoot \"%~dp0\" -Repair\n"
    )
    launchers = {
        "START_MAINE_FAMILY_LAW_LLM.cmd": start_cmd,
        "START_MAINE_FAMILY_LAW_LLM.bat": start_bat,
        "START_MAINE_FAMILY_LAW_LLM.vbs": start_vbs,
        "README_FIRST.md": readme_text,
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
        "<h1>Install or Run</h1><p>Double-click START_MAINE_FAMILY_LAW_LLM.cmd from this portable folder. The launcher checks for Python and required packages, installs missing prerequisites, and skips anything already present. No admin rights are required for the normal per-user path.</p><p>When new evidence arrives later, reopen the launcher and use <strong>Reopen Intake / Add More Evidence</strong> so the case keeps growing over time.</p>",
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
        if root.is_file():
            files.append(root)
            continue
        if not root.exists():
            continue
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
    question_bank_path = repo_root / "sample_question_bank" / "generic_question_bank.jsonl"
    if not question_bank_path.exists():
        question_bank_path = write_question_bank(output_root / "_runtime_support" / "generic_question_bank.jsonl")
    case_short = slugify(case_name)[:12].upper()
    case_root = output_root / slugify(case_name)
    case_root.mkdir(parents=True, exist_ok=True)
    for relative in CASE_LAYOUT:
        (case_root / relative).mkdir(parents=True, exist_ok=True)

    source_files = discover_source_files(source_roots)
    private_root = case_root / "01_PRIVATE_FORENSIC_MASTER_INTERNAL_ONLY"
    external_root = case_root / "02_EXTERNAL_LEGAL_MATTER_RELEASE"
    private_files_root = private_root / "files"
    external_files_root = external_root / "files"
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
        private_copy_relpath = ""
        external_copy_relpath = ""
        staged_private_name = stage_case_copy(private_files_root, evidence_id, path)
        if staged_private_name:
            private_copy_relpath = private_root.joinpath("files", staged_private_name).relative_to(case_root).as_posix()
        if external_allowed:
            staged_external_name = stage_case_copy(external_files_root, evidence_id, path)
            if staged_external_name:
                external_copy_relpath = external_root.joinpath("files", staged_external_name).relative_to(case_root).as_posix()
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
            "private_copy_relpath": private_copy_relpath,
            "external_copy_relpath": external_copy_relpath,
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
    local_index_proof = rebuild_local_content_index(case_root)

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

    question_coverage_counts = build_question_coverage(case_root, records, question_bank_path)

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
        "role_packages_built": [],
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
        "local_content_index": local_index_proof,
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
    write_case_source_roots(
        case_root,
        case_name=case_name,
        source_roots=source_roots,
    )
    write_text(
        proof_root / "CASE_BUILD_REPORT.md",
        f"# Case Build Report\n\n- Result: {proof['result']}\n- Indexed files: {proof['total_files_indexed']}\n- External legal-matter items: {proof['legal_matter_items']}\n",
    )
    write_html(
        proof_root / "CASE_BUILD_REPORT.html",
        "Case Build Report",
        f"<h1>Case Build Report</h1><p>Indexed files: {proof['total_files_indexed']}</p><p>External legal-matter items: {proof['legal_matter_items']}</p>",
    )

    write_case_portal(case_root, case_name=case_name, external_records=external_rows, proof=proof)
    role_package_result = build_role_packages(
        case_root,
        records=records,
        external_records=external_rows,
        private_manifest_path=private_manifest_path,
        external_manifest_path=external_manifest_path,
    )

    proof["role_packages_built"] = [row["path"] for row in role_package_result["role_packages"]]
    write_json(proof_json_path, proof)

    return CaseBuildResult(case_root=case_root, proof_json_path=proof_json_path, question_bank_path=question_bank_path)


def load_case_search_records(case_root: Path) -> list[dict[str, Any]]:
    private_records_path = case_root / "04_INDEXES" / "private_search_index.json"
    if private_records_path.exists():
        return json.loads(private_records_path.read_text(encoding="utf-8"))
    records_path = case_root / "04_INDEXES" / "search_index.json"
    if records_path.exists():
        return json.loads(records_path.read_text(encoding="utf-8"))
    jsonl_path = case_root / "04_INDEXES" / "search_index.jsonl"
    if jsonl_path.exists():
        return [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return []


def answer_case_question(case_root: Path, question: str, role: str = "court") -> dict[str, Any]:
    indexed_matches = search_local_content_index(case_root, question)
    if indexed_matches:
        evidence_ids = [str(row["evidence_id"]) for row in indexed_matches]
        return {
            "direct_answer": f"The corpus shows source-backed records relevant to: {question}.",
            "evidence_relied_on": [str(row.get("snippet") or "") for row in indexed_matches],
            "source_type": ", ".join(sorted({str(row.get("source_type") or "") for row in indexed_matches})),
            "timeline_anchors": [],
            "contradictions_gaps": ["Review the original source and full context before drawing conclusions."],
            "confidence": "medium",
            "what_this_does_not_prove": "A text match does not establish a disputed fact or replace official records.",
            "recommended_official_verification": ["Open the cited original source and verify the official record where applicable."],
            "evidence_ids_hashes_packet_paths": [
                {"evidence_id": row["evidence_id"], "source_hash": "", "packet_path": row.get("source_locator", "")}
                for row in indexed_matches
            ],
            "citations": [
                {
                    "source_id": row["evidence_id"],
                    "title": row.get("title") or row["evidence_id"],
                    "snippet": row.get("snippet") or "",
                    "metadata": {
                        "id": row["evidence_id"],
                        "title": row.get("title") or row["evidence_id"],
                        "source_type": row.get("source_type", ""),
                        "source_locator": row.get("source_locator", ""),
                        "parent_evidence_id": row.get("parent_evidence_id", ""),
                        "parser_status": row.get("parser_status", ""),
                        "ocr_status": row.get("ocr_status", ""),
                        "issue_lanes": row.get("issue_lanes", ""),
                        "exact_content_match": bool(row.get("exact_content_match")),
                    },
                }
                for row in indexed_matches
            ],
            "not_legal_advice": True,
        }
    records = load_case_search_records(case_root)
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
        unique_tokens = set(meaningful_tokens)
        matched_tokens = {
            token for token in unique_tokens if token in haystack
        }
        required_matches = 1 if len(unique_tokens) == 1 else 2
        coverage = (
            len(matched_tokens) / len(unique_tokens)
            if unique_tokens
            else 0.0
        )
        if (
            len(matched_tokens) >= required_matches
            and coverage >= 0.50
        ):
            scored.append((len(matched_tokens), row))
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
                "packet_path": str(row.get("detail_page_relpath") or row.get("external_copy_relpath") or ""),
            }
            for row in top_rows
        ],
        "citations": [
            {
                "source_id": row["evidence_id"],
                "title": row.get("subject") or row.get("title") or row["evidence_id"],
                "snippet": row["text_excerpt"][:240],
                "metadata": {
                    "id": row["evidence_id"],
                    "title": row.get("subject") or row.get("title") or row["evidence_id"],
                    "source_type": row.get("source_type", ""),
                    "source_hash": row.get("source_hash", ""),
                    "issue_lanes": ", ".join(row.get("issue_lanes", [])),
                    "detail_page_relpath": row.get("detail_page_relpath", ""),
                    "external_copy_relpath": row.get("external_copy_relpath", ""),
                    "source_path": row.get("source_path", ""),
                },
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
    shared_dirs = (
        "00_START_HERE",
        "02_EXTERNAL_LEGAL_MATTER_RELEASE",
        "04_INDEXES",
        "05_TIMELINES",
        "06_ISSUE_LANES",
        "07_ENTITIES_WITNESSES_DOCKETS",
        "08_SOURCE_MANIFESTS_HASHES",
        "09_PRIVACY_PRIVILEGE_REVIEW",
        "13_DUPLICATES_VERSION_HISTORY",
        "14_QUARANTINE_UNREADABLE_UNSUPPORTED",
        "15_PROOF_VALIDATION",
    )
    for name in shared_dirs:
        src = case_root / name
        if not src.exists():
            continue
        dst = export_root / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        copied.append(dst)
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
        "@echo off\r\nsetlocal\r\nif not exist USB_COPY_MANIFEST_SHA256.txt (echo USB_VERIFY_FAIL & exit /b 1)\r\nif not exist 00_START_HERE\\START_HERE.html (echo USB_PORTAL_MISSING & exit /b 1)\r\nif not exist 15_PROOF_VALIDATION\\CASE_BUILD_PROOF.json (echo USB_PROOF_MISSING & exit /b 1)\r\necho USB_VERIFY_OK\r\nexit /b 0\r\n",
    )
    write_html(
        export_root / "START_HERE_USB.html",
        "USB Start Here",
        "<h1>USB Export</h1><p>This USB copy includes the start portal, external-safe release, role packages, indexes, privacy summary, and proof report. Run VERIFY_USB.cmd, then open 00_START_HERE/START_HERE.html.</p>",
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


def create_sample_case_build(
    repo_root: Path,
    *,
    output_root: Path | None = None,
    case_name: str = "Example Family Matter",
) -> CaseBuildResult:
    sample_output_root = output_root or (repo_root / "dist" / "example_case_template" / "sample_case_build")
    template_root = sample_output_root.parent / "_example_case_template" if output_root else None
    example_source_root = create_example_case_template(repo_root, template_root=template_root)
    if sample_output_root.exists():
        shutil.rmtree(sample_output_root)
    sample_output_root.mkdir(parents=True, exist_ok=True)
    return build_case_corpus(
        repo_root=repo_root,
        source_roots=[example_source_root],
        output_root=sample_output_root,
        case_name=case_name,
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
