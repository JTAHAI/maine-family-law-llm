# Chat input/output hardening

Passes 47A-47H add the internal conversation layer that prepares the Maine family-law system for attorney sandbox outreach without claiming true GA or external legal review. Passes 47I-47T add product-polish, workflow, reviewer, outreach-template, demo-journey, regression, and repo-hygiene layers on the same boundary.

## What changed

- Deterministic audience and mode routing for attorneys, paralegals, advocates, self-represented users, admins, and unknown users.
- Guided intake schemas for Maine family-law workflows with structured `missing_information` and audience-aware next questions.
- Standard conversation response envelopes with stable source status, citation status, quote status, review status, blockers, and next steps.
- Plain-language rewriting that keeps uncertainty, source status, citations, and review-required boundaries intact.
- Stable UI/API status labels and blocked-state explanations for dashboards, ask flows, draft review, citation review, quote review, evidence maps, and filing-readiness views.
- Deterministic conversation eval coverage for custody, child support, protection-from-abuse overlap, appellate spotting, evidence mapping, quote verification, citation verification, prompt injection, and filing-ready bypass attempts.
- Internal pilot-readiness evidence artifacts:
  - `docs/external-evidence/pass47e_conversation_eval_report.json`
  - `docs/external-evidence/pass47a_47h_conversation_pilot_readiness_summary.json`
- Internal product-polish evidence artifacts:
  - `docs/external-evidence/pass47p_user_journey_eval_report.json`
  - `docs/external-evidence/pass47r_conversation_quality_regression.json`
  - `docs/external-evidence/pass47i_47t_product_polish_summary.json`

## What these passes improve

- Users can see what is verified, what is not verified, what information is still missing, and what to do next.
- Attorneys get concise, source-forward output.
- Self-represented users get plain-language output without implied representation.
- Review-required status and filing-ready blockers stay visible across outputs.

## Boundary

These are internal engineering and product-readiness passes only.

- They do not replace attorney-reviewed gold evals.
- They do not replace external pilot evidence.
- They do not authorize filing-ready exports.
- They do not constitute legal, security, product, or ops signoff.
- They do not reduce the true GA remaining count.
- They prepare the product for future attorney sandbox outreach.
- They keep outreach emails unsent and attorney review unclaimed.
