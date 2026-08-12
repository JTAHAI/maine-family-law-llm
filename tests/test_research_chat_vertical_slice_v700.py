from __future__ import annotations

from pathlib import Path

from maine_family_law_llm import api
from maine_family_law_llm.family_answer_contract import build_family_answer_contract, render_legacy_answer


class _AdmittedAuthorityFixture:
    def search(self, query: str, *, limit: int = 5) -> dict[str, object]:
        del query, limit
        text = "3. Best interest of child. The court shall apply the best-interest standard."
        return {
            "status": "pass",
            "build_id": "fixture-admitted-build",
            "retrieved_sources": [
                {
                    "source_id": "statute-19-a-1653",
                    "score": 1000.0,
                    "method": "admitted_exact_citation",
                    "matched_terms": ["exact_citation"],
                    "source_card": {"citation": "19-A M.R.S. § 1653(3)"},
                    "document": {
                        "source_id": "statute-19-a-1653",
                        "document_id": "statute-19-a-1653",
                        "chunk_id": "statute-19-a-1653:chunk:0",
                        "title": "19-A M.R.S. § 1653",
                        "citation": "19-A M.R.S. § 1653",
                        "text": text,
                        "source_class": "statute_section",
                        "jurisdiction": "maine",
                        "authority_status": "verified_official_maine",
                        "freshness_status": "known_extracted_timestamp",
                        "url_or_path": "https://legislature.maine.gov/statutes/19-A/title19-Asec1653.html",
                        "metadata": {"hash": "a" * 64},
                    },
                }
            ],
            "citation_resolution_context": [
                {
                    "status": "found",
                    "source_id": "statute-19-a-1653",
                    "authority_status": "verified_official_maine",
                    "citation": {"normalized": "19-A M.R.S. § 1653(3)"},
                    "metadata": {
                        "freshness_status": "known_extracted_timestamp",
                        "source_hash": "a" * 64,
                        "source_span": {"start_offset": 0, "end_offset": len(text)},
                    },
                }
            ],
            "review_required": True,
        }

    def get_source_span(self, source_id: str, *, start_offset: int, end_offset: int) -> dict[str, object]:
        assert source_id == "statute-19-a-1653"
        text = "3. Best interest of child. The court shall apply the best-interest standard."
        return {
            "status": "pass",
            "source_id": source_id,
            "source_span": {"start_offset": start_offset, "end_offset": end_offset},
            "source_span_preview": text[start_offset:end_offset],
            "review_required": True,
        }


def test_research_brief_is_source_scoped_and_reviewable_end_to_end() -> None:
    result = api.ask(
        api.AskRequest(
            question="What are Maine's best-interest factors?",
            answer_style="research_brief",
            search_mode="maine_law",
            session_id="research-brief-v700",
        )
    )

    brief = result["structured_answer"]["research_brief"]
    assert result["answer_style"] == "research_brief"
    assert result["structured_answer"]["answer_style"] == "research_brief"
    assert brief["schema_version"] == "research_brief_v1"
    assert brief["research_question"] == "What are Maine's best-interest factors?"
    assert "Maine-law authorities" in brief["scope"]
    assert brief["source_review_order"]
    assert all(item["lane"] == "Maine law" for item in brief["source_review_order"])
    assert "Research scope" in result["answer"]
    assert "Source review order" in result["answer"]
    assert result["review_required"] is True


def test_store_research_uses_admitted_authority_and_exact_span(monkeypatch) -> None:
    monkeypatch.setenv("MFL_RUNTIME_MODE", "store")
    monkeypatch.setattr(api, "AuthorityProductService", _AdmittedAuthorityFixture)

    result = api.ask(api.AskRequest(question="What does 19-A M.R.S. § 1653(3) say?"))

    assert result["grounded"] is True
    assert result["review_required"] is True
    assert result["citations"][0]["source_id"] == "statute-19-a-1653"
    assert result["citations"][0]["metadata"]["fixture_fallback_used"] is False
    assert result["citations"][0]["metadata"]["source_hash"] == "a" * 64
    assert result["citations"][0]["metadata"]["source_span"] == {
        "start_offset": 0,
        "end_offset": 76,
    }
    assert "exact retrieved source span" in result["answer"].lower()


def test_store_research_fails_closed_when_authority_product_is_unavailable(monkeypatch) -> None:
    class _UnavailableAuthority:
        def search(self, query: str, *, limit: int = 5) -> dict[str, object]:
            del query, limit
            raise RuntimeError("unavailable")

    monkeypatch.setenv("MFL_RUNTIME_MODE", "store")
    monkeypatch.setattr(api, "AuthorityProductService", _UnavailableAuthority)

    result = api.ask(api.AskRequest(question="What does 19-A M.R.S. § 1653(3) say?"))

    assert result["grounded"] is False
    assert result["citations"] == []
    assert result["failure_class"] == "official_authority_product_unavailable"
    assert "No bundled fixture or model memory was substituted" in result["answer"]


def test_research_brief_identifies_missing_authority_without_fabricating_support() -> None:
    contract = build_family_answer_contract(
        question="What law applies to my unusual situation?",
        legacy_answer="No source-backed conclusion was available.",
        citations=[],
        search_mode="maine_law",
        answer_style="research_brief",
    )

    brief = contract["research_brief"]
    assert brief["source_review_order"] == []
    assert any("No retrieved Maine-law authority" in issue for issue in brief["open_issues"])
    rendered = render_legacy_answer(contract)
    assert "Research scope" in rendered
    assert "Open research issues" in rendered


def test_research_brief_control_and_typed_rendering_are_present_in_workbench() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    js = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")

    assert 'option value="research_brief">Research brief' in html
    assert "structured.answer_style === 'research_brief'" in js
    assert "Open research issues" in js
    assert "Review sources in this order" in js
    assert "Use as draft:" in js
    assert "Follow-up drafted. Review it, then send when ready." in js
    assert "research_handoff" in js
    assert "Open research issues" in js
    assert "What could not be established" in js
    assert "This is a recovery path" in js
    assert "Ask about source" in js
    assert "Source-focused follow-up drafted" in js
