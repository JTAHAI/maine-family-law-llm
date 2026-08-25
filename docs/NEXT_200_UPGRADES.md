# Next 200 upgrades after v8.0.0

This backlog is ordered for implementation, not brainstorming. Earlier slices reduce risk or create leverage for later slices. It is an execution queue, not a release claim: every slice remains unadvertised until it satisfies the acceptance path below.

## Campaign status

- **Slices 1–2:** implemented and verified in the source checkout plus local production-asset smoke. Evidence: `dist/ga_today/evidence/09_chat_streaming_performance.json`.
- **Slice 3:** implemented and verified in the source checkout plus local production-asset smoke. Evidence: `dist/ga_today/evidence/10_fast_answer_path.json`.
- **Slice 4:** implemented and verified in the source checkout plus local production-asset smoke. Evidence: `dist/ga_today/evidence/11_progressive_grounded_answers.json`.
- **Slice 5:** implemented and verified in the source checkout plus local production-asset smoke, with intentionally no-prose continuity scope. Evidence: `dist/ga_today/evidence/12_safe_conversation_context.json`.
- **Slice 6:** implemented and verified in the source checkout plus local production-asset smoke. Evidence: `dist/ga_today/evidence/13_answer_intent_router.json`.
- **Slice 7:** implemented and verified by focused service/API, production-asset, and mirror tests. The browser smoke is pending because the retained browser session is not callable in this environment. Evidence: `dist/ga_today/evidence/14_actionable_answer_footer.json`.
- **Slice 8:** the existing inline source hover/preview path was audited and hardened so a snippet without an admitted character range is explicitly marked as not an exact span. Evidence: `dist/ga_today/evidence/15_inline_source_preview.json`.
- **Slice 9:** implemented with a session- and matter-scoped immutable correction receipt, transient verifier re-run, exact source drill-down, and fail-closed matter audit. Evidence: `dist/ga_today/evidence/16_answer_correction_workflow.json`.
- **Slice 10:** implemented with bounded local latency receipts, privacy-safe audit in active matters, aggregate inspection, and in-answer timing disclosure. Evidence: `dist/ga_today/evidence/17_chat_latency_observatory.json`.
- **Slice 11:** implemented with concise, standard, and thorough display modes carrying the same source-basis receipt and review requirements. Evidence: `dist/ga_today/evidence/18_response_depth_control.json`.
- **Slice 12:** implemented with explicit audience presentation lanes that cannot alter retrieval, sources, verifier states, or legal truth. Evidence: `dist/ga_today/evidence/19_audience_aware_explanations.json`.
- **Slice 13:** implemented with one material, explanation-backed clarification question and safe workflow-selecting follow-ups. Evidence: `dist/ga_today/evidence/20_clarification_minimizer.json`.
- **Slice 14:** implemented with an explicit source-bound/user-provided/unknown assumption ledger and non-mutating correction handoff. Evidence: `dist/ga_today/evidence/21_assumption_ledger.json`.
- **Slice 15:** implemented with transient same-source comparison, side-by-side verifier states, and no automatic selection or drafting. Evidence: `dist/ga_today/evidence/22_answer_comparison.json`.
- **Slice 16:** implemented with isolated source-lineage branches that omit raw conversation and matter text. Evidence: `dist/ga_today/evidence/23_conversation_branching.json`.
- **Slice 17:** implemented with encrypted, matter-scoped fact pins, exact source locators, effective-date and dispute fields, hash-linked local audit, and a review-required chat action. Evidence: `dist/ga_today/evidence/24_pinned_conversation_facts.json`.
- **Slice 18:** implemented with compound-question decomposition, explicit independent-verification status, shared-source-basis receipts, and focused follow-up actions. Evidence: `dist/ga_today/evidence/25_question_decomposition.json`.
- **Slice 19:** implemented with a narrow, source-bound conflicting-date review prompt against encrypted pinned facts; it cannot decide truth, legal effect, or materiality. Evidence: `dist/ga_today/evidence/26_contradiction_followups.json`.
- **Slice 20:** implemented with deterministic structural answer checks and a separate human-review rubric; it never represents synthetic signals as attorney review or a correctness certification. Evidence: `dist/ga_today/evidence/27_response_usefulness.json`.
- **Frozen runtime / MSIX status for slices 1–20:** not yet evaluated. No slice is represented here as Store or Enterprise GA evidence.
- **Slice 21:** implemented in the source checkout with bounded local lexical-plus-deterministic-semantic reciprocal-rank fusion, exact-citation priority, rank explanation, and a visible lexical fallback for corpora above the interactive cap. Evidence: `dist/ga_today/evidence/28_hybrid_retrieval_rank_explainability.json`.
- **Frozen runtime / MSIX status for slice 21:** not yet evaluated. The larger-corpus lexical fallback is a disclosed usability limitation, not a semantic-retrieval claim.
- **Slice 22:** implemented with deterministic, local Maine-vocabulary expansion that preserves exact references, refuses to add Maine synonyms when a non-Maine jurisdiction is detected, and makes that boundary visible in the shipped chat UI. Evidence: `dist/ga_today/evidence/29_guarded_query_expansion.json`.
- **Frozen runtime / MSIX status for slice 22:** not yet evaluated. No slice is represented here as Store or Enterprise GA evidence.
- **Slice 23:** blocked. The repository and the current packaged runtime contain no admitted local cross-encoder/reranker model or admission record. The existing authority-priority fallback works, but is not represented as cross-encoder reranking. Evidence: `dist/ga_today/evidence/30_cross_encoder_reranking_blocker.json`.
- **Slice 24:** implemented in the source checkout with an active-authority citation-graph API and shipped source-card action. It exposes parsed links only and never claims treatment or legal effect. Evidence: `dist/ga_today/evidence/31_citation_graph_retrieval.json`.
- **Slice 25:** implemented with an explicit as-of-date metadata review lane that blocks a historical-law conclusion when returned authority is later-dated, stale, unknown, or incomplete. Evidence: `dist/ga_today/evidence/32_temporal_authority_resolver.json`.
- **Slice 26:** implemented as an honest negative-treatment review lane: every legal source card visibly carries its parsed status, defaulting to unknown where no admitted treatment evidence exists. Evidence: `dist/ga_today/evidence/33_negative_treatment_lane.json`.
- **Slice 27:** implemented with a narrow same-citation metadata conflict explainer and explicit source-version drill-down; it does not decide controlling authority or legal effect. Evidence: `dist/ga_today/evidence/34_authority_conflict_explainer.json`.
- **Slice 28:** implemented in the source checkout with exact admitted nested statute and rule offsets, Law Court paragraph/page metadata, form revision metadata, a canonical authority API, and a hidden-by-default production UI control. It never infers legal effect and reports an absent exact span honestly. Focused service/API/UI tests pass.
- **Frozen runtime / MSIX status for slice 28:** source assets and frozen-runtime route registration are verified; a rebuilt MSIX is still required before any packaged-reachability claim.
- **Next implementation slice:** 29, Retrieval diversity control.

