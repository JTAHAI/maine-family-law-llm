param(
    [string]$OwnerRepo = "JTAHAI/maine-family-law-llm",
    [string]$Version = "v2.08-seo-preview-$(Get-Date -Format yyyyMMdd)",
    [bool]$CreateIssues = $true,
    [bool]$CreateRelease = $true,
    [bool]$CommitAndPush = $true
)

$ErrorActionPreference = "Stop"

function Need($cmd) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $cmd"
    }
}

function WriteUtf8($path, $content) {
    $dir = Split-Path $path -Parent
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    Set-Content -Path $path -Value $content -Encoding UTF8
}

function PrependMarkedBlock($path, $start, $end, $block) {
    if (-not (Test-Path $path)) {
        WriteUtf8 $path $block
        return
    }

    $text = Get-Content $path -Raw

    if ($text.Contains($start) -and $text.Contains($end)) {
        $pattern = [regex]::Escape($start) + ".*?" + [regex]::Escape($end)
        $newText = [regex]::Replace($text, $pattern, $block, "Singleline")
        WriteUtf8 $path $newText
    }
    else {
        WriteUtf8 $path ($block.TrimEnd() + "`r`n`r`n" + $text.TrimStart())
    }
}

Need git
Need gh

if (-not (Test-Path ".git")) {
    throw "Run this from the repository root. Current folder is not a git repo."
}

Write-Host "Applying Maine Family Law LLM repo SEO updates..." -ForegroundColor Cyan

$description = "Open-source Maine family law AI workbench for source-grounded legal research, court-form help, document review, evidence mapping, citation verification, and review-required drafting."

$topics = @(
    "maine",
    "maine-law",
    "family-law",
    "legal-ai",
    "legaltech",
    "lawtech",
    "llm",
    "rag",
    "retrieval-augmented-generation",
    "citation-verification",
    "source-grounded-ai",
    "access-to-justice",
    "self-represented-litigants",
    "court-forms",
    "document-review",
    "evidence-mapping",
    "legal-research",
    "python",
    "fastapi",
    "open-source"
)

Write-Host "Updating repo description..." -ForegroundColor Yellow
gh repo edit $OwnerRepo --description $description | Out-Null

Write-Host "Adding repo topics..." -ForegroundColor Yellow
foreach ($topic in $topics) {
    try {
        gh repo edit $OwnerRepo --add-topic $topic | Out-Null
        Write-Host "  added/kept topic: $topic"
    }
    catch {
        Write-Warning "Topic failed or already at limit: $topic"
    }
}

$readmeBlock = @"
<!-- SEO-INTRO-START -->
# Maine Family Law LLM

Open-source Maine family law AI workbench for legal research, court-form guidance, document review, evidence mapping, citation checking, and review-required drafting.

Built for Maine family-law workflows: divorce, parental rights and responsibilities, child support, protection from abuse, post-judgment motions, contempt, Rule 52 findings, best-interest factors, UCCJEA issues, appellate record problems, and Maine court forms.

This is not legal advice and not a lawyer. It is a local-first, source-grounded legal information and drafting-support tool. Outputs remain review-required unless verified by source, citation, quote-span, fact/evidence, freshness, and human-review gates.

## What is Maine Family Law LLM?

Maine Family Law LLM is a standalone legal AI workbench focused on Maine family law. It helps users research Maine authority, review legal documents, organize evidence, check citations, identify red flags, and produce review-required drafts.

## Maine family-law topics covered

- Divorce
- Parental rights and responsibilities
- Primary residence
- Contact schedules
- Child support
- Parentage
- Post-judgment motions
- Motions to modify
- Motions to enforce
- Motions for contempt
- Protection from abuse
- Protection from harassment
- Grandparent visitation
- Guardianship
- GAL issues
- UCCJEA jurisdiction
- Rule 52 findings
- Best-interest factor gaps
- Appeal preservation
- Transcript and record issues
- Maine eCourts record access
- Maine court forms

