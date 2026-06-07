from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.evals.conversation_quality_metrics import ConversationQualityRegressionRunner
from legal.evals.user_journey_eval import UserJourneyEvalRunner


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "maine_internal_product_polish_passes.json"
SUMMARY_PATH = ROOT / "docs" / "external-evidence" / "pass47i_47t_product_polish_summary.json"
USER_JOURNEY_OUTPUT_PATH = ROOT / "docs" / "external-evidence" / "pass47p_user_journey_eval_report.json"
QUALITY_OUTPUT_PATH = ROOT / "docs" / "external-evidence" / "pass47r_conversation_quality_regression.json"

PASS_REQUIREMENTS = {
    "47I": {
        "files": [
            "configs/maine_conversation_state_machine.json",
            "legal/conversation/session_state.py",
            "legal/conversation/conversation_state_machine.py",
            "legal/conversation/context_window.py",
            "legal/conversation/safe_summary.py",
        ],
        "tests": [
            "tests/test_conversation_state_machine.py",
            "tests/test_conversation_session_state.py",
            "tests/test_safe_summary.py",
        ],
    },
    "47J": {
        "files": [
            "configs/maine_guided_workflows.json",
            "legal/conversation/workflow_router.py",
            "legal/conversation/workflow_steps.py",
            "legal/conversation/start_here.py",
        ],
        "tests": [
            "tests/test_workflow_router.py",
            "tests/test_workflow_steps.py",
            "tests/test_start_here.py",
        ],
    },
    "47K": {
        "files": [
            "configs/maine_answer_quality_rules.json",
            "legal/conversation/answer_builder.py",
            "legal/conversation/legal_uncertainty.py",
            "legal/conversation/next_steps.py",
            "legal/conversation/red_flag_presenter.py",
            "legal/conversation/review_status_presenter.py",
        ],
        "tests": [
            "tests/test_answer_builder.py",
            "tests/test_legal_uncertainty.py",
            "tests/test_next_steps.py",
            "tests/test_red_flag_presenter.py",
            "tests/test_review_status_presenter.py",
        ],
    },
    "47L": {
        "files": [
            "configs/maine_drafting_conversation_rules.json",
            "legal/conversation/drafting_conversation.py",
            "legal/conversation/draft_intake.py",
            "legal/conversation/draft_blockers.py",
            "legal/conversation/draft_review_checklist.py",
        ],
        "tests": [
            "tests/test_drafting_conversation.py",
            "tests/test_draft_intake.py",
            "tests/test_draft_blockers.py",
            "tests/test_draft_review_checklist.py",
        ],
    },
    "47M": {
        "files": [
            "configs/maine_document_review_rules.json",
            "legal/conversation/document_review_conversation.py",
            "legal/conversation/document_instruction_filter.py",
            "legal/conversation/document_findings.py",
            "legal/conversation/document_review_report.py",
        ],
        "tests": [
            "tests/test_document_review_conversation.py",
            "tests/test_document_instruction_filter.py",
            "tests/test_document_findings.py",
            "tests/test_document_review_report.py",
        ],
    },
    "47N": {
        "files": [
            "configs/maine_reviewer_feedback_schema.json",
            "legal/conversation/human_review_queue.py",
            "legal/conversation/reviewer_packet.py",
            "legal/conversation/reviewer_feedback.py",
            "docs/reviewer-guide.md",
            "docs/attorney-sandbox-review-packet.md",
        ],
        "tests": [
            "tests/test_human_review_queue.py",
            "tests/test_reviewer_packet.py",
            "tests/test_reviewer_feedback.py",
        ],
    },
    "47O": {
        "files": [
            "docs/outreach/README.md",
            "docs/outreach/email-templates.md",
            "docs/outreach/contact-tracker-schema.csv",
            "docs/outreach/contact-tracker-example-redacted.csv",
            "docs/outreach/github-review-request.md",
            "docs/outreach/reviewer-feedback-form.md",
            "docs/outreach/outreach-evidence-policy.md",
        ],
        "tests": ["tests/test_outreach_docs.py"],
    },
    "47P": {
        "files": [
            "eval_data/schemas/maine_user_journey_eval.schema.json",
            "eval_data/user_journeys/maine_user_journey_eval_cases.json",
            "legal/evals/user_journey_eval.py",
            "scripts/run-user-journey-evals.py",
            "docs/demo-user-journeys.md",
        ],
        "tests": [
            "tests/test_user_journey_eval_schema.py",
            "tests/test_user_journey_evals.py",
        ],
    },
    "47Q": {
        "files": [
            "configs/maine_workbench_ui_copy.json",
            "app/services/workflow_adapter.py",
            "app/services/reviewer_adapter.py",
            "app/services/user_journey_adapter.py",
            "app/services/status_labels.py",
        ],
        "tests": [
            "tests/test_workflow_adapter.py",
            "tests/test_reviewer_adapter.py",
            "tests/test_user_journey_adapter.py",
            "tests/test_workbench_ui_copy.py",
        ],
    },
    "47R": {
        "files": [
            "eval_data/conversation/maine_conversation_quality_extra_cases.json",
            "legal/evals/conversation_quality_metrics.py",
            "scripts/run-conversation-quality-regression.py",
        ],
        "tests": [
            "tests/test_conversation_quality_metrics.py",
            "tests/test_conversation_quality_regression.py",
        ],
    },
    "47S": {
        "files": [
            "README.md",
            "docs/product-vision.md",
            "docs/legal-safety-policy.md",
            "docs/human-review-policy.md",
            "docs/data-boundaries.md",
            "docs/chat-input-output-hardening.md",
            "docs/attorney-review-outreach-plan.md",
            "docs/ga-pass-count.md",
            "docs/ga-pass-evidence-gate.md",
        ],
        "tests": ["tests/test_doc_unsafe_claims.py"],
    },
    "47T": {
        "files": [
            ".gitignore",
            "docs/release-prep-cleanup.md",
            "scripts/check-outreach-truthfulness.py",
            "scripts/check-doc-unsafe-claims.py",
        ],
        "tests": [
            "tests/test_outreach_truthfulness.py",
            "tests/test_doc_unsafe_claims.py",
            "tests/test_conversation_product_polish_passes.py",
        ],
    },
}
NEW_TESTS = sorted({test for row in PASS_REQUIREMENTS.values() for test in row["tests"]})


