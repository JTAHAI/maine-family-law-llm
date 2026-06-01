from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class DataClass(StrEnum):
    OFFICIAL_PUBLIC_AUTHORITY = "official_public_authority"
    PUBLIC_NON_OFFICIAL_SOURCE = "public_non_official_source"
    LICENSED_SECONDARY_SOURCE = "licensed_secondary_source"
    USER_PROVIDED_CONFIDENTIAL_MATTER_DATA = "user_provided_confidential_matter_data"
    SYNTHETIC_EVAL_DATA = "synthetic_eval_data"
    ATTORNEY_REVIEWED_EVAL_DATA = "attorney_reviewed_eval_data"
    MODEL_ARTIFACT = "model_artifact"
    AUDIT_RECORD = "audit_record"


class StoreName(StrEnum):
    OFFICIAL_AUTHORITY = "official_authority_store"
    PARSED_AUTHORITY = "parsed_authority_store"
    MATTER = "matter_store"
    EVAL = "eval_store"
    EMBEDDING = "embedding_store"
    AUDIT = "audit_store"
    MODEL_REGISTRY = "model_registry"


@dataclass(frozen=True)
class DataBoundaryDecision:
    allowed: bool
    reason: str


_STORE_ALLOWLIST: dict[StoreName, set[DataClass]] = {
    StoreName.OFFICIAL_AUTHORITY: {DataClass.OFFICIAL_PUBLIC_AUTHORITY},
    StoreName.PARSED_AUTHORITY: {
        DataClass.OFFICIAL_PUBLIC_AUTHORITY,
        DataClass.PUBLIC_NON_OFFICIAL_SOURCE,
        DataClass.LICENSED_SECONDARY_SOURCE,
    },
    StoreName.MATTER: {DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA},
    StoreName.EVAL: {DataClass.SYNTHETIC_EVAL_DATA, DataClass.ATTORNEY_REVIEWED_EVAL_DATA},
    StoreName.EMBEDDING: {
        DataClass.MODEL_ARTIFACT,
        DataClass.OFFICIAL_PUBLIC_AUTHORITY,
        DataClass.PUBLIC_NON_OFFICIAL_SOURCE,
        DataClass.LICENSED_SECONDARY_SOURCE,
    },
    StoreName.AUDIT: {DataClass.AUDIT_RECORD},
    StoreName.MODEL_REGISTRY: {DataClass.MODEL_ARTIFACT},
}

_PRIVATE_CLASSES = {
    DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA,
    DataClass.ATTORNEY_REVIEWED_EVAL_DATA,
    DataClass.AUDIT_RECORD,
}

_TRAINING_ALLOWED_BY_DEFAULT = {
    DataClass.OFFICIAL_PUBLIC_AUTHORITY,
    DataClass.SYNTHETIC_EVAL_DATA,
}

_RELEASE_ALLOWED_BY_DEFAULT = {DataClass.SYNTHETIC_EVAL_DATA}


def coerce_data_class(value: DataClass | str) -> DataClass:
    try:
        return value if isinstance(value, DataClass) else DataClass(value)
    except ValueError as exc:
        raise ValueError(f"unknown data class: {value!r}") from exc


def coerce_store(value: StoreName | str) -> StoreName:
    try:
        return value if isinstance(value, StoreName) else StoreName(value)
    except ValueError as exc:
        raise ValueError(f"unknown store name: {value!r}") from exc


def assert_known_data_classes(values: Iterable[str]) -> None:
    for value in values:
        coerce_data_class(value)


def can_store(data_class: DataClass | str, store_name: StoreName | str) -> DataBoundaryDecision:
    dc = coerce_data_class(data_class)
    store = coerce_store(store_name)
    allowed = dc in _STORE_ALLOWLIST[store]
    if allowed:
        return DataBoundaryDecision(True, f"{dc.value} is allowed in {store.value}")
    return DataBoundaryDecision(False, f"{dc.value} must not be stored in {store.value}")


def can_train_by_default(data_class: DataClass | str) -> DataBoundaryDecision:
    dc = coerce_data_class(data_class)
    if dc in _TRAINING_ALLOWED_BY_DEFAULT:
        return DataBoundaryDecision(True, f"{dc.value} may be used for default shared training/eval")
    return DataBoundaryDecision(False, f"{dc.value} is excluded from shared training by default")


def can_package_by_default(data_class: DataClass | str) -> DataBoundaryDecision:
    dc = coerce_data_class(data_class)
    if dc in _RELEASE_ALLOWED_BY_DEFAULT:
        return DataBoundaryDecision(True, f"{dc.value} may be packaged when private scan passes")
    return DataBoundaryDecision(False, f"{dc.value} must not be packaged in source releases")


def is_private_or_sensitive(data_class: DataClass | str) -> bool:
    return coerce_data_class(data_class) in _PRIVATE_CLASSES