## What the workbench can do

- Answer Maine family-law questions with source cards
- Retrieve Maine statutes, rules, forms, and Law Court authority
- Review documents for issue labels, posture, red flags, and missing information
- Build timelines and fact-to-evidence maps
- Generate authority matrices
- Check citations and quote spans
- Draft working motions, affidavits, letters, objections, proposed findings, and checklists
- Generate filing-readiness blocker reports
- Keep outputs review-required by default

## What it does not do

- It does not replace a lawyer.
- It does not provide legal advice.
- It does not guarantee filing-ready output.
- It does not treat model memory as authority.
- It does not train shared models on private matter data by default.
- It does not package private files, model weights, vector stores, corpora, OCR caches, or runtime databases in the source repository.

## Source-grounded legal AI, not a generic chatbot

This project prioritizes official Maine authority, verified retrieval, citation verification, quote-span verification, legal review gates, and human review. Source correctness matters more than polished prose.

## Local-first privacy and external data boundaries

Private matter files, corpora, vector databases, embeddings, OCR caches, runtime databases, generated legal work product, and model weights must stay outside the source repository.

<!-- SEO-INTRO-END -->
"@

Write-Host "Updating README.md..." -ForegroundColor Yellow
PrependMarkedBlock "README.md" "<!-- SEO-INTRO-START -->" "<!-- SEO-INTRO-END -->" $readmeBlock

$discoveryDoc = @"
# Maine Family Law AI and Legal Research Workbench

Maine Family Law LLM is an open-source, local-first legal AI workbench for Maine family law research, document review, court-form guidance, citation verification, evidence mapping, and review-required drafting.

## Search terms this project is meant to support

- Maine family law AI
- Maine legal AI
- Maine family court forms
- Maine divorce forms
- Maine custody law
- Maine parental rights and responsibilities
- Maine child support
- Maine protection from abuse
- Maine post-judgment motion
- Maine Rule 52 findings
- Maine best interest factors
- Maine court document review
- Maine legal research assistant
- Maine source-grounded legal AI
- Maine legal RAG
- legal RAG citation verification
- legal document review AI
- access to justice Maine
- self-represented litigants Maine
- family law drafting assistant
- citation verification legal AI
- quote-span verification legal AI
- evidence mapping legal AI

## Plain-language description

This repository builds a Maine-specific legal AI workbench. It focuses on source-grounded retrieval, verified Maine authority, citation and quote checking, document review, evidence mapping, and review-required drafting.

The system is not a generic chatbot. It is designed around official Maine family-law authority and legal-safety gates.

## Important safety note

This project does not provide legal advice. It is a research, drafting, and review-support tool. Drafts remain review-required unless all source, citation, quote-span, evidence, freshness, and human-review gates pass.
"@

Write-Host "Writing docs/discovery.md..." -ForegroundColor Yellow
WriteUtf8 "docs/discovery.md" $discoveryDoc

$imagesDoc = @"
# Images and Social Preview

Recommended GitHub social preview image size: 1280x640.

Suggested files:

- maine-family-law-ai-source-cards.png
- maine-legal-ai-citation-verification.png
- maine-family-court-evidence-map.png
- review-required-drafting-workbench.png
- maine-family-law-llm-social-preview.png

Suggested social preview text:

Maine Family Law LLM
Source-grounded legal AI workbench
Citation verification - Evidence mapping - Review-required drafting
"@

Write-Host "Writing docs/images/README.md..." -ForegroundColor Yellow
WriteUtf8 "docs/images/README.md" $imagesDoc