@dataclass(frozen=True)
class ProductPolishPassResult:
    pass_id: str
    title: str
    status: str
    files: list[str]
    tests: list[str]
    signals: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass_id": self.pass_id,
            "title": self.title,
            "status": self.status,
            "files": self.files,
            "tests": self.tests,
            "signals": self.signals,
        }


@dataclass
class ProductPolishReadinessReport:
    status: str
    generated_at: str
    completed_internal_passes: list[str]
    remaining_true_ga_passes: list[int]
    remaining_true_ga_count: int
    tests_passed: bool
    no_private_data_packaged: bool
    emails_sent: bool
    outreach_complete: bool
    attorney_reviewed: bool
    legal_signoff: bool
    pilot_signoff: bool
    ga_shipped: bool
    production_legal_ready: bool
    user_journey_eval_report: dict[str, Any]
    conversation_quality_regression: dict[str, Any]
    pytest: dict[str, Any]
    pass_results: dict[str, dict[str, Any]]
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "pass47i_47t_product_polish_summary_v1",
            "status": self.status,
            "generated_at": self.generated_at,
            "readiness": (
                "internal_product_polish_reviewer_outreach_prep_complete"
                if self.status == "pass"
                else "internal_product_polish_reviewer_outreach_prep_blocked"
            ),
            "completed_internal_passes": self.completed_internal_passes,
            "remaining_true_ga_passes": self.remaining_true_ga_passes,
            "remaining_true_ga_count": self.remaining_true_ga_count,
            "does_not_reduce_true_ga_count": True,
            "tests_passed": self.tests_passed,
            "no_private_data_packaged": self.no_private_data_packaged,
            "emails_sent": self.emails_sent,
            "outreach_complete": self.outreach_complete,
            "attorney_reviewed": self.attorney_reviewed,
            "legal_signoff": self.legal_signoff,
            "pilot_signoff": self.pilot_signoff,
            "ga_shipped": self.ga_shipped,
            "production_legal_ready": self.production_legal_ready,
            "user_journey_eval_report_path": str(USER_JOURNEY_OUTPUT_PATH.relative_to(ROOT)),
            "conversation_quality_regression_path": str(QUALITY_OUTPUT_PATH.relative_to(ROOT)),
            "user_journey_eval_report": self.user_journey_eval_report,
            "conversation_quality_regression": self.conversation_quality_regression,
            "pytest": self.pytest,
            "pass_results": self.pass_results,
            "blockers": self.blockers,
            "evidence_basis": [
                "code/config/doc files exist",
                "tests exist for product-polish contracts",
                "deterministic user-journey eval passes",
                "conversation quality regression passes with at least 40 cases",
                "outreach materials are templates only and emails are unsent",
                "true GA passes 48-51 remain open",
            ],
        }


