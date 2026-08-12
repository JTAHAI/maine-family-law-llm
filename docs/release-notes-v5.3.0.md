# Maine Family Law LLM v5.3.0

## Search intent and hyphen handling

The local matter search now recognizes list-style commands such as:

- `show me a list of everything contempt-related`
- `show me contempt records`
- `list all post-judgment documents`
- `find parent–child records`

Hyphenated, de-hyphenated, Unicode-dash, and spacing variants share the same deterministic search terms. OCR/layout breaks such as `inter-\nference` are searchable as `interference`. These transformations create local search aliases only; they do not alter original evidence, hashes, downloaded copies, or source-inspector text.

## Unique evidence first

Exact duplicate documents are collapsed by verified source hash. The answer shows one document card with the number of identical copies grouped, while the underlying inventory and audit metadata preserve the individual evidence IDs and safe filenames.

## Main-chat evidence workflow retained

Evidence remains directly under the answer. Users can open a large source preview or verified record inspector, jump to matching pages, draft from a record, open the original, and copy safe source-card details without hunting in the side rail.

## Compatibility and safety

- Newly built indexes include a normalized local FTS alias column.
- Existing v5.2 indexes remain searchable through a compatibility scan of the already-derived private inventory.
- No network access, shell execution, arbitrary plugins, or evidence mutation was added.
- Search matches remain non-conclusive and review-required.
- Product version: `5.3.0`.
- Microsoft Store package target: `5.3.0.0`.