## Twenty major capability tracks

These are the twenty substantial additions represented by the 200 slices; each is decomposed below so it can be tested and released honestly rather than shipped as a broad, untestable promise.

1. Streaming, cancellable, source-safe AI chat (1–10)
2. Calibrated conversation control and correction (11–20)
3. Hybrid official-authority retrieval and citation graph (21–30)
4. Atomic authority updates, freshness, and source lineage (31–40)
5. Matter fact graph, issue-to-proof mapping, and completeness review (41–50)
6. Resumable document intelligence and scanner ingestion (51–60)
7. Audio, video, screenshot, and chain-of-custody evidence workbench (61–70)
8. Source-bound drafting, revision, citations, and exports (71–80)
9. Guided procedure, deadlines, service, forms, and filing readiness (81–90)
10. Parenting, finance, settlement, and compliance planning workspaces (91–100)
11. Hardware-aware local AI runtime and admitted-model management (101–110)
12. Universal navigation, search, saved views, and work continuity (111–120)
13. Modular accessible UI, keyboard control, and visual regression coverage (121–130)
14. Per-matter cryptography, parser isolation, and adversarial defenses (131–140)
15. Durable jobs, recovery, storage resilience, and performance observability (141–150)
16. Encrypted backups, migrations, Store-install automation, and release controls (151–160)
17. Enterprise governance, policies, legal holds, and audit verification (161–170)
18. Reviewer collaboration, exports, printing, and interoperability receipts (171–180)
19. Attorney-quality evaluation, accessibility review, and controlled pilot operations (181–190)
20. Jurisdiction packs, extension sandboxing, reproducible releases, and Enterprise-GA evidence (191–200)

