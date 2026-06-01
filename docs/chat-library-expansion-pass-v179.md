# Chat Library Expansion Pass v1.79

This pass expands the local workbench from a small demo prompt set into a multi-audience starter library for non-technical testing.

## Added audience coverage

- Parents: served papers, mediation/conference prep, evidence organization, contact schedules, child preference, gender preference, safety vs. ordinary conflict.
- Lawyers/advocates: post-judgment triage, best-interest findings matrix, jurisdiction/scope warnings.
- Caregivers/relatives: existing-order triage and safety routing.
- Counselors: plain-language boundaries and court-letter caution.
- Therapists/clinicians: reunification/contact boundaries and therapy-record confidentiality caution.

## Workbench UX

- The library now has a search field.
- Starter prompts include served papers, evidence organization, and counselor court-letter questions.
- API `/ask` now returns a structured JSON payload for empty questions and internal workbench exceptions instead of letting the browser crash on a plain `Internal Server Error` response.

## Boundaries

The added answers are deterministic, source-backed starter responses. They are not legal advice and are not filing-ready. They are meant to help users ask better questions, organize facts, and find the right official source cards.