if (Test-Path "CITATION.cff") {
    $citation = Get-Content "CITATION.cff" -Raw
    if ($citation -notmatch "(?m)^keywords:") {
        Add-Content -Path "CITATION.cff" -Encoding UTF8 -Value @"

keywords:
  - Maine family law
  - Maine legal AI
  - legal AI
  - legal technology
  - source-grounded AI
  - citation verification
  - quote-span verification
  - retrieval augmented generation
  - access to justice
  - court forms
  - evidence mapping
"@
    }
}
else {
    WriteUtf8 "CITATION.cff" @"
cff-version: 1.2.0
title: "Maine Family Law LLM: Open-Source Maine Family Law AI Workbench"
message: "If you use this project, please cite it."
type: software
authors:
  - family-names: Tahai
    given-names: Justin
repository-code: "https://github.com/JTAHAI/maine-family-law-llm"
keywords:
  - Maine family law
  - Maine legal AI
  - legal AI
  - legal technology
  - source-grounded AI
  - citation verification
  - quote-span verification
  - retrieval augmented generation
  - access to justice
  - court forms
  - evidence mapping
"@
}

$labels = @(
    @{ n = "good first issue"; c = "7057ff"; d = "Small, well-scoped contribution for new contributors" },
    @{ n = "help wanted"; c = "008672"; d = "Extra help would be useful" },
    @{ n = "documentation"; c = "0075ca"; d = "Docs, README, examples, guides" },
    @{ n = "legal-research"; c = "5319e7"; d = "Maine law research and source mapping" },
    @{ n = "maine-law"; c = "0e8a16"; d = "Maine-specific legal authority or workflow" },
    @{ n = "seo"; c = "fbca04"; d = "Search, discoverability, metadata, screenshots" },
    @{ n = "access-to-justice"; c = "d93f0b"; d = "Public-interest and self-represented user improvements" }
)

Write-Host "Creating/updating labels..." -ForegroundColor Yellow
foreach ($label in $labels) {
    try {
        gh label create $label.n --repo $OwnerRepo --color $label.c --description $label.d --force | Out-Null
        Write-Host "  label: $($label.n)"
    }
    catch {
        Write-Warning "Could not create/update label: $($label.n)"
    }
}

if ($CreateIssues) {
    $issues = @(
        @{ t = "Add screenshots to README for Maine family law AI workbench"; b = "Add screenshots showing Ask Maine Family Law, source cards, citation verification, evidence map, and filing-readiness blockers. Use keyword-rich filenames under docs/images/."; l = "good first issue,help wanted,documentation,seo" },
        @{ t = "Add Maine family-law keyword glossary"; b = "Create a glossary covering divorce, parental rights and responsibilities, child support, protection from abuse, post-judgment motions, contempt, Rule 52 findings, best-interest factors, and UCCJEA jurisdiction."; l = "good first issue,help wanted,documentation,maine-law" },
        @{ t = "Add source-card examples to README"; b = "Add examples showing how a Maine statute, court rule, form, and Law Court opinion should appear as source cards."; l = "good first issue,documentation,legal-research" },
        @{ t = "Add sample citation verification report"; b = "Add a small example report showing citation existence, canonical source ID, quote-span match, freshness status, and blocker status."; l = "good first issue,documentation,legal-research" },
        @{ t = "Add local-first privacy diagram"; b = "Create a diagram explaining that private matter files, corpora, embeddings, vector stores, OCR caches, runtime databases, and model weights remain outside the source repository."; l = "good first issue,documentation,access-to-justice" },
        @{ t = "Add court-form topic map"; b = "Create a markdown map of Maine family court form topics: divorce, parental rights, child support, PFA, post-judgment, contempt, and related packets."; l = "help wanted,documentation,maine-law" },
        @{ t = "Improve Windows install troubleshooting guide"; b = "Add common Windows setup fixes for PowerShell execution policy, Python path, virtualenv, port conflicts, and local launcher errors."; l = "good first issue,documentation" },
        @{ t = "Add Rule 52 findings explainer"; b = "Add a plain-language explainer for Rule 52 findings in Maine family cases and how missing findings should appear in red-flag reports."; l = "help wanted,documentation,maine-law,legal-research" },
        @{ t = "Add parental rights and responsibilities explainer"; b = "Add a plain-language explanation of Maine parental rights and responsibilities terminology for users who search for custody or visitation."; l = "good first issue,documentation,maine-law,access-to-justice" },
        @{ t = "Add protection from abuse and family case overlap explainer"; b = "Add a document explaining why PFA issues may overlap with family cases and why the system should flag independent-analysis concerns."; l = "help wanted,documentation,maine-law,legal-research" }
    )

    $existing = @()
    try {
        $existing = gh issue list --repo $OwnerRepo --state all --limit 200 --json title | ConvertFrom-Json | ForEach-Object { $_.title }
    }
    catch {
        $existing = @()
    }

    Write-Host "Creating starter issues..." -ForegroundColor Yellow
    foreach ($issue in $issues) {
        if ($existing -contains $issue.t) {
            Write-Host "  exists: $($issue.t)" -ForegroundColor DarkYellow
            continue
        }

        try {
            gh issue create --repo $OwnerRepo --title $issue.t --body $issue.b --label $issue.l | Out-Null
            Write-Host "  created: $($issue.t)"
        }
        catch {
            Write-Warning "Could not create issue: $($issue.t)"
        }
    }
}

