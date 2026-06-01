# Chat question library and workbench UX

This pass adds a deterministic, source-backed starter question library for the local browser workbench.

## What changed

- Parents, lawyers/advocates, caregivers, counselors, and therapists now have starter prompts.
- Common questions route to structured local answers before falling back to generic snippet summaries.
- Answers remain review-required and include source cards/citation appendix output.
- The browser workbench no longer crashes when the API returns plain-text or HTML errors; it displays the error and recovery hint.
- Pressing `Enter` submits the question. Pressing `Shift+Enter` keeps a new line.
- The workbench has a FOCAF-flavored local brand treatment and links to `https://focaf.jtforme.com`.

## Included starter areas

- best-interest factor preparation
- starting a Maine family matter
- modifying or enforcing an existing order
- child-support preparation
- safety / protection-from-abuse routing
- Rule 52 and findings review
- source-stack / authority checklist
- PFA-family overlap
- caregiver / grandparent orientation
- counselor and therapist boundary questions
- stale form prevention

## Evidence command

```powershell
python scripts/run-chat-library-evidence.py --require-ready
```

The evidence report is written to:

```text
docs/external-evidence/chat_library_workbench_evidence.json
```
