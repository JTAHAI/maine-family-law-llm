from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.api.contracts import APICompletionPolicy, EndpointInventory, OpenAPICompletionAuditor
from app.api.main import app
from app.web.ui_contracts import UICompletionAuditor


@dataclass(frozen=True)
class RepoGAEvidenceResult:
    status: str
    generated_at: str
    openapi_path: str
    api_report_path: str
    ui_report_path: str
    completed_repo_only_passes: tuple[int, ...]
    blockers: tuple[str, ...]
    api_report: dict[str, Any]
    ui_report: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "openapi_path": self.openapi_path,
            "api_report_path": self.api_report_path,
            "ui_report_path": self.ui_report_path,
            "completed_repo_only_passes": list(self.completed_repo_only_passes),
            "blockers": list(self.blockers),
            "api_report": self.api_report,
            "ui_report": self.ui_report,
        }


class RepoGAEvidenceBuilder:
    """Build repo-local evidence for true-GA passes that do not require live legal data.

    This intentionally covers only Pass 39 and Pass 40. It does not close live authority,
    retrieval, gold eval, security, pilot, or signoff passes.
    """

    def __init__(self, *, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.openapi_path = self.project_root / "openapi.json"
        self.api_report_path = self.project_root / "docs" / "api-contract-test-report.json"
        self.ui_report_path = self.project_root / "docs" / "ui-completion-report.json"

    def _registered_routes(self) -> set[tuple[str, str]]:
        registered: set[tuple[str, str]] = set()
        for route in app.routes:
            methods = getattr(route, "methods", set()) or set()
            path = getattr(route, "path", "")
            for method in methods:
                if method in {"GET", "POST"} and str(path).startswith("/api"):
                    registered.add((method, str(path)))
        return registered

    def build(self, *, write: bool = True) -> RepoGAEvidenceResult:
        generated_at = datetime.now(timezone.utc).isoformat()
        openapi_schema = app.openapi()
        inventory_report = EndpointInventory().compare_to_registered(self._registered_routes())
        openapi_report = OpenAPICompletionAuditor().audit(openapi_schema).as_dict()
        policy_report = APICompletionPolicy().evidence().as_dict()
        ui_report = UICompletionAuditor(self.project_root / "app" / "web" / "pages").audit().as_dict()

        blockers: list[str] = []
        if inventory_report.get("status") != "pass":
            blockers.append("api_endpoint_inventory_failed")
        if openapi_report.get("status") != "pass":
            blockers.append("openapi_completion_failed")
        if policy_report.get("endpoint_count") != 15:
            blockers.append("api_endpoint_count_not_15")
        if not policy_report.get("auth_rbac_enforced"):
            blockers.append("auth_rbac_policy_not_enforced")
        if not policy_report.get("audit_events_required"):
            blockers.append("audit_event_policy_not_required")
        if ui_report.get("status") != "pass":
            blockers.append("ui_completion_failed")

        api_blockers = [
            item
            for item in blockers
            if item
            in {
                "api_endpoint_inventory_failed",
                "openapi_completion_failed",
                "api_endpoint_count_not_15",
                "auth_rbac_policy_not_enforced",
                "audit_event_policy_not_required",
            }
        ]
        status = "pass" if not blockers else "blocked"
        api_payload = {
            "schema": "maine_family_law_llm.pass39.api_contract_report.v1",
            "status": "pass" if not api_blockers else "blocked",
            "generated_at": generated_at,
            "pass": 39,
            "evidence_basis": "repo_contract_tests_and_openapi_schema",
            "production_legal_ga": False,
            "inventory": inventory_report,
            "openapi": openapi_report,
            "policy": policy_report,
        }
        # The UI report itself is the required Pass 40 artifact and must expose a top-level status.
        ui_payload = {
            "schema": "maine_family_law_llm.pass40.ui_completion_report.v1",
            "status": ui_report.get("status", "fail"),
            "generated_at": generated_at,
            "pass": 40,
            "evidence_basis": "repo_ui_contract_marker_tests",
            "production_legal_ga": False,
            **ui_report,
        }

        if write:
            self.openapi_path.write_text(json.dumps(openapi_schema, indent=2, sort_keys=True), encoding="utf-8")
            self.api_report_path.parent.mkdir(parents=True, exist_ok=True)
            self.api_report_path.write_text(json.dumps(api_payload, indent=2, sort_keys=True), encoding="utf-8")
            self.ui_report_path.write_text(json.dumps(ui_payload, indent=2, sort_keys=True), encoding="utf-8")

        return RepoGAEvidenceResult(
            status=status,
            generated_at=generated_at,
            openapi_path=str(self.openapi_path.relative_to(self.project_root)),
            api_report_path=str(self.api_report_path.relative_to(self.project_root)),
            ui_report_path=str(self.ui_report_path.relative_to(self.project_root)),
            completed_repo_only_passes=(39, 40) if status == "pass" else (),
            blockers=tuple(blockers),
            api_report=api_payload,
            ui_report=ui_payload,
        )
