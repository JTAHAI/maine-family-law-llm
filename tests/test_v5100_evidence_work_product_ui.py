from pathlib import Path


def test_evidence_work_product_controls_are_in_main_workbench():
    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")

    for marker in (
        'id="evidence-work-product-modal"',
        'id="evidence-work-product-all-records"',
        'id="evidence-work-product-focus"',
        'id="evidence-work-product-approved"',
        'id="evidence-work-product-build"',
        'id="evidence-work-product-results"',
    ):
        assert marker in html

    assert 'id="record-inspector-evidence-work-product"' not in html

    for marker in (
        "/api/evidence-work-product/status",
        "/api/evidence-work-product/build",
        "/api/evidence-work-product/active",
        "renderEvidenceWorkProduct",
        "buildEvidenceWorkProduct",
        "closeEvidenceWorkProduct",
        "No legal conclusion",
    ):
        assert marker in js

    assert ".evidence-work-product-modal" in css
    assert ".evidence-work-product-card" in css
    assert Path("src/maine_family_law_llm/ui/workbench.html").read_bytes() == Path("maine_family_law_llm/ui/workbench.html").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.css").read_bytes() == Path("maine_family_law_llm/ui/workbench.css").read_bytes()
