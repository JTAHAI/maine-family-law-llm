from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


ROLE_QUESTION_MINIMUMS = {
    "gal": 800,
    "court": 500,
    "lawyer": 400,
    "ada_prosecutor_investigator": 500,
    "board_bar_counsel": 300,
    "appellate": 300,
    "transcript_audio": 250,
    "tyler_efile": 250,
    "school_medical_counseling": 400,
    "privacy_limitations": 250,
}

ROLE_CATEGORY_MAP = {
    "gal": ("child stability", "contact implementation", "school/medical/therapy review", "gatekeeping allegations"),
    "court": ("docket/source navigation", "orders and filings", "service and notice", "missing proof"),
    "lawyer": ("10-minute overview", "issue map", "urgent deadlines", "open motions/appeals"),
    "ada_prosecutor_investigator": ("criminal context", "good-faith communications", "official verification", "witness/entity review"),
    "board_bar_counsel": ("professional conduct", "candor/process integrity", "nonresponse", "implementation friction"),
    "appellate": ("record preservation", "standard of review", "missing findings", "prejudice/relief"),
    "transcript_audio": ("transcript order status", "audio alternatives", "record completion", "service barriers"),
    "tyler_efile": ("submission defects", "rejections", "accepted entries", "support/access barriers"),
    "school_medical_counseling": ("attendance", "records access", "provider logistics", "sensitivity handling"),
    "privacy_limitations": ("not legal advice", "official verification", "privacy controls", "scope boundaries"),
}

ROLE_SOURCE_TYPES = {
    "gal": ["school_record", "provider_record", "email", "court_order"],
    "court": ["court_order", "filing", "service_record", "docket_entry"],
    "lawyer": ["timeline_index", "court_order", "email", "proof_report"],
    "ada_prosecutor_investigator": ["court_order", "email", "provider_record", "timeline_index"],
    "board_bar_counsel": ["email", "filing", "service_record", "proof_report"],
    "appellate": ["court_order", "transcript_record", "filing", "proof_report"],
    "transcript_audio": ["transcript_record", "audio_record", "filing", "service_record"],
    "tyler_efile": ["service_record", "docket_entry", "filing", "proof_report"],
    "school_medical_counseling": ["school_record", "provider_record", "email", "proof_report"],
    "privacy_limitations": ["proof_report", "timeline_index", "privacy_summary"],
}


def generate_builtin_question_bank() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for role, count in ROLE_QUESTION_MINIMUMS.items():
        categories = ROLE_CATEGORY_MAP[role]
        source_types = ROLE_SOURCE_TYPES[role]
        for idx in range(1, count + 1):
            category = categories[(idx - 1) % len(categories)]
            subcategory = f"{category.lower().replace('/', '_').replace(' ', '_')}_{((idx - 1) % 5) + 1}"
            rows.append(
                {
                    "question_id": f"{role.upper()}-{idx:04d}",
                    "role": role,
                    "category": category,
                    "subcategory": subcategory,
                    "question_text": f"For {role.replace('_', ' ')}, what does the corpus show about {category}?",
                    "plain_language_variant": f"Show me the records for {category}.",
                    "expected_answer_type": "source_grounded_summary",
                    "required_source_types": source_types,
                    "privacy_flags": ["child_sensitive_possible"] if role in {"gal", "school_medical_counseling"} else [],
                    "expected_not_found_behavior": "not found in the indexed corpus",
                    "test_query": f"{role.replace('_', ' ')} {category}",
                    "scoring_notes": "Green requires cited corpus evidence; gray requires a not-found answer.",
                }
            )
    return rows


def write_question_bank(path: Path, rows: Iterable[dict[str, object]] | None = None) -> Path:
    payload = list(rows or generate_builtin_question_bank())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in payload:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return path
