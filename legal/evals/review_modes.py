from __future__ import annotations

from typing import Any

ATTORNEY_REVIEW_MARKERS = ("attorney", "lawyer", "counsel", "reviewed_final", "final_reviewed")
OPERATOR_SOURCE_BACKED_MARKERS = (
    "operator_source_backed",
    "operator_reviewed",
    "operator_verified",
    "source_backed",
    "source_verified",
    "source-grounded",
    "source_grounded",
)
SEED_REVIEW_MARKERS = ("seed", "synthetic", "fixture", "generated", "schema_validation")
VALID_REVIEW_MODES = ("attorney_reviewed", "operator_source_backed")


def normalize_review_mode(review_mode: str | None) -> str:
    mode = (review_mode or "attorney_reviewed").strip().lower().replace("-", "_")
    if mode in {"attorney", "lawyer", "counsel"}:
        mode = "attorney_reviewed"
    if mode in {"operator", "source_backed", "operator_reviewed", "operator_verified"}:
        mode = "operator_source_backed"
    if mode not in VALID_REVIEW_MODES:
        raise ValueError(f"unsupported review_mode={review_mode!r}; expected one of {VALID_REVIEW_MODES}")
    return mode


def is_seed_or_synthetic(review_status: str, method: str) -> bool:
    value = f"{review_status} {method}".lower()
    return any(marker in value for marker in SEED_REVIEW_MARKERS)


def is_attorney_reviewed(review_status: str, method: str) -> bool:
    value = f"{review_status} {method}".lower()
    return any(marker in value for marker in ATTORNEY_REVIEW_MARKERS) and not is_seed_or_synthetic(
        review_status, method
    )


def is_operator_source_backed(row: dict[str, Any], review_status: str, method: str) -> bool:
    value = f"{review_status} {method} {row.get('review_mode', '')} {row.get('basis', '')}".lower()
    marker_match = any(marker in value for marker in OPERATOR_SOURCE_BACKED_MARKERS)
    explicit_bool = bool(row.get("operator_source_backed") or row.get("source_backed"))
    has_source_lineage = bool(
        row.get("source_id")
        or row.get("record_id")
        or row.get("source_ids")
        or row.get("citation")
        or row.get("quoted_text")
        or row.get("quote")
    )
    return (marker_match or explicit_bool) and has_source_lineage and not is_seed_or_synthetic(review_status, method)


def reviewed_count_key(review_mode: str) -> str:
    return "attorney_reviewed" if normalize_review_mode(review_mode) == "attorney_reviewed" else "operator_source_backed"


def reviewed_for_mode(
    *, row: dict[str, Any], review_status: str, method: str, review_mode: str
) -> bool:
    mode = normalize_review_mode(review_mode)
    if mode == "attorney_reviewed":
        return is_attorney_reviewed(review_status, method)
    return is_operator_source_backed(row, review_status, method)


def reviewer_status_for_metric(*, review_mode: str, reviewed: bool) -> str:
    mode = normalize_review_mode(review_mode)
    return mode if reviewed else f"blocked_missing_full_{mode}"


def basis_suffix(review_mode: str) -> str:
    return normalize_review_mode(review_mode)
