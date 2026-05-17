from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class FailureCluster:
    reason: str
    count: int
    examples: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"reason": self.reason, "count": self.count, "examples": self.examples}


class FailureClusterer:
    """Small deterministic failure clustering for release/eval dashboards."""

    def cluster(self, failures: Iterable[dict[str, Any] | str]) -> list[FailureCluster]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for item in failures:
            if isinstance(item, str):
                reason = item.split(":", 1)[0]
                example = item
            else:
                reason = str(item.get("reason") or item.get("blocker") or item.get("status") or "unknown")
                example = str(item.get("example") or item.get("metric") or item)
            grouped[reason].append(example)
        return [
            FailureCluster(reason=reason, count=len(examples), examples=examples[:3])
            for reason, examples in sorted(grouped.items(), key=lambda pair: (-len(pair[1]), pair[0]))
        ]
