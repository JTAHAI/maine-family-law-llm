# Maine Family Law LLM v3.2.0 — Chat and Intake Understanding

This release improves how the local workbench understands a family’s question, parses selected records, searches actual content, and turns source-grounded results into a calm response.

## What changed

- Added deterministic, transparent intake understanding for served papers, hearings, orders, enforcement, modification, child support, safety, record organization, printable search, and direct local-record search.
- Normalizes common plain-language terms and spelling errors without turning them into legal conclusions. For example, “parental interferrence” is routed neutrally as a possible parent-child-contact issue; it is not labeled contempt or proven misconduct.
- Extracts dates, document types, court/docket clues, procedural posture, child relevance, urgency signals, the user’s immediate goal, and no more than three essential follow-up questions.
- Replaced repeated generic chat blocks and raw citation appendices with a typed answer contract: what it means, what to do now, next three steps, what to gather, what is missing, child impact, source lanes, and when human help matters.
- Direct commands such as “Find all mentions of contempt” search private record contents only, return compact match counts and page/member locators, and do not substitute an unrelated Maine-law answer.
- Follow-ups such as “give me the source cards” reopen the prior local result set in the same session without running a new search.
- Added page-level PDF inventory, EML header/body/attachment parsing, MBOX parsing, safe ZIP-member parsing, document-kind profiles, date/case-number extraction, and page-aware FTS5 records.
- OCR-derived records remain explicitly labeled. Native extraction is attempted first; OCR remains a separate local user choice.

## Source boundaries

- Maine-law sources support statements of law, not disputed family facts.
- Private records may show what appears in a selected file, but a text match does not prove contempt, interference, abuse, intent, or any other legal conclusion.
- FOCAF printables remain optional secondary family resources, never legal authority or official court forms.
- Intake parsing, private-file extraction, OCR, inventorying, FTS5 indexing, snippets, and search remain local.

## Compatibility

The API continues returning the legacy `answer` string for existing clients, but it is now derived from `structured_answer`. Answer-style headings remain available for intake, missing-information, professional-boundary, questions-to-ask, and source-card-table clients.

## Release versions

- Product: `3.2.0`
- Microsoft Store package: `3.2.0.0`
