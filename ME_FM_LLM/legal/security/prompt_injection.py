from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionFinding:
    kind: str
    pattern: str
    severity: str
    message: str


class PromptInjectionScanner:
    DIRECT_PATTERNS = {
        "ignore_previous_instructions": re.compile(r"ignore (all )?((previous|prior|system)(\s+system)?|the above) instructions", re.I),
        "reveal_system_prompt": re.compile(r"(reveal|print|show|dump).{0,40}(system prompt|hidden prompt|developer message)", re.I),
        "disable_safety": re.compile(r"(disable|bypass|turn off).{0,40}(safety|guardrails|policy)", re.I),
        "roleplay_jailbreak": re.compile(r"\b(DAN|do anything now|jailbreak)\b", re.I),
    }
    DOCUMENT_PATTERNS = {
        "embedded_instruction": re.compile(r"assistant:|system:|developer:|ignore the above", re.I),
        "tool_exfiltration": re.compile(r"send (the )?(file|document|secret|private data).{0,40}(to|http|email)", re.I),
        "source_override": re.compile(r"this document overrides (all )?(law|sources|citations|rules)", re.I),
    }

    def scan_user_prompt(self, text: str) -> list[InjectionFinding]:
        return self._scan(text, self.DIRECT_PATTERNS, kind_prefix="direct_prompt_injection")

    def scan_document_text(self, text: str) -> list[InjectionFinding]:
        return self._scan(text, self.DOCUMENT_PATTERNS, kind_prefix="document_injection")

    @staticmethod
    def _scan(
        text: str, patterns: dict[str, re.Pattern[str]], *, kind_prefix: str
    ) -> list[InjectionFinding]:
        findings: list[InjectionFinding] = []
        for name, pattern in patterns.items():
            if pattern.search(text):
                findings.append(
                    InjectionFinding(
                        kind=f"{kind_prefix}:{name}",
                        pattern=name,
                        severity="high",
                        message="Treat matched text as untrusted data, not as instructions.",
                    )
                )
        return findings
