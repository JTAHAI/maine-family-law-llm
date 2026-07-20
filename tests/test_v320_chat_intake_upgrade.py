from __future__ import annotations

import json
from email.message import EmailMessage
from pathlib import Path

from pypdf import PdfWriter

from maine_family_law_llm import api
from maine_family_law_llm.family_answer_contract import build_family_answer_contract, render_legacy_answer
from maine_family_law_llm.intake_understanding import parse_intake
from maine_family_law_llm.local_corpus_index import (
    INDEX_NAME,
    rebuild_local_content_index,
    local_inventory_metrics,
    search_local_content_index,
    summarize_local_search,
)


def test_intake_understands_typo_and_does_not_make_a_legal_finding() -> None:
    summary = parse_intake(
        "My ex is causing parental interferrence and obstruction of contact. What do I do?"
    )
    assert summary.task == "enforce_order"
    assert "parent_child_contact_interference" in summary.issues
    assert "interference" in summary.normalized_text
    assert "legal conclusion" not in summary.user_goal.lower()
    assert summary.interpretation_note


def test_intake_extracts_record_search_target() -> None:
    summary = parse_intake('Find all mentions of "contempt" in my records')
    assert summary.task == "record_search"
    assert summary.search_target == "contempt"


def test_served_answer_is_tailored_and_has_no_raw_citation_appendix() -> None:
    contract = build_family_answer_contract(
        question="I was served with family court papers. What should I do first?",
        legacy_answer=(
            "Start by reading the papers carefully.\n\n"
            "Citation appendix:\n[1] raw source metadata"
        ),
        citations=[],
        search_mode="maine_law",
    )
    rendered = render_legacy_answer(contract)
    assert "Read every page" in rendered
    assert "proof or date of service" in rendered
    assert "Citation appendix" not in rendered
    assert len(contract["next_three_steps"]) == 3
    assert contract["intake"]["task"] == "served_papers"


def _write_case_manifest(case_root: Path, source_path: Path, evidence_id: str = "REC-001") -> None:
    manifest_root = case_root / "08_SOURCE_MANIFESTS_HASHES"
    manifest_root.mkdir(parents=True)
    manifest_root.joinpath("source_manifest.json").write_text(
        json.dumps(
            [
                {
                    "evidence_id": evidence_id,
                    "source_path": str(source_path),
                    "source_hash": "",
                    "source_type": source_path.suffix.lower().lstrip("."),
                    "issue_lanes": [],
                }
            ]
        ),
        encoding="utf-8",
    )


def test_local_intake_indexes_email_attachment_content_and_exact_search(tmp_path: Path) -> None:
    attachment = b"The court order uses the word contempt. Review the complete paragraph."
    message = EmailMessage()
    message["Subject"] = "Court follow-up"
    message["From"] = "sender@example.test"
    message["To"] = "recipient@example.test"
    message.set_content("Attached is the follow-up note.")
    message.add_attachment(attachment, maintype="text", subtype="plain", filename="note.txt")
    eml = tmp_path / "court-follow-up.eml"
    eml.write_bytes(message.as_bytes())
    case_root = tmp_path / "case"
    _write_case_manifest(case_root, eml)

    proof = rebuild_local_content_index(case_root)
    assert proof["result"] == "PASS"
    assert proof["attachment_or_archive_children"] >= 1
    rows = search_local_content_index(case_root, "Find all mentions of contempt", limit=20)
    assert rows
    assert any(row["match_type"] in {"exact_phrase", "exact_token"} for row in rows)
    assert any("note.txt" in row["source_locator"] for row in rows)
    summary = summarize_local_search("Find all mentions of contempt", rows)
    assert summary["result_count"] >= 1
    assert summary["exact_phrase"] + summary["exact_token"] >= 1


