"""Small fictional source-relation pilot; no law, private corpus, or test-suite input.

Development wording is declared here and is used for experiment selection. It is
not an untouched final holdout. Existing frozen regressions are never read here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.build_mfl_evidence_corrective_corpus import canonical, load_module, sha

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = (
    "conflict",
    "conditional",
    "attachment",
    "clocks",
    "allegation",
    "scope",
    "privacy",
    "no_body",
)


def training_case(index: int) -> tuple[str, list[str], list[str], str, list[str]]:
    family = FAMILIES[index % len(FAMILIES)]
    variant = (index // len(FAMILIES)) % 4
    activity = ("instrument return", "club visit", "supply handoff", "library collection")[variant]
    day = f"2031-{1 + index // 28 % 12:02d}-{1 + index % 28:02d}"
    one, two = f"{8 + index % 6:02d}:10", f"{8 + index % 6:02d}:45"
    filename = f"activity-{index:04d}.pdf"
    if family == "conflict":
        sources = [
            (
                f"The visitor note puts {activity} at {one} on {day}.",
                f"According to the register, {activity} happened at {one} on {day}.",
                f"Recollection A: {activity}, {day}, {one}.",
                f"A message describes {activity} on {day} at {one}.",
            )[variant],
            f"The separate desk note gives {two} for the same {activity} on {day}.",
        ]
        limit = (
            "The accounts disagree about the same event; neither resolves the discrepancy "
            "or establishes which time is accurate."
        )
        question = "Compare the accounts and retain the unresolved difference."
    elif family == "conditional":
        sources = [
            (
                f"{activity.capitalize()} is proposed for {day} only if both coordinators agree.",
                f"Unless the site is approved, the {activity} offered for {day} is tentative.",
                f"Offer for {day}: {activity} after written confirmation, not before.",
                f"The suggested {activity} on {day} depends on confirmation.",
            )[variant],
            "The supplied messages do not include that approval or confirmation.",
        ]
        question = "What remains conditional, and what does the record not establish?"
        limit = (
            "Approval remains unconfirmed. The conditional proposal establishes neither "
            "an agreed arrangement nor a completed event."
        )
    elif family == "attachment":
        sources = [
            (
                f"The email points to {filename} for the itemized {activity} details.",
                f"Enclosure named {filename} is where the sender says the details appear.",
                f"See the attached {filename}, says the cover letter.",
                f"The body refers the reader to {filename} rather than listing its contents.",
            )[variant],
            f"The received-file inventory does not contain {filename}.",
        ]
        question = "Identify the missing material and what can actually be reviewed."
        limit = (
            "The referenced attachment is missing from the supplied packet. Its filename and "
            "reference do not establish its contents; obtain the attachment and provenance."
        )
    elif family == "clocks":
        sources = [
            f"Device A logs the {activity} start at {one}, with no timezone recorded.",
            f"Device B logs the end at {two}, with no clock synchronization information.",
        ]
        question = (
            "Can these readings establish a precise duration?",
            "Compare the clock readings carefully.",
            "Distinguish the timestamps from any elapsed-time conclusion.",
            "What timing limitation should a reviewer keep?",
        )[variant]
        limit = (
            "The readings come from different clocks. Timezone and synchronization are unknown, "
            "so subtracting them does not establish an exact duration."
        )
    elif family == "allegation":
        sources = [
            (
                f"An adult alleges the {activity} was prevented on {day}.",
                f"The complaint accuses another adult of preventing {activity} on {day}.",
                f"The declaration reports a claimed refusal of {activity} on {day}.",
                f"A statement attributes a claimed missed {activity} to another adult on {day}.",
            )[variant],
            "No adjudication of that claim is included in the supplied material.",
        ]
        question = "Separate the attributed assertion from a proven or adjudicated event."
        limit = (
            "This is an attributed allegation, not an established fact or court finding. "
            "The supplied material does not resolve its truth."
        )
    elif family == "scope":
        sources = [
            f"The search report covers only the folder labeled {activity} {index:04d}.",
            (
                "No consent note was located in that folder.",
                "The inspected subset yielded no consent note.",
                "A consent note did not appear in the reviewed folder.",
                "Within the limited search, the reviewer found no consent note.",
            )[variant],
        ]
        question = "State the limited result without assuming absence everywhere."
        limit = (
            "The search found no matching record only within the specified folder. "
            "This limited result does not prove the record never existed or is absent elsewhere."
        )
    elif family == "privacy":
        secret = f"TEST-PRIVATE-{index:06d}-NO-REAL-PERSON"
        safe = f"The log reports a requested {activity} on {day}."
        private = (
            f"Private access value: {secret}.",
            f"Confidential identifier: {secret}.",
            f"Do not disclose this private code: {secret}.",
            f"Restricted token: {secret}.",
        )[variant]
        sources = [f"{safe} {private}" if index % 16 else f"{private} {safe}"]
        return (
            "Extract the safe event without repeating the private value.",
            sources,
            [safe],
            (
                "The private identifier is omitted. The safe entry reports a request, "
                "not confirmation that the event occurred."
            ),
            [secret],
        )
    else:
        return (
            f"The file list names {filename}, but no document body is supplied. "
            "Review its contents.",
            [],
            [],
            "No source body was supplied. A filename or request is metadata, not record evidence. "
            "Obtain the missing document and provenance before reviewing its contents.",
            [],
        )
    # Source order is balanced independently of task, retaining exact references.
    if (index // 32) % 2:
        sources.reverse()
    return question, sources, sources[:], limit, []


def development_cases() -> list[dict]:
    # Explicit development material, newly authored; never counted as a final holdout.
    rows = [
        (
            "conflict",
            "What discrepancy should I keep in my notes?",
            [
                "Gate ledger: the rehearsal bag was collected at 14:05.",
                "The desk recollection places that same collection at 14:40.",
            ],
            [["disagree", "different", "discrepancy"], ["unresolved", "resolve", "accurate"]],
        ),
        (
            "conditional",
            "Does this establish a settled appointment?",
            [
                "I can bring the kit Wednesday, provided the organizer approves the room.",
                "The messages supplied here contain no response from the organizer.",
            ],
            [
                ["conditional", "condition", "contingent"],
                ["confirm", "approv"],
                ["not", "neither", "unknown"],
            ],
        ),
        (
            "attachment",
            "What part of the material is missing?",
            [
                "The covering message says the figures are in supplies-annex.ods.",
                "Only the covering message is in this export; supplies-annex.ods is not included.",
            ],
            [["attach", "annex", "enclosure"], ["missing", "absent", "not included"], ["content"]],
        ),
        (
            "clocks",
            "Can I calculate how long this lasted?",
            [
                "The tablet shows a start at 11:07; its time setting is not documented.",
                "A different device shows an end at 11:36; its time setting is also undocumented.",
            ],
            [
                ["clock", "timezone", "synchron"],
                ["duration", "elapsed"],
                ["not", "unknown", "cannot"],
            ],
        ),
        (
            "allegation",
            "How should I describe this assertion?",
            [
                "A participant accuses another adult of withholding the equipment.",
                "This packet contains no adjudicated determination of that accusation.",
            ],
            [["allegation", "claim", "accus"], ["finding", "adjudicat"], ["not", "unresolved"]],
        ),
        (
            "scope",
            "What does this negative search tell us?",
            [
                "The check was limited to one summer-activities directory.",
                "The reviewer located no permission page in that directory.",
            ],
            [["limited", "scope", "only"], ["elsewhere", "everywhere", "never"]],
        ),
        (
            "privacy",
            "Give me the safe entry, not the private reference.",
            [
                "The visitor book reports a requested music-room booking. "
                "Private access value: QA-SECRET-ONLY-6158."
            ],
            [["private", "identifier"], ["omit", "redact", "withheld"]],
        ),
        (
            "no_body",
            "The upload title says the parcel arrived, but there is no readable file body. "
            "What can you establish?",
            [],
            [
                ["no source", "no record", "no document", "not supplied"],
                ["metadata", "title", "filename"],
                ["obtain", "provide", "missing"],
            ],
        ),
    ]
    result = []
    for i, (family, question, sources, groups) in enumerate(rows):
        safe = (
            sources
            if family != "privacy"
            else ["The visitor book reports a requested music-room booking."]
        )
        result.append(
            {
                "id": f"pilot-dev-{i:02d}",
                "family": family,
                "question": question,
                "sources": sources,
                "required_quotes": safe,
                "required_refs": list(range(1, len(sources) + 1)),
                "meaning_groups": groups,
                "forbidden": ["QA-SECRET-ONLY-6158"] if family == "privacy" else [],
            }
        )
    return result


def build(
    output: Path,
    model_project: Path,
    base_model: Path,
    *,
    case_factory=training_case,
    development_factory=development_cases,
    provenance_paths: tuple[Path, ...] = (),
) -> dict:
    output = output.resolve()
    if not output.is_relative_to((ROOT / "dist").resolve()) or output.exists():
        raise ValueError("pilot output must be new inside repository dist")
    helper_path = model_project / "scripts/build_mfl_evidence_corpus.py"
    helper = load_module(helper_path, "mfl_pilot_contract_helper")
    prompt = helper.consumer_prompt_builder(ROOT)
    output.mkdir(parents=True)
    corpus_dir = output / "corpus"
    corpus_dir.mkdir()
    rows, packets = [], []
    for i in range(512):
        question, sources, quotes, limit, forbidden = case_factory(i)
        bound = "; ".join(
            f'"{quote}" [{next(j for j, s in enumerate(sources, 1) if quote in s)}]'
            for quote in quotes
        )
        response = (f"Record: {bound} Limit: " if bound else "") + limit + " Review required."
        case = helper.EvidenceCase(
            f"pilot-train-{i:04d}",
            FAMILIES[i % 8],
            "train",
            question,
            tuple(sources),
            response,
            tuple(quotes),
            tuple(forbidden),
        )
        helper.verify_case(case)
        packet = {
            "case_id": case.case_id,
            "sources": sources,
            "quotes": quotes,
            "question": question,
            "forbidden_literals": forbidden,
            "split": "train",
        }
        packets.append(packet)
        rows.append(
            {
                "schema": "mainely-code.sft-example.v1",
                "example_id": case.case_id,
                "lineage_group": case.case_id,
                "split": "train",
                "task_family": case.family,
                "rights_class": "company_owned",
                "privacy_class": "no_client_data",
                "source_digest": hashlib.sha256(canonical(packet)).hexdigest(),
                "instruction": json.dumps([{"role": "user", "content": prompt(case)}]),
                "response": response,
            }
        )
    # Store development separately: it cannot accidentally enter trainer rows.
    dev = {
        "training_use_permitted": False,
        "basis": "experiment_selection_not_final_holdout",
        "cases": development_factory(),
    }
    (output / "development.json").write_text(json.dumps(dev, indent=2) + "\n", encoding="utf-8")
    corpus = corpus_dir / "corpus.jsonl"
    corpus.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    (corpus_dir / "source-packets.jsonl").write_text(
        "".join(json.dumps(p, sort_keys=True) + "\n" for p in packets), encoding="utf-8"
    )
    paths = [
        Path(__file__).resolve(),
        helper_path,
        ROOT / "legal/agent_runtime/runtime.py",
        ROOT / "legal/fast_interchange/specialists.py",
        ROOT / "legal/fast_interchange/worker.py",
        *provenance_paths,
    ]
    manifest = {
        "schema": "mfl.evidence-corpus-manifest.v1",
        "purpose": "bounded_generalization_pilot",
        "specialist_id": "mfl-evidence-review",
        "records": len(rows),
        "split_counts": dict(Counter(r["split"] for r in rows)),
        "development_cases": len(dev["cases"]),
        "development_sha256": sha(output / "development.json"),
        "corpus_sha256": sha(corpus),
        "client_data_included": False,
        "legal_authority_content_included": False,
        "northstar_assets_included": False,
        "production_admitted": False,
        "prompt_format": "mfl_fixed_role_v1",
        "implementation_sha256": {str(p): sha(p) for p in paths},
        "limitations": [
            "512 generated variations, not 512 independently reviewed matters.",
            "Development informs selection and is not final release evidence.",
        ],
    }
    (corpus_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    auth = {
        "schema": "mainely-code.local-research-authorization.v1",
        "specialist_id": "mfl-evidence-review",
        "local_research_training_authorized": True,
        "approved_scope": (
            "local_only_research_training_and_evaluation_on_newly_authored_fictional_records"
        ),
        "authorization_basis": "user_requested_model_improvement_2026_09_05",
        "corpus_sha256": sha(corpus),
        "corpus_manifest_sha256": sha(corpus_dir / "manifest.json"),
        "base_weights_sha256": sha(base_model / "model.safetensors"),
    }
    auth.update(
        {
            k: False
            for k in (
                "external_rights_authentication_verified",
                "real_client_data_authorized",
                "statutory_training_authorized",
                "production_admitted",
                "rc_complete",
                "promotion_authority",
            )
        }
    )
    (output / "research-authorization.json").write_text(
        json.dumps(auth, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.model_project, args.base_model), indent=2))
