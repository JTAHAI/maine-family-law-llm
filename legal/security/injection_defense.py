from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .prompt_injection import InjectionFinding, PromptInjectionScanner


@dataclass(frozen=True)
class RetrievedSegment:
    source_id: str
    text: str
    start_offset: int | None = None
    end_offset: int | None = None
    source_class: str | None = None


@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    purpose: str
    requested_capability: str | None = None
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InjectionDefenseReport:
    status: str
    blockers: list[str]
    warnings: list[str]
    direct_findings: list[dict[str, str]]
    document_findings: list[dict[str, str]]
    tool_decision: dict[str, Any]
    isolated_context: list[dict[str, Any]]
    output_filter: dict[str, Any]
    owasp_llm_2025_mapped_controls: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "direct_findings": [dict(item) for item in self.direct_findings],
            "document_findings": [dict(item) for item in self.document_findings],
            "tool_decision": dict(self.tool_decision),
            "isolated_context": [dict(item) for item in self.isolated_context],
            "output_filter": dict(self.output_filter),
            "owasp_llm_2025_mapped_controls": list(self.owasp_llm_2025_mapped_controls),
        }


class ToolSandboxPolicy:
    def __init__(self, allowed_tools: set[str], denied_capabilities: set[str]):
        self.allowed_tools = allowed_tools
        self.denied_capabilities = denied_capabilities

    @classmethod
    def from_policy(cls, policy: dict[str, Any]) -> "ToolSandboxPolicy":
        return cls(
            allowed_tools=set(policy.get("allowed_tools", [])),
            denied_capabilities=set(policy.get("denied_tool_capabilities", [])),
        )

    def decide(self, request: ToolRequest | None) -> dict[str, Any]:
        if request is None:
            return {"status": "not_requested", "allowed": True, "blockers": []}
        blockers: list[str] = []
        if request.tool_name not in self.allowed_tools:
            blockers.append(f"tool_not_allowed:{request.tool_name}")
        if request.requested_capability and request.requested_capability in self.denied_capabilities:
            blockers.append(f"tool_capability_denied:{request.requested_capability}")
        return {
            "status": "allowed" if not blockers else "blocked",
            "allowed": not blockers,
            "tool_name": request.tool_name,
            "purpose": request.purpose,
            "requested_capability": request.requested_capability,
            "blockers": blockers,
        }


class RetrievalContextIsolator:
    def __init__(self, *, strip_document_level_instructions: bool = True):
        self.strip_document_level_instructions = strip_document_level_instructions

    def isolate(self, segments: list[RetrievedSegment]) -> list[dict[str, Any]]:
        isolated: list[dict[str, Any]] = []
        for segment in segments:
            text = segment.text
            if self.strip_document_level_instructions:
                text = re.sub(r"(?im)^\s*(system|developer|assistant)\s*:\s*", "[untrusted_label_removed]: ", text)
                text = re.sub(r"(?i)ignore\s+(the\s+)?(above|previous|system)\s+instructions", "[untrusted_instruction_removed]", text)
            isolated.append(
                {
                    "source_id": segment.source_id,
                    "source_class": segment.source_class,
                    "text": text,
                    "start_offset": segment.start_offset,
                    "end_offset": segment.end_offset,
                    "trust_boundary": "retrieved_text_untrusted_data_not_instructions",
                    "may_change_policy": False,
                }
            )
        return isolated


class OutputFilter:
    SECRET_LIKE = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}")
    PROMPT_LEAK = re.compile(r"(?i)(system prompt|developer message|hidden prompt|internal policy)\s*[:\-]")

    def check(self, output_text: str, *, require_review_required: bool = True) -> dict[str, Any]:
        blockers: list[str] = []
        if self.PROMPT_LEAK.search(output_text):
            blockers.append("output_filter:system_prompt_leakage")
        if self.SECRET_LIKE.search(output_text):
            blockers.append("output_filter:secret_like_token")
        if require_review_required and "review_required" not in output_text.lower():
            blockers.append("output_filter:review_required_status_missing")
        return {
            "status": "pass" if not blockers else "blocked",
            "blockers": blockers,
        }


class PromptInjectionDefenseGateway:
    def __init__(self, policy_path: str | Path):
        self.policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        self.scanner = PromptInjectionScanner()
        self.tool_sandbox = ToolSandboxPolicy.from_policy(self.policy)
        retrieval_rules = self.policy.get("retrieval_context_rules", {})
        self.isolator = RetrievalContextIsolator(
            strip_document_level_instructions=bool(
                retrieval_rules.get("strip_document_level_instructions", True)
            )
        )
        self.output_filter = OutputFilter()

    @staticmethod
    def _finding_dict(finding: InjectionFinding) -> dict[str, str]:
        return {
            "kind": finding.kind,
            "pattern": finding.pattern,
            "severity": finding.severity,
            "message": finding.message,
        }

    def evaluate(
        self,
        *,
        user_prompt: str,
        retrieved_segments: list[RetrievedSegment] | None = None,
        tool_request: ToolRequest | None = None,
        output_text: str = "review_required: generated content must pass verifiers and human review.",
    ) -> InjectionDefenseReport:
        retrieved_segments = list(retrieved_segments or [])
        max_prompt_chars = int(self.policy.get("cost_controls", {}).get("max_prompt_chars", 20000))
        max_segments = int(self.policy.get("cost_controls", {}).get("max_retrieved_segments", 20))
        blockers: list[str] = []
        warnings: list[str] = []
        if len(user_prompt) > max_prompt_chars:
            blockers.append("cost_control:prompt_too_large")
        if len(retrieved_segments) > max_segments:
            blockers.append("cost_control:too_many_retrieved_segments")

        direct_findings = self.scanner.scan_user_prompt(user_prompt)
        document_findings: list[InjectionFinding] = []
        for segment in retrieved_segments:
            document_findings.extend(self.scanner.scan_document_text(segment.text))

        blockers.extend(finding.kind for finding in direct_findings if finding.severity == "high")
        blockers.extend(finding.kind for finding in document_findings if finding.severity == "high")

        tool_decision = self.tool_sandbox.decide(tool_request)
        blockers.extend(tool_decision.get("blockers", []))
        isolated_context = self.isolator.isolate(retrieved_segments)
        if any(item["may_change_policy"] for item in isolated_context):
            blockers.append("retrieval_context_policy_boundary_failed")

        output_check = self.output_filter.check(
            output_text,
            require_review_required=bool(
                self.policy.get("output_filter_rules", {}).get("require_review_required_status_on_generation", True)
            ),
        )
        blockers.extend(output_check.get("blockers", []))

        if document_findings:
            warnings.append("retrieved_or_uploaded_document_contains_instruction_like_text")
        if direct_findings:
            warnings.append("user_prompt_contains_instruction_override_attempt")

        return InjectionDefenseReport(
            status="pass" if not blockers else "blocked",
            blockers=blockers,
            warnings=warnings,
            direct_findings=[self._finding_dict(finding) for finding in direct_findings],
            document_findings=[self._finding_dict(finding) for finding in document_findings],
            tool_decision=tool_decision,
            isolated_context=isolated_context,
            output_filter=output_check,
            owasp_llm_2025_mapped_controls=list(
                self.policy.get("owasp_llm_2025_mapped_controls", [])
            ),
        )
