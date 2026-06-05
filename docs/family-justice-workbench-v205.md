# Family Justice Workbench v2.05

The Family Justice Workbench is a deterministic Maine family-law packet builder for local review workflows. It accepts a question, audience, procedural posture, optional context, and requested output style, then returns a structured packet with:

- answer preview and plain-language answer
- issue labels and posture label
- urgency and safety routing
- source cards and authority matrix preview
- legal caveats, missing information, and next-best-action planning
- red flags and filing-gate blocker explanations
- reviewer handoff and export metadata

It supports parent, caregiver, lawyer, counselor, therapist, and reviewer pathways. Counselor and therapist outputs use professional-boundary language and do not provide legal strategy.

## Not Legal Advice

The workbench is legal information and workflow support only. It does not create an attorney-client relationship, does not certify current law, and does not mark anything filing-ready. Official Maine authority and verified source-registry data outrank model memory, summaries, mirrors, and snippets.

All outputs default to `review_required`. Filing readiness remains blocked unless official-source freshness, authority, citation, quote-span, claim-support, form, posture, jurisdiction, and human-review gates pass.

## Evidence Files

Run:

```powershell
python scripts/build-family-justice-workbench-evidence.py --require-ready
```

This writes:

```text
docs/external-evidence/family_justice_workbench_v205_packet.json
docs/external-evidence/family_justice_workbench_v205_audit.json
docs/external-evidence/family_justice_workbench_v205.html
docs/external-evidence/family_justice_workbench_v205_test_summary.json
```

## API

When the local FastAPI app is running, call:

```text
POST /api/family-justice-workbench
```

Payload fields:

```json
{
  "question": "What should I gather before asking about a Maine parenting order?",
  "audience": "parent",
  "posture": "unknown",
  "facts_context": "",
  "requested_output_style": "plain_language"
}
```

## Tests

Run focused v2.05 tests:

```powershell
python -m py_compile legal/product/family_justice_workbench_v205.py
python -m pytest tests/test_family_justice_workbench_v205.py -q
```

Nearby tests requested for this pass:

```powershell
python -m pytest tests/test_filing_gate_studio_v203.py -q
python -m pytest tests/test_chat_library_v187_input_clear_and_routing.py -q
```

## Clean ZIP

After committing and pushing, create a local source ZIP without private/runtime artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/create-local-release-zip.ps1 -Version 2.05.0 -Label family_justice_workbench
```

The helper excludes repo metadata, virtual environments, runtime databases, vector stores, corpora, OCR caches, embeddings, model weights, private environment files, build outputs, caches, and generated dependency folders.
