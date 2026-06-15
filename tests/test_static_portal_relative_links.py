from __future__ import annotations

from corpus_builder_support import build_fixture_case, relative_links_from_html


def test_static_portal_links_are_relative(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    portal_root = built["case_root"] / "00_START_HERE"
    for html_path in list(portal_root.glob("*.html")) + list((portal_root / "records").glob("*.html")):
        for link in relative_links_from_html(html_path):
            assert not link.startswith(("http://", "https://"))
            target = (html_path.parent / link).resolve()
            assert target.exists(), link
