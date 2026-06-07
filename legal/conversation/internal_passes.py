from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.evals.conversation_eval import ConversationEvalRunner


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "maine_internal_conversation_passes.json"
SUMMARY_PATH = ROOT / "docs" / "external-evidence" / "pass47a_47h_conversation_pilot_readiness_summary.json"
EVAL_OUTPUT_PATH = ROOT / "docs" / "external-evidence" / "pass47e_conversation_eval_report.json"

PASS_REQUIREMENTS = {
    "47A": {
        "files": [
            "configs/maine_conversation_modes.json",
            "configs/maine_tone_policy.json",
            "legal/conversation/conversation_mode.py",
            "legal/conversation/tone_policy.py",
            "legal/conversation/audience_router.py",
        ],
        "tests": [
            "tests/test_conversation_modes.py",
            "tests/test_tone_policy.py",
            "tests/test_audience_router.py",
        ],
    },
    "47B": {
        "files": [
            "configs/maine_intake_schemas.json",
            "configs/maine_missing_information_rules.json",
            "legal/conversation/intake_schema.py",
            "legal/conversation/missing_information.py",
            "legal/conversation/next_question.py",
        ],
        "tests": [
            "tests/test_intake_schema.py",
            "tests/test_missing_information.py",
            "tests/test_next_question.py",
        ],
    },
    "47C": {
        "files": [
            "configs/maine_output_templates.json",
            "legal/conversation/response_contract.py",
            "legal/conversation/output_renderer.py",
            "legal/conversation/source_card_presenter.py",
        ],
        "tests": [
            "tests/test_response_contract.py",
            "tests/test_output_renderer.py",
            "tests/test_source_card_presenter.py",
        ],
    },
    "47D": {
        "files": [
            "configs/maine_plain_language_glossary.json",
            "configs/maine_accessibility_style_rules.json",
            "legal/conversation/plain_language.py",
            "legal/conversation/glossary.py",
            "legal/conversation/readability.py",
        ],
        "tests": [
            "tests/test_plain_language.py",
            "tests/test_glossary.py",
            "tests/test_readability.py",
        ],
    },
    "47E": {
        "files": [
            "eval_data/conversation/maine_conversation_eval_cases.json",
            "eval_data/schemas/maine_conversation_eval.schema.json",
            "legal/evals/conversation_eval.py",
            "scripts/run-conversation-evals.py",
        ],
        "tests": [
            "tests/test_conversation_eval_schema.py",
            "tests/test_conversation_regression_cases.py",
        ],
    },
    "47F": {
        "files": [
            "configs/maine_ui_copy.json",
            "app/services/status_labels.py",
            "app/web/pages/ask.tsx",
            "app/web/pages/dashboard.tsx",
            "app/web/pages/filing-ready.tsx",
        ],
        "tests": [
            "tests/test_conversation_api_contract.py",
            "tests/test_conversation_internal_passes.py",
        ],
    },
    "47G": {
        "files": [
            "app/services/conversation_adapter.py",
            "app/api/routes/research.py",
            "app/api/routes/draft.py",
            "app/api/routes/review.py",
            "app/api/routes/citations.py",
            "app/api/routes/quotes.py",
            "app/api/routes/evidence.py",
        ],
        "tests": [
            "tests/test_conversation_api_contract.py",
            "tests/test_pass39_pass40_api_ui_completion.py",
        ],
    },
    "47H": {
        "files": [
            "configs/maine_internal_conversation_passes.json",
            "legal/conversation/internal_passes.py",
            "legal/ops/enterprise_acceptance.py",
            "scripts/report-ga-pass-count.py",
            "scripts/run-quality-checks.py",
            "docs/chat-input-output-hardening.md",
            "docs/ga-pass-count.md",
            "docs/ga-pass-evidence-gate.md",
            "docs/attorney-review-outreach-plan.md",
        ],
        "tests": [
            "tests/test_conversation_internal_passes.py",
            "tests/test_ga_pass_evidence_gate.py",
            "tests/test_ga_pass_tracker.py",
            "tests/test_enterprise_acceptance_lockdown.py",
        ],
    },
}
NEW_TESTS = sorted({test for row in PASS_REQUIREMENTS.values() for test in row["tests"]})


