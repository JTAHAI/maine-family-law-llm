from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

from .schemas import WorkerTurnRequest, WorkerTurnResult, safe_identifier


class DeliberationWorker(Protocol):
    worker_id: str
    role: str

    def run(self, request: WorkerTurnRequest) -> WorkerTurnResult: ...


def _stable_score(*parts: str) -> int:
    payload = "|".join(parts).encode("utf-8")
    return int(sha256(payload).hexdigest()[:8], 16)


def _pick(items: list[str], seed: int, count: int) -> list[str]:
    if not items:
        return []
    selected: list[str] = []
    for offset in range(min(count, len(items))):
        index = (seed + offset * 7) % len(items)
        candidate = items[index]
        if candidate not in selected:
            selected.append(candidate)
    return selected


def _compact(text: str, limit: int = 140) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned[:limit]


@dataclass
class MockDeliberationWorker:
    worker_id: str
    role: str
    perspective: str
    confidence_bias: str = "medium"

    def run(self, request: WorkerTurnRequest) -> WorkerTurnResult:
        seed = _stable_score(request.run_id, request.task, request.role, self.worker_id, str(request.round))
        source_ids = [str(item.get("source_id") or item.get("record_id") or "") for item in request.approved_context_packet.get("sources", [])]
        source_ids = [item for item in source_ids if item]
        claims = self._claims(request, source_ids, seed)
        critiques = self._critiques(request, seed)
        omissions = self._omissions(request, seed)
        requested_sources = [{"source_id": source_id, "reason": "requested by worker"} for source_id in _pick(source_ids, seed, 2)]
        rationale = [
            _compact(f"{self.role} sees {len(source_ids)} source lanes and keeps the claim bounded to the approved packet."),
            _compact(f"{self.perspective}: {_pick([request.task, request.role, request.run_id], seed, 1)[0] if request.task else 'analysis continues'}"),
        ]
        return WorkerTurnResult(
            worker_id=safe_identifier(self.worker_id, fallback="worker"),
            model_runtime_metadata={
                "worker_type": "deterministic_mock",
                "role": self.role,
                "perspective": self.perspective,
                "loopback_only": True,
                "remote_providers_enabled": False,
            },
            round=request.round,
            claims=claims,
            source_refs=[{"source_id": source_id, "lane": self._lane_for_source(source_id, request)} for source_id in _pick(source_ids, seed, 3)],
            concise_rationale_summaries=rationale,
            critiques=critiques,
            omissions=omissions,
            assumptions=self._assumptions(request, seed),
            requested_sources=requested_sources,
            confidence_category=self.confidence_bias,
            usage={
                "prompt_tokens": min(512, 64 + len(request.approved_context_packet.get("sources", [])) * 32),
                "completion_tokens": min(256, 40 + len(claims) * 24),
                "tool_calls": len(request.tool_grants),
            },
            finish_status="completed_review_required",
            errors=[],
        )

    def _claims(self, request: WorkerTurnRequest, source_ids: list[str], seed: int) -> list[dict[str, Any]]:
        question = _compact(str(request.approved_context_packet.get("question") or request.task), 200)
        claims: list[dict[str, Any]] = []
        base = {
            "worker_id": self.worker_id,
            "role": self.role,
            "claim_type": "analysis",
            "materiality": "material" if request.round <= 2 else "contextual",
            "source_refs": [{"source_id": source_id} for source_id in _pick(source_ids, seed, 2)],
            "confidence_category": self.confidence_bias,
        }
        if self.role in {"scope_scout", "counterpoint_scout"}:
            claims.append(
                base
                | {
                    "canonical_claim": f"The approved packet is bounded to the exact question: {question}.",
                    "position": "maintain",
                    "support_status": "source_supported",
                }
            )
            claims.append(
                base
                | {
                    "canonical_claim": "Some factual support may remain incomplete without further record review.",
                    "position": "caution",
                    "support_status": "unverified",
                }
            )
        elif self.role == "contrary_authority":
            claims.append(
                base
                | {
                    "canonical_claim": "A narrower or contrary authority reading may still limit the answer.",
                    "position": "contradict",
                    "support_status": "worker_disagreement",
                }
            )
        elif self.role == "record_checker":
            claims.append(
                base
                | {
                    "canonical_claim": "Private records can support facts but cannot convert the record into legal authority.",
                    "position": "narrow",
                    "support_status": "evidence_supported",
                }
            )
        else:
            claims.append(
                base
                | {
                    "canonical_claim": f"{self.role} preserves review-required synthesis until verification closes the loop.",
                    "position": "maintain",
                    "support_status": "review_required",
                }
            )
        return claims[:3]

    def _critiques(self, request: WorkerTurnRequest, seed: int) -> list[dict[str, Any]]:
        if request.round == 1:
            return [{"target": "self", "issue": "independent first-pass only; no cross-worker visibility yet."}]
        critique_templates = [
            "unsupported claim",
            "missing source reference",
            "jurisdiction or freshness risk",
            "record support may be incomplete",
            "conclusion may be broader than the facts",
        ]
        return [
            {"target": "claim", "issue": item, "severity": "medium" if idx == 0 else "low"}
            for idx, item in enumerate(_pick(critique_templates, seed, 3))
        ]

    def _omissions(self, request: WorkerTurnRequest, seed: int) -> list[dict[str, Any]]:
        omission_templates = [
            "contrary authority",
            "missing record",
            "procedural defect",
            "alternative innocent explanation",
            "jurisdiction/freshness challenge",
            "child-impact missing context",
            "privacy/confidentiality concern",
        ]
        if request.round < 4:
            return []
        selected = _pick(omission_templates, seed, 3)
        return [{"role": item, "status": "needed"} for item in selected]

    def _assumptions(self, request: WorkerTurnRequest, seed: int) -> list[str]:
        assumptions = [
            "the approved packet is complete for the selected scope",
            "no worker may see another worker's raw answer during the blind pass",
            "tool calls are read-only and bounded",
            "the verifier decides support status",
        ]
        return _pick(assumptions, seed, 2)

    def _lane_for_source(self, source_id: str, request: WorkerTurnRequest) -> str:
        for item in request.approved_context_packet.get("sources", []):
            if str(item.get("source_id") or item.get("record_id") or "") == source_id:
                return str(item.get("lane") or item.get("source_lane") or "unknown")
        return "unknown"
