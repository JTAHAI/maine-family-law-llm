#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.drafting import DraftReviewer, Rule52BestInterestFindingsEngine
from legal.forms import FormCatalogBuilder
from legal.law_court import LawCourtIntelligenceExtractor


def build_evidence() -> dict:
    opinion = """
    Smith v. Smith
    Docket: FAM-25-12
    Decided: May 1, 2026
    In this post-judgment appeal, we review parental rights for abuse of discretion and findings for clear error.
    The court failed to make findings under Rule 52 and did not address best interest evidence.
    We vacate and remand because the lack of findings prevents appellate review.
    """
    brief = LawCourtIntelligenceExtractor().extract_case_brief(opinion, source_id="case-smoke", citation="2026 ME 99")

    forms = FormCatalogBuilder().build_catalog(
        [
            {
                "source_id": "form-fm-001",
                "form_id": "FM-001",
                "title": "FM-001 Complaint for Divorce with Children",
                "version_date": "01/2024",
                "text": "Docket Number: Plaintiff: Defendant: Child name: Signature: Depends on 19-A M.R.S. § 1653 and M.R. Civ. P. 120.",
            }
        ],
        current_versions={"FM-001": "01/2026"},
    ).to_dict()

    findings = Rule52BestInterestFindingsEngine().review_order(
        "Final order on parental rights. The prior protection from abuse order is adopted. Father shall have supervised contact.",
        posture="final_order",
    ).to_dict()

    draft_review = DraftReviewer().review(
        {
            "caption": "Smith v. Smith",
            "facts": "Facts.",
            "requested_relief": "Relief.",
            "source_cards": [{"source_id": "case-smoke"}],
            "authority_matrix": [{"source_id": "case-smoke"}],
            "citation_report": {"status": "pass"},
            "quote_report": {"status": "pass"},
            "human_review_complete": True,
            "law_court_briefs": [brief],
        }
    )

    status = "pass"
    if "missing Rule 52 findings" not in brief["appellate_red_flags"]:
        status = "fail"
    if "FM-001" not in forms["stale_forms"]:
        status = "fail"
    if "contact_restriction_without_supported_findings" not in findings["blockers"]:
        status = "fail"
    if not any(blocker.startswith("appellate_red_flag:") for blocker in draft_review["blockers"]):
        status = "fail"

    return {
        "stage": "enterprise_pass_32_33_34_maine_specific_intelligence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "law_court_brief": brief,
        "form_catalog": forms,
        "findings_review": findings,
        "draft_review": draft_review,
        "status": status,
        "readiness": "Pass 32-34 deterministic Maine appellate, forms, and findings intelligence is runnable. Attorney review and live official-source execution remain required for legal sufficiency claims.",
    }


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "sample-evidence" / "smoke_evidence_pass32_pass33_pass34_maine_intelligence.json"
    evidence = build_evidence()
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
