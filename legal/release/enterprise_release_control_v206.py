from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from legal.pilot import LaunchEvidenceGate, build_launch_evidence_templates

VERSION = "2.06.0"
PACKET_SCHEMA = "maine_family_law_llm.enterprise_release_control.packet.v1"
AUDIT_SCHEMA = "maine_family_law_llm.enterprise_release_control.audit.v1"
TEST_SUMMARY_SCHEMA = "maine_family_law_llm.enterprise_release_control.test_summary.v1"
DETERMINISTIC_GENERATED_AT = "2026-06-05T00:00:00Z"

DISCLAIMER = (
    "Enterprise release control is a fail-closed operator workflow. It does not "
    "create attorney review, legal signoff, pilot evidence, production deployment, "
    "or GA shipment evidence. The release is enterprise_ready only when the external "
    "Pass 48-51 launch evidence gate passes with real signed artifacts."
)

FORBIDDEN_RELEASE_CLAIMS = (
    "production_legal_ready_without_external_evidence",
    "attorney_review_completed_without_signed_pilot_report",
    "real_matter_pilot_completed_without_consent_and_isolation_evidence",
    "ga_release_candidate_signed_without_security_legal_product_ops_approval",
    "ga_shipped_without_external_shipment_manifest_and_all_controls",
    "filing_ready_without_source_citation_quote_fact_form_posture_and_human_review_gates",
)

ENTERPRISE_CONTROL_AREAS = (
    {
        "control_id": "official_authority",
        "label": "Official Maine authority",
        "release_requirement": "Live official-source manifests, parsed authority, retrieval indexes, and freshness reports must live outside the source repo.",
    },
    {
        "control_id": "legal_quality",
        "label": "Legal quality gates",
        "release_requirement": "Citation, quote-span, claim-support, staleness, jurisdiction, and form-freshness metrics must pass from accepted external evidence.",
    },
    {
        "control_id": "attorney_review",
        "label": "Attorney review",
        "release_requirement": "Attorney sandbox and limited pilot reports must be signed externally with reviewer, consent, and incident fields.",
    },
    {
        "control_id": "matter_privacy",
        "label": "Matter privacy",
        "release_requirement": "Private matter data must stay outside the repo, outside shared-model training by default, and inside isolated encrypted stores.",
    },
    {
        "control_id": "security_governance",
        "label": "Security and governance",
        "release_requirement": "Security, governance, incident, audit, rollback, and maintenance evidence must be approved before RC signoff.",
    },
    {
        "control_id": "deployment_ops",
        "label": "Deployment and operations",
        "release_requirement": "A clean deployment, source ZIP, external data manifests, runbooks, rollback package, and owner signoff must exist.",
    },
)


def _stable_path(path: str | Path) -> str:
    return str(Path(path)).replace("\\", "/")


def _launch_gate_report(pilot_root: str | Path, release_root: str | Path | None) -> dict[str, Any]:
    report = LaunchEvidenceGate().audit(pilot_root=pilot_root, release_root=release_root).as_dict()
    report["generated_at"] = DETERMINISTIC_GENERATED_AT
    return report


def build_external_evidence_checklist() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template in build_launch_evidence_templates():
        payload = template.payload
        row = {
            "pass": template.pass_number,
            "root": template.root,
            "filename": template.filename,
            "description": template.description,
            "default_status": payload.get("status"),
            "required_keys": sorted(payload.keys()),
            "private_data_allowed": False,
            "must_be_external": True,
        }
        if template.pass_number == 50:
            row["required_signoff_roles"] = ["security", "legal", "product", "ops"]
        if template.pass_number == 51:
            row["required_controls"] = sorted((payload.get("controls") or {}).keys())
        rows.append(row)
    return rows