## Universal definition of done

Every product slice must complete the real production path:

`service -> canonical loopback API -> matter/tenant/role enforcement -> encrypted private state -> append-only audit -> shipped desktop UI -> meaningful fictional action -> exact source/artifact drill-down -> visible review-required status -> focused and adversarial tests -> frozen-runtime reachability -> MSIX asset/privacy verification`

Additional rules:

- Never infer a legal conclusion, fact, filing status, tribal status, jurisdiction, credibility, or safety outcome.
- Keep official authority, private evidence, and model analysis visibly separate.
- Fail closed for missing, stale, wrong-jurisdiction, contradicted, or unverifiable support.
- Measure cold start, first useful feedback, first token or first result, total duration, memory, cancellation, and restart behavior where relevant.
- Do not advertise a slice until production-UI and frozen-runtime evidence pass.

## Wave 1 - Chat speed and immediate usefulness

1. **Streaming answer protocol** - Stream structured answer sections, citations, and verifier states over the canonical API; cancellation and interrupted-stream recovery must be deterministic.
2. **First-useful-feedback budget** - Show honest retrieval/rerank/verification progress within 150 ms and enforce performance budgets in CI.
3. **Fast answer path** - Route simple navigation, record lookup, definition, and status questions without invoking the full research pipeline.
4. **Progressive grounded answers** - Render a concise sourced answer first, then expand analysis, missing information, and next actions without changing the cited basis.
5. **Conversation context compaction** - Summarize long chats into source-bound, matter-scoped memory with reversible inspection and no silent fact promotion.
6. **Answer intent router v2** - Distinguish explain, locate, compare, draft, review, calculate, prepare, and navigate intents with calibrated ambiguity handling.
7. **Actionable answer footer** - End each response with the safest next action, required inputs, blockers, and one-click opening of the relevant workspace.
8. **Inline source hover and preview** - Open exact spans, freshness, jurisdiction, and source class without leaving the conversation.
9. **Answer correction workflow** - Let users flag a sentence, attach a reason, rerun verification, and preserve the original and corrected versions immutably.
10. **Chat latency observatory** - Record local-only stage timings, queue delay, model tokens, cache hits, and hardware context without private prompt text.

## Wave 2 - Answer quality and conversational control

11. **Response depth control** - Add concise, standard, and thorough modes while preserving the same verifier and safety requirements.
12. **Audience-aware explanations** - Support self-represented litigant, legal-aid intake, paralegal, and attorney review modes without changing legal truth.
13. **Clarification minimizer** - Ask only questions that materially change retrieval, procedure, drafting, or safety; explain why each is needed.
14. **Assumption ledger** - Display facts assumed, disputed, unknown, or inferred and allow the user to correct each one.
15. **Answer comparison** - Compare two generated approaches against the same sources, evidence, omissions, and risk flags.
16. **Conversation branching** - Fork a chat from any message while preserving source lineage and matter isolation.
17. **Pinned conversation facts** - Pin verified matter facts with source locators, effective dates, and dispute status for reuse.
18. **Question decomposition** - Break compound questions into independently sourced subquestions and report unresolved parts explicitly.
19. **Contradiction-aware follow-ups** - Detect when a new user statement conflicts with an order, record, or prior verified statement and request review.
20. **Response usefulness evaluation** - Add deterministic and human-review rubrics for correctness, actionability, clarity, restraint, and citation sufficiency.

## Wave 3 - Retrieval and official-authority excellence

21. **Hybrid retrieval v2** - Fuse lexical, vector, citation, heading, and metadata retrieval with explainable rank contributions.
22. **Query expansion with guardrails** - Generate Maine-law synonyms and procedural variants without changing jurisdiction or issue scope.
23. **Cross-encoder reranking** - Add an admitted local reranker with hardware-aware fallback and reproducible evaluation.
24. **Citation graph retrieval** - Traverse statutes, rules, opinions, forms, amendments, and cited authorities while preserving source hierarchy.
25. **Temporal authority resolver** - Answer “law as of date” questions using effective dates, amendments, supersession, and freshness blockers.
26. **Negative-treatment review lane** - Surface available subsequent-treatment signals without claiming comprehensive citator status.
27. **Authority conflict explainer** - Compare apparently conflicting sources by class, date, court, scope, and exact language.
28. **Pinpoint resolver expansion** - Support nested statute paragraphs, rule subdivisions, slip-opinion paragraphs, page spans, and form revisions.
29. **Retrieval diversity control** - Prevent redundant source cards and require coverage across the material source classes for the question.
30. **Authority gap detector** - Identify issue areas where the active admitted corpus lacks current or complete official sources.