def test_blank_pdf_creates_page_inventory_and_one_document_ocr_candidate(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    with pdf.open("wb") as handle:
        writer.write(handle)
    case_root = tmp_path / "case"
    _write_case_manifest(case_root, pdf)

    proof = rebuild_local_content_index(case_root)
    assert proof["page_records"] == 2
    assert proof["image_only_pages"] == 2
    assert proof["ocr_candidates"] == 1
    assert proof["ocr_candidate_documents"] == 1
    assert proof["ocr_candidate_pages"] == 2
    inventory = json.loads((case_root / "04_INDEXES" / "private_search_index.json").read_text(encoding="utf-8"))
    assert sum(1 for row in inventory if row.get("source_type") == "pdf_page") == 2
    assert (case_root / "04_INDEXES" / INDEX_NAME).exists()


def test_api_routes_direct_search_to_records_and_reuses_source_cards(monkeypatch) -> None:
    citation = {
        "source_id": "REC-1-P0002",
        "title": "Order — page 2",
        "snippet": "The word contempt appears here.",
        "metadata": {
            "source_lane": "private_record",
            "source_locator": "Order.pdf#page=2",
            "page_number": 2,
            "match_type": "exact_token",
        },
    }

    def fake_records(payload, *, finalize=True):
        result = {
            "question": payload.question,
            "answer_style": payload.answer_style,
            "search_mode": "my_records",
            "answer": "Search result:\n- Exact word/term match for contempt: 1 record.",
            "response_kind": "local_search_results",
            "direct_record_search": True,
            "search_summary": {
                "search_target": "contempt",
                "result_count": 1,
                "exact_phrase": 0,
                "exact_token": 1,
                "related": 0,
            },
            "grounded": True,
            "failure_class": "none",
            "citations": [citation],
            "source_card_count": 1,
            "review_required": True,
            "not_legal_advice": True,
            "active_case_label": "Test matter",
            "metadata": {},
        }
        return api._finalize_family_response(result, payload) if finalize else result

    monkeypatch.setattr(api, "_active_case_chat_payload", fake_records)
    first = api.ask(
        api.AskRequest(
            question="Find all mentions of contempt",
            search_mode="both",
            session_id="session-test",
        )
    )
    assert first["search_mode"] == "my_records"
    assert first["requested_search_mode"] == "both"
    assert first["source_card_count"] == 1
    assert first["citations"][0]["metadata"]["source_lane"] == "private_record"
    assert "Maine-law research" not in first["answer"]

    followup = api.ask(
        api.AskRequest(
            question="give me the source cards",
            search_mode="both",
            session_id="session-test",
        )
    )
    assert followup["response_kind"] == "source_card_followup"
    assert followup["source_card_count"] == 1
    assert followup["metadata"]["reused_prior_search"] is True
    assert "No new search was run" in followup["answer"]


def test_ui_surfaces_intake_and_record_match_provenance() -> None:
    js = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "maine_family_law_llm"
        / "ui"
        / "workbench.js"
    ).read_text(encoding="utf-8")
    assert "What I heard" in js
    assert "Searched for:" in js
    assert "Locator:" in js
    assert "local OCR-derived; verify against page image" in js
    assert "session_id: localSessionId" in js


def test_source_card_audit_question_is_not_mistaken_for_followup() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(
        AskRequest(
            question="How do I audit source cards before using an answer?",
            answer_style="source_card_table",
            session_id="audit-question-session",
        )
    )
    assert payload["response_kind"] != "source_card_followup"
    assert "Source-card audit table" in payload["answer"]
    assert "| Source | Type | Citation hint | Why it matters |" in payload["answer"]


def test_interference_wording_routes_neutrally_and_dedupes_authority() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(
        AskRequest(
            question="Find the latest parental interferrence guidance",
            search_mode="maine_law",
        )
    )
    answer = payload["answer"].lower()
    assert payload["metadata"]["matched_library_id"] == "parent_contact_interference_neutral_triage"
    assert "not self-proving legal findings" in answer
    assert "switch to my records" in answer
    assert "do not involve the child as a messenger" in answer
    source_ids = [row.get("source_id") for row in payload["citations"]]
    assert len(source_ids) == len(set(source_ids))


def test_direct_record_search_answer_stays_compact_without_generic_template(monkeypatch) -> None:
    citation = {
        "source_id": "REC-2-P0004",
        "title": "Messages — page 4",
        "snippet": "The word obstruction appears in this message.",
        "metadata": {
            "source_lane": "private_record",
            "source_locator": "messages.pdf#page=4",
            "page_number": 4,
            "match_type": "exact_token",
        },
    }

    def fake_records(payload, *, finalize=True):
        result = {
            "question": payload.question,
            "answer_style": payload.answer_style,
            "search_mode": "my_records",
            "answer": "Search result:\n- Exact word match ‘obstruction’: 1 record on 1 page.",
            "response_kind": "local_search_results",
            "direct_record_search": True,
            "search_summary": {
                "search_target": "obstruction",
                "result_count": 1,
                "document_count": 1,
                "page_count": 1,
                "exact_phrase": 0,
                "exact_token": 1,
                "related": 0,
            },
            "grounded": True,
            "failure_class": "none",
            "citations": [citation],
            "review_required": True,
            "not_legal_advice": True,
            "active_case_label": "Test matter",
            "metadata": {},
        }
        return api._finalize_family_response(result, payload) if finalize else result

    monkeypatch.setattr(api, "_active_case_chat_payload", fake_records)
    payload = api.ask(
        api.AskRequest(
            question="search contents for obstruction",
            search_mode="both",
            session_id="compact-search-session",
        )
    )
    assert payload["response_kind"] == "local_search_results"
    assert "What to do right now" not in payload["answer"]
    assert "Your next three steps" not in payload["answer"]
    assert payload["citations"][0]["metadata"]["source_lane"] == "private_record"


