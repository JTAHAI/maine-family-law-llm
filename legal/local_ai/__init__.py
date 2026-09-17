"""Device-scoped local AI setup state and recommendations."""

from .setup import LocalAiSetupError, LocalAiSetupStore, default_local_ai_state_root
from .catalog import LocalAiCatalog, LocalAiCatalogError, default_catalog_path

__all__ = [
    "LocalAiCatalog", "LocalAiCatalogError", "LocalAiSetupError", "LocalAiSetupStore",
    "default_catalog_path", "default_local_ai_state_root",
]
