# Demo user journeys

These deterministic journeys show what reviewers should expect from the workbench. They are demo/eval assets, not real matter data and not attorney review evidence.

Run:

```powershell
python scripts\run-user-journey-evals.py
python scripts\run-conversation-quality-regression.py
```

Covered journeys include self-represented custody/contact questions, attorney motion-to-modify research, paralegal draft review, child support guidance, protection-from-abuse overlap, malicious uploaded text, unsupported filing-ready attempts, fake citation checks, quote span checks, authority matrices, evidence maps, appellate Rule 52 spotting, stale forms, out-of-state jurisdiction, and emergency-adjacent input.

Expected behavior:

- Source, citation, quote, missing-information, red-flag, review-required, and filing-ready statuses are visible.
- Unsafe certainty language is absent.
- Prompt injection is treated as untrusted document text.
- Filing-ready status remains blocked unless verified gates and human review pass outside these demo journeys.

The current deterministic suite has 15 user journeys and 45 total conversation-quality regression cases across existing conversation evals, user journeys, and extra regression cases.
