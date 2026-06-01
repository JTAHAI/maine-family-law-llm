from legal.classifiers.posture_classifier import classify_posture

def test_posture_classifier():
    result = classify_posture("This is a motion to modify parental rights")
    assert result == "motion_to_modify"
