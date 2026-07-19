# Maine Family Law LLM v3.0.0 Release Candidate

## Release identity

- Product version: `3.0.0`
- Microsoft Store package version: `3.0.0.5`
- Package identity: `TAHAIWebServices.MaineFamilyLawLLM`
- Publisher: `CN=D75EE668-B409-45ED-87E5-E37AA5FE3868`
- Publisher display name: `TAHAI Web Services`

## Highlights

- Need-first onboarding that lets a family start a source-grounded chat immediately or create a private case corpus when ready.
- Clear source-lane controls for Maine law, private records, or a combined answer. Combined answers retain the distinction between legal authority and private record citations.
- A structured answer contract with practical next steps, records to gather, missing-information guidance, child-impact lens, sources, safety flags, and limits.
- Local-first cancellation, draft clearing, source drawers, keyboard-accessible controls, responsive composer behavior, and privacy-forward empty states.
- The composer now keeps source-lane selection, Child Impact Lens, and Send in a stable, readable control row at desktop widths and stacks them cleanly on small screens.
- The packaged runtime includes a fictional smoke-test workflow only. It does not include a user's personal corpus or raw mailbox material.

## Validation status

The release candidate passed the complete 623-test repository Python suite and focused v3 release, Store packaging, installer, launcher, API, UI, and hygiene checks. The packaged runtime smoke test passed, including the fictional sample workflow, source-grounded answer, local service launch, and external data-boundary checks.

Windows App Certification Kit was invoked for this package but requires elevation on this machine. It remains a required final Store-submission check.

## Important limits

- This software supports record navigation and source-grounded review; it is not legal advice.
- A result may be incomplete when relevant source material was not imported or was not found in the active corpus.
- Maine legal authorities should be verified against current official sources before relying on them.
- Microsoft Partner Center ingestion and elevated WACK validation remain outside this local release-candidate run.
