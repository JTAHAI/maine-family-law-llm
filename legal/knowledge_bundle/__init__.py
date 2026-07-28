"""Portable Markdown knowledge bundles for legal sources and playbooks.

This package implements a security-hardened subset inspired by the Apache-2.0
Open Knowledge Format project in GoogleCloudPlatform/knowledge-catalog.
"""

from .bundle import (
    BundleValidationReport,
    build_bundle,
    concept_path,
    read_concept,
    validate_bundle,
    write_concept,
)
from .models import KnowledgeBundleError, KnowledgeConcept, parse_concept_id

__all__ = [
    "BundleValidationReport",
    "KnowledgeBundleError",
    "KnowledgeConcept",
    "build_bundle",
    "concept_path",
    "parse_concept_id",
    "read_concept",
    "validate_bundle",
    "write_concept",
]
