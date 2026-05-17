from __future__ import annotations

from dataclasses import dataclass

from legal.data_boundaries.data_classes import DataClass, coerce_data_class


@dataclass(frozen=True)
class RetentionPolicy:
    data_class: DataClass
    retain: str
    delete_on_user_request: bool | str
    minimum_action: str | None = None


_POLICIES: dict[DataClass, RetentionPolicy] = {
    DataClass.OFFICIAL_PUBLIC_AUTHORITY: RetentionPolicy(
        DataClass.OFFICIAL_PUBLIC_AUTHORITY, "indefinite_snapshot_history", False
    ),
    DataClass.PUBLIC_NON_OFFICIAL_SOURCE: RetentionPolicy(
        DataClass.PUBLIC_NON_OFFICIAL_SOURCE, "until_source_review_or_superseded", False
    ),
    DataClass.LICENSED_SECONDARY_SOURCE: RetentionPolicy(
        DataClass.LICENSED_SECONDARY_SOURCE, "license_term_or_shorter", False
    ),
    DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA: RetentionPolicy(
        DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA,
        "matter_policy_defined",
        True,
        "delete_source_file_derived_text_embeddings_and_private_work_product",
    ),
    DataClass.SYNTHETIC_EVAL_DATA: RetentionPolicy(
        DataClass.SYNTHETIC_EVAL_DATA, "project_lifetime", False
    ),
    DataClass.ATTORNEY_REVIEWED_EVAL_DATA: RetentionPolicy(
        DataClass.ATTORNEY_REVIEWED_EVAL_DATA, "review_approval_term", True
    ),
    DataClass.MODEL_ARTIFACT: RetentionPolicy(
        DataClass.MODEL_ARTIFACT, "until_model_deprecated_and_audit_window_closed", False
    ),
    DataClass.AUDIT_RECORD: RetentionPolicy(
        DataClass.AUDIT_RECORD, "firm_or_deployment_policy", "redact_or_tombstone_if_allowed"
    ),
}


def retention_policy_for(data_class: DataClass | str) -> RetentionPolicy:
    return _POLICIES[coerce_data_class(data_class)]
