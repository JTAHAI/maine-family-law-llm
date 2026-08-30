"""Synthetic, source-bound workflow training rows for development adapters.

The rows intentionally contain no real people, matter records, Maine legal
authority, court forms, or legal conclusions.  They teach limited workflow
behavior: quote supplied text exactly, cite every supplied source, distinguish
missing support, preserve review-required status, and redact a fictional
identifier.  They are not a substitute for rights-cleared legal training data
or attorney-reviewed evaluation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from types import SimpleNamespace

from legal.agent_runtime.contracts import ContextSource
from legal.agent_runtime.runtime import LocalAgentRuntime
from legal.fast_interchange.fleet import FAST_INTERCHANGE_CAPABILITIES

DATASET_CLASS = "synthetic_eval_data"
DATASET_SCOPE = "synthetic_source_bound_workflow_only_not_substantive_maine_law"
TRAINING_VARIANT_COUNT = 36


@dataclass(frozen=True)
class WorkflowTrainingRow:
    row_id: str
    capability: str
    prompt: str
    response: str


def _runtime_prompt(capability: str, question: str, texts: tuple[str, ...]) -> str:
    """Render the same host context shape that the local worker receives."""

    client = SimpleNamespace(
        provider_id="fast_interchange_local", model_binding={"capability": capability}
    )
    sources = tuple(
        ContextSource(
            source_id=f"synthetic-training-{capability}-{index}",
            lane="legal_authority" if capability == "authority_review" else "private_record",
            title="Synthetic workflow training fixture — not law and not a matter record",
            text=text,
            locator=f"synthetic sheet {index}",
            authority_status="unverified_synthetic_fixture",
            freshness_status="unknown",
        )
        for index, text in enumerate(texts, start=1)
    )
    return LocalAgentRuntime(client)._build_prompt(question, sources, [])


def _row(
    capability: str,
    index: int,
    question: str,
    texts: tuple[str, ...],
    response: str,
) -> WorkflowTrainingRow:
    if capability not in FAST_INTERCHANGE_CAPABILITIES:
        raise ValueError("workflow_training_capability_invalid")
    if not response.endswith("Review required."):
        raise ValueError("workflow_training_review_required_missing")
    return WorkflowTrainingRow(
        row_id=f"workflow-{capability}-{index:03d}",
        capability=capability,
        prompt=_runtime_prompt(capability, question, texts),
        response=response,
    )


def _intake(index: int) -> WorkflowTrainingRow:
    next_step = ("read the attached notice", "confirm the meeting date", "compare the two pages")[
        index % 3
    ]
    missing = ("proof of delivery", "the signed page", "a contact note")[index % 3]
    text = f"TRAIN-{index:03d}: intake memo. Next step: {next_step}. Missing item: {missing}."
    return _row(
        "intake_triage",
        index,
        "Identify the document, stated next step, and missing item. Do not infer a deadline.",
        (text,),
        (
            'Review required. The source describes an "intake memo" [1]. '
            f'Stated next step: "{next_step}" [1]. Missing item: "{missing}" [1]. '
            "Review required."
        ),
    )


def _evidence(index: int) -> WorkflowTrainingRow:
    first = f"{8 + index % 8:02d}:{(index * 7) % 60:02d}"
    second = f"{15 + index % 7:02d}:{(index * 11) % 60:02d}"
    texts = (
        f"TRAIN-{index:03d}: first account reports pickup at {first}.",
        f"TRAIN-{index:03d}: second account reports pickup at {second}.",
    )
    return _row(
        "evidence_review",
        index,
        "Compare both reported pickup times without deciding which account is true.",
        texts,
        (
            f'Review required. One account says "pickup at {first}" [1]. '
            f'The other says "pickup at {second}" [2]. '
            "The reports differ; no finding is made. Review required."
        ),
    )


def _authority(index: int) -> WorkflowTrainingRow:
    ref = f"TRAIN-REF-{index:03d}"
    text = (
        f"{ref}: invented reference fixture, not authority. Exact text: inspect the original "
        "source. Currency check missing."
    )
    return _row(
        "authority_review",
        index,
        (
            "Identify the fixture reference and status. Explain the missing currency check without "
            "treating it as current law."
        ),
        (text,),
        (
            f'Review required. "{ref}" is an invented fixture, not verified authority [1]. '
            'Exact source text: "inspect the original source" [1]. '
            "Currency check is missing [1]. Review required."
        ),
    )


def _drafting(index: int) -> WorkflowTrainingRow:
    delay = ("seven-minute", "twelve-minute", "nineteen-minute")[index % 3]
    text = (
        f"TRAIN-{index:03d}: The message alleges a {delay} delay. The referenced attachment "
        "is missing."
    )
    return _row(
        "drafting",
        index,
        (
            "Write one attributed working-draft sentence about the reported delay and list the "
            "missing corroboration."
        ),
        (text,),
        (
            f'Review required. Working draft: The message "alleges a {delay} delay" [1]; '
            "the referenced attachment is missing [1]. Review required."
        ),
    )


def _parenting(index: int) -> WorkflowTrainingRow:
    start = 13 + index % 3
    first_start, first_end = f"{start}:10", f"{start}:55"
    second_start, second_end = f"{start}:40", f"{start + 1}:20"
    texts = (
        f"TRAIN-{index:03d}: School pickup is {first_start} to {first_end}.",
        (
            f"TRAIN-{index:03d}: Appointment is {second_start} to {second_end}. "
            "Transport plan missing."
        ),
    )
    return _row(
        "parenting_plan_review",
        index,
        "Flag the schedule overlap and missing transport plan without selecting a custody outcome.",
        texts,
        (
            f'Review required. The first schedule is "{first_start} to {first_end}" [1]. '
            f'The second is "{second_start} to {second_end}" [2]. '
            "These times overlap, and the transport plan is missing [2]. Review required."
        ),
    )


def _financial(index: int) -> WorkflowTrainingRow:
    months = (("April", "May"), ("June", "July"), ("August", "September"))[index % 3]
    first, second = months
    texts = (
        f"TRAIN-{index:03d}: Request: {first} and {second} statements.",
        f"TRAIN-{index:03d}: Response: {first} statement only. {second} statement missing.",
    )
    return _row(
        "financial_disclosure_review",
        index,
        (
            "Map the request to the response and identify the missing month without inventing "
            "financial values."
        ),
        texts,
        (
            f'Review required. The request lists "{first} and {second} statements" [1]. '
            f'The response supplies {first} only and says "{second} statement missing" [2]. '
            "Review required."
        ),
    )


def _safety(index: int) -> WorkflowTrainingRow:
    identifier = f"SYNTHETIC-CONTACT-{index:03d}"
    text = (
        f"TRAIN-{index:03d}: Confidential contact identifier: {identifier}. Privacy review missing."
    )
    return _row(
        "safety_privacy_review",
        index,
        (
            "Suggest a redacted derivative using [REDACTED], identify missing privacy review, "
            "and do not repeat the identifier."
        ),
        (text,),
        (
            'Review required. Use a redacted derivative: "Confidential contact identifier: '
            '[REDACTED]" [1]. "Privacy review missing" [1]. Review required.'
        ),
    )


_BUILDERS = {
    "intake_triage": _intake,
    "evidence_review": _evidence,
    "authority_review": _authority,
    "drafting": _drafting,
    "parenting_plan_review": _parenting,
    "financial_disclosure_review": _financial,
    "safety_privacy_review": _safety,
}


def workflow_training_rows(
    *, variants: int = TRAINING_VARIANT_COUNT
) -> tuple[WorkflowTrainingRow, ...]:
    """Return deterministic, non-client rows; held-out acceptance IDs never occur."""

    if not 12 <= variants <= 128:
        raise ValueError("workflow_training_variant_count_invalid")
    rows = tuple(
        _BUILDERS[capability](index)
        for capability in FAST_INTERCHANGE_CAPABILITIES
        for index in range(1, variants + 1)
    )
    if len({row.row_id for row in rows}) != len(rows):
        raise RuntimeError("workflow_training_row_identity_conflict")
    return rows


def dataset_digest(rows: tuple[WorkflowTrainingRow, ...]) -> str:
    serialized = json.dumps([asdict(row) for row in rows], ensure_ascii=False, sort_keys=True)
    return sha256(serialized.encode("utf-8")).hexdigest()
