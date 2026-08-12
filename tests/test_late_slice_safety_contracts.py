from pathlib import Path

from legal.matter.care_pathways import CarePathwayStore
from legal.matter.email_integrity import EmailIntegrityStore
from legal.matter.filing_readiness import FilingReadinessStore
from legal.matter.foaa_requests import FoaaRequestStore
from legal.matter.image_evidence_review import ImageEvidenceStore
from legal.matter.language_access import LanguageAccessStore
from legal.matter.modification_review import ModificationReviewStore
from legal.matter.negotiation_matrix import NegotiationMatrixStore
from legal.matter.parenting_schedule import ParentingScheduleStore
from legal.matter.property_valuation import PropertyValuationStore
from legal.matter.resource_navigator import ResourceNavigatorStore
from legal.matter.reviewer_handoff import ReviewerHandoffStore
from legal.matter.safety_review import SafetyReviewStore


def _case(tmp_path: Path) -> Path:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    return case


def test_late_slice_non_action_and_non_determination_contracts(tmp_path: Path) -> None:
    case = _case(tmp_path)
    key = "synthetic-test-passphrase"
    assert CarePathwayStore(case, encryption_key=key).inventory()["eligibility"] == "not_determined"
    assert SafetyReviewStore(case, encryption_key=key).inventory()["emergency_service"] is False
    assert (
        ParentingScheduleStore(case, encryption_key=key).inventory()["automatic_calendar_write"]
        is False
    )
    assert (
        NegotiationMatrixStore(case, encryption_key=key).inventory()["automatic_communication"]
        is False
    )
    assert (
        PropertyValuationStore(case, encryption_key=key).inventory()["division"] == "not_determined"
    )
    assert (
        ModificationReviewStore(case, encryption_key=key).inventory()["material_change"]
        == "not_determined"
    )
    assert FoaaRequestStore(case, encryption_key=key).inventory()["automatic_submission"] is False
    assert FilingReadinessStore(case, encryption_key=key).inventory()["automatic_filing"] is False
    assert ImageEvidenceStore(case, encryption_key=key).inventory()["originals_immutable"] is True
    assert EmailIntegrityStore(case, encryption_key=key).inventory()["mail_send"] is False
    assert ReviewerHandoffStore(case, encryption_key=key).inventory()["automatic_share"] is False
    assert (
        LanguageAccessStore(case, encryption_key=key).inventory()["certified_translation"] is False
    )
    assert (
        ResourceNavigatorStore(case, encryption_key=key).inventory()["automatic_outreach"] is False
    )


def test_late_slice_receipts_are_hash_bound(tmp_path: Path) -> None:
    case = _case(tmp_path)
    key = "synthetic-test-passphrase"
    stores = (
        CarePathwayStore(case, encryption_key=key),
        SafetyReviewStore(case, encryption_key=key),
        ParentingScheduleStore(case, encryption_key=key),
        NegotiationMatrixStore(case, encryption_key=key),
        PropertyValuationStore(case, encryption_key=key),
        ModificationReviewStore(case, encryption_key=key),
        FoaaRequestStore(case, encryption_key=key),
        FilingReadinessStore(case, encryption_key=key),
        ImageEvidenceStore(case, encryption_key=key),
        EmailIntegrityStore(case, encryption_key=key),
        ReviewerHandoffStore(case, encryption_key=key),
        LanguageAccessStore(case, encryption_key=key),
        ResourceNavigatorStore(case, encryption_key=key),
    )
    assert all(len(store.receipt()["receipt_hash"]) == 64 for store in stores)
