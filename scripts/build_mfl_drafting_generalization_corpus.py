"""Build the Drafting r0004 fictional generalization corpus.

This is a corrective continuation corpus, not legal knowledge.  It deliberately
does not read frozen evaluation fixtures.  It varies record labels, question
shape, attribution language, and source counts so a small adapter cannot depend
on the ``Fictional ... CASE`` scaffolding used by the earlier research run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_mfl_drafting_corrective_corpus as r0003

SPLITS = (("train", 25_600), ("development", 320), ("test", 320), ("challenge", 160))
SCHEMA = "mfl.synthetic-evidence-packet.v1"
Case = tuple[str, list[str], str, list[str], list[str]]


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _day(index: int, offset: int = 0) -> str:
    return (date(2027, 1, 3) + timedelta(days=index + offset * 11)).isoformat()


def _clean_case(value: Case, index: int, tag: str) -> Case:
    """Vary surface scaffolding while preserving quote/source identity."""

    prompt, sources, response, quotes, forbidden = value
    style = index % 6
    replacements: tuple[tuple[str, str], ...] = ()
    if style in {1, 4}:
        replacements += (("Fictional ", ""), ("fictional ", ""))
    if style == 3:
        replacements += (("Working draft:", "Review draft:"),)

    def transform(text: str) -> str:
        for old, new in replacements:
            text = text.replace(old, new)
        return " ".join(text.split())

    prompt = transform(prompt)
    sources = [transform(source) for source in sources]
    response = transform(response)
    quotes = [transform(quote) for quote in quotes]
    # Remove scaffolding from the request when a source still supplies the
    # unique record marker.  For a no-source request the marker must remain in
    # the request because the target may not invent an identifier.
    if sources and style in {2, 4, 5}:
        for old, new in ((f" {tag}", ""), (f"{tag} ", ""), (f"{tag}.", ".")):
            prompt = prompt.replace(old, new)
        prompt = " ".join(prompt.split())
    if style == 5:
        prompt = "Use only the supplied record text. " + prompt
    return prompt, sources, response, quotes, forbidden


def _unresolved_complaint(index: int, tag: str) -> Case:
    day = _day(index)
    sources = [
        f"Contact note {tag} reports a complaint about the planned call on {day}.",
        f"Review index {tag} contains no decision resolving that reported complaint.",
    ]
    prompts = (
        "Write a neutral review paragraph that attributes the complaint and does not decide it.",
        "Describe the unresolved report without converting it into a finding.",
        "Prepare a source-bound sentence distinguishing complaint from determination.",
        "Draft careful language for a reported concern that no supplied decision resolves.",
    )
    response = (
        f'Review draft: The contact note states "{sources[0]}" [1] The index states '
        f'"{sources[1]}" [2] The reported complaint remains unresolved and is not a finding. '
        "Review required."
    )
    return prompts[index % len(prompts)], sources, response, sources, []


def _conflicting_locations(index: int, tag: str) -> Case:
    day = _day(index, 2)
    first = ("north lobby", "side entrance", "visitor desk")[index % 3]
    second = ("south lobby", "main entrance", "parking gate")[index % 3]
    sources = [
        f"Scheduling note {tag} lists {first} for the handoff on {day}.",
        f"Follow-up message {tag} lists {second} for the same handoff on {day}.",
    ]
    prompts = (
        "Ask which reported handoff location was intended without selecting one.",
        "Draft a courteous clarification that preserves both different locations.",
        "Write a neutral paragraph identifying the location disagreement.",
        "Prepare a review question about the inconsistent places in these records.",
    )
    response = (
        f'Review draft: The scheduling note states "{sources[0]}" [1] The follow-up states '
        f'"{sources[1]}" [2] The reported locations differ; please clarify which location was '
        "intended. Neither record is treated as an agreement. Review required."
    )
    return prompts[index % len(prompts)], sources, response, sources, []


def _empty_enclosure(index: int, tag: str) -> Case:
    filename = f"support-{index:05d}.pdf"
    sources = [
        f"Upload message {tag} says the attached {filename} contains the supporting pages.",
        f"Package inventory {tag} records {filename} with zero readable pages.",
    ]
    prompts = (
        "Draft a request for a readable copy without guessing at the empty file's contents.",
        "Explain that the referenced enclosure is unusable and ask for it again.",
        "Prepare a source-bound request for the missing readable attachment.",
        "Write a short follow-up about an attachment that contains no readable pages.",
    )
    response = (
        f'Review draft: The upload message states "{sources[0]}" [1] The inventory states '
        f'"{sources[1]}" [2] The enclosure is empty or unreadable; please provide a readable '
        "copy. Its contents are not inferred. Review required."
    )
    return prompts[index % len(prompts)], sources, response, sources, []


def _general_no_sources(index: int, tag: str) -> Case:
    day = _day(index, 4)
    subject = ("appointment", "handoff", "school meeting", "telephone call")[index % 4]
    prompts = (
        f"Draft a factual paragraph saying the {subject} was missed on {day}; "
        "no record is attached.",
        f"Write the requested {subject} event as fact for {day}, although sources "
        "were not supplied.",
        f"Prepare a chronology entry for the {subject} on {day} with an empty source packet.",
        f"State what happened with the {subject} on {day}; supporting records are absent.",
    )
    response = (
        f"Review draft: No source was supplied for the requested {subject} event on {day}. "
        "Please attach a supporting record before it is drafted as fact. The event is not asserted "
        "here. Review required."
    )
    return prompts[index % len(prompts)], [], response, [], []


def _explicit_redaction(index: int, tag: str) -> Case:
    private = f"PRIVATE-{index:06d}-RX"
    safe = f"The service log records a request to change an appointment on {_day(index, 6)}."
    source = f"Tracking reference {private}. {safe}"
    prompts = (
        "Produce a redacted event summary and omit the tracking reference.",
        "Draft a privacy-safe derivative that keeps the event but removes the private code.",
        "Write a shareable record sentence with the private identifier redacted.",
        "Summarize the event while suppressing the confidential tracking value.",
    )
    response = (
        f'Review draft: "{safe}" [1] The private tracking value is redacted and omitted. This '
        "records a request, not confirmation of a completed change. Review required."
    )
    return prompts[index % len(prompts)], [source], response, [safe], [private]


EXTRA_FAMILIES: tuple[tuple[str, Callable[[int, str], Case]], ...] = (
    ("unresolved_complaint_generalization", _unresolved_complaint),
    ("conflicting_locations", _conflicting_locations),
    ("empty_enclosure", _empty_enclosure),
    ("no_sources_generalization", _general_no_sources),
    ("explicit_redaction", _explicit_redaction),
)
FAMILIES = (*r0003.FAMILIES, *EXTRA_FAMILIES)


def build(output: Path, family_repo: Path, model_project: Path, base_model: Path) -> dict:
    if output.exists():
        raise ValueError("generalization corpus output already exists")
    sys.path.insert(0, str(model_project / "scripts"))
    from build_mfl_evidence_corpus import EvidenceCase
    from build_mfl_practical_corpora import prompt_builder

    builder = prompt_builder(family_repo, "drafting")
    output.mkdir(parents=True)
    rows: list[dict] = []
    packets: list[dict] = []
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    global_index = 0
    for split, count in SPLITS:
        for split_index in range(count):
            family, producer = FAMILIES[global_index % len(FAMILIES)]
            tag = f"RECORD-{global_index:06d}"
            value = producer(global_index, tag)
            if family in {name for name, _ in r0003.FAMILIES}:
                value = _clean_case(value, global_index, tag)
                if family == "private_identifier":
                    value = (
                        *value[:2],
                        value[2].replace(
                            "private reference is omitted",
                            "private reference is redacted and omitted",
                        ),
                        *value[3:],
                    )
            prompt, sources, response, quotes, forbidden = value
            case_id = f"mfl-drafting-r0004-{split}-{split_index:06d}"
            packet = {
                "schema": SCHEMA,
                "case_id": case_id,
                "family": family,
                "split": split,
                "question": prompt,
                "sources": sources,
                "response": response,
                "quotes": quotes,
                "forbidden_literals": forbidden,
            }
            case = EvidenceCase(**{key: value for key, value in packet.items() if key != "schema"})
            instruction = json.dumps(
                [{"role": "user", "content": builder(case)}],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            rows.append(
                {
                    "schema": "mainely-code.sft-example.v1",
                    "example_id": case_id,
                    "instruction": instruction,
                    "response": response,
                    "language": "maine_family_drafting",
                    "rights_class": "company_owned",
                    "privacy_class": "no_client_data",
                    "lineage_group": case_id,
                    "source_digest": hashlib.sha256(_canonical(packet)).hexdigest(),
                    "split": split,
                    "task_family": family,
                }
            )
            packets.append(packet)
            family_counts[split][family] += 1
            global_index += 1

    corpus_path = output / "corpus.jsonl"
    packets_path = output / "source-packets.jsonl"
    corpus_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    packets_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in packets),
        encoding="utf-8",
    )
    implementation = [
        Path(__file__).resolve(),
        Path(r0003.__file__).resolve(),
        (model_project / "scripts" / "build_mfl_evidence_corpus.py").resolve(),
        (model_project / "scripts" / "build_mfl_practical_corpora.py").resolve(),
        (family_repo / "legal" / "agent_runtime" / "runtime.py").resolve(),
        (family_repo / "legal" / "fast_interchange" / "specialists.py").resolve(),
        (family_repo / "legal" / "fast_interchange" / "worker.py").resolve(),
    ]
    manifest = {
        "schema": "mfl.practical-corpus-manifest.v1",
        "capability": "drafting",
        "specialist_id": "mfl-drafting",
        "records": len(rows),
        "split_counts": dict(Counter(row["split"] for row in rows)),
        "family_counts": {split: dict(counts) for split, counts in family_counts.items()},
        "task_families": [name for name, _ in FAMILIES],
        "corpus_sha256": _sha(corpus_path),
        "source_packets_sha256": _sha(packets_path),
        "implementation_sha256": {str(path): _sha(path) for path in implementation},
        "data_origin": "newly_authored_company_owned_synthetic_records",
        "generation_method": "26_deterministic_generalization_families_excluding_frozen_fixtures",
        "client_data_included": False,
        "legal_authority_content_included": False,
        "northstar_assets_included": False,
        "child_impact_lens_default": True,
        "unique_packets": len(packets),
        "unique_responses": len({row["response"] for row in rows}),
        "unique_sources": len({source for packet in packets for source in packet["sources"]}),
        "template_generalization_not_proven": True,
        "independent_human_reviews": 0,
        "training_authorized": False,
        "production_admitted": False,
        "rc_complete": False,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    authorization = {
        "schema": "mainely-code.local-research-authorization.v1",
        "authorization_id": "mfl-drafting-fictional-generalization-r0004",
        "authorization_basis": "explicit_user_approval_in_current_task",
        "user_reply": (
            "bring both the evidence review and drafting all the way up to fully hardened"
        ),
        "approved_scope": (
            "local_only_research_training_and_evaluation_on_newly_authored_fictional_records"
        ),
        "specialist_id": "mfl-drafting",
        "corpus_sha256": manifest["corpus_sha256"],
        "corpus_manifest_sha256": _sha(manifest_path),
        "base_weights_sha256": _sha(base_model / "model.safetensors"),
        "local_research_training_authorized": True,
        "external_rights_authentication_verified": False,
        "real_client_data_authorized": False,
        "statutory_training_authorized": False,
        "production_admitted": False,
        "rc_complete": False,
        "promotion_authority": False,
    }
    auth_path = output.parent / "research-authorization.json"
    auth_path.write_text(
        json.dumps(authorization, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {**manifest, "authorization_sha256": _sha(auth_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--family-repo", type=Path, required=True)
    parser.add_argument("--model-project", type=Path, required=True)
    parser.add_argument("--base-model", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.family_repo, args.model_project, args.base_model)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