## Wave 4 - Authority operations and freshness

31. **Atomic authority update center** - Download only by explicit operator action, validate, stage, diff, activate, and roll back accepted builds.
32. **Source-change impact analysis** - Map an amended source to affected saved research, drafts, forms, deadlines, and packets.
33. **Freshness service-level dashboard** - Show source-class freshness thresholds, overdue sources, parser failures, and last accepted build.
34. **Official-source availability monitor** - Detect moved URLs, changed hashes, TLS failures, and access restrictions without silent mirror substitution.
35. **Parser regression corpus** - Maintain versioned official-page fixtures covering layout changes, footnotes, tables, and malformed downloads.
36. **Authority lineage inspector** - Drill from answer span to parsed node, snapshot, retrieval event, official URL, and build fingerprint.
37. **Forms catalog synchronizer** - Compare installed form metadata with current official catalog revisions and block stale completion paths.
38. **Law Court opinion enrichment** - Add disposition, date, docket, panel, paragraph map, cited authorities, and neutral case summary with exact spans.
39. **Rule-history timeline** - Show amendment history and effective dates for Maine procedural and evidentiary rules.
40. **Offline authority portability** - Export and import signed, hash-verified authority bundles without packaging authority data in the MSIX.

## Wave 5 - Matter intelligence foundation

41. **Timeline correction acceptance** - Complete event correction, append-only history, source rebinding, UI drill-down, and frozen-app proof.
42. **Claim-disposition acceptance** - Complete support, contradiction, qualification, missing-context, and reviewer-decision workflows.
43. **Whole-matter command center acceptance** - Finish snapshots, blocker aggregation, health history, and exact corrective actions.
44. **Missing-attachment coverage acceptance** - Distinguish alleged, referenced, expected, absent, and not-yet-reviewed attachments.
45. **Matter fact graph** - Link people, events, orders, assertions, records, and sources while preserving disputed/unknown states.
46. **Issue-to-proof matrix** - Map each issue to legal elements, supporting evidence, contradictions, missing proof, and authority.
47. **Matter change digest** - Summarize new records, altered conclusions, new contradictions, deadlines, and stale work since last review.
48. **Record supersession graph** - Track originals, duplicates, changed copies, corrected OCR, translations, redactions, and exported derivatives.
49. **Cross-document entity resolution** - Resolve likely duplicate entities with explicit reviewer confirmation and reversible merges.
50. **Matter completeness scoring** - Produce explainable coverage dimensions and blockers without predicting case outcomes.

## Wave 6 - Document ingestion and intelligence

51. **Incremental large-matter ingest** - Resume interrupted imports, deduplicate before parsing, and keep the UI responsive.
52. **Watch-folder review queue** - Offer an opt-in local candidate queue without silently importing or running as a hidden service.
53. **Scanner ingestion workflow** - Add scan profiles, duplex cleanup, blank-page review, orientation, and immutable originals.
54. **Handwriting review lane** - Identify probable handwriting and route uncertain OCR to human transcription without overstating confidence.
55. **Document type classifier v2** - Classify pleadings, orders, affidavits, correspondence, financial records, forms, and exhibits with review.
56. **Page-level quality map** - Show OCR confidence, skew, blur, missing text, parser fallbacks, and pages requiring review.
57. **Table lineage inspector** - Bind every extracted cell to page coordinates, OCR text, parser output, and reviewer corrections.
58. **Document comparison v2** - Compare text, structure, tables, signatures, metadata, and page images across versions.
59. **Batch metadata editor** - Apply reviewed labels, dates, custodians, confidentiality, and document types with immutable audit history.
60. **Import policy profiles** - Save matter-specific size, format, privacy, OCR, and quarantine rules without weakening global safeguards.

## Wave 7 - Evidence and multimedia

