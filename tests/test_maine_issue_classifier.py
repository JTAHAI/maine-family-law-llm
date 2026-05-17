from legal.classifiers.issue_classifier import RuleBasedIssueClassifier

def test_issue_classifier():
    classifier = RuleBasedIssueClassifier()
    results = classifier.classify("This divorce includes child support.")
    labels = [r.label for r in results]

    assert "divorce" in labels
    assert "child_support" in labels