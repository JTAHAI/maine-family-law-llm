#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.verifiers import LegalOutputVerifier, SourceAuthorityIndex, extract_legal_claims
from legal.verifiers.staleness_jurisdiction import FreshnessJurisdictionTreatmentChecker


def build_report(output_path: str | Path | None = None) -> dict:
    index = SourceAuthorityIndex()
    index.add_statute("19-A", "1653", "source-statute-1653")
    index.add_case("2026", "1", "source-case-2026-me-1")
    index.add_form("FM-002", "source-form-fm-002")
    source_texts = {
        "source-statute-1653": "19-A M.R.S. § 1653 provides that parental rights and responsibilities are decided according to the best interest of the child.",
        "source-case-2026-me-1": "2026 ME 1 applied best interest findings in a parental rights appeal.",
        "source-form-fm-002": "FM-002 is the Family Matter Summary Sheet form.",
    }
    source_metadata = {
        "source-statute-1653": {
            "source_id": "source-statute-1653",
            "title": "Parental rights and responsibilities",
            "citation": "19-A M.R.S. § 1653",
            "source_class": "statute_section_reference",
            "jurisdiction": "maine",
            "authority_status": "verified_official_maine",
            "freshness_status": "current",
        },
        "source-case-2026-me-1": {
            "source_id": "source-case-2026-me-1",
            "title": "Test v. Test",
            "citation": "2026 ME 1",
            "source_class": "law_court_opinion_index",
            "jurisdiction": "maine",
            "authority_status": "verified_maine_law_court",
            "freshness_status": "current",
            "negative_treatment_status": "positive_or_neutral",
        },
        "source-form-fm-002": {
            "source_id": "source-form-fm-002",
            "title": "Family Matter Summary Sheet",
            "citation": "FM-002",
            "source_class": "court_forms_index",
            "jurisdiction": "maine",
            "authority_status": "verified_official_maine",
            "freshness_status": "current",
            "form_version_status": "current",
        },
    }
    verifier_report = LegalOutputVerifier(index).verify_output(
        text='Under 19-A M.R.S. § 1653 and 2026 ME 1, Maine uses the "best interest of the child" standard.',
        source_texts=source_texts,
        source_metadata=source_metadata,
        quotes=[{"source_id": "source-statute-1653", "quoted_text": "best interest of the child"}],
        claims=[
            {
                "claim": "Maine uses the best interest of the child standard for parental rights.",
                "source_ids": ["source-statute-1653"],
            }
        ],
    )
    unsafe_scope_report = FreshnessJurisdictionTreatmentChecker().check(
        text="Current Maine law requires this old form.",
        source_metadata={
            "old-form": {
                "source_id": "old-form",
                "source_class": "court_forms_index",
                "jurisdiction": "maine",
                "authority_status": "verified_official_maine",
                "freshness_status": "unknown",
                "form_version_status": "unknown",
            }
        },
    )
    filing_gate_report = FilingReadyGate().evaluate(
        {
            "citations_verified": True,
            "quote_spans_verified": True,
            "human_review_complete": True,
            "authority_verified": True,
            "verification_report": {"blockers": unsafe_scope_report["blockers"]},
        }
    )
    report = {
        "stage": "enterprise_pass_29_30_31_verifier_intelligence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "completed_passes": [29, 30, 31],
        "verifier_report": verifier_report,
        "auto_extracted_claims": extract_legal_claims(
            "Maine requires best interest findings. Maine requires a purple parenting certificate."
        ),
        "unsafe_scope_report": unsafe_scope_report,
        "filing_gate_report": filing_gate_report,
        "status": "pass"
        if verifier_report["filing_ready_possible"]
        and unsafe_scope_report["blockers"]
        and filing_gate_report["export_status"] == "blocked"
        else "fail",
        "readiness": "Citation/quote, claim-support, stale-law, jurisdiction, negative-treatment, and form freshness verification plumbing is runnable; production thresholds still require attorney-reviewed gold metrics.",
    }
    if output_path:
        Path(output_path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "smoke_evidence_pass29_pass30_pass31_verifier_intelligence.json"
    evidence = build_report(output)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    raise SystemExit(0 if evidence["status"] == "pass" else 1)
