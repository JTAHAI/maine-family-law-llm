from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExternalEvidenceTemplate:
    pass_number: int
    filename: str
    description: str
    root: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.pass_number,
            "filename": self.filename,
            "description": self.description,
            "root": self.root,
            "payload": self.payload,
        }


def build_launch_evidence_templates() -> tuple[ExternalEvidenceTemplate, ...]:
    """Return blank, fail-closed Pass 48-51 external evidence templates.

    The templates are intended for an external pilot/release evidence directory.
    They intentionally default to blocked/pending values so committing or running
    the kit cannot accidentally claim attorney review, pilot success, or GA.
    """
    return (
        ExternalEvidenceTemplate(
            pass_number=48,
            filename="attorney_sandbox_pilot_report.json",
            root="pilot",
            description="Attorney-only sandbox pilot report signed by a Maine attorney reviewer or pilot owner.",
            payload={
                "status": "blocked",
                "source": "external_pilot",
                "signed_by": "",
                "signed_at": "",
                "attorney_reviewer_count": 0,
                "bar_status_verified": False,
                "training_complete": False,
                "real_matter_allowed": False,
                "critical_open_count": 0,
                "feedback_queue_reviewed": False,
                "notes": "Fill externally after attorney sandbox completion. Do not put private matter data in this file.",
            },
        ),
        ExternalEvidenceTemplate(
            pass_number=49,
            filename="limited_real_matter_pilot_report.json",
            root="pilot",
            description="Limited real-matter pilot report with explicit consent, isolation, review, and incident controls.",
            payload={
                "status": "blocked",
                "source": "external_pilot",
                "signed_by": "",
                "signed_at": "",
                "matter_count": 0,
                "all_matters_have_explicit_consent": False,
                "tenant_isolation_verified": False,
                "encrypted_storage_verified": False,
                "human_review_completed": False,
                "attorney_signoff_complete": False,
                "daily_review_complete": False,
                "training_use_allowed": False,
                "data_leakage_count": 0,
                "unsupported_export_attempt_count": 0,
                "open_incident_count": 0,
                "notes": "Use aggregate counts only. Do not include party names, docket numbers, facts, documents, or private matter text.",
            },
        ),
        ExternalEvidenceTemplate(
            pass_number=50,
            filename="ga_release_candidate_signoff.json",
            root="release",
            description="GA release-candidate signoff inventory with security, legal, product, and ops approvals.",
            payload={
                "status": "blocked",
                "source": "external_release",
                "signed_by": "",
                "signed_at": "",
                "release_candidate_frozen": False,
                "open_p0_p1_count": 0,
                "artifact_inventory_hash": "",
                "signoffs": [
                    {"role": "security", "status": "pending", "signer": "", "signed_at": ""},
                    {"role": "legal", "status": "pending", "signer": "", "signed_at": ""},
                    {"role": "product", "status": "pending", "signer": "", "signed_at": ""},
                    {"role": "ops", "status": "pending", "signer": "", "signed_at": ""},
                ],
                "notes": "Fill only after external artifacts, release metrics, pilot evidence, security evidence, and owner approvals exist.",
            },
        ),
        ExternalEvidenceTemplate(
            pass_number=51,
            filename="ga_shipment_signoff.json",
            root="release",
            description="Final GA shipment signoff asserting all required GA controls are true.",
            payload={
                "status": "blocked",
                "source": "external_release",
                "signed_by": "",
                "signed_at": "",
                "ga_shipped": False,
                "release_candidate_status": "blocked",
                "shipment_manifest_hash": "",
                "controls": {
                    "runs_from_clean_deployment": False,
                    "uses_real_official_maine_authority": False,
                    "attorney_reviewed_evals_present": False,
                    "release_metrics_pass": False,
                    "unsupported_filing_ready_output_blocked": False,
                    "private_matter_data_protected": False,
                    "audit_trails_present": False,
                    "security_controls_present": False,
                    "pilot_evidence_present": False,
                    "rollback_and_maintenance_operations_present": False,
                },
                "notes": "Final shipment remains blocked until every external artifact, control, and signoff is complete.",
            },
        ),
    )


def write_launch_evidence_starter_kit(output_root: str | Path) -> dict[str, Any]:
    output_root = Path(output_root)
    manifest_rows = []
    for template in build_launch_evidence_templates():
        target = output_root / template.root / template.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(template.payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_rows.append({
            "pass": template.pass_number,
            "filename": template.filename,
            "path": str(target),
            "root": template.root,
            "description": template.description,
            "defaults_to_blocked": True,
        })

    readme = output_root / "README.md"
    readme.write_text(
        "# Pass 48-51 external evidence starter kit\n\n"
        "These JSON templates are intentionally fail-closed. Fill them outside the source repository after real attorney sandbox, limited pilot, release-candidate, and GA-shipment evidence exists.\n\n"
        "Do not include private matter facts, party names, docket numbers, uploaded documents, model weights, runtime databases, parsed authority stores, or retrieval indexes in this kit.\n\n"
        "Run the gate from the source repo with:\n\n"
        "```powershell\n"
        "python .\\scripts\\run-pass48-51-launch-evidence-gates.py --pilot-root <kit>\\pilot --release-root <kit>\\release --require-ready\n"
        "```\n",
        encoding="utf-8",
    )
    manifest = {
        "status": "blocked_templates_created",
        "template_count": len(manifest_rows),
        "templates": manifest_rows,
        "readme": str(readme),
        "honesty_rule": "Templates do not close Passes 48-51. Only completed external evidence can pass the gate.",
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
