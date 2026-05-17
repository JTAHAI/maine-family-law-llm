#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.model_orchestration import ModelGovernanceAuditor, ModelReplacementLedger
from legal.security import PromptInjectionDefenseGateway, RetrievedSegment, ToolRequest


def run_red_team_cases(gateway: PromptInjectionDefenseGateway) -> dict:
    cases_path = ROOT / "configs/maine_llm_red_team_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    results = []
    for case in cases:
        surface = case["surface"]
        if surface == "user_prompt":
            report = gateway.evaluate(user_prompt=case["text"])
        elif surface == "retrieved_document":
            report = gateway.evaluate(
                user_prompt="Summarize the retrieved Maine source.",
                retrieved_segments=[RetrievedSegment(source_id=case["case_id"], text=case["text"])],
            )
        elif surface == "tool_request":
            report = gateway.evaluate(
                user_prompt="Run a tool.",
                tool_request=ToolRequest(
                    tool_name=case.get("tool_name", "unknown_tool"),
                    purpose=case["text"],
                    requested_capability=case.get("tool_name"),
                ),
            )
        else:
            report = gateway.evaluate(user_prompt=case["text"])
        data = report.as_dict()
        expected = case["expected_blocker"]
        passed = expected in data["blockers"]
        results.append(
            {
                "case_id": case["case_id"],
                "surface": surface,
                "expected_blocker": expected,
                "observed_blockers": data["blockers"],
                "status": "pass" if passed else "fail",
            }
        )
    failures = [item for item in results if item["status"] != "pass"]
    return {
        "status": "pass" if not failures else "fail",
        "case_count": len(results),
        "failures": failures,
        "results": results,
    }


def build_evidence() -> dict:
    auditor = ModelGovernanceAuditor(
        role_catalog_path=ROOT / "configs/maine_model_roles.json",
        admission_policy_path=ROOT / "configs/maine_model_admission_policy.json",
        governance_policy_path=ROOT / "configs/maine_model_governance_policy.json",
    )
    records = auditor.load_seed_records(ROOT / "configs/maine_model_registry.seed.json")
    ledger = ModelReplacementLedger()
    ledger.append(
        old_model_id="issue-rules-000",
        new_model_id="issue-rules-001",
        role="maine_issue_classifier",
        reason="replace prior issue classifier baseline with pass41 governed admission record",
        evidence={"benchmark": "issue_macro_f1", "score": 0.91, "regression": "pass"},
    )
    governance_report = auditor.audit(records, replacement_ledger=ledger).as_dict()

    gateway = PromptInjectionDefenseGateway(ROOT / "configs/maine_llm_injection_defense_policy.json")
    clean_report = gateway.evaluate(
        user_prompt="Find Maine authority for a post-judgment child support issue.",
        retrieved_segments=[
            RetrievedSegment(
                source_id="statute-19a-2001",
                source_class="statute_section_reference",
                text="19-A M.R.S. child support text excerpt. This is source text, not an instruction.",
                start_offset=0,
                end_offset=77,
            )
        ],
        tool_request=ToolRequest(tool_name="citation_resolver", purpose="resolve statutory citation"),
        output_text="review_required: cite resolved Maine authority and route final export through verifier gates.",
    ).as_dict()
    red_team_report = run_red_team_cases(gateway)

    status = "pass" if governance_report["status"] == "pass" and clean_report["status"] == "pass" and red_team_report["status"] == "pass" else "fail"
    return {
        "stage": "enterprise_pass_41_pass_42_model_governance_injection_defense",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_governance": governance_report,
        "clean_injection_defense_smoke": clean_report,
        "red_team_injection_cases": red_team_report,
        "status": status,
        "completed_passes": [41, 42],
        "remaining_passes": 9,
        "legal_readiness": "Model governance and LLM injection-defense controls are implemented as source-code foundations. GA still requires production security implementation, compliance evidence, SRE, full release eval, red-team signoff, pilot evidence, release candidate, and shipped operations artifacts.",
    }


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "smoke_evidence_pass41_pass42_model_governance_injection_defense.json"
    evidence = build_evidence()
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