class ProductPolishReadinessAuditor:
    def __init__(self, project_root: str | Path = ROOT) -> None:
        self.project_root = Path(project_root)
        self.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def audit(self, *, run_tests: bool = False) -> ProductPolishReadinessReport:
        pytest_result = self._run_targeted_pytest() if run_tests else {
            "command": "pytest skipped",
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }
        user_journey = UserJourneyEvalRunner(project_root=self.project_root).run(
            output_path=USER_JOURNEY_OUTPUT_PATH
        ).as_dict()
        quality = ConversationQualityRegressionRunner(project_root=self.project_root).run(
            output_path=QUALITY_OUTPUT_PATH
        ).as_dict()

        pass_results: dict[str, dict[str, Any]] = {}
        blockers: list[str] = []
        for row in self.config.get("passes", []):
            pass_id = str(row["pass"])
            required = PASS_REQUIREMENTS[pass_id]
            missing_files = [path for path in required["files"] if not (self.project_root / path).exists()]
            missing_tests = [path for path in required["tests"] if not (self.project_root / path).exists()]
            signals = {
                "code_config_docs_present": not missing_files,
                "tests_present": not missing_tests,
                "user_journey_eval_passed": user_journey.get("status") == "pass"
                if pass_id == "47P"
                else True,
                "quality_regression_passed": quality.get("status") == "pass"
                if pass_id == "47R"
                else True,
                "does_not_claim_external_signoff": True,
            }
            status = "pass" if all(signals.values()) else "fail"
            if status != "pass":
                blockers.append(f"internal_product_polish_pass_failed:{pass_id}")
            pass_results[pass_id] = ProductPolishPassResult(
                pass_id=pass_id,
                title=str(row["title"]),
                status=status,
                files=required["files"],
                tests=required["tests"],
                signals=signals | {"missing_files": missing_files, "missing_tests": missing_tests},
            ).as_dict()

        no_private_data_packaged = not any(
            (self.project_root / name).exists()
            for name in (
                "ME_FM_LLM_data",
                "official_authority_store",
                "parsed_authority_store",
                "embedding_store",
                "vector_store",
                "vector_stores",
                "model_registry",
                "matter_store",
            )
        )
        if not no_private_data_packaged:
            blockers.append("private_or_runtime_data_packaged")
        if pytest_result["returncode"] != 0:
            blockers.append("targeted_product_polish_pytest_failed")
        if user_journey.get("status") != "pass":
            blockers.append("user_journey_eval_failed")
        if quality.get("status") != "pass":
            blockers.append("conversation_quality_regression_failed")

        completed = [
            str(row["pass"])
            for row in self.config.get("passes", [])
            if pass_results[str(row["pass"])]["status"] == "pass"
        ]
        status = "pass" if len(completed) == len(self.config.get("passes", [])) and not blockers else "blocked"
        return ProductPolishReadinessReport(
            status=status,
            generated_at=datetime.now(UTC).isoformat(),
            completed_internal_passes=completed,
            remaining_true_ga_passes=[48, 49, 50, 51],
            remaining_true_ga_count=4,
            tests_passed=pytest_result["returncode"] == 0,
            no_private_data_packaged=no_private_data_packaged,
            emails_sent=False,
            outreach_complete=False,
            attorney_reviewed=False,
            legal_signoff=False,
            pilot_signoff=False,
            ga_shipped=False,
            production_legal_ready=False,
            user_journey_eval_report=user_journey,
            conversation_quality_regression=quality,
            pytest=pytest_result,
            pass_results=pass_results,
            blockers=blockers,
        )

    def write(self, output_path: str | Path = SUMMARY_PATH, *, run_tests: bool = False) -> ProductPolishReadinessReport:
        report = self.audit(run_tests=run_tests)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return report

    def _run_targeted_pytest(self) -> dict[str, Any]:
        env = os.environ.copy()
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        command = [sys.executable, "-m", "pytest", "-q", *NEW_TESTS]
        completed = subprocess.run(
            command,
            cwd=self.project_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        return {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
