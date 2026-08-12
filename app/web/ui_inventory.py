from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from maine_family_law_llm.production_ui import production_ui_manifest


@dataclass(frozen=True)
class UIViewSpec:
    name: str
    path: str
    file: str
    purpose: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "path": self.path, "file": self.file, "purpose": self.purpose}


REQUIRED_UI_VIEWS: tuple[UIViewSpec, ...] = (
    UIViewSpec("matter_dashboard", "/", "dashboard.tsx", "matter list and recent activity"),
    UIViewSpec("ask_maine_family_law", "/ask", "ask.tsx", "source-grounded Q&A"),
    UIViewSpec("upload_documents", "/upload", "upload.tsx", "matter document intake"),
    UIViewSpec("source_library", "/sources", "source-library.tsx", "browse admitted sources"),
    UIViewSpec("authority_matrix", "/authority", "authority-matrix.tsx", "authority analysis"),
    UIViewSpec("timeline", "/timeline", "timeline.tsx", "case timeline"),
    UIViewSpec("evidence_map", "/evidence", "evidence.tsx", "fact-to-evidence map"),
    UIViewSpec(
        "command_center",
        "/command-center",
        "command-center.tsx",
        "whole-matter review command center",
    ),
    UIViewSpec(
        "child_continuity_workbench",
        "/child-continuity",
        "child-continuity.tsx",
        "child-centered continuity and logistics workbench",
    ),
    UIViewSpec(
        "local_deliberation_workspace",
        "/deliberation",
        "local-deliberation-workspace.tsx",
        "local-only deliberation workspace",
    ),
    UIViewSpec(
        "connections_deliberation",
        "/connections",
        "connections-deliberation.tsx",
        "provider connections and exact outbound consent",
    ),
    UIViewSpec("draft_workspace", "/draft", "draft-workspace.tsx", "review-required drafting"),
    UIViewSpec("citation_report", "/citations", "citation-report.tsx", "citation verification"),
    UIViewSpec("quote_report", "/quotes", "quote-report.tsx", "quote-report verification"),
    UIViewSpec(
        "communications_parenting_time",
        "/communications",
        "communications-parenting-time.tsx",
        "communications and parenting-time review",
    ),
    UIViewSpec(
        "hearing_media_workbench",
        "/hearing-media",
        "hearing-media-workbench.tsx",
        "hearing media, transcript, and appellate record review",
    ),
    UIViewSpec("filing_readiness_gate", "/filing-ready", "filing-ready.tsx", "export blockers"),
    UIViewSpec("human_review_queue", "/review-queue", "human-review-queue.tsx", "attorney review"),
    UIViewSpec(
        "settings_data_policy", "/settings", "settings-data-policy.tsx", "data policy controls"
    ),
    UIViewSpec(
        "admin_eval_dashboard",
        "/admin/evals",
        "admin-eval-dashboard.tsx",
        "eval and release gate visibility",
    ),
    UIViewSpec(
        "governance_policy_center",
        "/admin/governance",
        "governance-policy-center.tsx",
        "governance controls, policies, cards, sign-offs, and diligence packet",
    ),
    UIViewSpec(
        "local_intelligence_control_center",
        "/admin/models",
        "local-intelligence-control-center.tsx",
        "model registry, hardware profiler, and safe routing",
    ),
    UIViewSpec(
        "security_privacy_center",
        "/admin/security",
        "security-privacy-center.tsx",
        "matter encryption, audit integrity, backup/restore, and incident controls",
    ),
    UIViewSpec(
        "release_control_center",
        "/admin/release",
        "release-control-center.tsx",
        "local observability, supply chain evidence, release gates, and ship readiness",
    ),
    UIViewSpec(
        "maintenance_center",
        "/admin/maintenance",
        "maintenance-center.tsx",
        "pilot hardening, attorney sandbox, real-matter pilot, and release maintenance",
    ),
)


class UIViewInventory:
    def __init__(self, web_pages_dir: str | Path) -> None:
        self.web_pages_dir = Path(web_pages_dir)

    def validate(self) -> dict[str, Any]:
        existing = {path.name for path in self.web_pages_dir.glob("*.tsx")}
        required = {view.file for view in REQUIRED_UI_VIEWS}
        missing = sorted(required - existing)
        production = production_ui_manifest()
        return {
            "status": "pass" if not missing and production["status"] == "pass" else "fail",
            "required_count": len(required),
            "existing_count": len(existing),
            "missing": missing,
            "views": [view.as_dict() for view in REQUIRED_UI_VIEWS],
            "production": production,
            "shadow_contracts_only": True,
            "capability_claim_basis": "bundled_workbench_runtime_manifest",
        }
