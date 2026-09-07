"""Repair narrow numeric/wording coverage in the fictional research corpus.

These are template-generated training variations, not independent legal gold.
No development fixture or generated model answer is read by this builder. The
existing corpus and every prior training/evaluation receipt remain unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_mfl_counterfactual_pilot import development_cases, training_case as original_case
from scripts.build_mfl_generalization_pilot import FAMILIES, build


def clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def training_case(index: int):
    if not 0 <= index < 512:
        raise ValueError("bounded fictional corpus index required")
    family, confirmed, pair = FAMILIES[index % 8], bool((index // 8) % 2), index // 16
    variant = pair % 8
    question, sources, quotes, conclusion, forbidden = original_case(index)
    if family == "clocks":
        start_minute, duration = 67 + (pair * 31) % 600, 3 + (pair * 11) % 46
        start, end = clock(start_minute), clock(start_minute + duration)
        if confirmed:
            sources = [
                f"The fictional instrument sheet records opening at {start} UTC and closing at {end} UTC.",
                "The instrument sheet identifies one instrument, one date, and unchanged UTC settings for both readings.",
            ]
            conclusion = (f"The readings on the supplied sheet are {duration} minutes apart. "
                          "This is the recorded interval, not independent proof of the instrument's accuracy or what happened.")
        else:
            sources = [
                f"The fictional entrance instrument records opening at {start}; its clock basis is not documented.",
                f"A separate fictional closing instrument records {end}; its clock basis and synchronization are not documented.",
            ]
            conclusion = ("The two instruments have unspecified clock settings. The actual elapsed time is unknown; "
                          "obtain their date, timezone, and synchronization information before calculating it.")
        question = ("Explain the interval supported by the instrument sheet.",
                    "Can a recorded elapsed interval be determined here?",
                    "Compare the readings and explain any missing basis for a calculation.",
                    "What can these readings establish, and what cannot be verified?")[variant % 4]
    elif family == "conditional":
        activity = ("display setup", "shelter booking", "map collection", "equipment demonstration")[variant % 4]
        needs_two = variant % 2 == 1
        prerequisite = "both the venue lead and the equipment lead" if needs_two else "the venue lead"
        first = (
            f"The fictional {activity} requires written authorization from {prerequisite}.",
            f"Written authorization from {prerequisite} is a prerequisite for the fictional {activity}.",
            f"The fictional {activity} remains tentative unless {prerequisite} authorize it in writing.",
            f"The fictional {activity} may proceed only after written authorization from {prerequisite}.",
        )[variant // 2]
        if confirmed:
            second = (f"The venue lead's signed note authorizes the {activity}. "
                      + (f"The equipment lead's signed note separately authorizes the same {activity}." if needs_two else
                         "No completion report is included."))
            conclusion = ("The supplied signed authorization satisfies the stated written-authorization prerequisite. "
                          "This documents authorization, not that the activity actually took place.")
        elif needs_two:
            second = (f"The venue lead's signed note authorizes the {activity}. "
                      "No written authorization from the equipment lead appears in this packet.")
            conclusion = ("Only one of the two required authorizations is documented. The full prerequisite is not "
                          "established by this packet; request the other authorization if available. Absence here does not prove it never existed.")
        else:
            second = "No written authorization is included in the received records."
            conclusion = ("The received records do not establish the prerequisite. Request the written authorization "
                          "if available. Its absence from this packet does not prove that authorization was never given.")
        sources = [first, second]
        question = ("Which prerequisites are documented by these records?",
                    "Review the authorization status without assuming the activity occurred.")[variant % 2]
    elif family == "attachment":
        filename = f"fictional-material-{pair:03d}.txt"
        first_count, second_count = 1 + pair % 9, 2 + (pair * 3) % 11
        first_item, second_item = (("cones", "trays"), ("sleeves", "clips"),
                                   ("cards", "boxes"), ("tubes", "tags"))[variant % 4]
        content = f"{first_count} {first_item} and {second_count} {second_item}"
        first = f"The fictional dispatch note refers to {filename} for its materials list."
        second = (f"Readable {filename} content: The list requests {content}." if confirmed else
                  f"The archive receipt says {filename} has no supplied readable content.")
        sources = [first, second]
        conclusion = (f"The supplied readable list requests {content}. A request does not establish delivery or inventory accuracy."
                      if confirmed else "The referenced list has no supplied readable body. Its filename and reference do not establish its contents; request a readable copy.")
        question = ("Identify the materials actually described by the available text.",
                    "Review what the referenced file does and does not support.")[variant % 2]
    elif family == "allegation":
        event = ("access was delayed", "a parcel was retained", "an appointment was canceled", "a request was refused")[variant % 4]
        first = f"A fictional participant's statement alleges that {event}."
        second = (f"The supplied fictional adjudication records this finding: {event}. No other findings are supplied."
                  if confirmed else "The supplied packet has no adjudication of the participant's allegation.")
        sources = [first, second]
        conclusion = ("The participant makes an allegation, and the supplied adjudication separately records a finding on that same point. "
                      "Attribute the finding to that excerpt; no additional findings or legal consequences are established."
                      if confirmed else "The participant's statement is an allegation. There is no supplied adjudication resolving it, so it must not be described as a finding.")
        question = "Separate the attributed assertion from any adjudication actually supplied."
    else:
        return question, sources, quotes, conclusion, forbidden
    if pair % 2:
        sources.reverse()
    return question, sources, sources[:], conclusion, forbidden


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.model_project, args.base_model,
                           case_factory=training_case, development_factory=development_cases,
                           provenance_paths=(Path(__file__).resolve(),)), indent=2))
