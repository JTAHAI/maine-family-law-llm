"""Bounded, local-only document intelligence adapters."""

from .service import (
    DocumentIntelligenceError,
    analyze_document,
    create_ocr_preservation_copy,
    create_redacted_copy,
    document_intelligence_status,
)

__all__ = [
    "DocumentIntelligenceError",
    "analyze_document",
    "create_ocr_preservation_copy",
    "create_redacted_copy",
    "document_intelligence_status",
]
