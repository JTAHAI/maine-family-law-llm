from legal.connectors.maine_forms import parse_form_text, parse_forms_index
from legal.connectors.maine_rules import parse_rules_index, parse_rules_text


FORMS_HTML = """
<html><body>
<a href="/forms/pdf/fm-002.pdf">Family Matter Summary Sheet (FM-002)</a>
<a href="/forms/pdf/packets/fm-divorce-with-children-packet.pdf">Divorce with Minor Children Packet</a>
</body></html>
"""

RULES_HTML = """
<html><body>
<a href="/rules/text/MRCivPPlusFamily.pdf">Maine Rules of Civil Procedure</a>
<a href="/rules/text/mr_civ_p_120_standing_order_2023-03-09.pdf">Rule 120 Standing Order</a>
</body></html>
"""


def test_forms_index_parser_extracts_form_ids_and_packets():
    forms, audit = parse_forms_index(
        FORMS_HTML,
        source_id="forms-index",
        url="https://www.courts.maine.gov/forms/index.html",
    )

    assert audit.status == "parsed"
    assert len(forms) == 2
    assert forms[0].form_id == "FM-002"
    assert forms[0].source_card().source_class == "court_form"


def test_form_text_parser_extracts_version_date():
    form, audit = parse_form_text(
        "Family Matter Summary Sheet FM-002 Rev. 01/2025 Required fields: plaintiff defendant",
        source_id="form-fm-002",
        url="https://www.courts.maine.gov/forms/pdf/fm-002.pdf",
    )

    assert audit.status == "parsed"
    assert form.form_id == "FM-002"
    assert form.version_date == "01/2025"
    assert form.retrieved_freshness_status == "known_version_date"


def test_rules_index_parser_extracts_rule_references():
    rules, audit = parse_rules_index(
        RULES_HTML,
        source_id="rules-index",
        url="https://www.courts.maine.gov/rules/rules-civil.html",
    )

    assert audit.status == "parsed"
    assert len(rules) == 2
    assert rules[1].rule_number == "120"


def test_rules_text_parser_extracts_pdf_rule_numbers_and_rule_set():
    rules, audit = parse_rules_text(
        "MAINE RULES OF APPELLATE PROCEDURE\nRULE 1. SCOPE OF RULES\nRULE 8. RECORD ON APPEAL",
        source_id="rules-pdf",
        url="https://www.courts.maine.gov/rules/text/mr_app_p_plus_2024-11-01.pdf",
    )

    assert audit.status == "parsed"
    assert audit.metadata["rule_set"] == "Maine Rules of Appellate Procedure"
    assert [rule.rule_number for rule in rules[:2]] == ["1", "8"]
    assert all(rule.source_location.url_or_path.endswith(f"#rule-{rule.rule_number}") for rule in rules)
