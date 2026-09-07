"""Optional, model-empty FAST INTERCHANGE local-worker lane.

This package contains no weights, adapters, corpora, worker secrets, or
admitted releases.  It is deliberately separate from the desktop host policy
layer: the host owns source selection, context approval, provenance, and all
legal review gates.
"""

from .fleet import FAST_INTERCHANGE_CAPABILITIES, FastInterchangeFleet, FleetError

# Hardware/fleet inspection must remain available without optional model/API
# dependencies. Only import the strict serving contracts when requested.
_WORKER_EXPORTS = frozenset({
    "ArtifactBinding", "ArtifactInventory", "FastInterchangeError",
    "FastInterchangeRelease", "HotSwapManager", "HotSwapRegistry",
})


def __getattr__(name):
    if name not in _WORKER_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(".worker", __name__), name)
    globals()[name] = value
    return value

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
