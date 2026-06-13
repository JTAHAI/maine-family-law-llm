from __future__ import annotations

from pathlib import Path
from typing import Any


PERSONAL_TERMS = (
    "newsletter",
    "vacation",
    "birthday",
    "promotion",
    "coupon",
    "fundraising campaign",
    "recruitment outreach",
    "volunteer application",
)
PRIVILEGED_TERMS = ("privileged", "attorney-client", "work product")
CHILD_TERMS = ("child", "minor", "student", "juvenile")
MEDICAL_TERMS = ("medical", "dental", "doctor", "hospital", "mainecare", "insurance")
THERAPY_TERMS = ("therapy", "therapist", "counseling", "mental health")
SCHOOL_TERMS = ("school", "attendance", "teacher", "classroom", "student support")


def classify_privacy(text: str, path: Path, source_type: str, issue_lanes: list[str]) -> dict[str, Any]:
    lowered = f"{path.as_posix()} {source_type} {text}".lower()
    classes: list[str] = []
    privacy_risk_score = 5
    sensitivity_score = 0

    if any(term in lowered for term in PERSONAL_TERMS):
        classes.append("personal_nonlegal")
        privacy_risk_score = max(privacy_risk_score, 95)
    if any(term in lowered for term in PRIVILEGED_TERMS):
        classes.append("privileged_or_possible_privileged")
        privacy_risk_score = max(privacy_risk_score, 100)
    if any(term in lowered for term in CHILD_TERMS):
        classes.append("child_sensitive")
        sensitivity_score = max(sensitivity_score, 80)
    if any(term in lowered for term in MEDICAL_TERMS):
        classes.append("medical_sensitive")
        sensitivity_score = max(sensitivity_score, 88)
    if any(term in lowered for term in THERAPY_TERMS):
        classes.append("therapy_sensitive")
        sensitivity_score = max(sensitivity_score, 90)
    if any(term in lowered for term in SCHOOL_TERMS):
        classes.append("school_sensitive")
        sensitivity_score = max(sensitivity_score, 76)
    if issue_lanes:
        classes.append("external_legal_matter_allowed")
    if not classes:
        classes.append("public_court_record")

    blocked = {"personal_nonlegal", "privileged_or_possible_privileged", "ambiguous_needs_human_review"}
    external_release_allowed = not any(name in blocked for name in classes)
    if "external_legal_matter_allowed" not in classes and external_release_allowed and issue_lanes:
        classes.append("external_legal_matter_allowed")

    return {
        "privacy_classes": sorted(dict.fromkeys(classes)),
        "privacy_status": sorted(dict.fromkeys(classes))[0],
        "privacy_risk_score": privacy_risk_score,
        "sensitivity_score": sensitivity_score,
        "external_release_allowed": external_release_allowed,
    }
