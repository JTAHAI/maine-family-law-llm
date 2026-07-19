from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest
from pypdf import PdfReader

from maine_family_law_llm.focaf_library import load_inventory, printable_pdf_path, search_printables
from maine_family_law_llm.local_corpus_index import local_ocr_choice, rebuild_local_content_index
from maine_family_law_llm.local_only_boundary import LocalOnlyNetworkBlocked, local_only_network_boundary


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_manifest(case_root: Path, source: Path) -> None:
    manifest = case_root / "08_SOURCE_MANIFESTS_HASHES" / "source_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            [
                {
                    "evidence_id": "EV-OCR-001",
                    "source_path": str(source),
                    "source_hash": _sha256(source),
                    "source_type": "image",
                    "issue_lanes": ["record_review"],
                    "privacy_status": "private",
                    "text_excerpt": "",
                }
            ]
        ),
        encoding="utf-8",
    )


def test_focaf_inventory_is_hashed_page_provenanced_and_non_authority() -> None:
    inventory = load_inventory()
    documents = inventory["documents"]

    assert len(documents) == 103
    assert sum(int(document["page_count"]) for document in documents) == 739
    assert sum(len(document["chunks"]) for document in documents) == 1092
    assert all(document["manifest_hash_matches"] for document in documents)
    assert all(document["native_text_status"] == "available" for document in documents)
    assert all(document["authority_status"] == "not_legal_authority" for document in documents)
    assert all(document["chunks"] and document["chunks"][0]["page_number"] >= 1 for document in documents)

    sample = documents[0]
    pdf_path = printable_pdf_path(sample["document_id"])
    assert pdf_path is not None and pdf_path.read_bytes().startswith(b"%PDF")
    assert len(PdfReader(str(pdf_path)).pages) == sample["page_count"]


def test_focaf_search_uses_actual_page_text_not_filename_only_terms() -> None:
    results = search_printables("calm message", limit=3)
    assert results["resource_lane"] == "family_printable_secondary_resource"
    assert results["authority_status"] == "not_legal_authority"
    assert results["results"]
    assert any("Calm Communication" in row["title"] for row in results["results"])
    assert all(row["matched_pages"] and row["snippet"] for row in results["results"])

    filename_only = search_printables("xqzvwmplk", limit=3)
    assert filename_only["results"] == []
    library_source = (ROOT / "src" / "maine_family_law_llm" / "focaf_library.py").read_text(encoding="utf-8")
    assert 'document["original_filename"]' not in library_source[library_source.index("def search_printables"):]


def test_local_index_boundary_blocks_socket_and_dns() -> None:
    with local_only_network_boundary():
        with pytest.raises(LocalOnlyNetworkBlocked):
            socket.getaddrinfo("example.test", 443)
        with pytest.raises(LocalOnlyNetworkBlocked):
            socket.create_connection(("example.test", 443))


def test_ocr_is_separate_opt_in_and_declining_keeps_sources_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "scanned_page.png"
    source.write_bytes(b"not-a-real-image-but-metadata-only")
    case_root = tmp_path / "case"
    _write_manifest(case_root, source)
    before = _sha256(source)

    proof = rebuild_local_content_index(case_root)
    declined = local_ocr_choice(case_root, approved=False)
    attempted = local_ocr_choice(case_root, approved=True)

    assert proof["inventory_status"] == "ocr_choice_required"
    assert declined["status"] == "declined"
    assert declined["candidate_files"][0]["source_locator"] == source.name
    assert attempted["status"] == "unavailable"
    assert attempted["ocr_derived_text_created"] == 0
    assert _sha256(source) == before


def test_launcher_requires_explicit_inventory_consent_and_separate_ocr_choice() -> None:
    source = (ROOT / "app" / "launcher.py").read_text(encoding="utf-8")
    consent = "The app will read the files you selected on this computer and create a local search index so chat can search inside them. Nothing is uploaded or transmitted."
    ocr = "OCR will analyze scanned or image-only pages on this computer and add recognized text to your local search index. OCR text may contain mistakes. Nothing is uploaded or transmitted."

    assert 'dialog.title("Build a local searchable inventory?")' in source
    assert consent in source
    assert 'text="Scan and inventory locally"' in source
    assert 'text="Cancel"' in source
    assert 'decision = tk.BooleanVar(value=False)' in source
    assert source.index("if not self._confirm_local_inventory_consent():") < source.index("def _worker() -> object:")
    assert 'dialog.title("Some pages need local OCR")' in source
    assert ocr in source
    assert 'text="OCR scanned pages locally"' in source
    assert 'text="Keep them unsearchable for now"' in source
    assert 'dialog.bind("<Escape>"' in source


def test_direct_record_search_bypasses_generic_family_answer_template() -> None:
    from maine_family_law_llm.api import AskRequest, _finalize_family_response

    result = _finalize_family_response(
        {
            "question": "search contents for obstruction",
            "answer": "Search result:\n- Exact content match: found in the selected matter.",
            "direct_record_search": True,
            "citations": [{"title": "Record", "metadata": {"exact_content_match": True}}],
            "metadata": {},
            "safety": {},
        },
        AskRequest(question="search contents for obstruction", search_mode="my_records"),
    )

    assert result["direct_record_search"] is True
    assert result["answer"].startswith("Search result:")
    assert "structured_answer" not in result
    assert result["citations"][0]["metadata"]["source_lane"] == "private_record"


def test_printables_and_local_indexes_are_packaged_separately() -> None:
    spec = (ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec").read_text(encoding="utf-8")
    html = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    js = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")

    assert '"resources" / "focaf"' in spec
    assert "family_printable_secondary_resource" in (ROOT / "src" / "maine_family_law_llm" / "focaf_library.py").read_text(encoding="utf-8")
    assert 'id="delete-index-button"' in html
    assert "Delete local index" in html
    assert "/api/corpus-delete-index" in js
    assert "Original source documents remain unchanged" in html
