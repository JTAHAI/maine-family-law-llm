from dataclasses import dataclass

@dataclass
class IssueMatch:
    label: str
    confidence: float

RULES = {
    "divorce": "divorce",
    "child support": "child_support",
    "contempt": "motion_for_contempt",
    "parental rights": "parental_rights_responsibilities",
}

class RuleBasedIssueClassifier:
    def classify(self, text: str):
        text = text.lower()
        matches = []

        for phrase, label in RULES.items():
            if phrase in text:
                matches.append(
                    IssueMatch(
                        label=label,
                        confidence=0.90,
                    )
                )

        return matches