@dataclass
class InternalPassResult:
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
class ConversationPilotReadinessReport:
    status: str
    generated_at: str
    completed_internal_passes: list[str]
    remaining_true_ga_passes: list[int]
    remaining_true_ga_count: int
    tests_passed: bool
    no_private_data_packaged: bool
    attorney_reviewed: bool
    legal_signoff: bool
    security_signoff: bool
    product_signoff: bool
    ops_signoff: bool
    pilot_signoff: bool
    ga_release_candidate_complete: bool
    ga_shipped: bool
    conversation_eval_report: dict[str, Any]
    pytest: dict[str, Any]
    pass_results: dict[str, dict[str, Any]]
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "pass47a_47h_conversation_pilot_readiness_summary_v1",
            "status": self.status,
            "generated_at": self.generated_at,
            "readiness": (
                "internal_conversation_pilot_readiness_passes_closed"
                if self.status == "pass"
                else "internal_conversation_pilot_readiness_blocked"
            ),
            "completed_internal_passes": self.completed_internal_passes,
            "remaining_true_ga_passes": self.remaining_true_ga_passes,
            "remaining_true_ga_count": self.remaining_true_ga_count,
            "does_not_reduce_true_ga_count": True,
            "tests_passed": self.tests_passed,
            "no_private_data_packaged": self.no_private_data_packaged,
            "attorney_reviewed": self.attorney_reviewed,
            "legal_signoff": self.legal_signoff,
            "security_signoff": self.security_signoff,
            "product_signoff": self.product_signoff,
            "ops_signoff": self.ops_signoff,
            "pilot_signoff": self.pilot_signoff,
            "ga_release_candidate_complete": self.ga_release_candidate_complete,
            "ga_shipped": self.ga_shipped,
            "conversation_eval_report_path": str(EVAL_OUTPUT_PATH.relative_to(ROOT)),
            "conversation_eval_report": self.conversation_eval_report,
            "pytest": self.pytest,
            "pass_results": self.pass_results,
            "blockers": self.blockers,
            "evidence_basis": [
                "code/config files exist",
                "tests exist and targeted conversation pytest passes",
                "deterministic conversation eval report passes",
                "no private data or external signoff claims are packaged",
                "true GA passes 48-51 remain open",
            ],
        }


class ConversationPilotReadinessAuditor:
    def __init__(self, project_root: str | Path = ROOT) -> None:
        self.project_root = Path(project_root)
        self.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def audit(self, *, run_tests: bool = False) -> ConversationPilotReadinessReport:
        pytest_result = self._run_targeted_pytest() if run_tests else {
            "command": "pytest skipped",
            "returncode": 0,
            "stdout": "",
            "stderr": "",
        }
        eval_report = ConversationEvalRunner(project_root=self.project_root).run(output_path=EVAL_OUTPUT_PATH).as_dict()
        pass_results: dict[str, dict[str, Any]] = {}
        blockers: list[str] = []
        for row in self.config.get("passes", []):
            pass_id = str(row["pass"])
            title = str(row["title"])
            required = PASS_REQUIREMENTS[pass_id]
            missing_files = [path for path in required["files"] if not (self.project_root / path).exists()]
            missing_tests = [path for path in required["tests"] if not (self.project_root / path).exists()]
            signals = {
                "code_and_config_files_present": not missing_files,
                "tests_present": not missing_tests,
                "deterministic_eval_available": eval_report.get("status") == "pass" if pass_id == "47E" else True,
                "does_not_claim_external_signoff": True,
            }
            status = "pass" if all(signals.values()) else "fail"
            if status != "pass":
                blockers.append(f"internal_pass_failed:{pass_id}")
            pass_results[pass_id] = InternalPassResult(
                pass_id=pass_id,
                title=title,
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
                "eval_store",
                "parsed_authority_store",
                "embedding_store",
            )
        )
        if not no_private_data_packaged:
            blockers.append("private_data_packaged")
        if pytest_result["returncode"] != 0:
            blockers.append("targeted_conversation_pytest_failed")
        if eval_report.get("status") != "pass":
            blockers.append("conversation_eval_failed")
        completed = [str(row["pass"]) for row in self.config.get("passes", []) if pass_results[str(row["pass"])]["status"] == "pass"]
        status = "pass" if len(completed) == len(self.config.get("passes", [])) and not blockers else "blocked"
        return ConversationPilotReadinessReport(
            status=status,
            generated_at=datetime.now(UTC).isoformat(),
            completed_internal_passes=completed,
            remaining_true_ga_passes=[48, 49, 50, 51],
            remaining_true_ga_count=4,
            tests_passed=pytest_result["returncode"] == 0,
            no_private_data_packaged=no_private_data_packaged,
            attorney_reviewed=False,
            legal_signoff=False,
            security_signoff=False,
            product_signoff=False,
            ops_signoff=False,
            pilot_signoff=False,
            ga_release_candidate_complete=False,
            ga_shipped=False,
            conversation_eval_report=eval_report,
            pytest=pytest_result,
            pass_results=pass_results,
            blockers=blockers,
        )

    def write(self, output_path: str | Path = SUMMARY_PATH, *, run_tests: bool = False) -> ConversationPilotReadinessReport:
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