61. **Audio transcript correction studio** - Edit timestamped segments with immutable original transcript, confidence, and reviewer history.
62. **Speaker labeling review** - Suggest speaker clusters locally and require explicit naming/confirmation before reuse.
63. **Video keyframe evidence review** - Generate local keyframes, timestamps, visual hashes, and source-bound annotations.
64. **Media redaction derivatives** - Create review-required audio muting and video blur proposals while preserving originals.
65. **Screenshot conversation reconstruction** - Order message screenshots using visible timestamps and metadata, exposing gaps and uncertainty.
66. **EXIF and media metadata inspector** - Present available metadata, absence, conflicts, and derivative effects without authentication claims.
67. **Evidence relationship graph v2** - Add temporal, attachment, reply, duplicate, contradiction, and derivative edges with exact provenance.
68. **Exhibit admission checklist** - Organize foundation questions, authenticity materials, objections, and missing proof without legal conclusions.
69. **Chain-of-custody event capture** - Record collection, transfer, transformation, hashing, review, and export events with signed receipts.
70. **Courtroom media player** - Provide offline keyboard-controlled playback, clips, transcript sync, and private-note separation.

## Wave 8 - Drafting and revision excellence

71. **Tracked-DOCX installed workflow acceptance** - Prove import, tracked changes, comments, reimport, comparison, and frozen-package operation.
72. **Structured draft outline builder** - Build issue-based outlines from selected authority and evidence before generating prose.
73. **Sentence-level support map** - Show factual and legal support, contradictions, qualifications, and missing context for every draft sentence.
74. **Citation insertion assistant** - Insert verified citations and pinpoints from selected source spans without free-form invention.
75. **Quote-safe drafting** - Permit quoted language only from verified exact or approved normalized spans.
76. **Draft requirement profiles** - Encode configurable document requirements, sections, limits, and review gates without claiming court approval.
77. **Revision rationale ledger** - Record why text changed, who changed it, affected claims, and verifier impact.
78. **Plain-language dual view** - Maintain legal-review and plain-language working copies with synchronized source lineage.
79. **Argument/counterargument matrix** - Organize competing positions, support, weaknesses, and missing proof without predicting outcomes.
80. **Export provenance footer** - Embed version, matter, source snapshot, review state, privacy state, and receipt identifiers in exports.

## Wave 9 - Forms, procedure, and deadlines

81. **Guided forms acceptance** - Complete current-form catalog checks, session persistence, validation, stale-form blocking, and packaged proof.
82. **Procedure pathway engine v2** - Generate reviewable procedural checklists from case type, posture, venue, and existing orders.
83. **Deadline dependency graph** - Recalculate candidate dates when a source-bound trigger changes while preserving prior calculations.
84. **Service-method rules matrix** - Compare selected service method, source authority, proof, exceptions, and unresolved facts.
85. **Court holiday and business-day engine** - Version calendar inputs, jurisdiction rules, and calculation receipts.
86. **Hearing preparation countdown** - Create local milestones, missing-proof prompts, and review reminders from confirmed dates.
87. **Filing package preflight v2** - Validate names, captions, signatures, attachments, format, redactions, form freshness, and review gates.
88. **Fee and waiver information workspace** - Organize current official fee/waiver sources and user-supplied facts without eligibility decisions.
89. **Venue and court-location navigator** - Present official location/contact information and unresolved venue facts without deciding venue.
90. **Post-filing receipt reconciliation** - Import a user-provided receipt and reconcile submitted filenames, hashes, and docket expectations.

## Wave 10 - Parenting, finance, and resolution support

91. **Parenting schedule simulation v2** - Compare neutral calendars, travel, holidays, school, and exchanges without recommending custody outcomes.
92. **Order-to-calendar extraction** - Convert confirmed exact order terms into review-required local calendar events.
93. **Child-support worksheet preparation** - Organize current official worksheet inputs and missing facts without calculating beyond admitted rules.
94. **Financial affidavit workbench** - Extract, reconcile, and source-bind income, expenses, assets, debts, and unknowns.
95. **Asset tracing ledger** - Track claimed source, transfers, valuation dates, supporting records, and disputed characterization.
96. **Debt reconciliation workspace** - Match statements, balances, responsibility assertions, payments, and missing periods.
97. **Settlement scenario comparator** - Compare user-entered proposals across schedules, property, support, implementation, and unresolved terms.
98. **Implementation feasibility review** - Flag internal conflicts, undefined terms, missing dates, and operational ambiguity in proposals.
99. **Communication-plan builder** - Draft neutral, review-required exchange and communication protocols from user-selected terms.
100. **Compliance log** - Record observed events against exact order terms while preserving allegation/finding distinctions.

