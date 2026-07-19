# Fork For Your State

Maine Family Law LLM is open source on purpose, but changing the name, colors, or state abbreviation is not enough to make a safe state-specific edition.

A real state fork must replace and validate the legal authority layer, the retrieval layer, the citation rules, the evaluation data, the privacy boundaries, and the review policies for that jurisdiction.

Public repository:

- [https://github.com/JTAHAI/maine-family-law-llm](https://github.com/JTAHAI/maine-family-law-llm)

## What must be replaced

At minimum, a state fork needs:

1. official statute connectors for that state.
2. official court-rule connectors for that state.
3. Official forms and freshness tracking.
4. Appellate opinions and their source manifests.
5. A citation resolver that matches that state's citation practice.
6. Authority-ranking policy for statutes, rules, forms, trial orders, and appellate opinions.
7. Jurisdiction labels that distinguish trial, appellate, agency, and local material correctly.
8. A family-law issue ontology that matches the target state's procedures and terminology.
9. Procedural-posture labels for that state's filing and review pathways.
10. State-specific red flags, service barriers, filing blockers, and review-required warnings.
11. Source manifests and hashes for every authority and every local build step.
12. Retrieval gold data for the new jurisdiction.
13. Citation and quote-span gold data for the new jurisdiction.
14. qualified attorney review for the new jurisdiction.
15. privacy-law review for that jurisdiction's confidentiality and records rules.
16. Unauthorized-practice-of-law boundaries that match that jurisdiction.
17. Filing-readiness gates and release blockers that are accurate for that state.
18. State-specific Microsoft Store and public-distribution disclaimers.

## State-port checklist

Use this checklist before you call a state fork ready:

- Replace the Maine statute source connectors.
- Replace the Maine court-rule source connectors.
- Replace Maine court-form inventories and freshness dates.
- Replace Maine appellate and precedential source collections.
- Replace Maine citation resolution and short-form handling.
- Replace Maine authority-priority rules.
- Replace Maine family-law issue lanes and ontology labels.
- Replace Maine procedural-posture labels.
- Replace Maine safety and red-flag wording where it is state-specific.
- Regenerate source manifests and hashes.
- Rebuild retrieval gold data.
- Rebuild citation-verification gold data.
- Rebuild quote-span verification gold data.
- Rebuild filing-readiness gate tests.
- Re-run attorney review and public-interest review.
- Review privacy-law differences for family, juvenile, medical, school, and counseling records.
- Review unauthorized-practice-of-law boundaries for the state.
- Rework the Store listing and public help text so it does not imply Maine law applies elsewhere.

## What a fork must not do

- Do not present Maine authority as if it applies in another state.
- Do not keep the Maine ontology and only swap logos.
- Do not skip freshness controls.
- Do not claim filing readiness without state-specific validation.
- Do not remove the review-required and not-legal-advice boundaries.
- Do not bundle private matter corpora into public distribution packages.

## Recommended fork flow

1. Fork the repository.
2. Rename the project surface for your state.
3. Replace the authority connectors and manifests.
4. Replace the retrieval evaluation data.
5. Replace the citation rules and quote-span checks.
6. Re-run privacy and release-boundary audits.
7. Run attorney review.
8. Rebuild the Store listing and help documents for the state.
9. Ship only after the state-specific test and evidence gates are green.

## Distribution truth

This repository invites public-interest collaboration. It does not authorize cross-jurisdiction legal reuse. Each state edition stands on its own authority, validation, privacy review, and human-review policies.
