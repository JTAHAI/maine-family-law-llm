POSTURE_RULES = {
    "motion to modify": "motion_to_modify",
    "contempt": "contempt",
    "appeal": "appeal",
    "temporary order": "temporary_order",
}

def classify_posture(text: str) -> str:
    lowered = text.lower()

    for key, value in POSTURE_RULES.items():
        if key in lowered:
            return value

    return "initial_complaint"
