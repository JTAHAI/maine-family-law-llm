from datetime import datetime, timezone

from legal.corpus.source_registry import SourceRecord, SourceRegistry
from legal.data_boundaries import DataClass


def test_registry_requires_boundary_metadata():
    registry = SourceRegistry()

    record = SourceRecord(
        source_id="test",
        source_class="statute",
        jurisdiction="maine",
        retrieved_at=datetime.now(timezone.utc),
        hash="abc",
        parser_status="ok",
        freshness_status="current",
        data_class=DataClass.OFFICIAL_PUBLIC_AUTHORITY,
    )

    registry.register(record)

    stored = registry.get("test")
    assert stored is not None
    assert stored.use_restrictions.training_allowed_by_default is True
    assert stored.use_restrictions.release_packaging_allowed is False
    assert stored.to_manifest_record()["freshness_status"] == "current"


def test_registry_blocks_incomplete_freshness_status():
    registry = SourceRegistry()
    record = SourceRecord(
        source_id="bad",
        source_class="statute",
        jurisdiction="maine",
        retrieved_at=datetime.now(timezone.utc),
        hash="abc",
        parser_status="ok",
        freshness_status="",
    )

    try:
        registry.register(record)
    except ValueError as exc:
        assert "missing freshness_status" in str(exc)
    else:
        raise AssertionError("expected incomplete source record to fail")
