RED_FLAGS = [
    "missing Rule 52 findings",
    "unsupported best-interest findings",
    "jurisdiction defect",
    "deadline risk",
]

def detect_red_flags(text: str):
    matches = []

    lowered = text.lower()

    for flag in RED_FLAGS:
        if any(term in lowered for term in flag.lower().split()):
            matches.append(flag)

    return matches
