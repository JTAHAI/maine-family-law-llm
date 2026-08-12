"""Optional, loopback-only local-agent runtime."""

from .contracts import (
    ContextManifest,
    ContextManifestBuilder,
    ContextManifestEntry,
    ContextSource,
    ProvenanceReceipt,
)
from .endpoint import LoopbackEndpoint, LoopbackEndpointPolicy
from .providers import (
    LocalGenerationClient,
    LocalModelError,
    LocalModelResponse,
    OllamaLocalClient,
    OpenAICompatibleLocalClient,
    build_local_client,
)
from .runtime import LocalAgentRunRequest, LocalAgentRunResult, LocalAgentRuntime
from .tools import CapabilityToolBroker, ToolDefinition, ToolInvocation, ToolReceipt

__all__ = [
    "CapabilityToolBroker",
    "ContextManifest",
    "ContextManifestBuilder",
    "ContextManifestEntry",
    "ContextSource",
    "LocalAgentRunRequest",
    "LocalAgentRunResult",
    "LocalAgentRuntime",
    "LocalGenerationClient",
    "LocalModelError",
    "LocalModelResponse",
    "LoopbackEndpoint",
    "LoopbackEndpointPolicy",
    "OllamaLocalClient",
    "OpenAICompatibleLocalClient",
    "ProvenanceReceipt",
    "ToolDefinition",
    "ToolInvocation",
    "ToolReceipt",
    "build_local_client",
]
