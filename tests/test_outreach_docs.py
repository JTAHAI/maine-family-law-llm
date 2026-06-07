from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTREACH = ROOT / "docs" / "outreach"
EXPECTED_COLUMNS = [
    "Priority",
    "Institution",
    "Group",
    "FirstName",
    "LastName",
    "Title",
    "Email",
    "WhyThisPerson",
    "OutreachType",
    "PersonalHook",
    "GithubLink",
    "Subject",
    "Status",
    "DateSent",
    "FollowUpDate",
    "Response",
    "ReviewerType",
    "AttorneyLicensedInMaine",
    "SupervisedByAttorneyFaculty",
    "ReviewedRepo",
    "ReviewedOutputs",
    "ReviewedEvalCases",
    "ProvidedWrittenFeedback",
    "SignedPilotEvidence",
    "CountsForAttorneyReview",
    "CanCloseGAPass",
    "EvidenceFilePath",
    "Notes",
]


def test_outreach_materials_exist_and_are_unsent_templates() -> None:
    required = [
        "README.md",
        "email-templates.md",
        "contact-tracker-schema.csv",
        "contact-tracker-example-redacted.csv",
        "github-review-request.md",
        "reviewer-feedback-form.md",
        "outreach-evidence-policy.md",
    ]
    for name in required:
        assert (OUTREACH / name).is_file()

    readme = (OUTREACH / "README.md").read_text(encoding="utf-8").lower()
    assert "no emails have been sent" in readme
    assert "does not count as attorney review" in readme
    assert "microsoft 365/outlook" in readme


def test_contact_tracker_schema_has_required_columns_and_redacted_example_is_not_sent() -> None:
    schema_header = next(csv.reader((OUTREACH / "contact-tracker-schema.csv").read_text().splitlines()))
    assert schema_header == EXPECTED_COLUMNS

    rows = list(csv.DictReader((OUTREACH / "contact-tracker-example-redacted.csv").open(encoding="utf-8")))
    assert len(rows) == 1
    row = rows[0]
    assert row["Status"] == "Not started"
    assert row["DateSent"] == ""
    assert row["CountsForAttorneyReview"] == "No"
    assert row["CanCloseGAPass"] == "No"


def test_email_templates_cover_required_outreach_types_without_endorsement_claims() -> None:
    text = (OUTREACH / "email-templates.md").read_text(encoding="utf-8").lower()
    for section in (
        "short attorney or clinic version",
        "legal-tech / innovation version",
        "pre-law / usability version",
        "legal-aid / access-to-justice version",
        "follow-up version",
        "thank-you / feedback-request version",
    ):
        assert section in text
    assert "not endorsement" in text or "not a request for endorsement" in text
    assert "unsent templates" in text
