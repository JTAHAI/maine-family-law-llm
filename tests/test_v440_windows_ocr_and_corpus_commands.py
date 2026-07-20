from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from maine_family_law_llm import api
from maine_family_law_llm.intake_understanding import parse_intake
from maine_family_law_llm.local_corpus_index import _write_fts, search_local_content_index
from maine_family_law_llm.ocr_prerequisites import install_local_ocr_prerequisites
from maine_family_law_llm.version import PACKAGE_VERSION, UI_PASS_MARKER, VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_pass_42_windows_launcher_normalizes_repo_root_and_cmd_avoids_trailing_quote_bug() -> None:
    bootstrap = (ROOT / "scripts" / "bootstrap-windows-launcher.ps1").read_text(encoding="utf-8")
    launcher = (ROOT / "START_MAINE_FAMILY_LAW_LLM.cmd").read_text(encoding="utf-8")
    generator = (ROOT / "src" / "maine_family_law_llm" / "case_corpus_builder.py").read_text(encoding="utf-8")
    assert "$ExplicitRepoRoot.Trim()" in bootstrap
    assert ".Trim([char[]]@([char]34, [char]39))" in bootstrap
    assert '-RepoRoot "%~dp0."' in launcher
    assert generator.count(r'RepoRoot \"%~dp0.\"') >= 3


def test_pass_42_ocr_installer_is_explicit_and_uses_only_allowlisted_winget_package() -> None:
    commands: list[list[str]] = []

    def runner(command, **_kwargs):
        commands.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout="installed", stderr="")

    denied = install_local_ocr_prerequisites(approved=False, platform_name="nt")
    assert denied["status"] == "consent_required"
    installed = install_local_ocr_prerequisites(
        approved=True,
        platform_name="nt",
        which=lambda name: "winget.exe" if name == "winget" else None,
        runner=runner,
    )
    assert installed["installed"] is True
    assert commands
    command = commands[0]
    assert command[:4] == ["winget.exe", "install", "--id", "UB-Mannheim.TesseractOCR"]
    assert "--accept-package-agreements" in command
    assert "--accept-source-agreements" in command
    assert all("matter" not in value.lower() for value in command)


def test_pass_42_ocr_dialog_has_one_click_manual_link_and_recheck_controls() -> None:
    html = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    js = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert 'id="install-ocr-prerequisites-button"' in html
    assert 'id="open-ocr-install-page-button"' in html
    assert 'id="recheck-ocr-button"' in html
    assert "/api/corpus-ocr/prerequisites/install" in js
    assert "Matter records are not read or uploaded" in js


def test_pass_43_intake_routes_inventory_and_pdf_search_as_record_commands() -> None:
    inventory = parse_intake("list what is in my indexed corpus")
    assert inventory.task == "corpus_inventory"
    pdf_search = parse_intake("find PDF re: contempt")
    assert pdf_search.task == "record_search"
    assert pdf_search.search_target == "contempt"
    assert pdf_search.record_type_filter == "pdf"


