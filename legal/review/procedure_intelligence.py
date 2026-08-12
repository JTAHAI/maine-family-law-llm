"""Deterministic procedure, posture, and court-form review helpers.

These helpers do not decide legal sufficiency.  They turn document text and
admitted authority metadata into a bounded review checklist.  Unknown or
ambiguous procedure and form freshness fail closed.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

MAX_TEXT_CHARS = 250_000
MAX_SOURCE_CARDS = 2_000
_FORM_ID_RE = re.compile(r"\b(?:FM|PA|CV|PB)[\s-]*\d{3}[A-Z]?\b", re.I)

_POSTURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("appeal", ("notice of appeal", "on appeal", "law court", "appellate record", "record on appeal")),
    ("remand", ("on remand", "remanded", "remand order")),
    ("stay_pending_appeal", ("stay pending appeal", "motion to stay")),
    ("motion_for_findings", ("motion for findings", "rule 52 findings", "additional findings")),
    ("motion_to_reconsider", ("motion to reconsider", "reconsideration")),
    ("motion_for_contempt", ("motion for contempt", "contempt motion", "civil contempt")),
    ("motion_to_enforce", ("motion to enforce", "enforce the order", "enforcement motion")),
    ("motion_to_modify", ("motion to modify", "amend the order", "modify parental rights", "modify child support")),
    ("post_judgment", ("post-judgment", "post judgment", "after judgment", "existing final order")),
    ("temporary_order", ("temporary order", "interim order", "pendente lite")),
    ("final_order", ("final order", "final judgment", "judgment of divorce")),
    ("protection_from_abuse", ("protection from abuse", "pfa complaint", "pfa order")),
    ("initial_complaint", ("complaint for divorce", "complaint for parentage", "initial complaint", "summons and complaint")),
)

_DOCUMENT_TYPE_DEFAULTS = {
    "complaint": "initial_complaint",
    "appeal": "appeal",
    "notice_of_appeal": "appeal",
    "temporary_order": "temporary_order",
    "final_order": "final_order",
    "pfa": "protection_from_abuse",
}

_REVIEW_ITEMS = {
    "motion_for_contempt": [
        "Identify the exact current order language allegedly not followed.",
        "Separate each dated event from legal conclusions and link it to record evidence.",
        "Confirm procedure, notice or service, requested relief, and any ability-to-comply issue with a qualified reviewer.",
    ],
    "motion_to_modify": [
        "Identify the current order and the exact terms requested to change.",
        "State the changed facts and map each material fact to evidence.",
        "Confirm the correct motion, accompanying forms, notice or service, and hearing procedure.",
    ],
    "motion_to_enforce": [
        "Identify the operative order and each obligation to be enforced.",
        "Map each alleged noncompliance event to a dated record span.",
        "Confirm whether enforcement, contempt, modification, or another procedure fits the requested relief.",
    ],
    "appeal": [
        "Confirm the appealable order, filing date, and applicable deadline from current authority.",
        "Check preservation, findings, transcripts, and the record on appeal.",
        "Separate the standard of review from the merits argument.",
    ],
    "protection_from_abuse": [
        "Keep immediate safety routing separate from ordinary family-case strategy.",
        "Confirm the current order, hearing status, service status, and evidence requested for review.",
        "Do not treat a PFA record as a substitute for independent family-case findings.",
    ],
    "initial_complaint": [
        "Confirm jurisdiction, venue, parties, service, and the requested relief.",
        "Check the current official form packet and required attachments.",
        "Map factual assertions to source records before filing review.",
    ],
    "temporary_order": [
        "Identify the temporary relief requested and the facts supporting urgency.",
        "Confirm notice, hearing procedure, and required affidavits or forms.",
        "Distinguish temporary requests from final requested relief.",
    ],
    "final_order": [
        "Confirm required findings, incorporated documents, signatures, and entry date.",
        "Check that restrictions and factual findings have identified support.",
        "Confirm any post-judgment or appeal deadlines with current authority.",
    ],
}

_FORM_REVIEW_POSTURES = {
    "initial_complaint",
    "temporary_order",
    "motion_for_contempt",
    "motion_to_enforce",
    "motion_to_modify",
    "appeal",
    "protection_from_abuse",
}


def _clean_text(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _normalize_form_id(value: str) -> str:
    compact = re.sub(r"[\s-]+", "-", value.strip().upper())
    prefix, number = compact.split("-", 1)
    return f"{prefix}-{number}"


def extract_form_ids(text: str) -> list[str]:
    return sorted({_normalize_form_id(match.group(0)) for match in _FORM_ID_RE.finditer(_clean_text(text))})


def build_procedure_posture_report(
    *,
    title: str,
    content: str,
    document_type: str = "draft",
) -> dict[str, Any]:
    combined = f"{_clean_text(title, 500)}\n{_clean_text(content)}".casefold()
    candidates: list[dict[str, Any]] = []
    for priority, (posture, phrases) in enumerate(_POSTURE_RULES):
        matched = [phrase for phrase in phrases if phrase in combined]
        if matched:
            candidates.append({"posture": posture, "matched_signals": matched, "score": len(matched), "priority": priority})

    default = _DOCUMENT_TYPE_DEFAULTS.get(str(document_type or "").strip().casefold())
    if default and not any(row["posture"] == default for row in candidates):
        candidates.append({"posture": default, "matched_signals": [f"document_type:{document_type}"], "score": 1, "priority": len(_POSTURE_RULES)})

    candidates.sort(key=lambda row: (-int(row["score"]), int(row.get("priority", 999)), str(row["posture"])))
    selected = candidates[0]["posture"] if candidates else "unknown"
    top_score = int(candidates[0]["score"]) if candidates else 0
    equally_ranked = [row for row in candidates if int(row["score"]) == top_score]
    contextual = {"post_judgment", "final_order"}
    competing = {row["posture"] for row in equally_ranked if row["posture"] != selected and row["posture"] not in contextual}
    ambiguous = bool(competing)

    blockers: list[str] = []
    if selected == "unknown":
        blockers.append("procedure_posture_not_identified")
    if ambiguous:
        blockers.append("procedure_posture_ambiguous")

    status = "checked" if selected != "unknown" and not ambiguous else "review_required"
    form_review_required = selected in _FORM_REVIEW_POSTURES or str(document_type or "").casefold() in {
        "motion", "affidavit", "parenting_plan", "court_form_notes"
    }
    items = list(_REVIEW_ITEMS.get(selected, [
        "Confirm the procedural posture and requested relief with current Maine authority.",
        "Identify any required filing, service, hearing, findings, and form requirements.",
        "Keep factual assertions linked to record evidence and legal assertions linked to admitted authority.",
    ]))
    return {
        "schema_version": "procedure_posture_review_v2",
        "status": status,
        "procedural_posture": selected,
        "candidates": candidates[:12],
        "ambiguous": ambiguous,
        "blockers": blockers,
        "review_items": items,
        "form_review_required": form_review_required,
        "review_required": True,
        "disclaimer": "This is a deterministic workflow checklist, not a legal conclusion or proof that the selected procedure is correct.",
    }


def _iter_source_cards(authority_result: dict[str, Any]) -> Iterable[dict[str, Any]]:
    containers = [
        authority_result.get("sources"),
        authority_result.get("source_cards"),
        (authority_result.get("verification_report") or {}).get("sources"),
        (authority_result.get("verification_report") or {}).get("source_cards"),
    ]
    count = 0
    for container in containers:
        if not isinstance(container, list):
            continue
        for row in container:
            if isinstance(row, dict):
                yield row
                count += 1
                if count >= MAX_SOURCE_CARDS:
                    return


def build_form_freshness_report(
    *,
    content: str,
    authority_result: dict[str, Any],
    procedure_report: dict[str, Any],
) -> dict[str, Any]:
    referenced = extract_form_ids(content)
    candidates: dict[str, list[dict[str, Any]]] = {}
    for card in _iter_source_cards(authority_result):
        metadata = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
        source_class = str(card.get("source_class") or metadata.get("source_class") or metadata.get("source_type") or "").casefold()
        joined = " ".join(
            str(value or "")
            for value in (
                card.get("form_id"), metadata.get("form_id"), card.get("citation"), card.get("title"), metadata.get("title")
            )
        )
        ids = extract_form_ids(joined)
        if not ids or ("form" not in source_class and not any(value in joined.casefold() for value in ("court form", "form packet"))):
            continue
        freshness = str(
            card.get("freshness_status")
            or metadata.get("freshness_status")
            or metadata.get("retrieved_freshness_status")
            or "unknown"
        ).casefold()
        for form_id in ids:
            candidates.setdefault(form_id, []).append({
                "form_id": form_id,
                "source_id": str(card.get("source_id") or metadata.get("source_id") or "")[:256],
                "title": str(card.get("title") or metadata.get("title") or form_id)[:300],
                "version_date": str(card.get("version_date") or metadata.get("version_date") or "")[:80],
                "freshness_status": freshness,
                "authority_status": str(card.get("authority_status") or metadata.get("authority_status") or "")[:80],
            })

    entries: list[dict[str, Any]] = []
    stale_forms: list[str] = []
    unknown_forms: list[str] = []
    current_forms: list[str] = []
    for form_id in referenced:
        rows = candidates.get(form_id, [])
        statuses = {str(row.get("freshness_status") or "unknown") for row in rows}
        if statuses & {"current", "fresh", "verified_current"}:
            status = "current"
            current_forms.append(form_id)
        elif statuses & {"stale", "superseded", "expired"}:
            status = "stale"
            stale_forms.append(form_id)
        else:
            status = "unknown"
            unknown_forms.append(form_id)
        entries.append({"form_id": form_id, "status": status, "candidates": rows[:10]})

    form_review_required = bool(procedure_report.get("form_review_required"))
    if form_review_required and not referenced:
        unknown_forms.append("required_form_selection_not_confirmed")

    stale_forms = sorted(set(stale_forms))
    unknown_forms = sorted(set(unknown_forms))
    current_forms = sorted(set(current_forms))
    status = "checked" if not stale_forms and not unknown_forms else "review_required"
    return {
        "schema_version": "court_form_freshness_review_v2",
        "status": status,
        "referenced_forms": referenced,
        "current_forms": current_forms,
        "stale_forms": stale_forms,
        "unknown_forms": unknown_forms,
        "entries": entries,
        "form_review_required": form_review_required,
        "blockers": [*(f"stale_form:{item}" for item in stale_forms), *(f"unknown_form_freshness:{item}" for item in unknown_forms)],
        "review_required": True,
        "disclaimer": "Current-form status is based only on the admitted active authority generation. Unknown status blocks filing review.",
    }
