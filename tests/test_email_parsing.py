from __future__ import annotations

from corpus_builder_support import build_fixture_case


def test_email_parser_extracts_headers_and_links_message_identity(tmp_path) -> None:
    built = build_fixture_case(tmp_path)
    email_rows = [row for row in built["search_index"] if row["source_type"] == "email"]
    assert email_rows
    email_row = email_rows[0]
    assert email_row["subject"].startswith("Good-faith request")
    assert email_row["message_id"] == "<fixture-1@test>"
    assert "school@example.test" in email_row["cc"]
