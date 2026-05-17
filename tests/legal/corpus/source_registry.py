from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from legal.data_boundaries.data_classes import DataClass, can_package_by_default, can_train_by_default


@dataclass(frozen=True)
class UseRestrictions:
    training_allowed_by_default: bool
    release_packaging_allowed: bool
    requires_human_review: bool = True
    notes: str = ""

    @classmethod
    def for_data_class(cls, data_class: DataClass | str) -> "UseRestrictions":
        training = can_train_by_default(data_class)
        packaging = can_package_by_default(data_class)
        return cls(
            training_allowed_by_default=training.allowed,
            release_packaging_allowed=packaging.allowed,
            requires_human_review=True,
            notes=f"{training.reason}; {packaging.reason}",
        )


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    source_class: str
    jurisdiction: str
    retrieved_at: datetime
    hash: str
    parser_status: str
    freshness_status: str
    data_class: DataClass | str = DataClass.OFFICIAL_PUBLIC_AUTHORITY
    source_url_or_path: str | None = None
    parser_version: str | None = None
    use_restrictions: UseRestrictions | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.retrieved_at.tzinfo is None:
            object.__setattr__(
                self, "retrieved_at", self.retrieved_at.replace(tzinfo=timezone.utc)
            )
        object.__setattr__(self, "data_class", DataClass(self.data_class))
        if self.use_restrictions is None:
            object.__setattr__(
                self, "use_restrictions", UseRestrictions.for_data_class(self.data_class)
            )

    def validate_boundary_metadata(self) -> list[str]:
        problems: list[str] = []
        required_strings = {
            "source_id": self.source_id,
            "source_class": self.source_class,
            "jurisdiction": self.jurisdiction,
            "hash": self.hash,
            "parser_status": self.parser_status,
            "freshness_status": self.freshness_status,
        }
        for field_name, value in required_strings.items():
            if not value:
                problems.append(f"missing {field_name}")
        if self.use_restrictions is None:
            problems.append("missing use_restrictions")
        return problems

    def to_manifest_record(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_class": self.source_class,
            "jurisdiction": self.jurisdiction,
            "retrieved_at": self.retrieved_at.isoformat(),
            "hash": self.hash,
            "parser_status": self.parser_status,
            "freshness_status": self.freshness_status,
            "data_class": DataClass(self.data_class).value,
            "source_url_or_path": self.source_url_or_path,
            "parser_version": self.parser_version,
            "use_restrictions": {
                "training_allowed_by_default": self.use_restrictions.training_allowed_by_default,
                "release_packaging_allowed": self.use_restrictions.release_packaging_allowed,
                "requires_human_review": self.use_restrictions.requires_human_review,
                "notes": self.use_restrictions.notes,
            },
            "metadata": self.metadata,
        }


class SourceRegistry:
    def __init__(self) -> None:
        self.records: dict[str, SourceRecord] = {}

    def register(self, record: SourceRecord) -> None:
        problems = record.validate_boundary_metadata()
        if problems:
            raise ValueError(f"invalid source record {record.source_id!r}: {', '.join(problems)}")
        self.records[record.source_id] = record

    def get(self, source_id: str) -> SourceRecord | None:
        return self.records.get(source_id)

    def all(self) -> list[SourceRecord]:
        return list(self.records.values())

    def boundary_report(self) -> dict[str, Any]:
        records = self.all()
        private_records = [
            record.source_id
            for record in records
            if record.data_class == DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA
        ]
        return {
            "record_count": len(records),
            "all_records_have_use_restrictions": all(
                record.use_restrictions is not None for record in records
            ),
            "all_records_have_freshness_status": all(bool(record.freshness_status) for record in records),
            "private_matter_record_count": len(private_records),
            "private_matter_training_allowed_by_default": any(
                bool(record.use_restrictions.training_allowed_by_default)
                for record in records
                if record.data_class == DataClass.USER_PROVIDED_CONFIDENTIAL_MATTER_DATA
            ),
        }
