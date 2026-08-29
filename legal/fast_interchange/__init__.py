"""Optional, model-empty FAST INTERCHANGE local-worker lane.

This package contains no weights, adapters, corpora, worker secrets, or
admitted releases.  It is deliberately separate from the desktop host policy
layer: the host owns source selection, context approval, provenance, and all
legal review gates.
"""

from .fleet import FAST_INTERCHANGE_CAPABILITIES, FastInterchangeFleet, FleetError
from .worker import (
    ArtifactBinding,
    ArtifactInventory,
    FastInterchangeError,
    FastInterchangeRelease,
    HotSwapManager,
    HotSwapRegistry,
)

__all__ = [
    "ArtifactBinding",
    "ArtifactInventory",
    "FAST_INTERCHANGE_CAPABILITIES",
    "FastInterchangeError",
    "FastInterchangeFleet",
    "FastInterchangeRelease",
    "FleetError",
    "HotSwapManager",
    "HotSwapRegistry",
]
