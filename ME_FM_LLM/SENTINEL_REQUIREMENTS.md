# SENTINEL_REQUIREMENTS — Maine Family Law LLM

> Build requirements for a best-in-class Maine family-law legal LLM. This file is a product and engineering backlog, not legal advice.

## Operating rules for SENTINEL

Status: planned

Owned files:
- src/**
- tests/**
- docs/**
- scripts/**
- pyproject.toml
- README.md
- Dockerfile
- docker-compose*.yml
- .dockerignore

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Build a court-source-first, authority-verified, review-required Maine family-law legal LLM with explicit privacy/data boundaries, citation and quote verification, claim support checks, filing-readiness gates, and measurable release evidence.

## Backlog overview

- Total epics: 29
- Total requirements: 700
- Default status: planned
- Data/corpora boundary: external data root only; never package legal corpora, private matter data, vector stores, OCR caches, secrets, model weights, or runtime databases inside the source repo.

## FEAT-001: Authority-first legal data

Status: planned

Owned files:
- src/maine_family_law_llm/sources/**
- src/maine_family_law_llm/ingest/**
- src/maine_family_law_llm/parsing/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Authority-first legal data` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-001: Ingest official primary law only from trusted sources.
- [ ] REQ-002: Prefer official Maine authority over mirrors, summaries, and model memory.
- [ ] REQ-003: Track every source with `source_id`.
- [ ] REQ-004: Track source URL.
- [ ] REQ-005: Track retrieval timestamp.
- [ ] REQ-006: Track hash/checksum.
- [ ] REQ-007: Track jurisdiction.
- [ ] REQ-008: Track source class.
- [ ] REQ-009: Track parser status.
- [ ] REQ-010: Track freshness status.
- [ ] REQ-011: Track effective date.
- [ ] REQ-012: Track superseded/stale status.
- [ ] REQ-013: Track copyright/licensing status.
- [ ] REQ-014: Track whether the source is official, secondary, user-provided, or unknown.
- [ ] REQ-015: Store all legal corpora outside the source repo.
- [ ] REQ-016: Never package official corpora inside the repo ZIP.
- [ ] REQ-017: Never bake legal corpora into Docker images.
- [ ] REQ-018: Maintain reproducible source manifests.
- [ ] REQ-019: Maintain source update history.
- [ ] REQ-020: Maintain source diff reports.
- [ ] REQ-021: Maintain source failure reports.
- [ ] REQ-022: Enforce minimum source-class coverage.
- [ ] REQ-023: Block “current law” claims when freshness is unknown.
- [ ] REQ-024: Block legal readiness when required source classes are incomplete.
- [ ] REQ-025: Keep official authority snapshots immutable after build.

## FEAT-002: Maine-specific legal corpus

Status: planned

Owned files:
- src/maine_family_law_llm/sources/**
- src/maine_family_law_llm/ingest/**
- src/maine_family_law_llm/parsing/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Maine-specific legal corpus` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-026: Maine Revised Statutes.
- [ ] REQ-027: Title 19-A Domestic Relations.
- [ ] REQ-028: Title 18-C Probate Code where relevant.
- [ ] REQ-029: Title 22 child welfare / DHHS-related family matters.
- [ ] REQ-030: Title 4 court/family division authority.
- [ ] REQ-031: Title 5 protection from harassment / administrative overlap.
- [ ] REQ-032: Title 14 civil procedure overlap.
- [ ] REQ-033: Title 15 criminal procedure overlap where relevant.
- [ ] REQ-034: Title 17-A domestic violence / criminal-family overlap.
- [ ] REQ-035: Maine Rules of Civil Procedure.
- [ ] REQ-036: Family Division rules.
- [ ] REQ-037: Rule 52 findings requirements.
- [ ] REQ-038: Rule 120 standing order.
- [ ] REQ-039: Maine Rules of Evidence.
- [ ] REQ-040: Maine Rules of Appellate Procedure.
- [ ] REQ-041: Maine Rules of Probate Procedure.
- [ ] REQ-042: Maine Rules of Electronic Court Systems.
- [ ] REQ-043: Judicial Branch administrative orders.
- [ ] REQ-044: Judicial Branch standing orders.
- [ ] REQ-045: Official Maine family court forms.
- [ ] REQ-046: Official form packets.
- [ ] REQ-047: Form instructions.
- [ ] REQ-048: Form version history.
- [ ] REQ-049: Maine Law Court opinions.
- [ ] REQ-050: Maine SJC published opinions.
- [ ] REQ-051: Family-law-relevant appellate opinions.
- [ ] REQ-052: Protection from abuse cases.
- [ ] REQ-053: Parental rights and responsibilities cases.
- [ ] REQ-054: Child support cases.
- [ ] REQ-055: Guardianship cases.
- [ ] REQ-056: Adoption cases.
- [ ] REQ-057: PFA/family overlap cases.
- [ ] REQ-058: Rule 52 findings cases.
- [ ] REQ-059: Best-interest factor cases.
- [ ] REQ-060: Appellate preservation cases.
- [ ] REQ-061: Transcript/record issue cases.
- [ ] REQ-062: Federal family-law-adjacent statutes.
- [ ] REQ-063: ICWA.
- [ ] REQ-064: UIFSA-related federal material.
- [ ] REQ-065: Federal child support enforcement law.
- [ ] REQ-066: Bankruptcy/family-law interaction.
- [ ] REQ-067: Federal tax/divorce support interaction.
- [ ] REQ-068: Constitutional family-law authority.
- [ ] REQ-069: Secondary sources only when licensed or clearly allowed.
- [ ] REQ-070: No copyrighted treatise ingestion without permission.

## FEAT-003: Data boundaries

Status: planned

Owned files:
- src/maine_family_law_llm/sources/**
- src/maine_family_law_llm/ingest/**
- src/maine_family_law_llm/parsing/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Data boundaries` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-071: No private matter files in repo.
- [ ] REQ-072: No client files in repo.
- [ ] REQ-073: No uploaded pleadings in repo.
- [ ] REQ-074: No PDFs in repo ZIP unless they are documentation explicitly allowed.
- [ ] REQ-075: No official corpora in repo ZIP.
- [ ] REQ-076: No model weights in repo.
- [ ] REQ-077: No vector stores in repo.
- [ ] REQ-078: No OCR caches in repo.
- [ ] REQ-079: No runtime databases in repo.
- [ ] REQ-080: No secrets in repo.
- [ ] REQ-081: No `.env` secrets in repo.
- [ ] REQ-082: No API keys in repo.
- [ ] REQ-083: No attorney work product in repo.
- [ ] REQ-084: No generated legal drafts in repo.
- [ ] REQ-085: No private facts used for shared training by default.
- [ ] REQ-086: Matter data stored only in external data root.
- [ ] REQ-087: External data root configurable.
- [ ] REQ-088: Default external root: `MAINE_FAMILY_LAW_DATA_ROOT`.
- [ ] REQ-089: Docker must mount external data at `/data`.
- [ ] REQ-090: Docker must not copy data root into image.
- [ ] REQ-091: Runtime state must be outside source tree.
- [ ] REQ-092: Local test artifacts must be cleaned automatically.
- [ ] REQ-093: Repo ZIP must be releasable without private data.
- [ ] REQ-094: One running repo TXT log only: `PASS_CHANGES.txt`.
- [ ] REQ-095: Separate operator reports should be JSON/MD unless intentionally outside repo.

## FEAT-004: Parsing and normalization

Status: planned

Owned files:
- src/maine_family_law_llm/sources/**
- src/maine_family_law_llm/ingest/**
- src/maine_family_law_llm/parsing/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Parsing and normalization` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-096: Robust PDF extraction.
- [ ] REQ-097: Robust HTML extraction.
- [ ] REQ-098: Robust Word/doc extraction where allowed.
- [ ] REQ-099: OCR for scanned official sources.
- [ ] REQ-100: OCR confidence tracking.
- [ ] REQ-101: Parser failure tracking.
- [ ] REQ-102: Text normalization.
- [ ] REQ-103: Section normalization.
- [ ] REQ-104: Citation normalization.
- [ ] REQ-105: Maine statute citation normalization.
- [ ] REQ-106: Maine rule citation normalization.
- [ ] REQ-107: Maine case citation normalization.
- [ ] REQ-108: Form ID normalization.
- [ ] REQ-109: Opinion metadata extraction.
- [ ] REQ-110: Statute title/chapter/section parsing.
- [ ] REQ-111: Rule/subdivision/comment/history parsing.
- [ ] REQ-112: Form field parsing.
- [ ] REQ-113: Form required-field extraction.
- [ ] REQ-114: Form filing-context extraction.
- [ ] REQ-115: Law Court caption extraction.
- [ ] REQ-116: Docket extraction.
- [ ] REQ-117: Decision date extraction.
- [ ] REQ-118: Holding extraction.
- [ ] REQ-119: Disposition extraction.
- [ ] REQ-120: Standard-of-review extraction.
- [ ] REQ-121: Pinpoint citation extraction.
- [ ] REQ-122: Internal citation extraction.
- [ ] REQ-123: Source-span offsets.
- [ ] REQ-124: Chunk parent/child linking.
- [ ] REQ-125: Parser regression tests.

## FEAT-005: Retrieval

Status: planned

Owned files:
- src/maine_family_law_llm/retrieval/**
- src/maine_family_law_llm/verification/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check
- python -m pytest -q tests -k 'retrieval or citation or quote or verifier'

Goal:
Implement, test, and document the `Retrieval` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-126: Exact citation lookup.
- [ ] REQ-127: Statute section lookup.
- [ ] REQ-128: Rule lookup.
- [ ] REQ-129: Case-name lookup.
- [ ] REQ-130: Form-ID lookup.
- [ ] REQ-131: BM25 lexical search.
- [ ] REQ-132: Vector search.
- [ ] REQ-133: Hybrid search.
- [ ] REQ-134: Reciprocal rank fusion.
- [ ] REQ-135: Authority-aware ranking.
- [ ] REQ-136: Freshness-aware ranking.
- [ ] REQ-137: Jurisdiction-aware ranking.
- [ ] REQ-138: Source-class-aware ranking.
- [ ] REQ-139: Issue-aware ranking.
- [ ] REQ-140: Posture-aware ranking.
- [ ] REQ-141: Query expansion for Maine family-law terms.
- [ ] REQ-142: Parent-child chunk retrieval.
- [ ] REQ-143: Source-card generation.
- [ ] REQ-144: Retrieval failure classification.
- [ ] REQ-145: Retrieval failure regression tests.
- [ ] REQ-146: Recall@5 measurement.
- [ ] REQ-147: Recall@10 measurement.
- [ ] REQ-148: Recall@20 measurement.
- [ ] REQ-149: MRR measurement.
- [ ] REQ-150: nDCG measurement.
- [ ] REQ-151: Citation retrieval smoke tests.
- [ ] REQ-152: Issue retrieval smoke tests.
- [ ] REQ-153: Freshness boosting tests.
- [ ] REQ-154: Official-source priority tests.
- [ ] REQ-155: Missing-source detection.

## FEAT-006: Citation verification

Status: planned

Owned files:
- src/maine_family_law_llm/retrieval/**
- src/maine_family_law_llm/verification/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check
- python -m pytest -q tests -k 'retrieval or citation or quote or verifier'

Goal:
Implement, test, and document the `Citation verification` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-156: Citation parser.
- [ ] REQ-157: Citation resolver.
- [ ] REQ-158: Maine statute resolver.
- [ ] REQ-159: Maine rule resolver.
- [ ] REQ-160: Maine case resolver.
- [ ] REQ-161: Federal citation resolver.
- [ ] REQ-162: Form resolver.
- [ ] REQ-163: Fake citation detection.
- [ ] REQ-164: Not-found status.
- [ ] REQ-165: Ambiguous citation status.
- [ ] REQ-166: Stale citation status.
- [ ] REQ-167: Jurisdiction mismatch status.
- [ ] REQ-168: Pinpoint support verification.
- [ ] REQ-169: Citation-to-source-card mapping.
- [ ] REQ-170: Citation-to-text-span mapping.
- [ ] REQ-171: Citation support score.
- [ ] REQ-172: Citation exact-match tests.
- [ ] REQ-173: Citation fuzzy-match tests.
- [ ] REQ-174: Citation hallucination tests.
- [ ] REQ-175: Citation batch API.
- [ ] REQ-176: Citation verification report.
- [ ] REQ-177: Citation verification UI.
- [ ] REQ-178: Citation verifier must block filing-ready export.

## FEAT-007: Quote verification

Status: planned

Owned files:
- src/maine_family_law_llm/retrieval/**
- src/maine_family_law_llm/verification/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check
- python -m pytest -q tests -k 'retrieval or citation or quote or verifier'

Goal:
Implement, test, and document the `Quote verification` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-179: Exact quote matching.
- [ ] REQ-180: Fuzzy quote matching.
- [ ] REQ-181: Offset recording.
- [ ] REQ-182: Source span recording.
- [ ] REQ-183: Quote source ID.
- [ ] REQ-184: Quote mismatch status.
- [ ] REQ-185: Quote not-found status.
- [ ] REQ-186: Quote altered status.
- [ ] REQ-187: Quote unsupported status.
- [ ] REQ-188: Quote verification table.
- [ ] REQ-189: Quote report.
- [ ] REQ-190: Quote verifier API.
- [ ] REQ-191: Quote verifier UI.
- [ ] REQ-192: Quote-span gold eval.
- [ ] REQ-193: Quote-span accuracy metric.
- [ ] REQ-194: Quote mismatch regression tests.
- [ ] REQ-195: Unverified quotes block filing-ready export.

## FEAT-008: Claim-support verification

Status: planned

Owned files:
- src/maine_family_law_llm/retrieval/**
- src/maine_family_law_llm/verification/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Claim-support verification` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-196: Extract legal claims from answers.
- [ ] REQ-197: Extract factual claims from drafts.
- [ ] REQ-198: Map claims to cited authority.
- [ ] REQ-199: Map facts to evidence.
- [ ] REQ-200: Classify claims as supported.
- [ ] REQ-201: Classify claims as partially supported.
- [ ] REQ-202: Classify claims as unsupported.
- [ ] REQ-203: Classify claims as contradicted.
- [ ] REQ-204: Classify claims as stale.
- [ ] REQ-205: Classify claims as jurisdiction mismatch.
- [ ] REQ-206: Detect unsupported legal assertions.
- [ ] REQ-207: Detect unsupported factual assertions.
- [ ] REQ-208: Detect overbroad claims.
- [ ] REQ-209: Detect missing qualifiers.
- [ ] REQ-210: Detect outdated-law claims.
- [ ] REQ-211: Detect wrong-court claims.
- [ ] REQ-212: Claim-to-source drilldown.
- [ ] REQ-213: Claim-to-evidence drilldown.
- [ ] REQ-214: Unsupported-claim report.
- [ ] REQ-215: Unsupported claims block final/final-like export.

## FEAT-009: Maine family-law intelligence

Status: planned

Owned files:
- src/maine_family_law_llm/intelligence/**
- src/maine_family_law_llm/evidence/**
- src/maine_family_law_llm/drafting/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Maine family-law intelligence` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-216: Issue classifier.
- [ ] REQ-217: Procedural posture classifier.
- [ ] REQ-218: Authority classifier.
- [ ] REQ-219: Red-flag classifier.
- [ ] REQ-220: Divorce issue detection.
- [ ] REQ-221: Parental rights detection.
- [ ] REQ-222: Primary residence detection.
- [ ] REQ-223: Contact schedule detection.
- [ ] REQ-224: Child support detection.
- [ ] REQ-225: Parentage detection.
- [ ] REQ-226: Post-judgment motion detection.
- [ ] REQ-227: Motion to modify detection.
- [ ] REQ-228: Motion to enforce detection.
- [ ] REQ-229: Contempt detection.
- [ ] REQ-230: Protection from abuse detection.
- [ ] REQ-231: Protection from harassment detection.
- [ ] REQ-232: Grandparent visitation detection.
- [ ] REQ-233: Guardianship detection.
- [ ] REQ-234: GAL issue detection.
- [ ] REQ-235: UCCJEA issue detection.
- [ ] REQ-236: Rule 52 findings detection.
- [ ] REQ-237: Best-interest factor gap detection.
- [ ] REQ-238: Appeal preservation detection.
- [ ] REQ-239: Transcript/record issue detection.
- [ ] REQ-240: eCourts access issue detection.
- [ ] REQ-241: Therapist/GAL improper delegation detection.
- [ ] REQ-242: PFA/family overlap detection.
- [ ] REQ-243: Contact restriction support detection.
- [ ] REQ-244: Missing findings detection.
- [ ] REQ-245: Missing form detection.
- [ ] REQ-246: Wrong procedure detection.
- [ ] REQ-247: Wrong court detection.
- [ ] REQ-248: Deadline risk detection.
- [ ] REQ-249: Service defect detection.
- [ ] REQ-250: Jurisdiction defect detection.

## FEAT-010: Law Court intelligence

Status: planned

Owned files:
- src/maine_family_law_llm/intelligence/**
- src/maine_family_law_llm/evidence/**
- src/maine_family_law_llm/drafting/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Law Court intelligence` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-251: Structured case briefs.
- [ ] REQ-252: Holding extraction.
- [ ] REQ-253: Procedural history extraction.
- [ ] REQ-254: Disposition extraction.
- [ ] REQ-255: Standard of review extraction.
- [ ] REQ-256: Preservation issue extraction.
- [ ] REQ-257: Rule 52 issue extraction.
- [ ] REQ-258: Best-interest factor analysis extraction.
- [ ] REQ-259: Transcript/record issue extraction.
- [ ] REQ-260: Abuse-of-discretion analysis extraction.
- [ ] REQ-261: Clear-error analysis extraction.
- [ ] REQ-262: Legal-error analysis extraction.
- [ ] REQ-263: Remand reason extraction.
- [ ] REQ-264: Affirmed/vacated/reversed/remanded classification.
- [ ] REQ-265: Negative-treatment placeholder.
- [ ] REQ-266: Case-to-statute graph edges.
- [ ] REQ-267: Case-to-rule graph edges.
- [ ] REQ-268: Case-to-case graph edges.
- [ ] REQ-269: Law Court holding gold dataset.
- [ ] REQ-270: Appellate red-flag report.

## FEAT-011: Forms intelligence

Status: planned

Owned files:
- src/maine_family_law_llm/intelligence/**
- src/maine_family_law_llm/evidence/**
- src/maine_family_law_llm/drafting/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Forms intelligence` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-271: Official form catalog.
- [ ] REQ-272: Form version tracker.
- [ ] REQ-273: Form freshness checker.
- [ ] REQ-274: Required-field extraction.
- [ ] REQ-275: Filing-context classifier.
- [ ] REQ-276: Form-to-statute dependency graph.
- [ ] REQ-277: Form-to-rule dependency graph.
- [ ] REQ-278: Stale form warning.
- [ ] REQ-279: Missing form warning.
- [ ] REQ-280: Missing required-field warning.
- [ ] REQ-281: Form packet completeness checker.
- [ ] REQ-282: Form lookup by issue.
- [ ] REQ-283: Form lookup by case posture.
- [ ] REQ-284: Form freshness gold dataset.
- [ ] REQ-285: Form freshness tests.
- [ ] REQ-286: Form-related filing blockers.

## FEAT-012: Matter workflow

Status: planned

Owned files:
- src/maine_family_law_llm/security/**
- src/maine_family_law_llm/matters/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Matter workflow` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-287: Matter creation.
- [ ] REQ-288: Matter metadata.
- [ ] REQ-289: Matter-level permissions.
- [ ] REQ-290: Document upload.
- [ ] REQ-291: Local document ingestion.
- [ ] REQ-292: OCR/text extraction.
- [ ] REQ-293: Document classification.
- [ ] REQ-294: PII detection.
- [ ] REQ-295: Privilege/confidentiality flags.
- [ ] REQ-296: Juvenile/sealed record warnings.
- [ ] REQ-297: Retention policy.
- [ ] REQ-298: Matter audit history.
- [ ] REQ-299: Tenant isolation.
- [ ] REQ-300: Matter isolation.
- [ ] REQ-301: Local encryption.
- [ ] REQ-302: Secure deletion.
- [ ] REQ-303: No matter data in repo.
- [ ] REQ-304: No matter data in shared training.
- [ ] REQ-305: Matter export controls.

## FEAT-013: Evidence product

Status: planned

Owned files:
- src/maine_family_law_llm/intelligence/**
- src/maine_family_law_llm/evidence/**
- src/maine_family_law_llm/drafting/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Evidence product` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-306: Fact extraction.
- [ ] REQ-307: Event extraction.
- [ ] REQ-308: Timeline builder.
- [ ] REQ-309: Exhibit index.
- [ ] REQ-310: Evidence map.
- [ ] REQ-311: Fact-to-evidence mapper.
- [ ] REQ-312: Missing-record checklist.
- [ ] REQ-313: Missing-fact checklist.
- [ ] REQ-314: Transcript checklist.
- [ ] REQ-315: Appeal-record checklist.
- [ ] REQ-316: Source-document span links.
- [ ] REQ-317: Confidence scoring.
- [ ] REQ-318: Evidence packet builder.
- [ ] REQ-319: Evidence packet export.
- [ ] REQ-320: Evidence map UI.
- [ ] REQ-321: Timeline UI.
- [ ] REQ-322: Fact-to-evidence gold dataset.

## FEAT-014: Drafting

Status: planned

Owned files:
- src/maine_family_law_llm/intelligence/**
- src/maine_family_law_llm/evidence/**
- src/maine_family_law_llm/drafting/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Drafting` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-323: Review-required drafting only by default.
- [ ] REQ-324: Motion templates.
- [ ] REQ-325: Affidavit templates.
- [ ] REQ-326: Objection templates.
- [ ] REQ-327: Proposed findings templates.
- [ ] REQ-328: Proposed order templates.
- [ ] REQ-329: Client letter templates.
- [ ] REQ-330: Plain-language explainer templates.
- [ ] REQ-331: Authority matrix insertion.
- [ ] REQ-332: Citation sidebar.
- [ ] REQ-333: Source-card sidebar.
- [ ] REQ-334: Evidence sidebar.
- [ ] REQ-335: Missing-fact sidebar.
- [ ] REQ-336: Unsupported-claim sidebar.
- [ ] REQ-337: Draft reviewer.
- [ ] REQ-338: Challenger/reviewer component.
- [ ] REQ-339: Draft risk report.
- [ ] REQ-340: Draft citation report.
- [ ] REQ-341: Draft quote report.
- [ ] REQ-342: Draft evidence map.
- [ ] REQ-343: Human review checklist.
- [ ] REQ-344: No filing-ready label by default.
- [ ] REQ-345: No final export unless all gates pass.

## FEAT-015: Filing-ready gate

Status: planned

Owned files:
- src/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Filing-ready gate` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-346: Authority verified.
- [ ] REQ-347: Citations resolved.
- [ ] REQ-348: Quotes found.
- [ ] REQ-349: Legal claims supported.
- [ ] REQ-350: Facts mapped to evidence.
- [ ] REQ-351: Procedure checked.
- [ ] REQ-352: Posture checked.
- [ ] REQ-353: Jurisdiction checked.
- [ ] REQ-354: Forms current.
- [ ] REQ-355: Required fields complete.
- [ ] REQ-356: Rule 52 findings checked.
- [ ] REQ-357: Best-interest factors checked.
- [ ] REQ-358: Deadlines checked.
- [ ] REQ-359: Service checked.
- [ ] REQ-360: Confidentiality checked.
- [ ] REQ-361: Human review completed.
- [ ] REQ-362: Attorney signoff captured.
- [ ] REQ-363: Immutable gate report.
- [ ] REQ-364: Zero silent overrides.
- [ ] REQ-365: Attorney override logged if allowed.
- [ ] REQ-366: Filing-ready false-pass rate target: zero.
- [ ] REQ-367: Blocked export explains every blocker.

## FEAT-016: API

Status: planned

Owned files:
- src/maine_family_law_llm/api/**
- tests/**
- docs/**
- openapi/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check
- python -m pytest -q tests -k 'api or contract or openapi'

Goal:
Implement, test, and document the `API` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-368: `GET /api/health`.
- [ ] REQ-369: `GET /api/version`.
- [ ] REQ-370: `POST /api/intake/matter`.
- [ ] REQ-371: `POST /api/intake/document`.
- [ ] REQ-372: `POST /api/query`.
- [ ] REQ-373: `POST /api/research`.
- [ ] REQ-374: `POST /api/draft`.
- [ ] REQ-375: `POST /api/review`.
- [ ] REQ-376: `POST /api/citations/verify`.
- [ ] REQ-377: `POST /api/quotes/verify`.
- [ ] REQ-378: `POST /api/evidence/map`.
- [ ] REQ-379: `POST /api/timeline/build`.
- [ ] REQ-380: `POST /api/filing-ready/check`.
- [ ] REQ-381: `GET /api/sources/{source_id}`.
- [ ] REQ-382: `GET /api/matters/{matter_id}/evidence-packet`.
- [ ] REQ-383: OpenAPI schema.
- [ ] REQ-384: Contract tests.
- [ ] REQ-385: Auth/RBAC.
- [ ] REQ-386: Audit events on every endpoint.
- [ ] REQ-387: Structured errors.
- [ ] REQ-388: Request validation.
- [ ] REQ-389: Response validation.
- [ ] REQ-390: Rate limits.
- [ ] REQ-391: Local-only default bind.
- [ ] REQ-392: Healthcheck endpoint.
- [ ] REQ-393: Version endpoint.

## FEAT-017: UI

Status: planned

Owned files:
- src/maine_family_law_llm/ui/**
- docs/**
- tests/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check
- python -m pytest -q tests -k 'ui or accessibility or export'

Goal:
Implement, test, and document the `UI` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-394: Matter dashboard.
- [ ] REQ-395: Ask Maine Family Law view.
- [ ] REQ-396: Upload documents view.
- [ ] REQ-397: Source library.
- [ ] REQ-398: Authority matrix.
- [ ] REQ-399: Timeline view.
- [ ] REQ-400: Evidence map view.
- [ ] REQ-401: Draft workspace.
- [ ] REQ-402: Citation report.
- [ ] REQ-403: Quote report.
- [ ] REQ-404: Filing-readiness gate.
- [ ] REQ-405: Human review queue.
- [ ] REQ-406: Settings/data policy.
- [ ] REQ-407: Admin/eval dashboard.
- [ ] REQ-408: Source cards for every legal claim.
- [ ] REQ-409: Claim-to-source drilldown.
- [ ] REQ-410: Citation-to-source drilldown.
- [ ] REQ-411: Quote-to-source drilldown.
- [ ] REQ-412: Review status badges.
- [ ] REQ-413: Export blocker display.
- [ ] REQ-414: Human reviewer workflow.
- [ ] REQ-415: Attorney signoff workflow.

## FEAT-018: Model governance

Status: planned

Owned files:
- src/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Model governance` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-416: Model registry.
- [ ] REQ-417: Model role definitions.
- [ ] REQ-418: Model admission policy.
- [ ] REQ-419: Allowed task list per model.
- [ ] REQ-420: Prohibited task list per model.
- [ ] REQ-421: Benchmark scores per model.
- [ ] REQ-422: Privacy status per model.
- [ ] REQ-423: Latency/cost tracking.
- [ ] REQ-424: Regression history.
- [ ] REQ-425: Fallback behavior.
- [ ] REQ-426: No generator self-certifies legal correctness.
- [ ] REQ-427: Model replacement audit trail.
- [ ] REQ-428: Hosted model lanes optional only.
- [ ] REQ-429: Hosted model privacy review.
- [ ] REQ-430: Local/open-weight preference for sensitive workflows.
- [ ] REQ-431: Prompt versioning.
- [ ] REQ-432: Tool versioning.
- [ ] REQ-433: Retrieval context versioning.

## FEAT-019: Security

Status: planned

Owned files:
- src/maine_family_law_llm/security/**
- src/maine_family_law_llm/matters/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check
- python -m pytest -q tests -k 'security or injection or secrets or rbac'

Goal:
Implement, test, and document the `Security` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-434: Authentication.
- [ ] REQ-435: RBAC.
- [ ] REQ-436: Tenant isolation.
- [ ] REQ-437: Matter-level permissions.
- [ ] REQ-438: Encryption at rest.
- [ ] REQ-439: Encryption in transit.
- [ ] REQ-440: Key rotation.
- [ ] REQ-441: Secrets management.
- [ ] REQ-442: No secrets in repo.
- [ ] REQ-443: Immutable audit logs.
- [ ] REQ-444: Export logs.
- [ ] REQ-445: Prompt logs.
- [ ] REQ-446: Source logs.
- [ ] REQ-447: Model logs.
- [ ] REQ-448: Verifier logs.
- [ ] REQ-449: Admin audit.
- [ ] REQ-450: Backup.
- [ ] REQ-451: Restore.
- [ ] REQ-452: Disaster recovery.
- [ ] REQ-453: Retention controls.
- [ ] REQ-454: Deletion controls.
- [ ] REQ-455: PII scanning.
- [ ] REQ-456: Confidentiality controls.
- [ ] REQ-457: Sealed-record controls.
- [ ] REQ-458: Juvenile-record warnings.
- [ ] REQ-459: Legal hold support.

## FEAT-020: Prompt/document injection defense

Status: planned

Owned files:
- src/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Prompt/document injection defense` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-460: Prompt-injection tests.
- [ ] REQ-461: Document-injection tests.
- [ ] REQ-462: Tool sandbox policy.
- [ ] REQ-463: Retrieval-context isolation.
- [ ] REQ-464: Treat retrieved documents as untrusted content.
- [ ] REQ-465: System prompt leakage tests.
- [ ] REQ-466: Output filtering.
- [ ] REQ-467: Tool-call authorization.
- [ ] REQ-468: File access allowlists.
- [ ] REQ-469: Network access controls.
- [ ] REQ-470: Cost controls.
- [ ] REQ-471: Denial-of-service controls.
- [ ] REQ-472: Malicious PDF tests.
- [ ] REQ-473: Malicious DOCX tests.
- [ ] REQ-474: Malicious OCR tests.
- [ ] REQ-475: Red-team bypass tests.

## FEAT-021: Evaluation

Status: planned

Owned files:
- evals/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Evaluation` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-476: Attorney-reviewed gold evals.
- [ ] REQ-477: No seed/synthetic rows counted as GA gold.
- [ ] REQ-478: Reviewer identity tracking.
- [ ] REQ-479: Review status tracking.
- [ ] REQ-480: Confidence tracking.
- [ ] REQ-481: Double review where required.
- [ ] REQ-482: Conflict resolution workflow.
- [ ] REQ-483: Retrieval gold dataset.
- [ ] REQ-484: Citation validity gold dataset.
- [ ] REQ-485: Quote span gold dataset.
- [ ] REQ-486: Hallucination negative cases.
- [ ] REQ-487: Forms freshness gold dataset.
- [ ] REQ-488: Drafting review gold dataset.
- [ ] REQ-489: Issue classification gold dataset.
- [ ] REQ-490: Posture classification gold dataset.
- [ ] REQ-491: Authority ranking gold dataset.
- [ ] REQ-492: Fact-to-evidence gold dataset.
- [ ] REQ-493: Law Court holding gold dataset.
- [ ] REQ-494: Rule 52 gap gold dataset.
- [ ] REQ-495: Eval runner.
- [ ] REQ-496: Release metrics JSON.
- [ ] REQ-497: Regression dashboard.
- [ ] REQ-498: Failure cluster report.
- [ ] REQ-499: Release comparison report.
- [ ] REQ-500: Attorney-review evidence packet.

## FEAT-022: GA metrics

Status: planned

Owned files:
- evals/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `GA metrics` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-501: Retrieval Recall@20 ≥ 95%.
- [ ] REQ-502: Citation existence ≥ 99%.
- [ ] REQ-503: Citation support ≥ 95%.
- [ ] REQ-504: Quote-span verification ≥ 97%.
- [ ] REQ-505: Hallucination rate ≤ 3%.
- [ ] REQ-506: Filing-ready false-pass rate = 0.
- [ ] REQ-507: Form freshness detection ≥ 99%.
- [ ] REQ-508: Private-data packaging = 100% pass.
- [ ] REQ-509: Source freshness report present.
- [ ] REQ-510: Attorney review sample present.
- [ ] REQ-511: Minimum sample sizes met.
- [ ] REQ-512: Metrics based on real gold files.
- [ ] REQ-513: Metrics include pass/fail.
- [ ] REQ-514: Metrics include sample size.
- [ ] REQ-515: Metrics include reviewer status.
- [ ] REQ-516: Metrics include basis/source.
- [ ] REQ-517: Missing metrics block release.
- [ ] REQ-518: Synthetic metrics block GA.
- [ ] REQ-519: Undersized metrics block GA.
- [ ] REQ-520: Non-attorney-reviewed metrics block GA.

## FEAT-023: Error checking and self-correction

Status: planned

Owned files:
- src/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Error checking and self-correction` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-521: Preflight checks before every script.
- [ ] REQ-522: Validate repo root.
- [ ] REQ-523: Validate data root.
- [ ] REQ-524: Validate Python version.
- [ ] REQ-525: Validate venv location.
- [ ] REQ-526: Warn if venv is inside repo.
- [ ] REQ-527: Auto-clean `.venv` contamination if allowed.
- [ ] REQ-528: Clean `.egg-info`.
- [ ] REQ-529: Clean `__pycache__`.
- [ ] REQ-530: Clean `.pytest_cache`.
- [ ] REQ-531: Clean nested `tests/tests`.
- [ ] REQ-532: Clean nested copied repo under `tests/`.
- [ ] REQ-533: Clean accidental `tests/PASS_CHANGES.txt`.
- [ ] REQ-534: Check required files exist.
- [ ] REQ-535: Check required scripts exist.
- [ ] REQ-536: Check source package files exist.
- [ ] REQ-537: Check pyproject dependencies.
- [ ] REQ-538: Check API importability.
- [ ] REQ-539: Check test collection.
- [ ] REQ-540: Check Dockerfile exists.
- [ ] REQ-541: Check `.dockerignore` exists.
- [ ] REQ-542: Check compose config.
- [ ] REQ-543: Check no corpora packaged.
- [ ] REQ-544: Check no PDFs packaged.
- [ ] REQ-545: Check no DBs packaged.
- [ ] REQ-546: Check no vector stores packaged.
- [ ] REQ-547: Check no weights packaged.
- [ ] REQ-548: Check no secrets packaged.
- [ ] REQ-549: Structured error output.
- [ ] REQ-550: Suggested correction per failure.
- [ ] REQ-551: Machine-readable JSON report.
- [ ] REQ-552: Human-readable console report.
- [ ] REQ-553: Fail closed on legal readiness.
- [ ] REQ-554: Auto-fix only local artifacts.
- [ ] REQ-555: Never auto-fake legal evidence.
- [ ] REQ-556: Never auto-generate attorney signoff.
- [ ] REQ-557: Never weaken production gates.

## FEAT-024: Docker/containerization

Status: planned

Owned files:
- Dockerfile
- docker-compose*.yml
- .dockerignore
- scripts/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check
- docker compose config
- docker build --pull=false -t maine-family-law-llm:local .

Goal:
Implement, test, and document the `Docker/containerization` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-558: Production-grade Dockerfile.
- [ ] REQ-559: Non-root user.
- [ ] REQ-560: Minimal base image.
- [ ] REQ-561: Healthcheck.
- [ ] REQ-562: Local-only API port by default.
- [ ] REQ-563: `/data` mount.
- [ ] REQ-564: `MAINE_FAMILY_LAW_DATA_ROOT=/data`.
- [ ] REQ-565: Repo mounted read-only where practical.
- [ ] REQ-566: No corpora copied into image.
- [ ] REQ-567: No private data copied into image.
- [ ] REQ-568: No weights copied into image.
- [ ] REQ-569: No vector DB copied into image.
- [ ] REQ-570: No OCR cache copied into image.
- [ ] REQ-571: `.dockerignore` blocks external data.
- [ ] REQ-572: `.dockerignore` blocks secrets.
- [ ] REQ-573: `.dockerignore` blocks runtime state.
- [ ] REQ-574: Compose file for local test.
- [ ] REQ-575: Docker build script.
- [ ] REQ-576: Docker run script.
- [ ] REQ-577: Docker smoke test.
- [ ] REQ-578: Docker audit tests.
- [ ] REQ-579: Container healthcheck script.
- [ ] REQ-580: Container docs.

## FEAT-025: Build/release

Status: planned

Owned files:
- src/maine_family_law_llm/ui/**
- docs/**
- tests/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check
- python -m pytest -q tests -k 'ui or accessibility or export'

Goal:
Implement, test, and document the `Build/release` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-581: Clean release ZIP.
- [ ] REQ-582: Reproducible package script.
- [ ] REQ-583: Release manifest.
- [ ] REQ-584: Source integrity check.
- [ ] REQ-585: Required-file check.
- [ ] REQ-586: No generated metadata in ZIP.
- [ ] REQ-587: No local caches in ZIP.
- [ ] REQ-588: No private files in ZIP.
- [ ] REQ-589: No external data in ZIP.
- [ ] REQ-590: No model weights in ZIP.
- [ ] REQ-591: No vector stores in ZIP.
- [ ] REQ-592: No runtime DBs in ZIP.
- [ ] REQ-593: Dependency manifest.
- [ ] REQ-594: Versioning.
- [ ] REQ-595: Changelog in `PASS_CHANGES.txt`.
- [ ] REQ-596: Smoke JSON.
- [ ] REQ-597: Test summary.
- [ ] REQ-598: Remaining blockers list.
- [ ] REQ-599: Legal readiness status.
- [ ] REQ-600: Production readiness status.

## FEAT-026: Operations

Status: planned

Owned files:
- scripts/**
- docs/**
- tests/**
- pyproject.toml
- README.md

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Operations` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-601: Install scripts.
- [ ] REQ-602: Test scripts.
- [ ] REQ-603: Smoke scripts.
- [ ] REQ-604: API launch scripts.
- [ ] REQ-605: Docker scripts.
- [ ] REQ-606: Ingest scripts.
- [ ] REQ-607: Parse scripts.
- [ ] REQ-608: Index scripts.
- [ ] REQ-609: Eval scripts.
- [ ] REQ-610: Audit scripts.
- [ ] REQ-611: Cleanup scripts.
- [ ] REQ-612: Preflight scripts.
- [ ] REQ-613: Recovery scripts.
- [ ] REQ-614: Operator handoff bundle.
- [ ] REQ-615: Admin guide.
- [ ] REQ-616: User guide.
- [ ] REQ-617: Attorney reviewer guide.
- [ ] REQ-618: Incident runbook.
- [ ] REQ-619: Rollback runbook.
- [ ] REQ-620: Source update runbook.
- [ ] REQ-621: Model update runbook.
- [ ] REQ-622: Backup/restore runbook.
- [ ] REQ-623: Troubleshooting guide.

## FEAT-027: Compliance/governance

Status: planned

Owned files:
- src/maine_family_law_llm/security/**
- src/maine_family_law_llm/matters/**
- tests/**
- docs/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Compliance/governance` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-624: Legal safety policy.
- [ ] REQ-625: Human review policy.
- [ ] REQ-626: Data boundaries policy.
- [ ] REQ-627: Citation verification policy.
- [ ] REQ-628: Authority ranking policy.
- [ ] REQ-629: Model admission policy.
- [ ] REQ-630: Evaluation plan.
- [ ] REQ-631: Privacy impact assessment.
- [ ] REQ-632: Threat model.
- [ ] REQ-633: Vendor risk review.
- [ ] REQ-634: Incident response plan.
- [ ] REQ-635: NIST AI RMF mapping.
- [ ] REQ-636: OWASP LLM mapping.
- [ ] REQ-637: Security control mapping.
- [ ] REQ-638: Data-flow diagram.
- [ ] REQ-639: Model cards.
- [ ] REQ-640: Data cards.
- [ ] REQ-641: Source cards.
- [ ] REQ-642: Human review SOP.
- [ ] REQ-643: Attorney reviewer SOP.
- [ ] REQ-644: Source update SOP.
- [ ] REQ-645: Rollback SOP.
- [ ] REQ-646: Owner signoff workflow.
- [ ] REQ-647: Legal signoff.
- [ ] REQ-648: Security signoff.
- [ ] REQ-649: Product signoff.
- [ ] REQ-650: Ops signoff.

## FEAT-028: Product quality

Status: planned

Owned files:
- src/maine_family_law_llm/ui/**
- docs/**
- tests/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Product quality` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-651: Fast local startup.
- [ ] REQ-652: Clear local testing path.
- [ ] REQ-653: Clear failure messages.
- [ ] REQ-654: Clear status reports.
- [ ] REQ-655: No hidden magic.
- [ ] REQ-656: No fake legal readiness.
- [ ] REQ-657: No unsupported legal answers.
- [ ] REQ-658: No silent retrieval failures.
- [ ] REQ-659: No silent citation failures.
- [ ] REQ-660: No silent quote failures.
- [ ] REQ-661: Every answer traceable.
- [ ] REQ-662: Every draft review-required.
- [ ] REQ-663: Every blocked export explained.
- [ ] REQ-664: Every model action auditable.
- [ ] REQ-665: Every source versioned.
- [ ] REQ-666: Every release reproducible.
- [ ] REQ-667: Every dangerous gap visible.
- [ ] REQ-668: Attorney-first UX.
- [ ] REQ-669: Engineer-operable scripts.
- [ ] REQ-670: Court-source-first behavior.

## FEAT-029: Pilot and GA

Status: planned

Owned files:
- evals/**
- tests/**
- docs/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m py_compile $(git ls-files '*.py')
- python -m pytest -q
- git diff --check

Goal:
Implement, test, and document the `Pilot and GA` capability set while preserving authority-first legal safety, review-required outputs, strict data boundaries, and proof-backed release gates.

Requirements:

- [ ] REQ-671: Attorney-only sandbox pilot.
- [ ] REQ-672: Pilot onboarding.
- [ ] REQ-673: Pilot training materials.
- [ ] REQ-674: Feedback workflow.
- [ ] REQ-675: Error triage.
- [ ] REQ-676: Pilot dashboard.
- [ ] REQ-677: Limited real-matter pilot.
- [ ] REQ-678: Explicit privacy consent.
- [ ] REQ-679: Limited tenant group.
- [ ] REQ-680: Human review required.
- [ ] REQ-681: Export restrictions.
- [ ] REQ-682: Daily pilot review.
- [ ] REQ-683: Pilot evidence packet.
- [ ] REQ-684: No data leakage.
- [ ] REQ-685: No unsupported filing-ready exports.
- [ ] REQ-686: Pilot attorney signoff.
- [ ] REQ-687: GA release candidate.
- [ ] REQ-688: Versioned source ZIP.
- [ ] REQ-689: Versioned external data manifest.
- [ ] REQ-690: Versioned parsed authority manifest.
- [ ] REQ-691: Versioned retrieval index manifest.
- [ ] REQ-692: Versioned gold eval pack manifest.
- [ ] REQ-693: Release metrics.
- [ ] REQ-694: Security evidence packet.
- [ ] REQ-695: Pilot evidence packet.
- [ ] REQ-696: Rollback package.
- [ ] REQ-697: Release notes.
- [ ] REQ-698: No P0/P1 blockers.
- [ ] REQ-699: All production gates pass.
- [ ] REQ-700: GA shipped only after real evidence and signoffs.

## Global release gate

Status: planned

Owned files:
- docs/**
- evals/**
- tests/**
- scripts/**

Blocked files:
- .git/**
- node_modules/**
- dist/**
- build/**
- release/**
- .env
- .env.*
- **/*.pem
- **/*.key
- **/*.pfx
- **/id_rsa
- **/secrets.*
- **/credentials.*
- **/__pycache__/**
- **/.pytest_cache/**
- data/**
- corpora/**
- vector_stores/**
- runtime/**

Acceptance checks:
- python -m pytest -q
- git diff --check
- release metrics JSON exists and all required gates pass

Goal:
Do not ship GA until every production, legal, privacy, security, evaluation, and attorney-review gate has real proof and required signoff.