## Wave 11 - Local AI runtime and hardware performance

101. **Hardware benchmark wizard** - Measure CPU, GPU, RAM, storage, and model throughput locally and recommend bounded settings.
102. **Model admission benchmark** - Test latency, memory, context, structured-output reliability, and safety before enabling a local model.
103. **Task-specific model routing** - Route extraction, classification, summarization, chat, and drafting to admitted local models by measured capability.
104. **Warm model pool** - Keep only safe, resource-bounded workers warm and release them under memory or thermal pressure.
105. **Prompt-prefix and retrieval cache** - Cache only non-private or encrypted matter-scoped artifacts with invalidation on source changes.
106. **Speculative retrieval** - Begin likely local retrieval from typed intent without sending text externally or committing an answer.
107. **Adaptive context budgeting** - Allocate tokens by task, source density, hardware, and verifier requirements.
108. **Batch inference scheduler** - Coalesce compatible background extraction jobs while preserving cancellation and matter isolation.
109. **Graceful low-memory mode** - Fall back to lexical retrieval, smaller models, smaller batches, and clear degraded-state messaging.
110. **Runtime crash recovery** - Restart failed workers, preserve job state safely, and explain what completed or was discarded.

## Wave 12 - Search, navigation, and personal productivity

111. **Universal command bar v2** - Search commands, matters, records, sources, drafts, and settings with scoped permissions.
112. **Unified matter search** - Search text, metadata, entities, dates, citations, annotations, and review states from one surface.
113. **Saved smart views** - Save encrypted matter-scoped filters for deadlines, blockers, missing proof, unread records, and review queues.
114. **Recent-work continuity** - Restore the last safe context, scroll position, selected sources, and unsent draft after restart.
115. **Workspace tabs** - Open multiple source, record, draft, and comparison contexts without losing chat state.
116. **Command history and replay** - Re-run safe read operations and require reconfirmation for mutations.
117. **Bulk review queue** - Triage records, claims, citations, privacy findings, and corrections with keyboard-first actions.
118. **Favorites and pinning** - Pin matters, records, sources, drafts, and workspaces with role-aware visibility.
119. **User-defined labels** - Add encrypted labels with collision, export, migration, and audit handling.
120. **Daily matter brief** - Produce a local digest of changed records, due reviews, deadlines, and blockers on explicit open.

## Wave 13 - UI, accessibility, and interaction quality

121. **Design-token consolidation** - Replace accumulated one-off CSS values with tested semantic color, spacing, type, focus, and status tokens.
122. **Componentized production UI** - Break the monolithic workbench into tested modules without changing the frozen asset contract.
123. **Virtualized long lists** - Keep records, sources, timelines, chats, and audit histories responsive at large scale.
124. **Responsive workspace rules v2** - Define and test supported widths, zoom, high contrast, panels, and minimum action visibility.
125. **Screen-reader workflow audit** - Verify landmarks, names, descriptions, live regions, tables, dialogs, and reading order end to end.
126. **Keyboard command system** - Provide discoverable shortcuts, conflict handling, remapping, and focus-safe execution.
127. **Focus and dialog manager** - Guarantee focus trap, return, escape behavior, nested-dialog safety, and error focus.
128. **Density and text-size controls** - Offer comfortable/compact density and independent readable type scaling.
129. **User-facing error center** - Normalize safe error codes, preserved state, retry actions, technical details, and support export.
130. **Visual regression matrix** - Capture critical screens across theme, contrast, zoom, viewport, empty, loading, blocked, and error states.

## Wave 14 - Privacy and security hardening

