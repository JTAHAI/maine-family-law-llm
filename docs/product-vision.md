# Product vision

This project is a Maine-specific family-law legal-information workbench. It is built to help people and reviewers see source status, missing information, citation status, quote status, red flags, review-required status, filing-ready blockers, and next steps.

The product is not a generic chatbot. It prioritizes official Maine authority and transparent uncertainty over fluent prose.

## Current Status

The repository is ready for internal reviewer-outreach preparation. It is not true legal GA, not legal advice, and not filing-ready.

Passes 47I-47T add the guided product layer around the existing conversation engine: state continuity, workflow selection, answer quality, drafting and document-review conversations, reviewer queues, outreach templates, user-journey evals, workbench adapters, regression metrics, and repo-safety checks.

## How Reviewers Can Help

Reviewers can test whether the workflow is understandable, whether source status is visible, and whether unsafe claims stay blocked.

## What Evidence Would Count

Real review evidence would be actual correspondence, signed feedback, or review artifacts from qualified reviewers. Attorney review evidence requires a licensed Maine attorney or documented attorney-supervised review.

## What Evidence Does Not Count

Templates, sample evidence, generated fixture reports, unsent emails, and plans do not count as attorney review, pilot evidence, or signoff.

## Running Local Checks

```powershell
python scripts\run-conversation-product-polish-evidence.py
python scripts\run-user-journey-evals.py
python scripts\run-conversation-quality-regression.py
python scripts\check-outreach-truthfulness.py
python scripts\check-doc-unsafe-claims.py
```
