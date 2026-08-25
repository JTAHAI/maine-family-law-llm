from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

from maine_family_law_llm import api
from maine_family_law_llm.answer_support_integrity import assess_answer_support_integrity
from maine_family_law_llm.handoff_integrity import build_handoff_safe_source_card
from maine_family_law_llm.input_integrity import harden_text_input, normalize_session_id

ROOT = Path(__file__).resolve().parents[1]


def _legal_card(snippet: str, *, freshness: str = "verified_current") -> dict:
    return {
        "source_id": "LAW-1653",
        "title": "Maine best-interest statute",
        "citation": "19-A M.R.S. § 1653",
        "snippet": snippet,
        "metadata": {
            "source_lane": "legal_authority",
            "official": True,
            "source_type": "statute",
            "jurisdiction": "Maine",
            "freshness_status": freshness,
            "current_law_verified": freshness == "verified_current",
        },
    }


def _record_card() -> dict:
    return {
        "source_id": "REC-7",
        "title": "Message export",
        "snippet": "DOB: 01/02/2012, call 207-555-1212, email child@example.com",
        "metadata": {
            "source_lane": "private_record",
            "source_locator": r"C:\\Users\\Person\\Private Matter\\message.pdf",
            "absolute_path": r"C:\\Users\\Person\\Private Matter\\message.pdf",
            "page_number": 7,
            "raw_text": "private raw text",
        },
    }


def test_pass_36_input_integrity_neutralizes_invisible_controls_and_bounds_text() -> None:
    result = harden_text_input("  What\u202e is\x00 Maine law?  ", max_length=12)
    assert "\u202e" not in result.value
    assert "\x00" not in result.value
    assert result.truncated is True
    assert result.report()["removed_bidi_count"] == 1
    assert result.report()["removed_null_count"] == 1
    assert "input_truncated_to_local_limit" in result.report()["flags"]

    accepted, report = normalize_session_id("550e8400-e29b-41d4-a716-446655440000")
    assert accepted
    assert report["accepted"] is True
    rejected, report = normalize_session_id("../../private matter")
    assert rejected == ""
    assert report["reason"] == "invalid_session_identifier_format"


def test_pass_36_api_reports_request_hardening_without_echoing_raw_input() -> None:
    result = api.ask(
        api.AskRequest(
            question="What\u202e are Maine's best-interest factors?\x00",
            session_id="not a valid/session id",
            search_mode="maine_law",
        )
    )
    report = result["request_integrity"]
    assert "unicode_direction_controls_removed" in report["security_flags"]
    assert "null_bytes_removed" in report["security_flags"]
    assert "invalid_session_identifier_rejected" in report["security_flags"]
    assert report["raw_input_stored"] is False
    assert "not a valid/session id" not in json.dumps(report)
    assert result["security_warnings"]


def test_pass_37_claim_support_integrity_is_conservative_and_blocks_stale_or_unsupported() -> None:
    supported = assess_answer_support_integrity(
        "Maine law requires the court to consider the best interest of the child.",
        [_legal_card("The court shall consider the best interest of the child.")],
        grounding_integrity={"current_law_verified": True, "stale_or_superseded_count": 0},
    )
    assert supported["candidate_legal_claim_count"] == 1
    assert supported["status_counts"]["supported"] == 1
    assert supported["filing_ready"] is False

    unsupported = assess_answer_support_integrity(
        "Maine law requires automatic sole custody after one missed exchange.",
        [_legal_card("The court shall consider the best interest of the child.")],
        grounding_integrity={"current_law_verified": True, "stale_or_superseded_count": 0},
    )
    assert "candidate_legal_claims_without_lexical_source_support" in unsupported["blockers"]

    stale = assess_answer_support_integrity(
        "Under Maine law, the court must consider the best interest of the child.",
        [_legal_card("The court shall consider the best interest of the child.", freshness="stale_or_superseded")],
        grounding_integrity={"current_law_verified": False, "stale_or_superseded_count": 1},
    )
    assert "stale_or_superseded_source_in_claim_support_set" in stale["blockers"]
    assert "current_law_language_requires_live_official_verification" in stale["blockers"]


def test_pass_37_chat_contract_exposes_claim_support_diagnostics() -> None:
    result = api.ask(
        api.AskRequest(
            question="What are Maine's best-interest factors?",
            search_mode="maine_law",
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )
    )
    support = result["answer_support_integrity"]
    assert result["structured_answer"]["schema_version"] == "family_answer_v4_1"
    assert result["structured_answer"]["answer_support_integrity"] == support
    assert support["human_review_required"] is True
    assert support["filing_ready"] is False
    assert "Claim-to-source review" in result["answer"]