131. **Per-matter key hierarchy** - Support key rotation, recovery, revocation, and cryptographic deletion without cross-matter impact.
132. **Windows Hello matter unlock** - Add optional local user-presence protection with secure fallback and recovery policy.
133. **Sensitive clipboard controls** - Warn, time-clear app-originated sensitive clipboard content, and never silently read the clipboard.
134. **Secure temporary-file broker** - Centralize private temporary files, permissions, cleanup receipts, crash recovery, and leak tests.
135. **Parser sandboxing** - Isolate risky PDF, Office, OCR, archive, image, and media parsing with resource and network restrictions.
136. **Content-disarm derivatives** - Generate safe review copies of risky documents while preserving immutable originals.
137. **Fine-grained capability tokens** - Bind record/source/artifact access to matter, role, action, expiry, and single-use policy.
138. **Local API abuse resistance v2** - Harden origin, session, CSRF, replay, rate, websocket, and stale-capability defenses.
139. **Privacy-safe diagnostics** - Produce user-approved support bundles with deterministic redaction and inclusion preview.
140. **Continuous adversarial corpus** - Expand prompt/OCR/tool/HTML/archive/path/SQL/model injection tests with zero false-pass gates.

## Wave 15 - Reliability, durability, and observability

141. **Structured local telemetry opt-in** - Record performance and failure classes without prompts, records, names, or paths; default off.
142. **Health and dependency dashboard** - Show API, database, authority, model, OCR, media, storage, backup, and clock health.
143. **Job journal** - Persist every long-running job state, inputs by hash, stage, cancellation, retry, and final receipt.
144. **Idempotency everywhere** - Extend request IDs and duplicate suppression to every mutation and export route.
145. **Database integrity monitor** - Run bounded checks, detect corruption, preserve evidence, and guide recovery without destructive repair.
146. **Power-loss resilience tests** - Interrupt imports, writes, encryption, index swaps, backups, and exports at deterministic fault points.
147. **Storage-pressure controls** - Forecast space, stop safely before exhaustion, and offer reviewed cleanup candidates.
148. **Clock-skew detection** - Detect material clock changes that affect audit ordering, deadlines, certificates, or freshness.
149. **Performance regression gates** - Track launch, matter open, import, search, ask, draft, packet, memory, and package-size budgets.
150. **Failure replay harness** - Reproduce sanitized failure envelopes locally without private content.

## Wave 16 - Backup, migration, installation, and updates

151. **Incremental encrypted backups** - Deduplicate encrypted chunks, verify every snapshot, and preserve restore independence.
152. **Point-in-time matter restore** - Browse safe snapshot metadata and restore into an isolated recovery matter.
153. **Cross-device transfer wizard** - Create encrypted, hash-verified, user-carried transfer bundles without cloud dependency.
154. **Schema migration laboratory** - Test every supported prior version, interruption point, rollback, and forward recovery.
155. **MSIX upgrade qualification automation** - Install prior Store build, create state, upgrade, verify, restart, uninstall, and reinstall in isolation.
156. **WACK automation and report parser** - Locate the kit, run it, preserve reports, classify findings, and block package release when required.
157. **Store asset validator** - Validate screenshots, captions, icons, copy claims, privacy links, and accepted feature scope.
158. **Package-size optimization** - Measure engine contribution and introduce safe feature-on-demand or tiering without runtime downloads in Local-only mode.
159. **Rollback preparation** - Preserve compatible data recovery and document exact operator steps for a failed release.
160. **Signed update metadata** - Verify release metadata and package hashes while leaving Store update control to Windows/Partner Center.

## Wave 17 - Enterprise administration and governance

161. **Admin console acceptance** - Complete production UI for users, roles, tenants, policy, authority status, release evidence, and blocked exports.
162. **Role-policy simulator** - Preview permissions and denials for a fictional user before applying a policy change.
163. **Separation-of-duties rules** - Require independent roles for authority activation, security approval, legal sign-off, and release approval.
164. **Policy-pack lifecycle** - Draft, validate, approve, activate, diff, expire, and roll back signed policy packs.
165. **Legal-hold controls** - Preserve selected matter artifacts and prevent retention deletion with explicit authority and audit.
166. **Retention-policy engine** - Preview and apply organization-approved retention with exceptions, holds, receipts, and recovery windows.
167. **Audit verification console** - Verify hash chains, signatures, gaps, clock anomalies, and export scoped audit reports.
168. **Enterprise configuration export** - Produce a signed, privacy-safe configuration and compliance manifest.
169. **Offline license/entitlement model** - If commercialized, support signed offline entitlements without telemetry or matter access.
170. **Organization readiness dashboard** - Separate engineering, legal, security, privacy, operations, accessibility, pilot, and Store decisions.

## Wave 18 - Collaboration and interoperability