def build_operator_action_plan(packet: dict[str, Any]) -> list[dict[str, str]]:
    open_passes = set(packet.get("launch_gate_report", {}).get("open_passes", []))
    actions: list[dict[str, str]] = []
    if 48 in open_passes:
        actions.append(
            {
                "step": "pass48_attorney_sandbox",
                "action": "Run an attorney-only sandbox with public/synthetic prompts, verify reviewer bar status, complete onboarding, review the feedback queue, and sign the external attorney_sandbox_pilot_report.json.",
            }
        )
    if 49 in open_passes:
        actions.append(
            {
                "step": "pass49_limited_real_matter_pilot",
                "action": "Run a limited real-matter pilot only with explicit consent, tenant isolation, encryption, daily review, attorney signoff, zero leakage, and zero unsupported filing-ready exports.",
            }
        )
    if 50 in open_passes:
        actions.append(
            {
                "step": "pass50_release_candidate",
                "action": "Freeze a release-candidate artifact inventory and collect security, legal, product, and ops approvals with zero open P0/P1 blockers.",
            }
        )
    if 51 in open_passes:
        actions.append(
            {
                "step": "pass51_ga_shipment",
                "action": "Ship only after the RC passed, clean deployment and external manifests exist, all GA controls are true, and ga_shipment_signoff.json is signed.",
            }
        )
    actions.extend(
        [
            {
                "step": "run_fail_closed_gate",
                "action": "Run scripts/run-pass48-51-launch-evidence-gates.py against the external pilot and release roots with --require-ready.",
            },
            {
                "step": "preserve_repo_boundary",
                "action": "Do not commit private matter data, source corpora, parsed authority stores, retrieval indexes, eval stores, model weights, runtime DBs, or .env files.",
            },
        ]
    )
    return actions


def build_enterprise_release_packet(
    *,
    pilot_root: str | Path = ".missing_external_launch_evidence/pilot",
    release_root: str | Path | None = ".missing_external_launch_evidence/release",
    version: str = VERSION,
    generated_at: str = DETERMINISTIC_GENERATED_AT,
) -> dict[str, Any]:
    launch_gate = _launch_gate_report(pilot_root, release_root)
    open_passes = launch_gate.get("open_passes", [])
    closed_passes = launch_gate.get("closed_passes", [])
    enterprise_ready = launch_gate.get("status") == "pass" and open_passes == []
    blockers = list(launch_gate.get("blockers", []))
    if not enterprise_ready:
        blockers.insert(0, "enterprise_release_blocked_until_pass48_51_external_evidence_passes")

    packet = {
        "schema": PACKET_SCHEMA,
        "version": version,
        "generated_at": generated_at,
        "status": "enterprise_ready" if enterprise_ready else "blocked_external_launch_evidence_required",
        "enterprise_ready": enterprise_ready,
        "production_legal_ready": enterprise_ready,
        "ga_shipped": enterprise_ready,
        "pilot_root": _stable_path(pilot_root),
        "release_root": _stable_path(release_root or pilot_root),
        "remaining_passes": open_passes,
        "closed_launch_passes": closed_passes,
        "launch_gate_report": launch_gate,
        "external_evidence_checklist": build_external_evidence_checklist(),
        "enterprise_control_areas": list(ENTERPRISE_CONTROL_AREAS),
        "operator_action_plan": [],
        "release_blockers": sorted(set(blockers)),
        "forbidden_release_claims": list(FORBIDDEN_RELEASE_CLAIMS),
        "legal_safety_defaults": {
            "review_required_by_default": True,
            "filing_ready_by_default": False,
            "generator_self_certifies_legal_correctness": False,
            "official_registry_outweighs_model_memory": True,
            "private_matter_training_by_default": False,
        },
        "export_metadata": {
            "deterministic_offline": True,
            "source_repo_release_evidence_only": True,
            "external_evidence_required": True,
            "private_matter_data_included": False,
            "evidence_outputs": [
                "docs/external-evidence/enterprise_release_control_v206_packet.json",
                "docs/external-evidence/enterprise_release_control_v206_audit.json",
                "docs/external-evidence/enterprise_release_control_v206.html",
                "docs/external-evidence/enterprise_release_control_v206_test_summary.json",
            ],
        },
        "claims": {
            "legal_advice": False,
            "filing_ready": False,
            "attorney_review_completed": enterprise_ready,
            "limited_real_matter_pilot_completed": enterprise_ready,
            "release_candidate_signed": enterprise_ready,
            "ga_shipment_completed": enterprise_ready,
            "private_data_packaged": False,
        },
        "disclaimer": DISCLAIMER,
    }
    packet["operator_action_plan"] = build_operator_action_plan(packet)
    return packet


