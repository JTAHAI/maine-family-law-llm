from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_LANES = (
    "Parent-child contact",
    "Electronic contact",
    "In-person contact",
    "Parenting time",
    "Shared parental rights",
    "Records access",
    "Medical/dental records",
    "School records",
    "Therapy/counseling records",
    "Insurance/MaineCare/DHHS",
    "School attendance",
    "Provider communications",
    "Reunification counseling",
    "GAL history",
    "PFA / protection order overlap",
    "Criminal matter overlap",
    "Court orders",
    "Motions",
    "Appeals",
    "Transcript/audio/record access",
    "Tyler/eFile/Odyssey",
    "Filing/service/notice",
    "Professional conduct / Board / Bar Counsel",
    "Federal access-to-courts / due process",
    "Lawyer communications",
)

LANE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Parent-child contact": ("contact", "parent-child", "visitation", "parenting time"),
    "Electronic contact": ("facetime", "video call", "electronic contact", "phone call"),
    "In-person contact": ("in-person", "supervised visit", "contact center"),
    "Shared parental rights": ("shared parental rights", "decision-making", "allocated authority"),
    "Records access": ("records access", "authorization", "release", "records"),
    "Medical/dental records": ("medical", "dental", "hospital", "doctor", "provider"),
    "School records": ("school", "attendance", "grade", "teacher", "records office"),
    "Therapy/counseling records": ("therapy", "counseling", "therapist", "session"),
    "Insurance/MaineCare/DHHS": ("mainecare", "insurance", "dhhs", "coverage"),
    "School attendance": ("attendance", "tardy", "absence"),
    "Provider communications": ("provider", "office", "scheduling", "care coordinator"),
    "Reunification counseling": ("reunification", "family therapy", "therapeutic reunification"),
    "GAL history": ("gal", "guardian ad litem", "guardian-ad-litem"),
    "PFA / protection order overlap": ("pfa", "protection from abuse", "protective order"),
    "Criminal matter overlap": ("criminal", "ada", "prosecutor", "conditions of release"),
    "Court orders": ("order", "ordered", "decree", "judgment"),
    "Motions": ("motion", "affidavit", "filing", "submitted"),
    "Appeals": ("appeal", "law court", "appellate", "appendix"),
    "Transcript/audio/record access": ("transcript", "audio", "record completion", "escribers", "oto"),
    "Tyler/eFile/Odyssey": ("tyler", "efile", "odyssey", "rejection notice"),
    "Filing/service/notice": ("service", "notice", "receipt", "entry"),
    "Professional conduct / Board / Bar Counsel": ("board", "bar counsel", "grievance", "professional conduct"),
    "Federal access-to-courts / due process": ("federal", "due process", "district of maine"),
    "Lawyer communications": ("counsel", "attorney", "law office", "legal correspondence"),
}

PROMOTIONAL_TERMS = (
    "newsletter",
    "sale",
    "coupon",
    "unsubscribe",
    "volunteermatch",
    "board member recruitment",
)


def classify_legal_matter(text: str, path: Path, source_type: str) -> dict[str, Any]:
    lowered = f"{path.as_posix()} {source_type} {text}".lower()
    issue_lanes: list[str] = []
    for lane, keywords in LANE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            issue_lanes.append(lane)
    issue_lanes = sorted(dict.fromkeys(issue_lanes))

    promotional_hit = next((term for term in PROMOTIONAL_TERMS if term in lowered), "")
    legal_score = min(100, 18 + len(issue_lanes) * 14)
    if promotional_hit:
        legal_score = 0

    external_release_allowed = bool(issue_lanes) and not promotional_hit
    needs_human_review = bool("privileged" in lowered or "unknown" in lowered)
    inclusion_reason = (
        f"Matched issue lanes: {', '.join(issue_lanes)}."
        if issue_lanes
        else "No Maine family-law issue lane match was found."
    )
    exclusion_reason = ""
    if promotional_hit:
        exclusion_reason = f"Matched non-legal promotional/personal term: {promotional_hit}."
    elif not issue_lanes:
        exclusion_reason = "No legal-matter issue lane match."

    return {
        "legal_score": legal_score,
        "issue_lanes": issue_lanes,
        "inclusion_reason": inclusion_reason,
        "exclusion_reason": exclusion_reason,
        "external_release_allowed": external_release_allowed,
        "needs_human_review": needs_human_review,
    }
