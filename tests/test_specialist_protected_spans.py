"""Deterministic privacy projection, not a trained specialist quality claim."""

from dataclasses import replace
from hashlib import sha256

import pytest

from legal.agent_runtime.contracts import ContextManifestBuilder, ContextSource
from legal.fast_interchange.drafting_output import verify_drafting_output
from legal.fast_interchange.evidence_output import verify_evidence_output
from legal.security.protected_spans import model_context_projection, protected_spans

SOURCE = ContextSource(
    "fictional",
    "private_record",
    "Fictional source",
    "The packet is missing. Personal string: DEMO-ONLY-1234. Keep the cover sheet.",
)


@pytest.mark.parametrize(
    "label", ["Personal access string", "Personal string", "Private identifier", "API key"]
)
@pytest.mark.parametrize("separator", [":", "：", " = ", " — "])
@pytest.mark.parametrize("verifier", [verify_evidence_output, verify_drafting_output])
def test_both_specialists_withhold_labeled_secrets(label, separator, verifier):
    source = replace(SOURCE, text=f"{label}{separator}DEMO-ONLY-1234. The packet is missing.")
    report = verifier('"DEMO-ONLY-1234" [1]', (source,))
    assert report["status"] == "withheld"
    assert any("sensitive_quote_withheld" in code for code in report["blockers"])


def test_annotations_protect_unclassified_values_before_model_context():
    text = "Unknown marker DEMO-ONLY-1234. The packet is missing."
    start = text.index("DEMO")
    source = replace(
        SOURCE,
        text=text,
        metadata={
            "privacy_exclusions": [
                {
                    "start_offset": start,
                    "end_offset": start + 14,
                    "source_text_sha256": sha256(text.encode()).hexdigest(),
                }
            ]
        },
    )
    manifest, selected = ContextManifestBuilder().build(
        question="Inspect fictional evidence", sources=[source], run_id="fictional"
    )
    assert "DEMO-ONLY-1234" not in selected[0].text
    assert "DEMO-ONLY-1234" not in str(manifest.to_dict())
    assert source.text == text  # never alter the original source
    assert len(selected[0].text) == len(text)
    for verifier in (verify_evidence_output, verify_drafting_output):
        assert verifier('"DEMO-ONLY-1234" [1]', (source,))["status"] == "withheld"
        report = verifier('"The packet is missing." [1]', selected)
        assert not report["blockers"]
        start = report["source_spans"][0]["start_offset"]
        assert text[start:].startswith("The packet")


@pytest.mark.parametrize(
    "exclusions",
    [
        "invalid",
        [None],
        [{"start_offset": -1, "end_offset": 3}],
        [{"start_offset": 0, "end_offset": 3, "source_text_sha256": "0" * 64}],
    ],
)
def test_malformed_and_stale_exclusions_fail_closed(exclusions):
    assert protected_spans(SOURCE.text, {"protected_spans": exclusions}) == ((0, len(SOURCE.text)),)


def test_projection_is_idempotent_and_masks_cannot_be_quoted():
    text, meta = model_context_projection(SOURCE.text, {})
    again, second = model_context_projection(text, meta)
    assert again == text
    projected = replace(SOURCE, text=again, metadata=second)
    for verifier in (verify_evidence_output, verify_drafting_output):
        assert verifier('"██████████████" [1]', (projected,))["blockers"]


def test_changed_exclusions_change_approval_manifest():
    builder = ContextManifestBuilder()
    clean = replace(SOURCE, text="Fictional marker and safe fact.")
    excluded = replace(clean, metadata={"protected_spans": [{"start_offset": 0, "end_offset": 16}]})
    first, _ = builder.build(question="Review", sources=[clean], run_id="same", created_at="same")
    second, _ = builder.build(
        question="Review", sources=[excluded], run_id="same", created_at="same"
    )
    assert first.manifest_sha256 != second.manifest_sha256