def build_audit(packet: dict[str, Any] | None = None, html_text: str = "") -> dict[str, Any]:
    packet = packet or build_enterprise_release_packet()
    html_text = html_text or render_enterprise_release_html(packet)
    checks = {
        "packet_schema_present": packet.get("schema") == PACKET_SCHEMA,
        "default_fail_closed": packet.get("enterprise_ready") is False,
        "production_legal_ready_false_by_default": packet.get("production_legal_ready") is False,
        "remaining_launch_passes_visible": packet.get("remaining_passes") == [48, 49, 50, 51],
        "external_evidence_checklist_complete": [row["pass"] for row in packet.get("external_evidence_checklist", [])] == [48, 49, 50, 51],
        "no_private_data_packaged": packet.get("export_metadata", {}).get("private_matter_data_included") is False,
        "forbidden_claims_listed": bool(packet.get("forbidden_release_claims")),
        "legal_safety_defaults_preserved": packet.get("legal_safety_defaults", {}).get("filing_ready_by_default") is False,
        "html_markers_present": all(
            marker in html_text
            for marker in (
                "Enterprise Release Control",
                "enterprise_ready=false",
                "production_legal_ready=false",
                "Pass 48",
                "Pass 51",
                "release-blocker-card",
                "external-evidence-checklist",
            )
        ),
    }
    return {
        "schema": AUDIT_SCHEMA,
        "version": VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "production_legal_ready": False,
        "ga_shipped": False,
    }


def build_test_summary(packet: dict[str, Any] | None = None, html_text: str = "") -> dict[str, Any]:
    packet = packet or build_enterprise_release_packet()
    html_text = html_text or render_enterprise_release_html(packet)
    checks = {
        "launch_gate_blocks_missing_evidence": packet["launch_gate_report"]["status"] == "blocked",
        "pass48_51_open_by_default": packet["remaining_passes"] == [48, 49, 50, 51],
        "no_enterprise_ready_claim_without_external_evidence": packet["enterprise_ready"] is False,
        "no_ga_shipment_claim_without_external_evidence": packet["ga_shipped"] is False,
        "templates_require_external_roots": all(row["must_be_external"] for row in packet["external_evidence_checklist"]),
        "templates_forbid_private_data": all(not row["private_data_allowed"] for row in packet["external_evidence_checklist"]),
        "human_review_gate_preserved": packet["legal_safety_defaults"]["review_required_by_default"] is True,
        "filing_ready_false_by_default": packet["legal_safety_defaults"]["filing_ready_by_default"] is False,
        "html_expected_markers": all(
            marker in html_text
            for marker in ("Enterprise Release Control", "Ask", "Audit", "Ship", "release-blocker-card")
        ),
    }
    return {
        "schema": TEST_SUMMARY_SCHEMA,
        "version": VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
    }


