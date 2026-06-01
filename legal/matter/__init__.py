"""Matter ingestion and confidential workflow boundaries."""

from legal.matter.document_ingestor import MatterDocumentIngestor
from legal.matter.matter_store import MatterStore
from legal.matter.models import (
    DocumentClassification,
    ExtractedFact,
    IntakeReport,
    Matter,
    MatterDocument,
    MatterEvent,
)

__all__ = [
    "DocumentClassification",
    "ExtractedFact",
    "IntakeReport",
    "Matter",
    "MatterDocument",
    "MatterDocumentIngestor",
    "MatterEvent",
    "MatterStore",
]
