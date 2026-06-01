from legal.classifiers.red_flag_classifier import detect_red_flags

def test_red_flag_classifier():
    result = detect_red_flags("There may be a jurisdiction defect.")

    assert "jurisdiction defect" in result