def render_enterprise_release_html(packet: dict[str, Any] | None = None) -> str:
    packet = packet or build_enterprise_release_packet()
    blockers = packet.get("release_blockers", [])
    checklist = packet.get("external_evidence_checklist", [])
    controls = packet.get("enterprise_control_areas", [])
    actions = packet.get("operator_action_plan", [])

    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    blocker_cards = "\n".join(
        f'<article class="release-blocker-card"><strong>{esc(blocker)}</strong></article>'
        for blocker in blockers[:18]
    )
    checklist_rows = "\n".join(
        "<tr>"
        f"<td>Pass {row['pass']}</td>"
        f"<td>{esc(row['root'])}/{esc(row['filename'])}</td>"
        f"<td>{esc(row['description'])}</td>"
        f"<td>{esc(', '.join(row['required_keys']))}</td>"
        "</tr>"
        for row in checklist
    )
    control_cards = "\n".join(
        f'<article class="control-card"><strong>{esc(row["label"])}</strong><p>{esc(row["release_requirement"])}</p></article>'
        for row in controls
    )
    action_cards = "\n".join(
        f'<article class="action-card"><strong>{esc(row["step"])}</strong><p>{esc(row["action"])}</p></article>'
        for row in actions
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Enterprise Release Control v{VERSION}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; color: #172033; background: #f6f8fb; }}
    header {{ padding: 34px clamp(18px, 5vw, 64px); background: linear-gradient(135deg, #17324d, #0b766d); color: white; }}
    h1 {{ margin: 0 0 10px; font-size: clamp(34px, 5vw, 58px); line-height: 1.04; }}
    .lede {{ max-width: 880px; font-size: 18px; line-height: 1.55; margin: 0; color: #e9f4f2; }}
    .status {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }}
    .chip {{ display: inline-flex; padding: 7px 10px; border-radius: 8px; background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.28); font-weight: 900; font-size: 12px; }}
    .chip.block {{ background: #fff1ef; color: #991b1b; border-color: #ffc8bf; }}
    main {{ padding: 28px clamp(18px, 5vw, 64px); }}
    section {{ margin-bottom: 28px; }}
    h2 {{ margin: 0 0 14px; font-size: 26px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); gap: 14px; }}
    .release-blocker-card, .control-card, .action-card {{ background: white; border: 1px solid #d8e1ea; border-radius: 8px; padding: 13px; box-shadow: 0 12px 28px rgba(23, 32, 51, .08); }}
    .release-blocker-card {{ border-left: 4px solid #b42318; }}
    .control-card {{ border-left: 4px solid #0b766d; }}
    .action-card {{ border-left: 4px solid #b7791f; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #d8e1ea; border-radius: 8px; overflow: hidden; }}
    th, td {{ text-align: left; vertical-align: top; padding: 10px; border-bottom: 1px solid #d8e1ea; }}
    th {{ background: #edf3f7; font-size: 12px; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: 0; }}
    .note {{ color: #516173; line-height: 1.5; }}
    @media (max-width: 860px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body data-version="{VERSION}">
  <header>
    <h1>Enterprise Release Control</h1>
    <p class="lede">A fail-closed control surface for the final Maine Family Law LLM launch gates. It shows what remains before attorney pilot, real-matter pilot, release-candidate, and GA shipment can be claimed.</p>
    <div class="status" aria-label="release status">
      <span class="chip block">enterprise_ready={str(packet["enterprise_ready"]).lower()}</span>
      <span class="chip block">production_legal_ready={str(packet["production_legal_ready"]).lower()}</span>
      <span class="chip block">ga_shipped={str(packet["ga_shipped"]).lower()}</span>
      <span class="chip">version={VERSION}</span>
    </div>
  </header>
  <main>
    <section aria-labelledby="ask-title">
      <h2 id="ask-title">Ask</h2>
      <p class="note">Ask whether the release can ship only after the external Pass 48-51 evidence gate passes. The committed evidence page intentionally shows a blocked state.</p>
    </section>
    <section aria-labelledby="audit-title">
      <h2 id="audit-title">Audit</h2>
      <div class="grid">{blocker_cards}</div>
    </section>
    <section class="external-evidence-checklist" aria-labelledby="checklist-title">
      <h2 id="checklist-title">External Evidence Checklist</h2>
      <table>
        <thead><tr><th>Pass</th><th>File</th><th>Purpose</th><th>Required Keys</th></tr></thead>
        <tbody>{checklist_rows}</tbody>
      </table>
    </section>
    <section aria-labelledby="controls-title">
      <h2 id="controls-title">Enterprise Controls</h2>
      <div class="grid">{control_cards}</div>
    </section>
    <section aria-labelledby="ship-title">
      <h2 id="ship-title">Ship</h2>
      <div class="grid">{action_cards}</div>
      <p class="note">{esc(DISCLAIMER)}</p>
    </section>
  </main>
</body>
</html>"""


def write_evidence_outputs(output_dir: str | Path) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    packet = build_enterprise_release_packet()
    html_text = render_enterprise_release_html(packet)
    audit = build_audit(packet, html_text)
    summary = build_test_summary(packet, html_text)
    paths = {
        "packet": output_dir / "enterprise_release_control_v206_packet.json",
        "audit": output_dir / "enterprise_release_control_v206_audit.json",
        "html": output_dir / "enterprise_release_control_v206.html",
        "test_summary": output_dir / "enterprise_release_control_v206_test_summary.json",
    }
    paths["packet"].write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    paths["audit"].write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    paths["html"].write_text(html_text, encoding="utf-8")
    paths["test_summary"].write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return {key: str(path) for key, path in paths.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build v2.06 enterprise release control packet")
    parser.add_argument("--pilot-root", default=".missing_external_launch_evidence/pilot")
    parser.add_argument("--release-root", default=".missing_external_launch_evidence/release")
    parser.add_argument("--output", default="")
    parser.add_argument("--html", default="")
    parser.add_argument("--evidence-dir", default="")
    args = parser.parse_args(argv)

    if args.evidence_dir:
        outputs = write_evidence_outputs(args.evidence_dir)
        print(json.dumps({"status": "pass", "version": VERSION, "outputs": outputs}, indent=2, sort_keys=True))
        return 0

    packet = build_enterprise_release_packet(pilot_root=args.pilot_root, release_root=args.release_root)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    else:
        print(json.dumps(packet, indent=2, sort_keys=True))
    if args.html:
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_enterprise_release_html(packet), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
