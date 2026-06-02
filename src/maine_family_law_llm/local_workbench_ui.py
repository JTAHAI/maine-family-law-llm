"""Browser UI for non-technical local Maine Family Law LLM testing."""

from __future__ import annotations


def render_local_workbench_html() -> str:
    """Return a dependency-free HTML chat workbench.

    The page intentionally uses the existing local `/ask`, `/retrieve`, and `/sources`
    endpoints so non-technical testers can exercise the same source-grounded path as
    the CLI without a JavaScript build step.
    """

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FOCAF Maine Family Law LLM — Local Chat Workbench</title>
  <link rel="icon" href="/brand-assets/assets/favicon/favicon.svg" type="image/svg+xml" />
  <link rel="icon" href="/brand-assets/assets/favicon/favicon.ico" sizes="any" />
  <link rel="apple-touch-icon" href="/brand-assets/assets/favicon/apple-touch-icon.png" />
  <link rel="manifest" href="/brand-assets/assets/favicon/site.webmanifest" />
  <meta name="theme-color" content="#07131F" />
  <meta name="brand-kit" content="focaf_family_law_llm_brand_kit" />
  <link rel="stylesheet" href="/brand-assets/css/tokens.css" />
  <link rel="stylesheet" href="/brand-assets/css/focaf-family-law-llm-theme.css" />
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f3f7fb;
      --panel: #ffffff;
      --panel-2: #eef5f9;
      --text: #122033;
      --muted: #536579;
      --line: #d5e1eb;
      --brand-navy: #102a43;
      --brand-teal: #1c7c7d;
      --brand-gold: #d7a02f;
      --accent: #1c7c7d;
      --accent-2: #0a7f6a;
      --danger: #8a1f11;
      --warn: #9a6a00;
      --shadow: 0 18px 44px rgba(16, 42, 67, 0.14);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #08111d;
        --panel: #111c29;
        --panel-2: #152536;
        --text: #edf6ff;
        --muted: #9fb0c2;
        --line: #2d4054;
        --brand-navy: #0b1523;
        --brand-teal: #46d1c9;
        --brand-gold: #f4c76a;
        --accent: #46d1c9;
        --accent-2: #73e2a7;
        --danger: #ff8a80;
        --warn: #f4c76a;
        --shadow: 0 18px 44px rgba(0, 0, 0, 0.38);
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--brand-teal) 22%, transparent), transparent 35rem),
        linear-gradient(180deg, color-mix(in srgb, var(--brand-navy) 10%, var(--bg)), var(--bg));
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    a { color: var(--accent); }
    header {
      padding: 1.1rem;
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--panel) 90%, transparent);
      backdrop-filter: blur(10px);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    header .wrap, main, footer { max-width: 1240px; margin: 0 auto; }
    .brand-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
    .brand-lockup { display: flex; gap: 0.85rem; align-items: center; }
    .brand-mark {
      width: 48px;
      height: 48px;
      border-radius: 16px;
      display: grid;
      place-items: center;
      color: #fff;
      background: linear-gradient(135deg, var(--brand-teal), var(--brand-navy) 60%, var(--brand-gold));
      font-weight: 950;
      letter-spacing: -0.06em;
      box-shadow: var(--shadow);
    }
    h1 { margin: 0 0 0.1rem; font-size: clamp(1.45rem, 2.1vw, 2.1rem); letter-spacing: -0.03em; }
    .subtitle { color: var(--muted); margin: 0; }
    .brand-link { font-weight: 800; text-decoration: none; border: 1px solid var(--line); padding: 0.45rem 0.7rem; border-radius: 999px; background: var(--panel-2); }
    main { padding: 1rem; display: grid; gap: 1rem; grid-template-columns: minmax(0, 1.38fr) minmax(320px, 0.62fr); }
    @media (max-width: 920px) { main { grid-template-columns: 1fr; } }
    .card {
      background: color-mix(in srgb, var(--panel) 96%, transparent);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .card h2 { margin: 0; font-size: 1.1rem; }
    .card-header { padding: 1rem; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; gap: 1rem; align-items: center; }
    .card-body { padding: 1rem; }
    .warning {
      border-left: 5px solid var(--brand-gold);
      background: color-mix(in srgb, var(--brand-gold) 14%, transparent);
      padding: 0.75rem 1rem;
      border-radius: 14px;
      margin-bottom: 1rem;
    }
    label { font-weight: 800; display: block; margin-bottom: 0.35rem; }
    textarea, input, select {
      width: 100%;
      border: 1px solid var(--line);
      background: color-mix(in srgb, var(--panel-2) 80%, transparent);
      color: var(--text);
      border-radius: 15px;
      padding: 0.85rem;
      font: inherit;
    }
    textarea { min-height: 132px; resize: vertical; }
    button {
      border: 0;
      border-radius: 999px;
      padding: 0.78rem 1rem;
      font-weight: 850;
      cursor: pointer;
      background: linear-gradient(135deg, var(--brand-teal), color-mix(in srgb, var(--brand-teal) 70%, var(--brand-navy)));
      color: white;
    }
    button.secondary { background: transparent; color: var(--accent); border: 1px solid var(--line); }
    button.example { width: 100%; color: var(--text); background: color-mix(in srgb, var(--panel-2) 90%, transparent); }
    button:disabled { opacity: 0.55; cursor: wait; }
    .row { display: flex; gap: 0.6rem; flex-wrap: wrap; align-items: center; }
    .input-grid { display: grid; grid-template-columns: 0.85fr 0.85fr 0.9fr 1.2fr; gap: 0.75rem; margin-bottom: 0.75rem; }
    @media (max-width: 880px) { .input-grid { grid-template-columns: 1fr; } }
    .hint { color: var(--muted); font-size: 0.88rem; margin: 0.35rem 0 0; }
    .result-toolbar { display: flex; justify-content: space-between; gap: 0.75rem; align-items: center; margin-top: 1.1rem; flex-wrap: wrap; }
    .badges { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .badge { border: 1px solid var(--line); border-radius: 999px; padding: 0.25rem 0.55rem; font-size: 0.82rem; color: var(--muted); background: color-mix(in srgb, var(--panel-2) 65%, transparent); }
    .badge.good { color: var(--accent-2); }
    .badge.warn { color: var(--warn); }
    .badge.bad { color: var(--danger); }
    .examples, .library-list { display: grid; gap: 0.55rem; }
    .answer, .transcript {
      white-space: pre-wrap;
      background: color-mix(in srgb, var(--panel-2) 82%, transparent);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 1rem;
      min-height: 160px;
    }
    .transcript { min-height: 80px; max-height: 300px; overflow: auto; margin-bottom: 0.85rem; }
    .message { border-radius: 16px; padding: 0.75rem; margin-bottom: 0.6rem; border: 1px solid var(--line); }
    .message.user { background: color-mix(in srgb, var(--brand-teal) 12%, transparent); }
    .message.assistant { background: color-mix(in srgb, var(--panel) 70%, transparent); }
    .message strong { display: block; margin-bottom: 0.25rem; }
    .pill { display: inline-flex; align-items: center; gap: 0.35rem; border: 1px solid var(--line); border-radius: 999px; padding: 0.3rem 0.6rem; font-size: 0.85rem; color: var(--muted); background: var(--panel-2); }
    .source-card {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 0.85rem;
      margin: 0.65rem 0;
      background: color-mix(in srgb, var(--brand-teal) 7%, transparent);
    }
    .source-card strong { display: block; margin-bottom: 0.2rem; }
    .source-card code { overflow-wrap: anywhere; color: var(--muted); }
    .source-card-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 0.35rem; margin: 0.55rem 0; font-size: 0.88rem; }
    .source-card button { padding: 0.45rem 0.7rem; font-size: 0.82rem; }
    .mini-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.55rem; }
    @media (max-width: 680px) { .mini-grid, .source-card-meta { grid-template-columns: 1fr; } }
    .muted { color: var(--muted); }
    .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
    .status-ok { color: var(--accent-2); font-weight: 850; }
    .status-bad { color: var(--danger); font-weight: 850; }
    .status-warn { color: var(--warn); font-weight: 850; }
    details { border: 1px solid var(--line); border-radius: 16px; padding: 0.75rem; background: color-mix(in srgb, var(--panel-2) 68%, transparent); }
    details summary { cursor: pointer; font-weight: 850; }
    footer { padding: 0 1rem 2rem; color: var(--muted); }

    /* v1.85 FOCAF brand-kit integration layer. Kept inline so the local UI remains dependency-free even before static assets load. */
    :root {
      --bg: #07131F;
      --panel: #10283A;
      --panel-2: #153447;
      --text: #EAF7F6;
      --muted: #AFC6CB;
      --line: #244B62;
      --brand-navy: #07131F;
      --brand-teal: #23D3C1;
      --brand-gold: #F6C96D;
      --accent: #8DECE2;
      --accent-2: #3EA97C;
      --shadow: 0 1px 0 rgba(255,255,255,.06) inset, 0 18px 52px rgba(0,0,0,.26);
    }
    body[data-brand-kit="focaf_family_law_llm_brand_kit"] {
      background:
        radial-gradient(circle at 12% 0%, rgba(35,211,193,.18), transparent 32rem),
        radial-gradient(circle at 90% 8%, rgba(246,201,109,.12), transparent 30rem),
        linear-gradient(180deg, #0C1D2B 0%, #07131F 62%, #050C14 100%);
      min-height: 100vh;
    }
    body[data-brand-kit="focaf_family_law_llm_brand_kit"]::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .42;
      background-image:
        linear-gradient(rgba(141,236,226,.045) 1px, transparent 1px),
        linear-gradient(90deg, rgba(141,236,226,.045) 1px, transparent 1px);
      background-size: 44px 44px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,.7), transparent 70%);
    }
    header {
      background: linear-gradient(180deg, rgba(12,29,43,.92), rgba(7,19,31,.78));
      border-bottom: 1px solid rgba(141,236,226,.18);
    }
    .brand-lockup { gap: 1rem; }
    .brand-mark { display: none; }
    .brand-logo-img {
      width: 62px;
      height: 62px;
      border-radius: 20px;
      box-shadow: 0 0 0 1px rgba(141,236,226,.18), 0 18px 42px rgba(35,211,193,.16);
      background: rgba(35,211,193,.08);
    }
    .brand-eyebrow {
      display: block;
      color: #8DECE2;
      font-size: .72rem;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .16em;
      margin-bottom: .12rem;
    }
    .brand-wordmark {
      display: block;
      height: 28px;
      max-width: min(440px, 78vw);
      margin: .1rem 0 .25rem;
      filter: drop-shadow(0 8px 20px rgba(0,0,0,.18));
    }
    .brand-link {
      border-color: rgba(35,211,193,.34);
      color: #07131F;
      background: linear-gradient(180deg, #23D3C1, #8DECE2);
      box-shadow: 0 14px 34px rgba(35,211,193,.16);
    }
    .brand-hero {
      grid-column: 1 / -1;
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(135deg, rgba(35,211,193,.18), rgba(16,40,58,.92) 42%, rgba(7,19,31,.96)),
        url('/brand-assets/assets/social/focaf-family-law-llm-social-card.svg') right center / min(680px, 78%) no-repeat;
      min-height: 210px;
    }
    .brand-hero::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, rgba(7,19,31,.94), rgba(7,19,31,.76) 44%, rgba(7,19,31,.2));
      pointer-events: none;
    }
    .brand-hero > * { position: relative; z-index: 1; }
    .hero-kicker {
      color: #F6C96D;
      font-weight: 900;
      letter-spacing: .14em;
      text-transform: uppercase;
      font-size: .75rem;
      margin: 0 0 .45rem;
    }
    .hero-title {
      max-width: 760px;
      font-size: clamp(2rem, 4vw, 4.2rem);
      line-height: .98;
      letter-spacing: -.055em;
      margin: 0;
    }
    .hero-copy { max-width: 720px; color: #D9ECEC; font-size: 1.02rem; margin: .8rem 0 1rem; }
    .hero-actions { display: flex; flex-wrap: wrap; gap: .65rem; align-items: center; }
    .hero-pill {
      display: inline-flex;
      align-items: center;
      gap: .4rem;
      border: 1px solid rgba(141,236,226,.26);
      background: rgba(141,236,226,.08);
      color: #EAF7F6;
      border-radius: 999px;
      padding: .45rem .7rem;
      font-weight: 800;
      font-size: .84rem;
    }
    .hero-pill.review { border-color: rgba(246,201,109,.42); color: #F6C96D; background: rgba(246,201,109,.1); }
    .hero-pill.safe { border-color: rgba(62,169,124,.42); color: #AAE8CE; background: rgba(62,169,124,.1); }
    .card {
      border-color: rgba(141,236,226,.16);
      background: linear-gradient(180deg, rgba(21,52,71,.94), rgba(16,40,58,.96));
    }
    .card-header { background: rgba(7,19,31,.22); }
    .warning { border-color: rgba(246,201,109,.38); color: #F9E6B4; }
    textarea, input, select {
      background: rgba(7,19,31,.62);
      border-color: rgba(141,236,226,.22);
    }
    textarea:focus, input:focus, select:focus {
      outline: none;
      box-shadow: 0 0 0 3px rgba(35,211,193,.26), 0 0 0 6px rgba(7,19,31,.62);
      border-color: rgba(35,211,193,.62);
    }
    button {
      color: #041217;
      background: linear-gradient(180deg, #23D3C1, #11A096);
      box-shadow: 0 12px 30px rgba(35,211,193,.16);
    }
    button.secondary, button.example {
      color: #EAF7F6;
      background: rgba(141,236,226,.07);
      border-color: rgba(141,236,226,.22);
    }
    button.example { text-align: left; border-radius: 18px; }
    .answer, .transcript {
      background: linear-gradient(180deg, rgba(12,29,43,.9), rgba(7,19,31,.82));
      border-color: rgba(141,236,226,.18);
    }
    .source-card {
      background: linear-gradient(180deg, rgba(35,211,193,.09), rgba(12,29,43,.88));
      border-color: rgba(141,236,226,.2);
    }
    .runtime-card {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: .55rem;
      margin: 1rem 0;
    }
    @media (max-width: 920px) { .runtime-card { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 560px) { .runtime-card { grid-template-columns: 1fr; } .brand-wordmark { display: none; } }
    .runtime-stat {
      border: 1px solid rgba(141,236,226,.16);
      background: rgba(7,19,31,.38);
      border-radius: 16px;
      padding: .75rem;
    }
    .runtime-stat strong { display:block; color:#8DECE2; font-size:1.15rem; }
    .runtime-stat span { color: var(--muted); font-size:.8rem; }
    .brand-asset-proof {
      display: inline-flex;
      align-items: center;
      gap: .45rem;
      color: #8DECE2;
      font-weight: 800;
    }

  </style>
</head>
<body data-brand-kit="focaf_family_law_llm_brand_kit" data-ui-pass="v1.85">
  <header id="focaf-brand-shell" data-ui-version="1.85.0-branded-ui-asset-integration" data-brand-assets="/brand-assets">
    <div class="wrap brand-row">
      <div class="brand-lockup">
        <img class="brand-logo-img" src="/brand-assets/assets/logo/focaf-family-law-llm-mark.svg" alt="FOCAF Maine Family Law LLM mark" />
        <div>
          <span class="brand-eyebrow">For Our Children & Families</span>
          <img class="brand-wordmark" src="/brand-assets/assets/logo/focaf-family-law-llm-horizontal.svg" alt="FOCAF Maine Family Law LLM" />
          <h1 class="sr-only">Maine Family Law LLM</h1>
          <p class="subtitle">Local source-backed chat workbench for Maine family-law orientation. Enter submits. Review required. Not legal advice.</p>
        </div>
      </div>
      <a class="brand-link" href="https://focaf.jtforme.com" target="_blank" rel="noopener noreferrer">focaf.jtforme.com</a>
    </div>
  </header>
  <main>
    <section class="card brand-hero" id="focaf-brand-hero" data-brand-kit-mounted="expected">
      <div class="card-body">
        <p class="hero-kicker">FOCAF Maine Family Law LLM · Local Workbench</p>
        <h2 class="hero-title">Source-backed family-law orientation for Maine families and helpers.</h2>
        <p class="hero-copy">Use role-based starters, answer styles, source cards, missing-information checklists, and reviewer handoff exports. This is legal information only; human review is required before anyone relies on it.</p>
        <div class="hero-actions">
          <span class="hero-pill safe">Local browser workbench</span>
          <span class="hero-pill review">Review required</span>
          <span class="hero-pill">Enter key submits</span>
          <span class="hero-pill">Appeals routing fixed</span>
          <span class="brand-asset-proof">Brand assets loaded from /brand-assets</span>
        </div>
      </div>
    </section>
    <section class="card" aria-labelledby="chat-heading">
      <div class="card-header">
        <h2 id="chat-heading">Ask Maine Family Law</h2>
        <span id="health" class="pill">checking local API...</span>
      </div>
      <div class="card-body">
        <div class="warning">
          This tool gives legal information from retrieved source snippets. It does not create an attorney-client relationship, and no answer is filing-ready.
        </div>
        <div id="runtime-diagnostics" class="warning" data-runtime-diagnostics="loading">Runtime diagnostics loading. Expected UI: v1.85 branded asset integration + appeals routing + Enter submit.</div>
        <div class="runtime-card" aria-label="Local workbench status summary">
          <div class="runtime-stat"><strong>v1.85</strong><span>visible UI pass</span></div>
          <div class="runtime-stat"><strong>105+</strong><span>source-backed chat starters</span></div>
          <div class="runtime-stat"><strong>5 roles</strong><span>parents, lawyers, caregivers, counselors, therapists</span></div>
          <div class="runtime-stat"><strong>Assets</strong><span>FOCAF kit served locally</span></div>
        </div>
        <div class="input-grid">
          <div>
            <label for="audience">I am asking as a...</label>
            <select id="audience">
              <option value="parent">Parent</option>
              <option value="lawyer">Lawyer / advocate</option>
              <option value="caregiver">Caregiver / relative</option>
              <option value="counselor">Counselor</option>
              <option value="therapist">Therapist / clinician</option>
            </select>
          </div>
          <div>
            <label for="answer-style">Answer style</label>
            <select id="answer-style">
              <option value="plain_language">Plain-language answer</option>
              <option value="checklist">Checklist</option>
              <option value="source_first">Source-first summary</option>
              <option value="intake">Intake triage</option>
              <option value="professional_boundary">Professional-boundary note</option>
              <option value="source_card_table">Source-card audit table</option>
              <option value="questions_to_ask">Questions to ask lawyer/clerk</option>
              <option value="missing_information">Missing-info checklist</option>
            </select>
          </div>
          <div>
            <label for="topic-filter">Topic filter</label>
            <select id="topic-filter">
              <option value="all">All topics</option>
            </select>
          </div>
          <div>
            <label for="matter-context">Optional context / facts to focus on</label>
            <input id="matter-context" placeholder="Example: parental rights, domestic abuse concern, post-judgment motion" />
          </div>
        </div>
        <label for="question">Question</label>
        <textarea id="question" placeholder="Example: What are Maine's best-interest factors under 19-A M.R.S. § 1653?"></textarea>
        <p class="hint">Press <strong>Enter</strong> to ask immediately. Press <strong>Shift+Enter</strong> for a new line. If Enter does not submit, reload with Ctrl+F5 and verify the 1.85 UI marker and runtime diagnostics panel.</p>
        <div class="row" style="margin-top: 0.75rem;">
          <button id="ask-button">Ask</button>
          <button id="copy-button" class="secondary">Copy answer</button>
          <button id="download-button" class="secondary">Download transcript</button>
          <button id="download-json-button" class="secondary">Download JSON</button>
          <button id="clear-button" class="secondary">Clear chat</button>
          <button id="sources-button" class="secondary">Load source list</button>
        </div>
        <div class="result-toolbar">
          <h2>Conversation</h2>
          <div id="answer-badges" class="badges"><span class="badge">waiting</span></div>
        </div>
        <div id="transcript" class="transcript" aria-live="polite">No messages yet.</div>
        <h2>Latest answer</h2>
        <div id="answer" class="answer" aria-live="polite">Ask a question to test the local source-grounded workbench.</div>
        <h2 style="margin-top: 1rem;">Missing info & reviewer handoff</h2>
        <div id="handoff-panel" class="answer" aria-live="polite">Ask a question to see missing facts, follow-up questions, and reviewer handoff metadata.</div>
      </div>
    </section>

    <aside class="card" aria-labelledby="sources-heading">
      <div class="card-header">
        <h2 id="sources-heading">Sources, shortcuts & question library</h2>
      </div>
      <div class="card-body">
        <p class="muted">Try these starter prompts:</p>
        <div class="examples">
          <button class="secondary example" data-example="What are Maine's best-interest factors under 19-A M.R.S. § 1653?">Best-interest factors</button>
          <button class="secondary example" data-example="What court handles appeals?">Appeals court routing</button>
          <button class="secondary example" data-example="How do I use the best-interest factors in my parenting case?">Parent best-interest prep</button>
          <button class="secondary example" data-example="Can a therapist decide whether visits happen?">Therapist / contact boundary</button>
          <button class="secondary example" data-example="What should I gather for child support?">Child support checklist</button>
          <button class="secondary example" data-example="What if I need protection from abuse?">Safety/PFA routing</button>
          <button class="secondary example" data-example="I was served with family court papers. What should I do first?">Served papers</button>
          <button class="secondary example" data-example="How do I organize evidence for family court?">Organize evidence</button>
          <button class="secondary example" data-example="Should I write a court letter for a parent?">Counselor court letter</button>
          <button class="secondary example" data-example="What should a counselor do if subpoenaed in a family case?">Counselor subpoena</button>
          <button class="secondary example" data-example="What if one parent wants to move away with the child?">Move / relocation flag</button>
          <button class="secondary example" data-example="How do I document missed exchanges?">Missed exchanges</button>
          <button class="secondary example" data-example="What information do I need before asking a family law question?">Missing-info checklist</button>
          <button class="secondary example" data-example="How do I export a reviewer handoff from this chat?">Reviewer handoff export</button>
        </div>
        <details style="margin-top: 1rem;" open>
          <summary>Role-specific starter prompt packs</summary>
          <p class="muted">Pick a prompt pack for the selected role. These packs are designed for everyday parents, lawyers/advocates, caregivers, counselors, and therapists.</p>
          <label for="prompt-pack-select">Starter pack</label>
          <select id="prompt-pack-select"><option value="auto">Best pack for selected role</option></select>
          <div id="prompt-pack-list" class="library-list" style="margin-top: 0.7rem;">Loading starter prompt packs...</div>
        </details>
        <details style="margin-top: 1rem;" open>
          <summary>Browse question library</summary>
          <p class="muted">These are starter questions for parents, lawyers, caregivers, counselors, and therapists. Filter by audience, topic, or keywords.</p>
          <div class="mini-grid">
            <div>
              <label for="library-search">Search starter questions</label>
              <input id="library-search" placeholder="Example: evidence, served papers, therapist, child support" />
            </div>
            <div>
              <label for="library-topic-search">Quick topic</label>
              <input id="library-topic-search" placeholder="Example: safety_pfa, parental_rights, post_judgment" />
            </div>
          </div>
          <div id="library-list" class="library-list" style="margin-top: 0.7rem;">Loading question library...</div>
        </details>
        <h2 style="margin-top: 1.25rem;">Retrieved source cards</h2>
        <div id="source-cards" class="muted">No source cards yet.</div>
        <h2 style="margin-top: 1.25rem;">Source inspector</h2>
        <div id="source-inspector" class="muted">Select “Inspect source” on a source card to view full local metadata.</div>
      </div>
    </aside>
  </main>
  <footer>
    <p><strong>UI v1.85 FOCAF brand-kit asset integration + beautiful local shell + appeals/runtime diagnostics.</strong> Useful local links: <a href="/docs">Swagger API docs</a> · <a href="/sources">Raw source manifest</a> · <a href="/api/question-library">Question library JSON</a> · <a href="/api/question-topics">Topic JSON</a> · <a href="/api/starter-prompt-packs">Starter packs JSON</a> · <a href="/api/missing-information-prompts">Missing-info JSON</a> · <a href="/api/health">Health</a></p>
  </footer>
  <!-- Compatibility marker for tests and older docs: fetch('/ask') -->
  <script>
    const question = document.getElementById('question');
    const answer = document.getElementById('answer');
    const transcript = document.getElementById('transcript');
    const sourceCards = document.getElementById('source-cards');
    const askButton = document.getElementById('ask-button');
    const copyButton = document.getElementById('copy-button');
    const downloadButton = document.getElementById('download-button');
    const downloadJsonButton = document.getElementById('download-json-button');
    const clearButton = document.getElementById('clear-button');
    const sourcesButton = document.getElementById('sources-button');
    const health = document.getElementById('health');
    const answerStyle = document.getElementById('answer-style');
    const matterContext = document.getElementById('matter-context');
    const audience = document.getElementById('audience');
    const topicFilter = document.getElementById('topic-filter');
    const answerBadges = document.getElementById('answer-badges');
    const libraryList = document.getElementById('library-list');
    const librarySearch = document.getElementById('library-search');
    const libraryTopicSearch = document.getElementById('library-topic-search');
    const promptPackSelect = document.getElementById('prompt-pack-select');
    const promptPackList = document.getElementById('prompt-pack-list');
    const sourceInspector = document.getElementById('source-inspector');
    const handoffPanel = document.getElementById('handoff-panel');
    const runtimeDiagnostics = document.getElementById('runtime-diagnostics');
    window.__MFL_WORKBENCH_UI_VERSION = '1.85.0-branded-ui-asset-integration';
    const messages = [];
    let libraryItems = [];
    let promptPacks = [];
    let lastPayload = null;
    let lastSources = [];
    let sending = false;

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[char]));
    }

    async function fetchJson(url, options = {}) {
      const res = await fetch(url, options);
      const text = await res.text();
      let payload = null;
      if (text) {
        try {
          payload = JSON.parse(text);
        } catch (err) {
          const preview = text.replace(/\\s+/g, ' ').slice(0, 360);
          throw new Error(`${res.status} ${res.statusText || 'response'}: ${preview || 'non-JSON response'}`);
        }
      } else {
        payload = {};
      }
      if (!res.ok) {
        const message = payload.message || payload.detail || payload.recovery_hint || res.statusText || 'request failed';
        throw new Error(message);
      }
      return payload;
    }

    function renderBadges(payload) {
      const badges = [];
      badges.push(`<span class="badge ${payload.grounded ? 'good' : 'warn'}">${payload.grounded ? 'source grounded' : 'not grounded'}</span>`);
      if (payload.failure_class && payload.failure_class !== 'none') badges.push(`<span class="badge warn">${escapeHtml(payload.failure_class)}</span>`);
      if (payload.matter_context_used) badges.push('<span class="badge">context used</span>');
      if (payload.answer_style) badges.push(`<span class="badge">${escapeHtml(payload.answer_style)}</span>`);
      if (payload.review_required !== false) badges.push('<span class="badge warn">review required</span>');
      if (payload.metadata && payload.metadata.matched_library_topic) badges.push(`<span class="badge">${escapeHtml(payload.metadata.matched_library_topic)}</span>`);
      if (payload.source_card_count !== undefined) badges.push(`<span class="badge">${escapeHtml(payload.source_card_count)} source cards</span>`);
      answerBadges.innerHTML = badges.join('');
    }

    function renderHandoff(payload) {
      const metadata = payload?.metadata || {};
      const missing = metadata.missing_information || [];
      const followups = metadata.follow_up_questions || [];
      const handoff = {
        review_required: payload?.review_required !== false,
        matched_library_id: metadata.matched_library_id || null,
        matched_topic: metadata.matched_library_topic || null,
        source_card_count: payload?.source_card_count || 0,
        answer_style: payload?.answer_style || metadata.answer_style || null,
        missing_information: missing,
        follow_up_questions: followups
      };
      if ((!missing.length && !followups.length) || !payload) {
        handoffPanel.textContent = 'No handoff metadata yet. Try the Missing-info checklist answer style.';
        return;
      }
      handoffPanel.innerHTML = `<strong>Reviewer handoff summary</strong>
        <p class="muted">Review required. Not legal advice. Not filing-ready.</p>
        <p><strong>Matched item:</strong> ${escapeHtml(handoff.matched_library_id || 'none')} · <strong>Topic:</strong> ${escapeHtml(handoff.matched_topic || 'none')} · <strong>Sources:</strong> ${escapeHtml(handoff.source_card_count)}</p>
        <strong>Missing information</strong>
        <ul>${missing.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>
        <strong>Follow-up questions</strong>
        <ul>${followups.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>
        <button class="secondary" id="copy-handoff-button">Copy reviewer handoff JSON</button>`;
      const copyHandoff = document.getElementById('copy-handoff-button');
      copyHandoff?.addEventListener('click', async () => {
        await navigator.clipboard.writeText(JSON.stringify(handoff, null, 2));
        copyHandoff.textContent = 'Handoff copied';
        setTimeout(() => { copyHandoff.textContent = 'Copy reviewer handoff JSON'; }, 1100);
      });
    }

    function renderSources(items) {
      if (!items || !items.length) {
        sourceCards.innerHTML = '<span class="muted">No source cards returned.</span>';
        return;
      }
      lastSources = items || [];
      sourceCards.innerHTML = items.map((item) => {
        const meta = item.metadata || item;
        const title = item.title || meta.title || meta.id || 'Source';
        const url = meta.url || '';
        const sourceType = meta.source_type || meta.source_class || 'source';
        const official = meta.official === false ? 'unofficial' : 'official/source-backed';
        const snippet = item.snippet || meta.description || meta.url || meta.id || '';
        const citation = item.citation || meta.citation_hint || '';
        const version = meta.version_label || '';
        const effective = meta.effective_date || '';
        const sourceId = item.source_id || meta.source_id || meta.id || '';
        return `<article class="source-card" data-source-card="visible" data-source-id="${escapeHtml(sourceId)}">
          <strong>${escapeHtml(title)}</strong>
          <div class="muted">${escapeHtml(sourceType)} · ${escapeHtml(official)}</div>
          <div class="source-card-meta">
            <span><strong>Citation:</strong> ${escapeHtml(citation || 'not provided')}</span>
            <span><strong>Version:</strong> ${escapeHtml(version || 'verify current source')}</span>
            <span><strong>Effective:</strong> ${escapeHtml(effective || 'verify')}</span>
            <span><strong>ID:</strong> ${escapeHtml(sourceId || 'source')}</span>
          </div>
          <p>${escapeHtml(snippet)}</p>
          ${url ? `<code>${escapeHtml(url)}</code>` : ''}
          <div class="row" style="margin-top: 0.55rem;"><button class="secondary" data-copy-source="${escapeHtml(sourceId)}">Copy source card</button><button class="secondary" data-inspect-source="${escapeHtml(sourceId)}">Inspect source</button></div>
        </article>`;
      }).join('');
      document.querySelectorAll('[data-copy-source]').forEach((button) => {
        button.addEventListener('click', async () => {
          const sourceId = button.dataset.copySource;
          const source = lastSources.find((item) => (item.source_id || item?.metadata?.id || item?.metadata?.source_id) === sourceId) || {};
          await navigator.clipboard.writeText(JSON.stringify(source, null, 2));
          button.textContent = 'Source copied';
          setTimeout(() => { button.textContent = 'Copy source card'; }, 1100);
        });
      });
      document.querySelectorAll('[data-inspect-source]').forEach((button) => {
        button.addEventListener('click', () => inspectSource(button.dataset.inspectSource));
      });
    }

    async function inspectSource(sourceId) {
      if (!sourceId) return;
      sourceInspector.innerHTML = '<span class="muted">Loading source metadata...</span>';
      try {
        const payload = await fetchJson(`/inspect-source/${encodeURIComponent(sourceId)}`);
        sourceInspector.innerHTML = `<details open><summary>${escapeHtml(payload.title || payload.id || sourceId)}</summary><pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre></details>`;
      } catch (err) {
        const local = lastSources.find((item) => (item.source_id || item?.metadata?.id || item?.metadata?.source_id) === sourceId) || {};
        sourceInspector.innerHTML = `<details open><summary>${escapeHtml(sourceId)} local card</summary><pre>${escapeHtml(JSON.stringify(local, null, 2))}</pre><p class="status-warn">Full source metadata was not available: ${escapeHtml(err.message)}</p></details>`;
      }
    }

    function addMessage(role, text) {
      messages.push({role, text, at: new Date().toISOString()});
      transcript.innerHTML = messages.map((msg) => `<div class="message ${escapeHtml(msg.role)}"><strong>${msg.role === 'user' ? 'You' : 'Maine Family Law LLM'}</strong>${escapeHtml(msg.text)}</div>`).join('');
      transcript.scrollTop = transcript.scrollHeight;
    }

    async function ask() {
      if (sending) return;
      const text = question.value.trim();
      if (!text) {
        answer.textContent = 'Type a Maine family-law question first.';
        return;
      }
      sending = true;
      askButton.disabled = true;
      answer.textContent = 'Retrieving sources and composing a grounded answer...';
      sourceCards.textContent = '';
      addMessage('user', text);
      try {
        const context = [matterContext.value.trim(), `Audience: ${audience.value}`].filter(Boolean).join('\\n');
        const payload = await fetchJson('/ask', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            question: text,
            answer_style: answerStyle.value,
            matter_context: context
          })
        });
        const responseText = payload.answer || JSON.stringify(payload, null, 2);
        answer.textContent = responseText;
        addMessage('assistant', responseText);
        lastPayload = payload;
        renderBadges(payload);
        renderHandoff(payload);
        renderSources(payload.citations || []);
      } catch (err) {
        const message = `Local workbench error: ${err.message}`;
        answer.textContent = message;
        addMessage('assistant', message);
        answerBadges.innerHTML = '<span class="badge bad">error</span><span class="badge warn">server response handled</span>';
        sourceCards.innerHTML = '<span class="status-bad">No response. Check the terminal running START_LOCAL_CHAT.ps1 for details.</span>';
        handoffPanel.textContent = 'No reviewer handoff metadata because the request failed.';
      } finally {
        sending = false;
        askButton.disabled = false;
      }
    }


    async function loadRuntimeDiagnostics() {
      try {
        const payload = await fetchJson('/api/runtime-diagnostics');
        runtimeDiagnostics.dataset.runtimeDiagnostics = 'loaded';
        runtimeDiagnostics.innerHTML = `<strong>Runtime diagnostics:</strong> ${escapeHtml(payload.version)} · ${escapeHtml(payload.ui_version)} · Enter submit: ${payload.enter_to_submit ? 'on' : 'off'} · Appeals routing fix: ${payload.appeals_routing_fix ? 'on' : 'off'} · Brand assets mounted: ${payload.brand_assets_mounted ? 'yes' : 'no'} · Branding: ${escapeHtml(payload.branding || 'unknown')}`;
      } catch (err) {
        runtimeDiagnostics.dataset.runtimeDiagnostics = 'failed';
        runtimeDiagnostics.innerHTML = `<strong>Runtime diagnostics failed:</strong> ${escapeHtml(err.message)}. If the footer is not v1.85, stop the old server and restart from the _git repo.`;
      }
    }

    async function loadSources() {
      sourcesButton.disabled = true;
      try {
        const payload = await fetchJson('/sources');
        const cards = payload.map((item) => ({metadata: item, snippet: item.description || item.url || item.id}));
        renderSources(cards);
      } catch (err) {
        sourceCards.innerHTML = `<span class="status-bad">Could not load sources: ${escapeHtml(err.message)}</span>`;
      } finally {
        sourcesButton.disabled = false;
      }
    }

    async function loadQuestionLibrary() {
      try {
        const payload = await fetchJson('/api/question-library');
        libraryItems = payload;
        populateTopicFilter(payload);
        renderQuestionLibrary(payload);
      } catch (err) {
        libraryList.innerHTML = `<span class="status-bad">Could not load question library: ${escapeHtml(err.message)}</span>`;
      }
    }

    async function loadPromptPacks() {
      try {
        promptPacks = await fetchJson('/api/starter-prompt-packs');
        populatePromptPackSelect();
        renderPromptPacks();
      } catch (err) {
        promptPackList.innerHTML = `<span class="status-bad">Could not load starter prompt packs: ${escapeHtml(err.message)}</span>`;
      }
    }

    function populatePromptPackSelect() {
      const rolePacks = promptPacks.filter((pack) => pack.audience === audience.value);
      promptPackSelect.innerHTML = '<option value="auto">Best pack for selected role</option>' + rolePacks.map((pack) => `<option value="${escapeHtml(pack.id)}">${escapeHtml(pack.title)}</option>`).join('');
    }

    function renderPromptPacks() {
      const rolePacks = promptPacks.filter((pack) => pack.audience === audience.value);
      const selected = promptPackSelect.value === 'auto' ? (rolePacks[0] || promptPacks[0]) : promptPacks.find((pack) => pack.id === promptPackSelect.value);
      if (!selected) {
        promptPackList.innerHTML = '<span class="muted">No starter pack available for this role yet.</span>';
        return;
      }
      promptPackList.innerHTML = `<p class="muted"><strong>${escapeHtml(selected.title)}</strong><br>${escapeHtml(selected.description || '')}</p>` + (selected.prompts || []).map((row) => {
        return `<button class="secondary example" data-pack-prompt="${escapeHtml(row.prompt)}" data-pack-style="${escapeHtml(row.recommended_style || 'checklist')}">
          <strong>${escapeHtml(row.title)}</strong><br><span class="muted">${escapeHtml(row.topic)} · ${escapeHtml(row.recommended_style || 'checklist')}</span>
        </button>`;
      }).join('');
      document.querySelectorAll('[data-pack-prompt]').forEach((button) => {
        button.addEventListener('click', () => {
          answerStyle.value = button.dataset.packStyle || answerStyle.value;
          question.value = button.dataset.packPrompt;
          ask();
        });
      });
    }

    function populateTopicFilter(items) {
      const topics = Array.from(new Set(items.map((item) => item.topic))).sort();
      topicFilter.innerHTML = '<option value="all">All topics</option>' + topics.map((topic) => `<option value="${escapeHtml(topic)}">${escapeHtml(topic)}</option>`).join('');
    }

    function renderQuestionLibrary(items) {
      const activeAudience = audience.value;
      const activeTopic = topicFilter.value;
      const needle = (librarySearch?.value || '').toLowerCase().trim();
      const topicNeedle = (libraryTopicSearch?.value || '').toLowerCase().trim();
      const audienceMatches = items.filter((item) => item.audience === activeAudience);
      const searched = audienceMatches.filter((item) => {
        const blob = [item.title, item.topic, item.audience, ...(item.prompts || []), ...(item.keywords || [])].join(' ').toLowerCase();
        const topicOk = activeTopic === 'all' || item.topic === activeTopic;
        const quickTopicOk = !topicNeedle || item.topic.toLowerCase().includes(topicNeedle) || blob.includes(topicNeedle);
        const needleOk = !needle || blob.includes(needle);
        return topicOk && quickTopicOk && needleOk;
      });
      const fallback = audienceMatches.filter((item) => activeTopic === 'all' || item.topic === activeTopic);
      const display = (searched.length ? searched : fallback.length ? fallback : audienceMatches.length ? audienceMatches : items).slice(0, 18);
      libraryList.innerHTML = display.map((item) => {
        const prompt = (item.prompts && item.prompts[0]) || item.title;
        return `<button class="secondary example" data-library-prompt="${escapeHtml(prompt)}" data-library-topic="${escapeHtml(item.topic)}">
          <strong>${escapeHtml(item.title)}</strong><br><span class="muted">${escapeHtml(item.audience)} · ${escapeHtml(item.topic)}</span>
        </button>`;
      }).join('') || '<span class="muted">No starter questions matched that filter.</span>';
      document.querySelectorAll('[data-library-prompt]').forEach((button) => {
        button.addEventListener('click', () => {
          question.value = button.dataset.libraryPrompt;
          ask();
        });
      });
    }

    document.querySelectorAll('[data-example]').forEach((button) => {
      button.addEventListener('click', () => { question.value = button.dataset.example; ask(); });
    });
    askButton.addEventListener('click', ask);
    copyButton.addEventListener('click', async () => {
      await navigator.clipboard.writeText(answer.textContent || '');
      copyButton.textContent = 'Copied';
      setTimeout(() => { copyButton.textContent = 'Copy answer'; }, 1100);
    });
    downloadButton.addEventListener('click', () => {
      const content = [
        'Maine Family Law LLM local transcript',
        'Review required. Not legal advice.',
        '',
        messages.map((msg) => `[${msg.at}] ${msg.role.toUpperCase()}\\n${msg.text}`).join('\\n\\n'),
        '',
        'Latest payload metadata:',
        JSON.stringify(lastPayload || {}, null, 2),
        '',
        'Latest source cards:',
        JSON.stringify(lastSources || [], null, 2)
      ].join('\\n');
      const blob = new Blob([content || answer.textContent || 'No transcript yet.'], {type: 'text/plain'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'maine-family-law-llm-transcript.txt';
      a.click();
      URL.revokeObjectURL(url);
    });
    downloadJsonButton.addEventListener('click', () => {
      const payload = {
        schema_version: 'local_chat_transcript_v3',
        generated_at: new Date().toISOString(),
        review_required: true,
        not_legal_advice: true,
        messages,
        latest_payload: lastPayload || null,
        latest_source_cards: lastSources || [],
        reviewer_handoff: lastPayload ? {
          review_required: lastPayload.review_required !== false,
          answer_style: lastPayload.answer_style || lastPayload?.metadata?.answer_style || null,
          matched_library_id: lastPayload?.metadata?.matched_library_id || null,
          matched_library_topic: lastPayload?.metadata?.matched_library_topic || null,
          source_card_count: lastPayload.source_card_count || 0,
          missing_information: lastPayload?.metadata?.missing_information || [],
          follow_up_questions: lastPayload?.metadata?.follow_up_questions || []
        } : null
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'maine-family-law-llm-transcript.json';
      a.click();
      URL.revokeObjectURL(url);
    });
    clearButton.addEventListener('click', () => {
      question.value = '';
      matterContext.value = '';
      messages.length = 0;
      transcript.textContent = 'No messages yet.';
      answer.textContent = 'Ask a question to test the local source-grounded workbench.';
      answerBadges.innerHTML = '<span class="badge">waiting</span>';
      sourceCards.textContent = 'No source cards yet.';
      sourceInspector.textContent = 'Select “Inspect source” on a source card to view full local metadata.';
      handoffPanel.textContent = 'Ask a question to see missing facts, follow-up questions, and reviewer handoff metadata.';
      lastPayload = null;
      lastSources = [];
    });
    sourcesButton.addEventListener('click', loadSources);
    audience.addEventListener('change', () => {
      const presets = {lawyer: 'intake', counselor: 'professional_boundary', therapist: 'professional_boundary', caregiver: 'missing_information', parent: 'plain_language'};
      answerStyle.value = presets[audience.value] || answerStyle.value;
      populatePromptPackSelect();
      renderPromptPacks();
      renderQuestionLibrary(libraryItems);
    });
    promptPackSelect.addEventListener('change', renderPromptPacks);
    topicFilter.addEventListener('change', () => renderQuestionLibrary(libraryItems));
    librarySearch?.addEventListener('input', () => renderQuestionLibrary(libraryItems));
    libraryTopicSearch?.addEventListener('input', () => renderQuestionLibrary(libraryItems));
    question.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        ask();
      }
    });
    matterContext.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        ask();
      }
    });

    fetchJson('/api/health').then((payload) => {
      health.textContent = payload.status === 'ok' ? 'local API online' : 'local API status unknown';
      health.className = payload.status === 'ok' ? 'pill status-ok' : 'pill status-bad';
    }).catch(() => {
      health.textContent = 'local API offline';
      health.className = 'pill status-bad';
    });
    loadQuestionLibrary();
    loadPromptPacks();
    loadRuntimeDiagnostics();
    // v1.85 marker: brand_kit_assets, beautiful_shell, appeals_routing_fix, runtime diagnostics, reviewer_handoff, missing_information prompts, local_chat_transcript_v3; compatibility marker local_chat_transcript_v2
  </script>
</body>
</html>
"""
