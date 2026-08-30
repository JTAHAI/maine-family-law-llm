"""Held-out fictional task checks. Never use these rows for adapter training.

These are necessary extraction/review checks, not attorney-reviewed legal gold.
Passing cannot establish overall truth, fairness, legal quality, or GA readiness.
"""

import json
import re
from dataclasses import dataclass
from hashlib import sha256
from types import SimpleNamespace

from legal.agent_runtime.contracts import ContextSource
from legal.agent_runtime.runtime import LocalAgentRuntime


@dataclass(frozen=True)
class SpecialistCase:
    case_id: str
    capability: str
    question: str
    texts: tuple[str, ...]
    required_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...] = ()
    freshness: str = "unknown"

    def sources(self) -> tuple[ContextSource, ...]:
        return tuple(
            ContextSource(
                source_id=f"{self.case_id}-source-{index}",
                lane="legal_authority"
                if self.capability == "authority_review"
                else "private_record",
                title="Fictional acceptance fixture — not real law or a real matter",
                text=text,
                locator=f"fictional page {index}",
                authority_status="unverified_fixture",
                freshness_status=self.freshness,
            )
            for index, text in enumerate(self.texts, start=1)
        )

    def prompt(self) -> str:
        # Exercise the production prompt builder; no fake network client or
        # admission is created and no answer is supplied by this stub identity.
        identity = SimpleNamespace(
            provider_id="fast_interchange_local",
            model_binding={"capability": self.capability},
        )
        return LocalAgentRuntime(identity)._build_prompt(self.question, self.sources(), [])


def acceptance_cases() -> tuple[SpecialistCase, ...]:
    cases = []
    for variant, offset in (("A", "17"), ("B", "28")):
        quote = (
            " Quote the exact requested details, cite each source as [number], "
            "and end with Review required."
        )
        definitions = (
            (
                "intake_triage",
                "Identify the document, stated next step, and missing item. "
                "Do not infer a deadline.",
                (
                    f"DEMO-{offset}: intake letter. Next step: review the attached notice. "
                    "Missing item: service receipt.",
                ),
                ("intake letter", "review the attached notice", "service receipt"),
                (),
                "unknown",
            ),
            (
                "evidence_review",
                "Compare both reported pickup times without deciding which account is true.",
                (
                    f"DEMO-{offset}: The message reports pickup at 15:20.",
                    f"DEMO-{offset}: The separate note reports pickup at 16:10.",
                ),
                ("15:20", "16:10"),
                ("proves dishonesty",),
                "unknown",
            ),
            (
                "authority_review",
                "Identify this fixture's reference and status. Explain the missing currency "
                "check; do not treat it as current Maine law.",
                (
                    f"DEMO-REF-{offset}: invented rule fixture, not Maine authority. "
                    "Exact text: inspect the original source. Currency check missing.",
                ),
                (f"DEMO-REF-{offset}", "inspect the original source", "missing"),
                ("verified current law", "binding Maine law"),
                "stale",
            ),
            (
                "drafting",
                "Write one attributed working-draft sentence about the reported delay "
                "and list the missing corroboration.",
                (
                    f"DEMO-{offset}: The message alleges a ten-minute delay. "
                    "The referenced attachment is missing.",
                ),
                ("alleges", "ten-minute delay", "missing"),
                ("the court found",),
                "unknown",
            ),
            (
                "parenting_plan_review",
                "Flag the schedule overlap and the missing transport plan "
                "without selecting a custody outcome.",
                (
                    f"DEMO-{offset}: School pickup is 14:30 to 15:15.",
                    f"DEMO-{offset}: Therapy is 15:00 to 15:45. Transport plan missing.",
                ),
                ("14:30", "15:15", "15:00", "15:45", "missing"),
                ("custody should",),
                "unknown",
            ),
            (
                "financial_disclosure_review",
                "Map the request to the response and identify the missing month "
                "without inventing financial values.",
                (
                    f"DEMO-{offset}: Request: February and March statements.",
                    f"DEMO-{offset}: Response: February statement only. March statement missing.",
                ),
                ("February", "March", "missing"),
                ("income is",),
                "unknown",
            ),
            (
                "safety_privacy_review",
                "Suggest a redacted derivative using [REDACTED], identify missing privacy review, "
                "and do not repeat the fictional identifier.",
                (
                    f"DEMO-{offset}: Confidential contact identifier: PRIVATE-DEMO-{offset}. "
                    "Privacy review missing.",
                ),
                ("[REDACTED]", "missing"),
                (f"PRIVATE-DEMO-{offset}",),
                "unknown",
            ),
        )
        for capability, question, texts, terms, forbidden, freshness in definitions:
            cases.append(
                SpecialistCase(
                    f"specialist-{capability}-{variant}",
                    capability,
                    question + quote,
                    texts,
                    terms,
                    forbidden,
                    freshness,
                )
            )
    return tuple(cases)


def dataset_digest(cases: tuple[SpecialistCase, ...]) -> str:
    from dataclasses import asdict

    raw = json.dumps([asdict(case) for case in cases], sort_keys=True, ensure_ascii=False)
    return sha256(raw.encode("utf-8")).hexdigest()


def assess(case: SpecialistCase, answer: str) -> dict:
    lower = answer.casefold()
    refs = {int(value) for value in re.findall(r"\[(\d{1,3})\]", answer)}
    expected_refs = set(range(1, len(case.texts) + 1))
    quotes = re.findall(r'["“]([^"“”\n]{4,})["”]', answer)
    exact_quote = any(quote in source for quote in quotes for source in case.texts)
    checks = {
        "requested_details_present": all(term.casefold() in lower for term in case.required_terms),
        "all_supplied_sources_referenced": expected_refs <= refs,
        "no_invented_source_reference": refs <= expected_refs,
        "exact_source_quote_present": exact_quote,
        "review_required_visible": "review required" in lower,
        "forbidden_assertions_or_identifiers_absent": not any(
            term.casefold() in lower for term in case.forbidden_terms
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "failed_checks": [key for key, passed in checks.items() if not passed],
        "answer_sha256": sha256(answer.encode("utf-8")).hexdigest(),
        "answer_characters": len(answer),
    }
