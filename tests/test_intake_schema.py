from legal.conversation import IntakeSchemaCatalog


def test_intake_schema_catalog_contains_required_workflows() -> None:
    catalog = IntakeSchemaCatalog()
    assert {
        "divorce",
        "parental_rights_and_responsibilities",
        "child_support",
        "parentage",
        "motion_to_modify",
        "motion_to_enforce",
        "motion_for_contempt",
        "protection_from_abuse_overlap",
        "guardianship",
        "appellate_rule_52_findings_issue",
        "document_review",
        "form_guidance",
        "evidence_mapping",
    }.issubset(catalog.required_workflows())


def test_intake_schema_validation_reports_required_and_recommended_missing_fields() -> None:
    catalog = IntakeSchemaCatalog()
    result = catalog.validate_payload("divorce", {"county": "York"})
    assert "children_involved" in result.missing_required
    assert "existing_orders" in result.missing_recommended
