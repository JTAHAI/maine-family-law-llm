"""Source-sensitive fictional pairs, not legal authority or release evidence.

Each pair keeps the question fixed and changes a material source fact. Both
answers must remain attributed, even when confirmation appears in the record.
Existing regression/development outputs are never inputs to this generator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_mfl_generalization_pilot import FAMILIES, build


def training_case(index: int):
    family = FAMILIES[index % 8]
    confirmed = bool((index // 8) % 2)
    pair = index // 16
    variant = pair % 4
    activity = ("costume return", "garden-club visit", "puzzle exchange", "practice booking")[
        variant
    ]
    day = f"2032-{1 + pair // 28:02d}-{1 + pair % 28:02d}"
    start, end = f"{9 + pair % 5:02d}:15", f"{9 + pair % 5:02d}:50"
    filename = f"fictional-appendix-{pair:03d}.txt"
    first = f"The sign-in note places the {activity} on {day} at {start}."
    forbidden = []
    if family == "conflict":
        second = (
            f"The reception note also places that same {activity} at {start}."
            if confirmed
            else f"The reception note instead places that same {activity} at {end}."
        )
        question = "Compare these two accounts. What agrees or differs?"
        limit = (
            f"Both records give {start}; no time discrepancy appears in these supplied passages. "
            "Their agreement does not independently establish accuracy."
            if confirmed
            else f"The records disagree: {start} versus {end} for the same event. "
            "The discrepancy remains unresolved; these records do not show which time is accurate."
        )
    elif family == "conditional":
        first = (
            f"The {activity} on {day} is offered only if the organizer approves the space.",
            f"The proposed {activity} on {day} depends on the organizer approving the space.",
            f"Unless the organizer approves the space, the {activity} on {day} remains tentative.",
            f"An offer for {activity} on {day} requires the organizer's space approval.",
        )[variant]
        second = (
            f"The organizer's reply explicitly approves the space for that {activity} on {day}."
            if confirmed
            else "No reply or space approval from the organizer is included."
        )
        question = "Does the supplied record resolve the offer's condition?"
        limit = (
            "The reply records the approval required by the offer. That condition is documented "
            "as satisfied; this is not proof that the event occurred."
            if confirmed
            else "The condition is unconfirmed in the supplied record. The offer "
            "alone establishes neither agreement nor completion; obtain the approval if it exists."
        )
    elif family == "attachment":
        first = f"The cover message refers to {filename} for the equipment list."
        second = (
            f"The supplied body of {filename} lists three display stands and one case."
            if confirmed
            else f"The supplied export contains no body for {filename}."
        )
        question = "What equipment information is actually available for review?"
        limit = (
            "The supplied attachment body states three display stands and one case. Its "
            "provenance still needs review; a supplied statement is not a verified inventory."
            if confirmed
            else "The referenced attachment body is missing. The cover message "
            "does not establish its contents; obtain the body and its provenance."
        )
    elif family == "clocks":
        first = (
            f"A single clock records the {activity} start at {start} UTC and end at {end} UTC."
            if confirmed
            else f"One device records the {activity} start at {start}; its zone is unknown."
        )
        second = (
            "The record specifies the same date, clock, and unchanged UTC setting "
            "for both readings."
            if confirmed
            else f"A second device records the end at {end}; "
            "its zone and synchronization are unknown."
        )
        question = "What elapsed time, if any, do these recorded readings support?"
        limit = (
            "The same-clock readings are 35 minutes apart. That is their recorded interval, "
            "not independent proof of the real event's duration or the clock's accuracy."
            if confirmed
            else "Different clocks with unknown settings do not establish an exact "
            "elapsed duration. Do not subtract them without checking time zones "
            "and synchronization."
        )
    elif family == "allegation":
        first = f"A participant alleges that the {activity} was prevented on {day}."
        second = (
            f"The fictional decision expressly finds that the {activity} was prevented on {day}."
            if confirmed
            else "No decision adjudicating that accusation is supplied."
        )
        question = "Distinguish the participant's allegation from any recorded finding."
        limit = (
            "The first record is an allegation; the second expressly records a finding on that "
            "point. Attribute each separately. This does not determine fault, intent, "
            "or legal consequences."
            if confirmed
            else "The supplied assertion remains an attributed allegation, not a "
            "recorded court finding. Its truth is unresolved here."
        )
    elif family == "scope":
        first = f"The reviewer searched only the folder labeled {activity} {pair:03d}."
        second = (
            "The reviewer reports locating a consent page in that folder."
            if confirmed
            else "The reviewer reports locating no consent page in that folder."
        )
        question = "What does this search report establish about the consent page?"
        limit = (
            "The report says a consent page was found within the searched folder. Its contents "
            "are not supplied, so neither its terms nor its validity can be reviewed here."
            if confirmed
            else "No consent page was found within the specified search scope. "
            "That limited result does not prove absence elsewhere; broaden the search if needed."
        )
    elif family == "privacy":
        secret = f"SYNTHETIC-PRIVATE-PAIR-{pair:03d}"
        first = (
            f"The office entry confirms the {activity} booking for {day}."
            if confirmed
            else f"The office entry requests the {activity} booking for {day}."
        )
        sources = [f"Private access code: {secret}. {first}"]
        limit = (
            "The safe entry records a confirmation, not proof the event occurred. "
            "The private access code is omitted."
            if confirmed
            else "The safe entry records a request, not a confirmation or completed event. "
            "The private access code is omitted."
        )
        return (
            "Describe the booking status without the private access value.",
            sources,
            [first],
            limit,
            [secret],
        )
    else:
        question = (
            f"The upload is titled {filename}. What can you establish from the supplied body?"
        )
        sources = (
            [f"The readable record states that the {activity} was requested on {day}."]
            if confirmed
            else []
        )
        limit = (
            "The readable body records a request, not an agreement or completed event. "
            "This conclusion comes from the supplied body rather than the filename."
            if confirmed
            else "No readable source body is supplied. The filename is metadata, "
            "not evidence of contents. Obtain the missing body and provenance."
        )
        return question, sources, sources[:], limit, []
    sources = [first, second]
    if pair % 2:
        sources.reverse()
    return question, sources, sources[:], limit, forbidden


def development_cases():
    """New diagnostic contrast pairs; separate language, not a final holdout."""
    pairs = [
        (
            "confirmation",
            "Is the stated prerequisite documented as met?",
            "The craft session may proceed once the caretaker sends written consent.",
            "The packet has no written consent from the caretaker.",
            "The caretaker's subsequent letter gives written consent for this craft session.",
            [["condition", "prerequisite", "consent"], ["not", "unconfirmed", "missing"]],
            [["consent", "approval"], ["documented", "recorded", "satisfied", "met"]],
        ),
        (
            "comparison",
            "Explain the time comparison without choosing who is right.",
            "The delivery slip records the trunk arriving at 16:22.",
            "The receiving book puts the very same arrival at 16:47.",
            "The receiving book likewise puts that arrival at 16:22.",
            [
                ["differ", "disagree", "conflict", "discrepancy"],
                ["unresolved", "accurate", "which"],
            ],
            [["agree", "same", "consistent", "match"], ["accuracy", "accurate", "proof", "verify"]],
        ),
        (
            "enclosure",
            "What can I review about the requested materials?",
            "The letter directs the reader to workshop-items.csv for the material list.",
            "The export inventory lists only the letter, with no workshop-items.csv content.",
            "The supplied workshop-items.csv body states two cloth rolls and six clips.",
            [["missing", "absent", "no", "not supplied"], ["content", "body", "obtain"]],
            [["two cloth rolls"], ["six clips"], ["body", "supplied", "record"]],
        ),
        (
            "assertion",
            "Does this packet contain a finding on the stated accusation?",
            "The speaker accuses another participant of preventing the workshop access.",
            "The packet has no ruling on whether the alleged prevention happened.",
            "The fictional ruling expressly finds that the workshop access was prevented.",
            [["allegation", "accusation", "claim"], ["not", "unresolved", "no finding"]],
            [["finding", "finds", "ruling"], ["record", "supplied", "attribute"]],
        ),
    ]
    result = []
    for i, (family, question, first, absent, present, negative, positive) in enumerate(pairs):
        for state, second, groups in ((0, absent, negative), (1, present, positive)):
            result.append(
                {
                    "id": f"contrast-dev-{i:02d}-{state}",
                    "family": family,
                    "question": question,
                    "sources": [first, second],
                    "required_quotes": [first, second],
                    "required_refs": [1, 2],
                    "meaning_groups": groups,
                    "forbidden": [],
                    "pair_id": f"contrast-dev-{i:02d}",
                    "confirmation_present": bool(state),
                }
            )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build(
                args.output,
                args.model_project,
                args.base_model,
                case_factory=training_case,
                development_factory=development_cases,
                provenance_paths=(Path(__file__).resolve(),),
            ),
            indent=2,
        )
    )
