# Full Corpus Requirements

The Maine Family Law LLM corpus must be a maintained legal data product, not a
folder of downloaded PDFs. The source repository stores requirements, parsers,
tests, fixtures, and manifests. The live corpus, parsed authority records,
retrieval indexes, audit files, and attorney-reviewed evaluation rows must live
outside the repo in `ME_FM_LLM_DATA_ROOT` or the default sibling data root
`D:\dev\ME_FM_LLM_data`.

## First-Class Source Lanes

The corpus must not be legislature-only. It must ingest, parse, cite, and rank:

- Maine Revised Statutes, with complete Title 19-A coverage and family-law
  overlap from Titles 18-C, 22, 4, 5, 14, 15, 17-A, and 30-A.
- Maine Rules of Civil Procedure, including Family Division Rules 100-129 and
  post-judgment Rule 120 workflows.
- The Rule 120 standing order on motions for findings of fact and conclusions
  of law in family matters.
- Maine Rules of Evidence, Appellate Procedure, Probate Procedure, and
  Electronic Court Systems.
- Maine Rules of Professional Conduct, Maine Bar Rules, Maine Code of Judicial
  Conduct, judicial-discipline materials, attorney-regulation materials, and GAL
  rules/guidance.
- Maine Judicial Branch family forms, packets, instructions, self-help pages,
  eCourts guidance, access/confidentiality guidance, and safety resources.
- Maine Law Court / SJC opinions, including binding family-law cases and
  family-law tags.
- U.S. District Court for the District of Maine local rules, Appendix B
  electronic filing procedures, self-representation guidance, civil/pro se
  forms, CM/ECF guidance, sealing/restricted-document guidance, opinions, and
  intake/relief workflows.
- Federal rules, federal statutes, First Circuit precedent, and U.S. Supreme
  Court authority needed for federal family-adjacent questions.
- Legal-aid and secondary sources only when license-safe and clearly labeled
  nonbinding.

The source-controlled registry for these lanes is
`src/maine_family_law_llm/corpus_registry.py`.

## Required Authority Records

Every collected authority must produce structured records with:

- source id
- authority class
- corpus lane
- title
- official flag
- jurisdiction
- source type
- source URL
- retrieved timestamp
- effective date or version label
- hash
- citation hint and aliases
- parser status
- freshness status
- related statutes/rules/forms/cases when available

Statutes must split by title/chapter/section/subsection. Rules must split by
rule/subdivision/advisory note/history. Forms must expose form id, title,
version date, case type, required fields, instructions, related rules/statutes,
and stale status. Cases must expose caption, docket, court, date, citation,
issues, holding, disposition, posture, standards of review, authority cited, and
pinpoint quote spans.

## Required Indexes

The external data root must contain:

- exact citation index
- statute section lookup
- rule lookup
- case name lookup
- case citation lookup
- form ID lookup
- BM25 lexical index
- optional vector index
- hybrid retrieval index
- source-card index
- authority graph
- freshness index

## District of Maine Federal Lane

The federal Maine lane must support:

- complaint intake
- IFP applications and 28 U.S.C. section 1915 screening
- summons, waiver, and service of process
- CM/ECF and pro se electronic filing
- motion practice under Local Rule 7
- requests for immediate relief
- TRO and preliminary injunction practice under FRCP 65
- attachment and trustee process under Local Rule 64
- bonds/security under Local Rule 65.1
- sealing, redaction, restricted documents, and highly sensitive documents
- magistrate judge review and objections
- appeal and stay basics

For family-law-adjacent federal questions, answers must warn about
jurisdictional blockers, including the domestic relations exception,
Rooker-Feldman, Younger abstention, the Anti-Injunction Act, sovereign immunity,
judicial immunity, quasi-judicial immunity, qualified immunity, preclusion, IFP
screening, and service defects. The assistant must not say federal court can
simply overturn a state family-court order unless a valid federal procedural path
and jurisdictional basis are verified from sources.

## Attorney-Reviewed Evaluation Pack

Enterprise GA legal-data readiness requires attorney-reviewed gold rows. The
minimum row counts are encoded in `REQUIRED_ATTORNEY_REVIEWED_EVALS`:

- retrieval gold: 500
- citation validity: 500
- quote span: 500
- hallucination negative cases: 250
- forms freshness: 100
- drafting review: 100
- issue classification: 250
- posture classification: 150
- authority ranking: 250
- fact-to-evidence: 250
- Law Court holding: 150
- Rule 52 gap: 100
- federal Maine intake/relief: 150
- federal jurisdiction blockers: 150

Without this pack, the project may be locally useful for source-grounded
research workflows, but it must remain blocked for enterprise GA legal-data
readiness.

## Commands

```powershell
cd D:\dev\ME_FM_LLM
powershell -ExecutionPolicy Bypass -File .\START_LOCAL_TEST.ps1 -SkipTests
mfl corpus requirements
mfl corpus build-manifest --data-root D:\dev\ME_FM_LLM_data
mfl corpus fetch-live --allow-live --data-root D:\dev\ME_FM_LLM_data
mfl corpus normalize --data-root D:\dev\ME_FM_LLM_data
mfl corpus parse --data-root D:\dev\ME_FM_LLM_data
mfl corpus build-indexes --data-root D:\dev\ME_FM_LLM_data
mfl corpus audit --data-root D:\dev\ME_FM_LLM_data
```

The live fetch command writes official-source raw files and metadata outside the
repo. It does not create a production-ready legal product by itself; parsing,
indexing, freshness checks, source-card generation, and attorney-reviewed evals
must also pass.