171. **Reviewer bundle round trip** - Export, review, comment, sign, reimport, reconcile, and preserve immutable lineage.
172. **Structured comment threads** - Attach comments to exact record spans, source spans, claims, draft text, and artifacts.
173. **Review assignment queue** - Assign local tasks by role, due date, scope, and required evidence without external messaging.
174. **Conflict-aware merge** - Merge independently reviewed matter bundles with explicit conflict resolution and no silent overwrites.
175. **Standards-based calendar export v2** - Improve ICS timezone, recurrence, alarms, UID stability, and update/cancel semantics.
176. **Email export package** - Create a user-reviewed EML/ZIP handoff without sending and with privacy warnings and manifest.
177. **PDF/A review export** - Produce archival PDF derivatives where supported and disclose conversion limitations.
178. **CSV/JSON evidence export** - Export scoped structured data with schema, hashes, source locators, and review state.
179. **Print workflow** - Add accessible print preview, page headers, confidentiality markings, and source/review footers.
180. **External-tool boundary receipts** - Record what was exported, why, by whom, hash, destination class, and acknowledged privacy risk.

## Wave 19 - Evaluation, legal quality, and pilot readiness

181. **Attorney gold-data workbench** - Create blinded review tasks, adjudication, provenance, licensing, and immutable reviewer metadata.
182. **Retrieval benchmark expansion** - Build issue-balanced real-authority queries with Recall, MRR, nDCG, pinpoint, and freshness metrics.
183. **Claim-verifier benchmark** - Measure supported, partial, unsupported, contradicted, stale, jurisdiction mismatch, and unknown states.
184. **Quote-verifier benchmark** - Measure exact, normalized, fuzzy-review, mismatch, and not-found decisions across parser variants.
185. **Procedural safety evaluation** - Test deadlines, service, posture, forms, venue, and filing blockers against reviewed scenarios.
186. **Bias and accessibility evaluation** - Review language, disability, literacy, cultural, and self-represented-user failure modes.
187. **Longitudinal matter evaluation** - Test multi-session changes, corrected facts, amended authority, restart, migration, and stale work.
188. **Controlled attorney sandbox** - Run approved fictional matters with licensed Maine reviewers and capture actual usability/legal findings.
189. **Controlled pilot operations** - Define enrollment, consent, support, incident response, stop criteria, metrics, and post-pilot review.
190. **Release metric eligibility gate** - Accept only correctly labeled, licensed, reproducible, non-synthetic evidence for enterprise decisions.

## Wave 20 - Platform scale and Enterprise GA closure

191. **Jurisdiction pack interface** - Separate state-specific authority, citation, forms, procedure, terminology, and safety rules behind signed packs.
192. **Second-state reference implementation** - Prove the interface with a non-production fictional jurisdiction pack before real expansion.
193. **Extension SDK sandbox** - Run signed local extensions with declared permissions, versioned contracts, quotas, and revocation.
194. **Extension review and certification kit** - Static scan, dependency audit, adversarial tests, UX review, and signed admission record.
195. **Public API stability program** - Version schemas, compatibility policy, deprecation warnings, migration tools, and contract tests.
196. **Software bill of materials** - Generate exact-source and exact-MSIX SBOMs with licenses, hashes, origins, and vulnerability status.
197. **Reproducible release pipeline** - Pin tools and inputs, compare payload manifests, verify provenance, and sign release evidence.
198. **Incident response program** - Establish severity, containment, evidence preservation, user notice, recovery, and postmortem templates.
199. **Required organizational sign-offs** - Capture actual legal, security, privacy, accessibility, product, operations, and release approvals.
200. **Enterprise GA decision packet** - Assemble live authority, attorney eval, security, pilot, Store, rollback, support, and sign-off evidence into a two-axis release decision.

## Recommended execution gates

- **Gate A - Best immediate product return:** slices 1-20.
- **Gate B - Trustworthy legal research:** slices 21-40.
- **Gate C - Complete core work product:** slices 41-100.
- **Gate D - Fast and dependable local platform:** slices 101-160.
- **Gate E - Enterprise operations and external validation:** slices 161-200.

Do not version-bump merely because a wave is coded. A wave is release-eligible only after its accepted-feature manifest, production UI evidence, frozen-runtime evidence, package-boundary audit, and honest blocker report are complete.