def test_pass_38_default_handoff_omits_private_excerpt_and_absolute_path() -> None:
    safe = build_handoff_safe_source_card(_record_card())
    encoded = json.dumps(safe)
    assert safe["snippet"] == "[private record excerpt omitted from default handoff]"
    assert safe["metadata"]["source_locator_basename"] == "message.pdf"
    assert safe["metadata"]["private_content_omitted_by_default"] is True
    assert "C:\\\\Users" not in encoded
    assert "private raw text" not in encoded
    assert "date_of_birth_label" in safe["metadata"]["sensitive_data_categories"]
    assert "phone_number" in safe["metadata"]["sensitive_data_categories"]
    assert "email_address" in safe["metadata"]["sensitive_data_categories"]


def test_pass_38_api_and_browser_use_reviewer_safe_source_cards_by_default() -> None:
    result = api.ask(
        api.AskRequest(
            question="What are Maine's best-interest factors?",
            search_mode="maine_law",
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )
    )
    assert len(result["handoff_safe_source_cards"]) == result["source_card_count"]
    assert result["metadata"]["handoff_integrity"]["default_export_is_redacted"] is True

    js = (ROOT / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "lastHandoffSources" in js
    assert "Redacted reviewer-safe source cards copied." in js
    assert "confirmFullLocalExport" in js
    assert "This full local export includes private-record excerpts" in js


def _load_release_builder():
    path = ROOT / "scripts/build-deterministic-source-release.py"
    spec = importlib.util.spec_from_file_location("deterministic_release_builder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pass_38_deterministic_release_builder_reproduces_bytes_and_excludes_runtime(tmp_path: Path) -> None:
    module = _load_release_builder()
    repo = tmp_path / "repo"
    (repo / "src/maine_family_law_llm/resources/focaf").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "runtime").mkdir()
    (repo / "store/msix").mkdir(parents=True)
    (repo / "docs/readme.txt").write_text("hello\n", encoding="utf-8")
    (repo / "runtime/private.db").write_bytes(b"private")
    (repo / "store/msix/identity.local.json").write_text("{}\n", encoding="utf-8")
    (repo / "docs/private.local.json").write_text("{}\n", encoding="utf-8")
    (repo / "src/maine_family_law_llm/resources/focaf/public.pdf").write_bytes(b"%PDF-public")
    first = tmp_path / "one.zip"
    second = tmp_path / "two.zip"
    report_one = module.build_release(repo, first, "ME_FM_LLM")
    report_two = module.build_release(repo, second, "ME_FM_LLM")
    assert report_one["zip_sha256"] == report_two["zip_sha256"]
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        assert "ME_FM_LLM/RELEASE_SOURCE_MANIFEST.json" in names
        assert "ME_FM_LLM/docs/readme.txt" in names
        assert "ME_FM_LLM/src/maine_family_law_llm/resources/focaf/public.pdf" in names
        assert "ME_FM_LLM/store/msix/identity.local.json" in names
        assert "ME_FM_LLM/docs/private.local.json" not in names
        assert all("private.db" not in name for name in names)


def test_pass_38_source_zip_audit_allows_only_bundled_public_focaf_pdfs(tmp_path: Path) -> None:
    import subprocess

    required = {
        "openapi.json",
        "docs/api-contract-test-report.json",
        "docs/ui-completion-report.json",
        "docs/model_registry_admission_report.json",
        "docs/llm_injection_red_team_report.json",
        "docs/enterprise-security-test-report.json",
        "docs/governance-compliance-packet-report.json",
        "docs/sre-reliability-report.json",
        "configs/maine_true_ga_pass_tracker.json",
        "configs/maine_ga_pass_evidence_requirements.json",
    }
    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as archive:
        for path in required:
            archive.writestr(f"ME_FM_LLM/{path}", "{}")
        archive.writestr("ME_FM_LLM/src/maine_family_law_llm/resources/focaf/public.pdf", b"%PDF")
    completed = subprocess.run(
        ["python", str(ROOT / "scripts/audit-source-zip-contents.py"), str(good)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout)["allowed_public_pdf_count"] == 1

    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        for path in required:
            archive.writestr(f"ME_FM_LLM/{path}", "{}")
        archive.writestr("ME_FM_LLM/private_case.pdf", b"%PDF")
    completed = subprocess.run(
        ["python", str(ROOT / "scripts/audit-source-zip-contents.py"), str(bad)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "prohibited_release_zip_entry:private_case.pdf" in json.loads(completed.stdout)["blockers"]


def test_v380_version_and_store_revision_are_aligned() -> None:
    from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, UI_PASS_MARKER, VERSION

    assert VERSION == "8.0.0"
    assert PACKAGE_VERSION == "8.0.0.0"
    assert BUILD_NUMBER == 53
    assert UI_PASS_MARKER == "v8.0.0-ga"
    assert json.loads((ROOT / "store/msix/identity.local.json").read_text(encoding="utf-8"))["package_version"] == PACKAGE_VERSION