def test_order_clarification_does_not_route_to_interference_triage() -> None:
    from maine_family_law_llm.api import AskRequest, ask

    payload = ask(
        AskRequest(
            question="What does my order mean when it says reasonable contact?",
            search_mode="maine_law",
        )
    )
    assert payload["metadata"]["matched_library_id"] == "parent_order_language_confusing"
    assert "exact confusing language" in payload["answer"].lower()
    assert "not self-proving legal findings" not in payload["answer"].lower()


def test_plain_chat_missing_information_is_task_specific_not_generic_dump() -> None:
    contract = build_family_answer_contract(
        question="What does my order mean when it says reasonable contact?",
        legacy_answer="The exact wording and context matter.",
        citations=[],
        search_mode="maine_law",
        missing_information=[
            "case type and procedural posture",
            "existing orders, papers served, and upcoming court dates",
            "requested outcome stated in one sentence",
            "facts separated from conclusions",
        ],
    )
    missing = contract["what_may_be_missing"]
    assert any("exact signed-order paragraph" in item for item in missing)
    assert "case type and procedural posture" not in missing
    assert len(missing) <= 5


def test_onboarding_safety_phrase_is_unmissably_routed() -> None:
    summary = parse_intake("Someone may be unsafe")
    assert summary.task == "immediate_safety"
    assert "immediate_safety" in summary.urgency_flags

    contract = build_family_answer_contract(
        question="Someone may be unsafe",
        legacy_answer="Safety comes first.",
        citations=[],
        search_mode="maine_law",
        intake=summary,
    )
    assert contract["safety_flags"]["immediate_safety_concern"] is True
    assert "Safety comes before routine case planning" in contract["what_this_means"]
    assert "Hi. Ask" not in contract["what_this_means"]
    assert any("911" in item for item in contract["what_to_do_right_now"])


def test_archive_intake_rejects_decompression_bomb_and_hashes_safe_members() -> None:
    import io
    import zipfile

    from maine_family_law_llm.local_corpus_index import parse_bytes

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("safe-note.txt", "Hearing date October 7, 2026. Bring the signed order.")
        archive.writestr("high-ratio.txt", b"0" * (2 * 1024 * 1024))
    parsed = parse_bytes(buffer.getvalue(), suffix=".zip", locator="records.zip")
    assert parsed.metadata["archive_member_count"] == 1
    assert parsed.metadata["archive_skipped_decompression_ratio"] == 1
    assert parsed.children[0].title == "safe-note.txt"
    assert parsed.children[0].metadata["original_content_sha256"]
    assert "October 7, 2026" in parsed.text


