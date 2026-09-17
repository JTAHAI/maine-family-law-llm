# Maine Family Law LLM 9.0.0

## What's new

- Optional local Qwen 4B and 8B assistance for reviewing selected records and preparing working drafts.
- Task-specific instructions preserve allegations, conflicting proposals and missing information, with numbered source references.
- Evidence Review shows model-selected excerpts only after exact record matching. Unverified narrative conclusions are withheld; relevance and completeness still require review.
- Drafting assembles source-attributed working material from exact record quotations. Free factual prose is withheld because live testing found invented absence claims; this is not an unrestricted legal drafter.
- Exact context approval binds the matter, session, selected records, task and model. Changed requests require fresh approval.
- Incomplete answers, missing evidence references and detectable unbound quotations/citations are withheld. These checks do not verify every factual or legal claim.
- Improved compatibility with older Qwen templates prevents internal thinking text from appearing as the answer.
- Memory preflight includes system reserve for GPU use. Each completed request releases its model residency to support modest hardware.
- Clear recovery messages preserve original records when a request cannot finish.
- Updated production workbench layout and in-chat local-AI setup guidance.

## What is and is not included

The MSIX contains the app and its essential offline engines. Ollama and Qwen weights are separately installed; this release does not download them automatically. Qwen is general-purpose local AI, not a trained or legally qualified Maine-law specialist. Failed research adapters remain excluded. Every answer and draft requires human review; the app does not file, serve or decide a case.

## Upgrade and recovery

9.0.0.0 retains the Store identity and existing data schema. Back up matter data using the app before upgrading. Existing corpora, drafts and history are not converted into model training data. A prior-version reinstall may require Windows package removal; preserve and verify backups first. No downgrade or Store-install certification is claimed by source tests.

## Verification boundary

Current-run evidence is under `dist/qa/v9-qwen`; package qualification is recorded under `dist/release/v9.0.0/evidence`. Real local inference, mocked adversarial checks, source API tests, frozen runtime smoke and installed-package validation are distinct evidence levels. None substitutes for a comprehensive legal-quality evaluation or Microsoft Store certification.
