from legal.connectors import load_official_source_targets


def test_official_source_catalog_covers_pass_2_sources():
    targets = load_official_source_targets()
    target_ids = {target.target_id for target in targets}

    assert "me-revisor-title-19a-index" in target_ids
    assert "me-courts-forms-index" in target_ids
    assert "me-lawcourt-opinions-2025" in target_ids
    assert "me-lawcourt-opinions-2019" in target_ids
    assert "me-lawcourt-opinions-2026" not in target_ids
    assert all(target.jurisdiction == "maine" for target in targets)
    assert all("maine.gov" in target.url or "courts.maine.gov" in target.url for target in targets)


def test_official_source_targets_are_valid():
    for target in load_official_source_targets():
        assert target.validate() == []
        assert target.priority >= 1
        assert target.parser_name


def test_court_rules_targets_use_current_index_or_direct_official_pdfs():
    targets = load_official_source_targets()
    by_id = {target.target_id: target for target in targets}

    assert by_id["me-courts-rules-index"].url == "https://www.courts.maine.gov/rules/index.html"
    assert by_id["me-courts-appellate-rules"].url.endswith("mr_app_p_plus_2024-11-01.pdf")
    assert by_id["me-courts-evidence-rules"].url.endswith("mr_evid_plus_2018-06-29.pdf")
    assert by_id["me-courts-probate-rules"].url.endswith("mr_prob_p_only_2019-04-11.pdf")
    assert by_id["me-courts-electronic-court-systems-rules"].url.endswith("mrecs.pdf")
    assert by_id["me-courts-rule-120-standing-order"].source_class == "court_policy_index"
    assert by_id["me-courts-records-access-policy"].url == "https://www.courts.maine.gov/help/records.html"

    forbidden_stale_html = {
        "https://www.courts.maine.gov/rules/rules-appellate.html",
        "https://www.courts.maine.gov/rules/rules-evidence.html",
        "https://www.courts.maine.gov/rules/rules-probate.html",
    }
    assert forbidden_stale_html.isdisjoint({target.url for target in targets})


def test_official_source_catalog_is_loaded_from_json_config():
    targets = load_official_source_targets()
    assert any(target.target_id == "me-courts-electronic-court-systems-rules" for target in targets)
    assert len(targets) >= 34


def test_official_source_catalog_avoids_known_404_targets():
    targets = load_official_source_targets()
    urls = {target.url for target in targets}

    assert "https://www.courts.maine.gov/maine-courts/records.html" not in urls
    assert "https://www.courts.maine.gov/courts/sjc/lawcourt/2026/index.html" not in urls
    assert "https://www.courts.maine.gov/help/records.html" in urls
    assert "https://www.courts.maine.gov/courts/sjc/lawcourt/2019/index.html" in urls