def test_pass_43_pdf_scoped_search_does_not_return_non_pdf_records(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    index_root = case_root / "04_INDEXES"
    index_root.mkdir(parents=True)
    rows = [
        {
            "evidence_id": "PDF-1",
            "title": "Contempt motion.pdf",
            "source_type": "pdf",
            "source_locator": "Contempt motion.pdf",
            "parent_evidence_id": "",
            "page_number": 0,
            "parser_status": "parsed",
            "ocr_status": "not_needed",
            "parser_metadata": {"document_kind": "pdf"},
            "issue_lanes": [],
            "text_content": "Motion for contempt and enforcement of the order.",
        },
        {
            "evidence_id": "TXT-1",
            "title": "notes.txt",
            "source_type": "text",
            "source_locator": "notes.txt",
            "parent_evidence_id": "",
            "page_number": 0,
            "parser_status": "parsed",
            "ocr_status": "not_needed",
            "parser_metadata": {"document_kind": "text"},
            "issue_lanes": [],
            "text_content": "Notes about contempt and enforcement.",
        },
    ]
    _write_fts(index_root / "private_content_index.sqlite", rows)
    results = search_local_content_index(case_root, "find PDF re: contempt", limit=10)
    assert results
    assert {row["evidence_id"] for row in results} == {"PDF-1"}


def test_pass_43_inventory_command_returns_real_counts_and_record_cards(monkeypatch) -> None:
    records = [
        {
            "evidence_id": "DOC-1",
            "title": "Signed order.pdf",
            "source_type": "pdf",
            "source_locator": "Signed order.pdf",
            "parser_status": "parsed",
            "text_status": "available",
            "ocr_status": "not_needed",
            "page_count": 1,
            "text_content": "Signed order text.",
            "text_excerpt": "Signed order text.",
            "parser_metadata": {"document_kind": "pdf"},
        },
        {
            "evidence_id": "DOC-1-P1",
            "title": "Signed order.pdf page 1",
            "source_type": "pdf_page",
            "source_locator": "Signed order.pdf#page=1",
            "parent_evidence_id": "DOC-1",
            "page_number": 1,
            "parser_status": "parsed",
            "text_status": "available",
            "ocr_status": "not_needed",
            "text_content": "Signed order text.",
            "text_excerpt": "Signed order text.",
            "parser_metadata": {"document_kind": "pdf"},
        },
    ]
    monkeypatch.setattr(api, "active_case_root", lambda: Path("/private/matter"))
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: records)
    monkeypatch.setattr(api, "describe_case_root", lambda _root: {"label": "03 ALL PDFS"})
    result = api.ask(
        api.AskRequest(
            question="list what is in my indexed corpus",
            search_mode="both",
            session_id="inventory-session",
        )
    )
    assert result["response_kind"] == "corpus_inventory"
    assert result["search_mode"] == "my_records"
    assert result["inventory_summary"]["top_level_records"] == 1
    assert result["inventory_summary"]["records"] == 2
    assert result["source_card_count"] == 1
    assert "Signed order.pdf" in result["answer"]
    assert "no Maine-law search was run" in result["mode_routing_note"]


def test_pass_44_version_and_store_target_advance_three_pass_increment() -> None:
    identity = json.loads((ROOT / "store" / "msix" / "identity.example.json").read_text(encoding="utf-8"))
    assert VERSION == "4.4.0"
    assert PACKAGE_VERSION == "4.4.0.0"
    assert identity["package_version"] == "4.4.0.0"
    assert UI_PASS_MARKER == "v4.4.0-windows-ocr-corpus-ux"


def test_ocr_progress_payload_redacts_paths_and_reports_stall_state() -> None:
    state = {
        "status": "running",
        "started_at": time.time() - 75,
        "last_progress_at": time.time() - 61,
        "current": 2,
        "total": 5,
        "processed_documents": 2,
        "processed_pages": 7,
        "candidate_pages": 12,
        "source_locator": r"C:\private\matter\medical-records.pdf",
        "cancel_event": object(),
    }
    payload = api._public_ocr_progress(state)
    assert payload["display_status"] == "stalled"
    assert payload["stalled"] is True
    assert payload["current_file"] == "medical-records.pdf"
    assert "C:\\private" not in json.dumps(payload)
    assert "cancel_event" not in payload
    assert payload["local_only"] is True
    assert payload["network_used"] is False


def test_ocr_progress_ui_includes_counts_timing_stall_and_local_only_notice() -> None:
    js = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    for marker in (
        "Local OCR is running",
        "Documents: ${escapeHtml(docs.toLocaleString())} of ${escapeHtml(total.toLocaleString())} completed",
        "Pages: ${escapeHtml(pages.toLocaleString())} of ${escapeHtml(candidatePages.toLocaleString())} completed",
        "Last update: ${escapeHtml(secondsSinceUpdate.toLocaleString())} seconds ago",
        "Large collections may take several minutes or longer",
        "Current file:",
        "Elapsed:",
        "Last update:",
        "No progress update has been received for 60 seconds",
        "remains entirely on this computer",
        "<progress",
    ):
        assert marker in js
    assert "String(part).padStart(2, '0')" in js
    assert "documentsRemaining = Math.max(0, total - docs)" in js
    assert "pagesRemaining = Math.max(0, candidatePages - pages)" in js