$releaseNotesPath = "docs/release-notes-$Version.md"

$releaseNotes = @"
# $Version

## Maine Family Law LLM - Local Source-Backed Workbench Preview

This release improves public discovery and contributor onboarding for the Maine Family Law LLM project.

## Included

- Updated repository description
- Added GitHub topics for Maine law, family law, legal AI, RAG, citation verification, evidence mapping, and access to justice
- Added README SEO introduction
- Added discovery document for Maine family-law AI search terms
- Added image/social-preview guidance
- Added or updated citation metadata keywords
- Added contributor-friendly labels and starter issues

## Project positioning

Maine Family Law LLM is an open-source, local-first legal AI workbench for Maine family law research, document review, court-form guidance, citation verification, evidence mapping, and review-required drafting.

It is not legal advice. It is not a lawyer. It does not mark generated legal work as filing-ready unless source, citation, quote-span, fact/evidence, freshness, and human-review gates pass.
"@

Write-Host "Writing release notes..." -ForegroundColor Yellow
WriteUtf8 $releaseNotesPath $releaseNotes

if ($CommitAndPush) {
    Write-Host "Committing and pushing local SEO docs..." -ForegroundColor Yellow
    git add README.md docs CITATION.cff

    $status = git status --porcelain
    if ($status) {
        git commit -m "docs: improve Maine family law AI repo discovery"
        git push
    }
    else {
        Write-Host "No local file changes to commit." -ForegroundColor DarkYellow
    }
}

if ($CreateRelease) {
    Write-Host "Creating release $Version..." -ForegroundColor Yellow

    $tagExists = $false
    try {
        git rev-parse -q --verify "refs/tags/$Version" | Out-Null
        $tagExists = $true
    }
    catch {
        $tagExists = $false
    }

    if (-not $tagExists) {
        git tag -a $Version -m "Maine Family Law LLM SEO discovery preview"
        git push origin $Version
    }

    $releaseExists = $false
    try {
        gh release view $Version --repo $OwnerRepo | Out-Null
        $releaseExists = $true
    }
    catch {
        $releaseExists = $false
    }

    if (-not $releaseExists) {
        gh release create $Version --repo $OwnerRepo --title "Maine Family Law LLM $Version - Local Source-Backed Workbench Preview" --notes-file $releaseNotesPath | Out-Null
        Write-Host "Release created: $Version" -ForegroundColor Green
    }
    else {
        Write-Host "Release already exists: $Version" -ForegroundColor DarkYellow
    }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Manual next steps:"
Write-Host "1. Add a GitHub social preview image in repo settings."
Write-Host "2. Add real screenshots or GIFs under docs/images/."
Write-Host "3. Pin the best issues or release from the GitHub UI."
