from legal.data_boundaries import redact_private_identifiers, scan_text


def test_private_data_scanner_detects_obvious_identifiers():
    findings = scan_text("Parent email parent@example.com SSN 123-45-6789 DOB: 1/2/2010")
    kinds = {finding.kind for finding in findings}

    assert "email" in kinds
    assert "ssn" in kinds
    assert "date_of_birth" in kinds


def test_redaction_removes_common_private_identifiers():
    result = redact_private_identifiers("Email parent@example.com, phone 207-555-1212, SSN 123-45-6789")

    assert result.redaction_count == 3
    assert "parent@example.com" not in result.text
    assert "207-555-1212" not in result.text
    assert "123-45-6789" not in result.text
