from __future__ import annotations

import pytest

from maine_family_law_llm.source_manifest import (
    ManifestValidationError,
    SourceManifestEntry,
    load_manifest,
    validate_manifest,
)
from maine_family_law_llm.sources import DEFAULT_MANIFEST_PATH


def test_seed_manifest_validates_and_preserves_dates() -> None:
    entries = load_manifest(DEFAULT_MANIFEST_PATH)

    assert entries
    assert any(entry.official for entry in entries)
    assert any(entry.source_type == "secondary" for entry in entries)
    assert entries[0].effective_date
    assert entries[0].version_label
    assert entries[0].citation_hint


def test_official_flag_required_and_bad_source_type_rejected() -> None:
    payload = load_manifest(DEFAULT_MANIFEST_PATH)[0].to_dict()
    payload["official"] = "yes"
    with pytest.raises(ManifestValidationError):
        SourceManifestEntry.from_dict(payload)

    payload = load_manifest(DEFAULT_MANIFEST_PATH)[0].to_dict()
    payload["source_type"] = "blog"
    with pytest.raises(ManifestValidationError):
        SourceManifestEntry.from_dict(payload)


def test_secondary_cannot_be_official_or_outrank_official() -> None:
    official = load_manifest(DEFAULT_MANIFEST_PATH)[0]
    secondary_payload = load_manifest(DEFAULT_MANIFEST_PATH)[-1].to_dict()
    secondary_payload["official"] = True
    with pytest.raises(ManifestValidationError):
        SourceManifestEntry.from_dict(secondary_payload)

    secondary_payload["official"] = False
    secondary_payload["source_priority"] = 1
    secondary = SourceManifestEntry.from_dict(secondary_payload)
    with pytest.raises(ManifestValidationError):
        validate_manifest([official, secondary])


def test_citation_hint_required_for_legal_sources() -> None:
    payload = load_manifest(DEFAULT_MANIFEST_PATH)[0].to_dict()
    payload["citation_hint"] = ""
    with pytest.raises(ManifestValidationError):
        SourceManifestEntry.from_dict(payload)
