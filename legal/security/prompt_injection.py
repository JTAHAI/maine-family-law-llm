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
        "ignore_previous_instructions": re.compile(
            r"ignore\s+(?:all\s+)?(?:(?:previous|prior|system|developer)(?:\s+system)?|the\s+above)\s+(?:instructions?|messages?|rules?)",
            re.I,
        ),
        "ignore_rules_or_policy": re.compile(
            r"(?:ignore|disregard|override)\s+(?:all\s+|the\s+)?(?:rules?|policy|policies|guardrails?|review requirements?|source requirements?)",
            re.I,
        ),
        "reveal_system_prompt": re.compile(
            r"(?:reveal|print|show|dump|repeat|quote).{0,50}(?:system prompt|hidden prompt|developer message|internal instructions?)",
            re.I,
        ),
        "disable_safety": re.compile(
            r"(?:disable|bypass|turn off|skip|remove).{0,50}(?:safety|guardrails?|policy|review gate|human review|citation check|source check)",
            re.I,
        ),
        "filing_ready_bypass": re.compile(
            r"(?:make|mark|treat).{0,30}filing[- ]ready.{0,50}(?:anyway|without|skip|ignore)|(?:no|without)\s+(?:human\s+)?review",
            re.I,
        ),
        "source_suppression": re.compile(
            r"(?:do not|don't|never)\s+(?:cite|show sources|use sources|verify citations)|answer\s+without\s+(?:sources|citations|review)",
            re.I,
        ),
        "roleplay_jailbreak": re.compile(r"\b(?:DAN|do anything now|jailbreak|unfiltered mode)\b", re.I),
    }
    DOCUMENT_PATTERNS = {
        "embedded_instruction": re.compile(
            r"(?:^|\n)\s*(?:assistant|system|developer)\s*:|ignore\s+(?:all\s+)?(?:the\s+)?(?:above|previous|prior)|follow\s+these\s+instructions",
            re.I,
        ),
        "tool_exfiltration": re.compile(
            r"(?:send|upload|transmit|email)\s+(?:the\s+)?(?:file|document|secret|private data|records?).{0,60}(?:to|http|email|server)",
            re.I,
        ),
        "source_override": re.compile(
            r"(?:this document|these records?)\s+(?:overrides?|supersedes?|replaces?)\s+(?:all\s+)?(?:law|sources|citations|rules|system instructions)",
            re.I,
        ),
        "review_bypass": re.compile(
            r"(?:mark|make|treat).{0,30}filing[- ]ready|skip\s+(?:human\s+)?review|do\s+not\s+verify\s+(?:citations|sources)",
            re.I,
        ),
    }

    def scan_user_prompt(self, text: str) -> list[InjectionFinding]:
        return self._scan(text, self.DIRECT_PATTERNS, kind_prefix="direct_prompt_injection")

    def scan_document_text(self, text: str) -> list[InjectionFinding]:
        return self._scan(text, self.DOCUMENT_PATTERNS, kind_prefix="document_injection")

    def sanitize_user_prompt_for_retrieval(self, text: str) -> str:
        """Remove matched override clauses before retrieval.

        The original prompt is preserved for the visible transcript and safety
        routing. Only the local retrieval query is neutralized so jailbreak
        language cannot steer source selection.
        """

        cleaned = str(text or "")
        for pattern in self.DIRECT_PATTERNS.values():
            cleaned = pattern.sub(" ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
        return cleaned

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
