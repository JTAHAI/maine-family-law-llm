"""Predeclared separate software challenge; agent-authored fiction, not legal gold.

No fitting, thresholds or prompt changes may use this challenge's evaluation
partition. Neither partition is authorized training data or a release admission.
"""

ROWS = (
    (
        "cal-role-e",
        "Parent C signed the blue cover sheet; Parent D signed the green one.",
        "The blue cover sheet bears Parent C's signature.",
        "entailment",
    ),
    (
        "cal-role-n",
        "Parent C's folder was scanned. Nothing is recorded about Parent D's folder.",
        "Parent D's folder was scanned.",
        "neutral",
    ),
    (
        "cal-role-c",
        "Only Parent C collected the single envelope; Parent D did not collect it.",
        "Parent D collected that envelope.",
        "contradiction",
    ),
    (
        "cal-attribution-e",
        "The private letter accuses Parent D of withholding the calendar.",
        "The letter contains an accusation about withholding a calendar.",
        "entailment",
    ),
    (
        "cal-attribution-n",
        "The letter alleges an unpaid expense; no court decision is included.",
        "A judge determined that the expense is unpaid.",
        "neutral",
    ),
    (
        "cal-attribution-c",
        "The letter says no court has ruled on the claimed expense.",
        "The letter says a court ruled on that expense.",
        "contradiction",
    ),
    (
        "cal-time-e",
        "A March 1 note proposes an April 2 meeting; a March 4 reply accepts April 2.",
        "The reply accepts the proposed April 2 meeting.",
        "entailment",
    ),
    (
        "cal-time-n",
        "A March 1 note proposes an April 2 meeting. No later events are recorded.",
        "The April 2 meeting took place.",
        "neutral",
    ),
    (
        "cal-time-c",
        "The March 4 reply rejects the April 2 meeting and accepts April 9 instead.",
        "The reply accepts April 2 for that meeting.",
        "contradiction",
    ),
    (
        "cal-scope-e",
        "The list includes three receipts and identifies the fourth receipt as missing.",
        "The list identifies a missing fourth receipt.",
        "entailment",
    ),
    (
        "cal-scope-n",
        "The list names three receipts but says nothing about other records.",
        "All requested records have been produced.",
        "neutral",
    ),
    (
        "cal-scope-c",
        "Exactly three receipts were listed, with no fourth listed receipt.",
        "Four receipts were listed.",
        "contradiction",
    ),
    (
        "cal-negation-e",
        "The note reads, 'I did not receive a copy of the map'.",
        "The note's author reports not receiving a map copy.",
        "entailment",
    ),
    (
        "cal-negation-n",
        "The note has no statement about whether the gate was locked.",
        "The gate was unlocked.",
        "neutral",
    ),
    (
        "cal-negation-c",
        "The note explicitly says the gate was locked, not unlocked.",
        "The note says the gate was unlocked.",
        "contradiction",
    ),
    (
        "cal-auth-e",
        "The inventory labels the image as a screenshot with an unverified timestamp.",
        "The inventory marks the screenshot timestamp unverified.",
        "entailment",
    ),
    (
        "cal-auth-n",
        "The screenshot displays 9:15. Its origin and clock accuracy are unknown.",
        "The event actually happened at 9:15.",
        "neutral",
    ),
    (
        "cal-auth-c",
        "The inventory marks the image unauthenticated, not authenticated.",
        "The inventory marks that image authenticated.",
        "contradiction",
    ),
    (
        "eval-role-e",
        "Reviewer Elm logged the red binder; Reviewer Ash logged the yellow binder.",
        "Reviewer Ash logged the yellow binder.",
        "entailment",
    ),
    (
        "eval-role-n",
        "Reviewer Elm initialed page seven. Reviewer Ash's actions are not described.",
        "Reviewer Ash initialed page seven.",
        "neutral",
    ),
    (
        "eval-role-c",
        "The sole signature belongs to Reviewer Ash, not Reviewer Elm.",
        "The sole signature belongs to Reviewer Elm.",
        "contradiction",
    ),
    (
        "eval-attribution-e",
        "The draft declaration attributes the damaged parcel allegation to Sender One.",
        "Sender One is identified as the source of the damaged parcel allegation.",
        "entailment",
    ),
    (
        "eval-attribution-n",
        "Sender One's declaration claims a parcel was damaged. "
        "The claim is not adjudicated in this record.",
        "The parcel damage is an established judicial finding.",
        "neutral",
    ),
    (
        "eval-attribution-c",
        "The declaration expressly withdraws its earlier assertion that the parcel was damaged.",
        "The declaration maintains its earlier assertion that the parcel was damaged.",
        "contradiction",
    ),
    (
        "eval-time-e",
        "An older note names June 8; the dated correction replaces June 8 with June 18.",
        "The correction names June 18 in place of June 8.",
        "entailment",
    ),
    (
        "eval-time-n",
        "A note dated June 1 predicts delivery on June 18. No delivery receipt is supplied.",
        "Delivery occurred on June 18.",
        "neutral",
    ),
    (
        "eval-time-c",
        "The corrected ledger records the only delivery on June 18, explicitly not June 8.",
        "That delivery occurred on June 8.",
        "contradiction",
    ),
    (
        "eval-scope-e",
        "The manifest records a partial response: the cover and page one are present, "
        "page two absent.",
        "The manifest reports that page two is absent.",
        "entailment",
    ),
    (
        "eval-scope-n",
        "Page one states an amount. Page two and its possible qualifications are unavailable.",
        "There are no qualifications anywhere in the document.",
        "neutral",
    ),
    (
        "eval-scope-c",
        "The manifest expressly reports that the parcel excludes the photograph.",
        "The manifest reports the photograph is included in the parcel.",
        "contradiction",
    ),
    (
        "eval-negation-e",
        "A message denies that consent was given for the proposed trip.",
        "The message disputes that consent was given.",
        "entailment",
    ),
    (
        "eval-negation-n",
        "The message neither confirms nor denies whether consent was given.",
        "Consent was not given.",
        "neutral",
    ),
    (
        "eval-negation-c",
        "The message expressly denies receiving consent for that trip.",
        "The message confirms receiving consent for that trip.",
        "contradiction",
    ),
    (
        "eval-auth-e",
        "The examiner describes the scan as a derivative and says the original was not examined.",
        "The examiner did not examine the original.",
        "entailment",
    ),
    (
        "eval-auth-n",
        "An email export lists a sender name. The sender identity was not independently checked.",
        "The named person truly sent that email.",
        "neutral",
    ),
    (
        "eval-auth-c",
        "The examiner states that no authenticity verification was completed.",
        "The examiner states that authenticity verification was completed.",
        "contradiction",
    ),
)


def cases():
    return [
        {
            "id": i,
            "premise": "Fictional record: " + p,
            "hypothesis": h,
            "expected": e,
            "split": i.split("-")[0],
            "category": i.split("-")[1],
        }
        for i, p, h, e in ROWS
    ]
