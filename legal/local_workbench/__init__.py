"""Local-first workbench control-plane primitives.

The package deliberately manages only local, reviewable metadata.  It does not
download model weights, enable remote providers, or execute arbitrary commands.
"""

from .service import LocalWorkbenchError, LocalWorkbenchService

__all__ = ["LocalWorkbenchError", "LocalWorkbenchService"]
