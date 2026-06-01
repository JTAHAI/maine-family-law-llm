# Chat prompt-pack and source-drilldown hardening — v1.81.0

This pass continues the local browser chat workbench hardening from v1.80.0. It focuses on making the workbench easier to use for everyday Maine family-law questions without weakening the core project guardrails: source-backed answers, review-required outputs, and no legal-advice or filing-ready claims.

## What changed

- Expanded the deterministic source-backed chat library from 54 to 78 items.
- Added more real-world questions for parents, lawyers/advocates, caregivers, counselors, and therapists.
- Added a `questions_to_ask` answer style that separates:
  - questions for a lawyer or qualified reviewer, and
  - logistics-only questions for a court clerk.
- Added role-specific starter prompt packs through `public_prompt_packs()` and `/api/starter-prompt-packs`.
- Added UI starter-pack selection for the currently selected role.
- Added source-card inspection in the UI with an `Inspect source` button.
- Added JSON transcript export with source cards, latest payload metadata, review-required status, and local transcript messages.
- Refreshed the chat-library evidence runner to cover 40 sample questions and the new UI/endpoint requirements.

## New coverage examples

Parent-facing examples include:

- What should I ask a lawyer before filing?
- What can I ask the court clerk?
- What if I cannot afford filing fees?
- How should I think about service of papers?
- What if both parents agree on a parenting plan?
- What if substance-use or mental-health concerns affect parenting?
- What if a GAL is involved?
- How should I organize school and medical records?
- What if I was served with PFA papers?

Lawyer/advocate examples include:

- Review an opposition or objection.
- Audit a settlement or agreed order.
- Build a plain-language client explainer.
- Triage appeal preservation.
- Audit family form-packet selection.
- Help a self-represented person without giving legal advice.

Caregiver examples include:

- Guardianship versus parental rights.
- Parent absent, incarcerated, or unavailable.
- Existing order / relative caregiver questions.

Counselor and therapist examples include:

- Client asks what to file.
- Mandated-reporting boundary questions.
- Testimony requests.
- Parent pressure for a custody opinion.
- Collateral contacts and records.
- Child resistance to contact.

## Evidence

The refreshed evidence report is written to:

```text
/docs/external-evidence/chat_library_workbench_evidence_v181.json
```

Current focused evidence from this pass:

- 78 deterministic chat library items.
- 20 topics.
- 6 role-specific starter prompt packs.
- 40 grounded sample questions.
- UI checks for role packs, source inspection, JSON export, topic filters, source copying, branding, transcript handling, and Enter-to-ask.

## Guardrails preserved

- Outputs remain `review_required`.
- No answer is filing-ready.
- No attorney review, legal signoff, real-matter pilot, production GA, or filing-ready status is claimed.
- The deterministic library uses bundled official/safe fixture source snippets; it is not an LLM fine-tune.
- Private matter data should not be uploaded to public repos or shared models.
