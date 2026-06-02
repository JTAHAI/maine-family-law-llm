from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from maine_family_law_llm.chat_library import ChatLibraryItem, get_chat_library

from .evidence_templates import build_launch_evidence_templates


@dataclass(frozen=True)
class AttorneyReviewQuestion:
    question_id: str
    topic: str
    audience: str
    title: str
    prompt: str
    expected_source_terms: tuple[str, ...]
    review_focus: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "topic": self.topic,
            "audience": self.audience,
            "title": self.title,
            "prompt": self.prompt,
            "expected_source_terms": list(self.expected_source_terms),
            "review_focus": list(self.review_focus),
            "review_status": "needs_attorney_review",
            "attorney_notes": "",
            "creates_eval_candidate": False,
            "private_data_included": False,
        }


class AttorneySandboxReviewKitBuilder:
    """Build a fail-closed Pass 48 attorney sandbox review kit.

    The kit is intended to be written outside the source repository and given to
    Maine-licensed attorney reviewers. It contains public/synthetic prompts,
    templates, and review workflows only. It does not create signoff evidence,
    does not permit real matter data, and does not close Pass 48 by itself.
    """

    FORBIDDEN_PRIVATE_DATA_MARKERS = (
        "party_names",
        "docket_numbers",
        "private_matter_facts",
        "uploaded_documents",
        "sealed_records",
        "juvenile_records",
        "client_confidential_material",
    )
    REVIEW_FOCUS_BY_TOPIC = {
        "parental_rights": (
            "best_interest_factor_coverage",
            "safety_factor_handling",
            "source_grounding",
        ),
        "findings_review": (
            "rule_52_findings_gap",
            "record_support",
            "review_required_export_status",
        ),
        "safety_pfa": (
            "emergency_routing",
            "pfa_family_overlap",
            "no_safety_plan_substitution",
        ),
        "appeals": (
            "deadline_caution",
            "appellate_rule_scope",
            "no_deadline_calculation_without_review",
        ),
        "child_support": (
            "official_form_freshness",
            "calculation_boundary",
            "source_grounding",
        ),
        "professional_boundaries": (
            "role_boundary",
            "confidentiality_warning",
            "no_professional_ethics_substitution",
        ),
    }

    def __init__(self, *, library: Iterable[ChatLibraryItem] | None = None) -> None:
        self.library = tuple(library) if library is not None else get_chat_library()

    def build_question_queue(self, *, max_questions: int = 48) -> list[dict[str, Any]]:
        selected: list[AttorneyReviewQuestion] = []
        seen_topics: set[str] = set()

        # Prioritize breadth first so attorney time covers the highest-risk lanes.
        for item in self.library:
            if item.topic in seen_topics:
                continue
            selected.append(self._question_from_item(item))
            seen_topics.add(item.topic)
            if len(selected) >= max_questions:
                return [question.as_dict() for question in selected]

        for item in self.library:
            if len(selected) >= max_questions:
                break
            if any(question.question_id == item.id for question in selected):
                continue
            selected.append(self._question_from_item(item))
        return [question.as_dict() for question in selected]

    def build_manifest(self, output_root: str | Path, *, max_questions: int = 48) -> dict[str, Any]:
        output_root = Path(output_root)
        pilot_dir = output_root / "pilot"
        pilot_dir.mkdir(parents=True, exist_ok=True)

        queue = self.build_question_queue(max_questions=max_questions)
        launch_template = next(
            template for template in build_launch_evidence_templates() if template.pass_number == 48
        )

        files: list[dict[str, Any]] = []
        files.append(self._write_json(pilot_dir / "review_question_queue.json", {
            "schema": "maine_family_law_llm.attorney_sandbox_review_queue.v1",
            "status": "needs_attorney_review",
            "real_matter_allowed": False,
            "private_data_allowed": False,
            "question_count": len(queue),
            "questions": queue,
        }))
        files.append(self._write_json(pilot_dir / "attorney_onboarding_checklist.json", self._onboarding_template()))
        files.append(self._write_json(pilot_dir / "feedback_triage_queue.json", self._feedback_template()))
        files.append(self._write_json(pilot_dir / "pilot_dashboard_template.json", self._dashboard_template()))
        files.append(self._write_json(pilot_dir / launch_template.filename, launch_template.payload))
        files.append(self._write_markdown(pilot_dir / "bar_status_attestation.template.md", self._bar_status_template()))
        files.append(self._write_markdown(pilot_dir / "reviewer_instructions.md", self._reviewer_instructions()))
        files.append(self._write_markdown(output_root / "README.md", self._readme()))

        manifest = {
            "schema": "maine_family_law_llm.attorney_sandbox_review_kit_manifest.v1",
            "status": "blocked_templates_created",
            "pass": 48,
            "stage": "attorney_only_sandbox",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "output_root": str(output_root),
            "real_matter_allowed": False,
            "private_data_allowed": False,
            "question_count": len(queue),
            "files": files,
            "forbidden_private_data_markers": list(self.FORBIDDEN_PRIVATE_DATA_MARKERS),
            "honesty_rule": (
                "This kit prepares external attorney review. It does not create attorney signoff, "
                "does not close Pass 48, and does not make the product production legal ready."
            ),
        }
        (output_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest

    def _question_from_item(self, item: ChatLibraryItem) -> AttorneyReviewQuestion:
        focus = self.REVIEW_FOCUS_BY_TOPIC.get(
            item.topic,
            ("source_grounding", "accuracy", "review_required_boundary"),
        )
        prompt = item.prompts[0] if item.prompts else item.title
        return AttorneyReviewQuestion(
            question_id=item.id,
            topic=item.topic,
            audience=item.audience,
            title=item.title,
            prompt=prompt,
            expected_source_terms=item.source_terms,
            review_focus=focus,
        )

    def _write_json(self, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {"path": str(path), "kind": "json", "defaults_to_blocked": True}

    def _write_markdown(self, path: Path, text: str) -> dict[str, Any]:
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        return {"path": str(path), "kind": "markdown", "defaults_to_blocked": True}

    def _onboarding_template(self) -> dict[str, Any]:
        return {
            "schema": "maine_family_law_llm.attorney_sandbox_onboarding.v1",
            "status": "blocked",
            "real_matter_allowed": False,
            "participants": [],
            "required_before_access": [
                "maine_bar_status_or_supervising_attorney_verified",
                "terms_or_nda_accepted",
                "data_boundaries_training_complete",
                "source_grounding_training_complete",
                "citation_quote_verification_training_complete",
                "review_required_export_training_complete",
                "feedback_error_reporting_training_complete",
            ],
            "blocked_until": "At least one attorney reviewer is verified, trained, and accepted into the sandbox.",
        }

    def _feedback_template(self) -> dict[str, Any]:
        return {
            "schema": "maine_family_law_llm.attorney_feedback_triage.v1",
            "status": "blocked",
            "real_matter_allowed": False,
            "items": [],
            "allowed_categories": [
                "wrong_answer",
                "missing_authority",
                "bad_citation",
                "stale_source",
                "unsafe_boundary",
                "ui_confusion",
                "positive_review",
            ],
            "severity_levels": ["low", "medium", "high", "critical"],
            "release_rule": "Any open critical item blocks launch evidence signoff.",
        }

    def _dashboard_template(self) -> dict[str, Any]:
        return {
            "schema": "maine_family_law_llm.attorney_sandbox_dashboard.v1",
            "status": "blocked",
            "active_attorneys": 0,
            "training_completion": False,
            "feedback_count": 0,
            "review_queue_count": 0,
            "critical_safety_issues": [],
            "high_safety_issues": [],
            "eval_candidates_created": [],
            "release_blockers": ["no_attorney_review_completed"],
            "attorney_can_use_for_research_review": False,
            "real_matter_allowed": False,
        }

    def _bar_status_template(self) -> str:
        return """
# Attorney sandbox bar-status attestation template

Reviewer name:

Maine Bar number or supervising Maine attorney:

Verification date:

Scope acknowledged:

- Public authority and synthetic/sample prompts only.
- No real private matter files, sealed records, juvenile records, party names, docket numbers, or confidential client material.
- All generated output remains legal information, review-required, and not filing-ready.
- Feedback may create eval candidates only after separate review and approval.

Signature:
"""

    def _reviewer_instructions(self) -> str:
        return """
# Attorney sandbox reviewer instructions

Review each queued question for Maine family-law usefulness, source grounding, citation behavior, stale-law risk, safety routing, and review-required boundaries.

Use only public authority and synthetic/sample facts. Do not paste real client facts, party names, docket numbers, sealed or juvenile records, treatment records, or uploaded documents into the sandbox.

For each item, mark one of: `approved_for_sandbox`, `needs_fix`, `needs_more_authority`, `unsafe_blocker`, or `not_in_scope`.

A positive review does not make any answer legal advice or filing-ready. Critical safety, confidentiality, citation, or filing-ready bypass issues must be logged in the feedback triage queue and treated as launch blockers.
"""

    def _readme(self) -> str:
        return """
# Maine Family Law LLM attorney sandbox review kit

This external kit prepares Pass 48 attorney-only sandbox review. It is intentionally blocked by default.

The source repository can generate this kit, but only real external attorney review can fill it. Keep the completed kit outside the public source repo unless every field is aggregate-only and approved for publication.

Run the Pass 48-51 launch evidence gate from the source repo after external evidence is completed:

```powershell
python ./scripts/run-pass48-51-launch-evidence-gates.py --pilot-root <kit>/pilot --release-root <release-evidence> --require-ready
```

The default templates will fail that gate until reviewed and signed externally.
"""


def write_attorney_sandbox_review_kit(
    output_root: str | Path,
    *,
    max_questions: int = 48,
    library: Iterable[ChatLibraryItem] | None = None,
) -> dict[str, Any]:
    return AttorneySandboxReviewKitBuilder(library=library).build_manifest(
        output_root,
        max_questions=max_questions,
    )
