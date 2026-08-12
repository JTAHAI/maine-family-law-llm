from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdapterStatus:
    adapter_id: str
    available: bool
    version: str
    license: str
    mode: str
    capabilities: tuple[str, ...]
    detail: str = ""
    network_used: bool = False
    review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentBlock:
    block_id: str
    kind: str
    text: str
    page_number: int = 0
    order: int = 0
    char_start: int = 0
    char_end: int = 0
    confidence: float | None = None
    bbox: tuple[float, float, float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
