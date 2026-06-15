from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfWriter

from maine_family_law_llm.case_corpus_builder import (
    ROOT_LAUNCHERS,
    bootstrap_repository,
    build_case_corpus,
)


REPO_ROOT = Path(__file__).resolve().parent


def create_fixture_source_corpus(tmp_path: Path) -> Path:
    source_root = tmp_path / "fixture_source_corpus"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "2026-02-11_order.txt").write_text(
        "Court order about shared parental rights, records access, electronic contact, and in-person contact.",
        encoding="utf-8",
    )
    (source_root / "2026-02-16_good_faith_request.eml").write_text(
        "\n".join(
            [
                "From: parent@example.test",
                "To: counsel@example.test",
                "Cc: school@example.test",
                "Subject: Good-faith request for school, medical, therapy, and contact logistics",
                "Date: Tue, 16 Feb 2026 09:30:00 -0500",
                "Message-ID: <fixture-1@test>",
                "",
                "This communication requests therapy scheduling, records access, school information, and medical coordination in good faith.",
            ]
        ),
        encoding="utf-8",
    )
    (source_root / "school_attendance.txt").write_text(
        "School attendance, tardy notices, academic support, and records-access barrier context.",
        encoding="utf-8",
    )
    (source_root / "medical_release.txt").write_text(
        "Medical provider release, dental records request, MaineCare coverage, and counseling logistics.",
        encoding="utf-8",
    )
    (source_root / "unrelated_personal_newsletter.txt").write_text(
        "Unrelated volunteer newsletter and birthday planning with nonlegal chapter updates.",
        encoding="utf-8",
    )
    (source_root / "unknown_payload.bin").write_bytes(b"\x00\x01\x02unsupported")
    pdf_path = source_root / "filing_notice.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with pdf_path.open("wb") as handle:
        writer.write(handle)
    return source_root


def build_fixture_case(tmp_path: Path, case_name: str = "Fixture Family Matter") -> dict[str, object]:
    bootstrap_repository(REPO_ROOT)
    source_root = create_fixture_source_corpus(tmp_path)
    output_root = tmp_path / "case_output"
    result = build_case_corpus(
        repo_root=REPO_ROOT,
        source_roots=[source_root],
        output_root=output_root,
        case_name=case_name,
    )
    case_root = result.case_root
    proof = json.loads(result.proof_json_path.read_text(encoding="utf-8"))
    search_index = [
        json.loads(line)
        for line in (case_root / "04_INDEXES" / "search_index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "repo_root": REPO_ROOT,
        "source_root": source_root,
        "output_root": output_root,
        "case_root": case_root,
        "proof_path": result.proof_json_path,
        "proof": proof,
        "question_bank_path": result.question_bank_path,
        "search_index": search_index,
    }


def relative_links_from_html(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    links = re.findall(r'href="([^"]+)"', text)
    return [
        link
        for link in links
        if not link.startswith(("http://", "https://", "mailto:", "#"))
        and "${" not in link
    ]


def assert_root_launchers_exist(repo_root: Path) -> None:
    for name in ROOT_LAUNCHERS:
        assert (repo_root / name).exists(), name