def test_local_ocr_processes_only_missing_pdf_pages_and_preserves_native_text(
    tmp_path: Path, monkeypatch
) -> None:
    from maine_family_law_llm import local_corpus_index as indexer

    case_root = tmp_path / "case"
    index_root = case_root / "04_INDEXES"
    index_root.mkdir(parents=True)
    records = [
        {
            "evidence_id": "DOC-1",
            "title": "Mixed PDF",
            "source_type": "pdf",
            "source_locator": "mixed.pdf",
            "source_path": str(tmp_path / "mixed.pdf"),
            "parent_evidence_id": "",
            "page_number": 0,
            "parser_status": "parsed",
            "text_status": "partial_native_text",
            "ocr_status": "ocr_not_run",
            "page_count": 2,
            "text_content": "Native page one text.",
            "text_excerpt": "Native page one text.",
            "parser_metadata": {"native_text_pages": 1, "image_only_pages": 1},
            "issue_lanes": [],
        },
        {
            "evidence_id": "DOC-1-P0001",
            "title": "Mixed PDF — page 1",
            "source_type": "pdf_page",
            "source_locator": "mixed.pdf#page=1",
            "source_path": str(tmp_path / "mixed.pdf"),
            "parent_evidence_id": "DOC-1",
            "page_number": 1,
            "parser_status": "parsed",
            "text_status": "available",
            "ocr_status": "not_needed",
            "page_count": 1,
            "text_content": "Native page one text.",
            "text_excerpt": "Native page one text.",
            "parser_metadata": {"native_text": True},
            "issue_lanes": [],
        },
        {
            "evidence_id": "DOC-1-P0002",
            "title": "Mixed PDF — page 2",
            "source_type": "pdf_page",
            "source_locator": "mixed.pdf#page=2",
            "source_path": str(tmp_path / "mixed.pdf"),
            "parent_evidence_id": "DOC-1",
            "page_number": 2,
            "parser_status": "image_only_page",
            "text_status": "not_available",
            "ocr_status": "ocr_not_run",
            "page_count": 1,
            "text_content": "",
            "text_excerpt": "",
            "parser_metadata": {"native_text": False},
            "issue_lanes": [],
        },
    ]
    (index_root / "private_search_index.json").write_text(json.dumps(records), encoding="utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        indexer,
        "local_ocr_choice",
        lambda *_args, **_kwargs: {
            "status": "ready",
            "engine": {"tesseract": "test", "tesseract_version": "test-ocr"},
        },
    )

    def fake_ocr(row, engine, *, language, page_numbers=None):
        captured["page_numbers"] = set(page_numbers or set())
        return {
            "text": "OCR page two text.",
            "pages": [
                {
                    "page_number": 2,
                    "confidence": 94.0,
                    "character_count": 18,
                    "text": "OCR page two text.",
                }
            ],
            "page_count": 1,
            "confidence": 94.0,
        }

    monkeypatch.setattr(indexer, "_ocr_one", fake_ocr)
    before_metrics = local_inventory_metrics(records)
    assert before_metrics["ocr_candidate_documents"] == 1
    assert before_metrics["ocr_candidate_pages"] == 1
    assert before_metrics["searchable_pages"] == 1

    result = indexer.run_local_ocr(case_root)
    assert result["status"] == "completed"
    assert result["remaining_candidate_documents"] == 0
    assert result["remaining_candidate_pages"] == 0
    assert result["searchable_pages"] == 2
    assert captured["page_numbers"] == {2}

    updated = json.loads((index_root / "private_search_index.json").read_text(encoding="utf-8"))
    parent = next(row for row in updated if row["evidence_id"] == "DOC-1")
    assert "Native page one text." in parent["text_content"]
    assert "OCR page two text." in parent["text_content"]
    assert parent["parser_metadata"]["native_text_preserved"] is True
    page1 = next(row for row in updated if row["evidence_id"] == "DOC-1-P0001")
    page2 = next(row for row in updated if row["evidence_id"] == "DOC-1-P0002")
    assert page1["ocr_status"] == "not_needed"
    assert page2["ocr_status"] == "ocr_completed"
    assert page2["parser_metadata"]["ocr_derived"] is True


def test_inventory_metrics_do_not_count_mixed_pdf_parent_as_all_ocr_pages() -> None:
    records = [
        {
            "evidence_id": "MIXED",
            "source_type": "pdf",
            "source_locator": "mixed.pdf",
            "ocr_status": "ocr_not_run",
            "text_status": "partial_native_text",
            "page_count": 4,
            "text_content": "Native text on three pages.",
            "parser_metadata": {"image_only_pages": 1},
        },
        {
            "evidence_id": "MIXED-P0001",
            "source_type": "pdf_page",
            "parent_evidence_id": "MIXED",
            "page_number": 1,
            "ocr_status": "not_needed",
            "text_status": "available",
            "text_content": "Native page one.",
        },
        {
            "evidence_id": "MIXED-P0002",
            "source_type": "pdf_page",
            "parent_evidence_id": "MIXED",
            "page_number": 2,
            "ocr_status": "not_needed",
            "text_status": "available",
            "text_content": "Native page two.",
        },
        {
            "evidence_id": "MIXED-P0003",
            "source_type": "pdf_page",
            "parent_evidence_id": "MIXED",
            "page_number": 3,
            "ocr_status": "not_needed",
            "text_status": "available",
            "text_content": "Native page three.",
        },
        {
            "evidence_id": "MIXED-P0004",
            "source_type": "pdf_page",
            "parent_evidence_id": "MIXED",
            "page_number": 4,
            "ocr_status": "ocr_not_run",
            "text_status": "not_available",
            "text_content": "",
        },
    ]
    metrics = local_inventory_metrics(records)
    assert metrics == {
        "ocr_candidate_documents": 1,
        "ocr_candidate_pages": 1,
        "searchable_records": 4,
        "searchable_pages": 3,
    }


def test_printable_search_prioritizes_practical_family_tools_without_duplicate_variants() -> None:
    from maine_family_law_llm.focaf_library import search_printables

    served = search_printables("I was served with court papers", limit=3)
    titles = [row["title"].lower() for row in served["results"]]
    assert "before you call or file" in titles[0]
    assert sum("before you call or file" in title for title in titles) == 1
    assert all(row["authority_status"] == "not_legal_authority" for row in served["results"])
    assert all(row["match_basis"] == "extracted_content_with_practical_metadata_reranking" for row in served["results"])

    local = search_printables("Portland family resources", limit=2)
    assert "portland family resource quick sheet" in local["results"][0]["title"].lower()

    medication = search_printables("exchange medication", limit=2)
    assert "medication transfer" in medication["results"][0]["title"].lower()
