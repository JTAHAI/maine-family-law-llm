# Maine Family Law LLM v5.4.0 — Optional Loopback Local Agent and Provenance

v5.4.0 adds a disabled-by-default local-model review lane for users who run Ollama, LM Studio, llama.cpp, or another OpenAI-compatible server on the same computer. The application remains fully usable without a model server.

## Exact context review

Before a local-model request can run, the workbench displays the exact approved packet:

- user question;
- legal-authority excerpts;
- private-record excerpts;
- source lane and source class;
- character counts;
- content hashes;
- detected instruction-like text that will be quarantined as data.

The user approves the packet's SHA-256 manifest. The run fails closed if the packet changes before transmission.

## Loopback-only provider adapters

- Supports Ollama's `/api/generate` interface.
- Supports local OpenAI-compatible `/v1/chat/completions` interfaces.
- Accepts literal `127.0.0.1` and `::1` endpoints only.
- Rejects DNS hostnames, userinfo, query strings, fragments, traversal-like paths, and non-loopback addresses.
- Bounds prompt, request, response, timeout, and model-name sizes.
- Uses no remote provider, provider discovery, telemetry, or background connection check.

## Prompt-injection and source-lane controls

Retrieved authority, private records, filenames, tool descriptions, and model output are untrusted data. They cannot alter system policy or grant tools. Direct prompt-injection attempts block the run. Instruction-like text found inside documents is labeled and quarantined rather than followed.

Legal authority, private matter records, and model analysis remain separate:

- verified authority may support a legal statement;
- a private record may support or contradict a factual proposition but is not legal authority and does not prove an allegation;
- local-model output is analytical work product and remains review-required.

## Capability-scoped local tools

The host defines an allowlisted read/search/verify tool catalog with matter, run, argument, and call limits. The local model never receives shell execution, arbitrary filesystem access, credentials, unrestricted networking, original-evidence modification, deletion, filing, email, calendar, or payment authority.

## Provenance that follows the work

Every normal answer now receives a deterministic host provenance receipt. Local-model answers receive a receipt binding:

- provider and model;
- loopback endpoint class;
- approved context-manifest hash;
- output hash;
- cited source references;
- tool receipts;
- warnings, blockers, and review status.

Saving an answer as a draft carries its provenance reference into the protected document workspace and revision history. A model cannot self-certify legal correctness or filing readiness.

## Preserved v5.3 behavior

Hyphen-aware record search, OCR line-break repair, unique evidence cards, large in-chat source flyouts, protected drafting, immutable imported originals, tracked Word review copies, and local-only evidence inspection remain intact.

## Release qualification

This is a source release. A signed Store package still requires a clean Windows build, declared dependency installation, `pip-audit`, WACK testing, signing, and Store submission. The local-agent HTTP adapters were exercised against bounded literal-loopback mock servers; no real model weights or private matter files are packaged.
