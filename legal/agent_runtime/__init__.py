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
    FastInterchangeLocalClient,
    CuratedOllamaReasoningClient,
    OllamaLocalClient,
    OpenAICompatibleLocalClient,
    SentinelOllamaLocalClient,
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
    "FastInterchangeLocalClient",
    "CuratedOllamaReasoningClient",
    "LoopbackEndpoint",
    "LoopbackEndpointPolicy",
    "OllamaLocalClient",
    "OpenAICompatibleLocalClient",
    "SentinelOllamaLocalClient",
    "ProvenanceReceipt",
    "ToolDefinition",
    "ToolInvocation",
    "ToolReceipt",
    "build_local_client",
]
