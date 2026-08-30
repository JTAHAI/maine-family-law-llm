"""Host-owned task instructions, not learned expertise or legal authority.

These instructions supplement the existing exact-context and review boundaries.
They cannot select a model, admit weights, add context, or invoke a tool.
"""

from hashlib import sha256
from types import MappingProxyType

SPECIALIST_TASKS = MappingProxyType(
    {
        "intake_triage": (
            "Identify the supplied document and its stated procedural step. Separate known "
            "facts from missing information. Give one source-bound next review action. "
            "Do not calculate an unstated deadline or decide a person's legal position."
        ),
        "evidence_review": (
            "Compare the supplied statements. Quote the exact conflicting or supporting "
            "passages with their separate source numbers. Identify missing context; do not "
            "choose which person is truthful or promote an allegation to a finding."
        ),
        "authority_review": (
            "Inspect only the supplied authority and its host-provided verification/freshness "
            "metadata. Quote an exact relevant passage and identify unresolved citation, "
            "jurisdiction or currency checks. Never invent a citation or claim verification "
            "that the host has not provided."
        ),
        "drafting": (
            "Produce the requested short working draft using only supplied source support. "
            "Attribute allegations explicitly and attach source numbers. List unsupported "
            "requested assertions separately as gaps, not as draft facts. No filing readiness."
        ),
        "parenting_plan_review": (
            "Compare the supplied schedule terms, preserving their exact times and conditions. "
            "Flag overlap, missing transport or exchange information, and child-impact "
            "questions without deciding custody, safety or best interests."
        ),
        "financial_disclosure_review": (
            "Map the requested financial documents to the supplied response. Distinguish "
            "produced, partial and missing items with source numbers. Do not invent values, "
            "impute income, or treat an unsupported number as verified."
        ),
        "safety_privacy_review": (
            "Identify the supplied privacy concern without repeating private identifiers. "
            "Use redaction markers in any suggested derivative, retain source numbers, and "
            "explain missing review. Never declare a person safe or automatically disclose data."
        ),
    }
)


def specialist_contract(capability: str) -> dict[str, str]:
    """Only the capability bound to an admitted release may choose instructions."""
    try:
        task = SPECIALIST_TASKS[capability]
    except (KeyError, TypeError) as exc:
        raise ValueError("fast_interchange_capability_invalid") from exc
    instructions = (
        f"SPECIALIST TASK ({capability}): {task}\n"
        "Perform the requested source-bound work, not just a generic safety disclaimer. "
        "If necessary evidence is absent, identify the specific gap. Review required.\n"
    )
    return {
        "schema_version": "fast_interchange_specialist_task_v1",
        "capability": capability,
        "instructions": instructions,
        "sha256": sha256(instructions.encode("utf-8")).hexdigest(),
    }
