"""Browser UI for non-technical local Maine Family Law LLM testing."""

from __future__ import annotations


def render_local_workbench_html() -> str:
    """Return a dependency-free HTML chat workbench."""

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Maine Family Law LLM - Constitutional Workbench</title>
  <link rel="icon" href="/brand-assets/assets/favicon/favicon.svg" type="image/svg+xml" />
  <link rel="icon" href="/brand-assets/assets/favicon/favicon.ico" sizes="any" />
  <link rel="apple-touch-icon" href="/brand-assets/assets/favicon/apple-touch-icon.png" />
  <link rel="manifest" href="/brand-assets/assets/favicon/site.webmanifest" />
  <meta name="theme-color" content="#1f2933" />
  <meta name="brand-kit" content="focaf_family_law_llm_brand_kit" />
  <link rel="stylesheet" href="/brand-assets/css/tokens.css" />
  <link rel="stylesheet" href="/brand-assets/css/focaf-family-law-llm-theme.css" />
  <style>
    :root {
      --bg: #f3eee5;
      --bg-2: #ece5d9;
      --panel: rgba(255, 252, 247, 0.94);
      --panel-strong: #ffffff;
      --border: rgba(69, 78, 87, 0.18);
      --border-strong: rgba(22, 31, 39, 0.16);
      --ink: #18202a;
      --muted: #5f6b74;
      --deep: #1f2933;
      --accent: #0d5c73;
      --accent-2: #8c5a2b;
      --assistant: #eef5f8;
      --user: #18202a;
      --user-ink: #f7fafc;
      --warning: #8b5e00;
      --danger: #9b2c2c;
      --ok: #1f7a43;
      --shadow: 0 18px 48px rgba(24, 32, 42, 0.12);
      --radius: 8px;
      --font-body: "Segoe UI", Arial, sans-serif;
      --font-display: Georgia, "Times New Roman", serif;
    }
    * { box-sizing: border-box; }
    html, body {
      height: 100%;
      overflow: hidden;
      overflow-x: hidden;
    }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(13,92,115,0.10), transparent 24rem),
        radial-gradient(circle at top right, rgba(140,90,43,0.10), transparent 24rem),
        linear-gradient(180deg, var(--bg), var(--bg-2));
      color: var(--ink);
      font-family: var(--font-body);
      font-size: 15px;
      line-height: 1.45;
    }
    a { color: var(--accent); }
    button, input, select, textarea { font: inherit; }
    button {
      border: 1px solid var(--border-strong);
      border-radius: 8px;
      background: var(--panel-strong);
      color: var(--ink);
      padding: 10px 14px;
      cursor: pointer;
      transition: background-color 120ms ease, border-color 120ms ease, transform 120ms ease;
    }
    button:hover { background: #f8fafb; border-color: rgba(13,92,115,0.36); }
    button:disabled { opacity: 0.66; cursor: wait; }
    .primary-action {
      background: var(--deep);
      color: var(--user-ink);
      min-width: 112px;
      font-weight: 700;
    }
    .primary-action:hover { background: #111922; }
    .secondary {
      background: transparent;
      color: var(--ink);
    }
    label {
      display: block;
      margin: 0 0 6px;
      color: var(--muted);
      font-size: 0.88rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel-strong);
      color: var(--ink);
      padding: 11px 12px;
    }
    textarea {
      min-height: 78px;
      resize: none;
    }
    input:focus, select:focus, textarea:focus, button:focus {
      outline: 2px solid rgba(13,92,115,0.22);
      outline-offset: 1px;
      border-color: rgba(13,92,115,0.40);
    }
    .app-shell {
      width: min(1600px, calc(100vw - 24px));
      height: calc(100vh - 24px);
      margin: 12px auto;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 12px;
      padding: 14px;
      border: 1px solid rgba(31,41,51,0.10);
      border-radius: 12px;
      background: rgba(255, 250, 244, 0.78);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }
    .hero-banner {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 184px;
      gap: 20px;
      padding: 22px 24px 18px;
      border: 1px solid rgba(31,41,51,0.12);
      border-radius: 10px;
      background:
        linear-gradient(135deg, rgba(255,252,247,0.96), rgba(245,238,228,0.92)),
        linear-gradient(90deg, rgba(13,92,115,0.06), rgba(140,90,43,0.04));
      min-height: 0;
    }
    .hero-copy {
      min-width: 0;
      display: grid;
      gap: 8px;
      align-content: center;
    }
    .eyebrow {
      color: var(--accent);
      font-size: 0.86rem;
      font-weight: 700;
      letter-spacing: 0.34em;
      text-transform: uppercase;
    }
    .hero-copy h1 {
      margin: 0;
      font-family: var(--font-display);
      font-size: 56px;
      line-height: 0.94;
      font-weight: 700;
      color: var(--ink);
      max-width: 100%;
      overflow-wrap: anywhere;
    }
    .hero-product {
      margin: 0;
      color: var(--accent);
      font-size: 0.92rem;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }
    .hero-note {
      margin: 0;
      max-width: 980px;
      color: var(--ink);
      font-size: 1rem;
      overflow-wrap: anywhere;
    }
    .hero-support {
      margin: 0;
      color: var(--muted);
      max-width: 920px;
      overflow-wrap: anywhere;
    }
    .hero-seal {
      display: grid;
      justify-items: center;
      align-content: center;
      gap: 10px;
      padding: 14px;
      border-radius: 10px;
      background: linear-gradient(180deg, #1f2933, #273342);
      color: #f7fafc;
      text-align: center;
    }
    .hero-seal img {
      width: 92px;
      height: 92px;
      object-fit: contain;
      filter: drop-shadow(0 10px 24px rgba(0,0,0,0.22));
    }
    .seal-caption {
      color: rgba(247,250,252,0.88);
      font-size: 0.9rem;
      line-height: 1.35;
    }
    .main-stage {
      min-height: 0;
      display: grid;
      grid-template-columns: minmax(0, 2.1fr) minmax(360px, 0.95fr);
      gap: 12px;
      overflow: hidden;
    }
    .panel, .rail-panel {
      border: 1px solid var(--border);
      border-radius: 10px;
      background: var(--panel);
      min-height: 0;
      min-width: 0;
    }
    .chat-panel {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      overflow: hidden;
    }
    .chat-header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      padding: 16px 18px 12px;
      border-bottom: 1px solid var(--border);
      background: rgba(255,255,255,0.75);
    }
    .section-kicker {
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 700;
      letter-spacing: 0.10em;
      text-transform: uppercase;
    }
    .chat-header h2 {
      margin: 4px 0 0;
      font-size: 1.25rem;
      line-height: 1.2;
    }
    .pill, .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: rgba(255,255,255,0.82);
      color: var(--ink);
      padding: 5px 10px;
      font-size: 0.84rem;
      font-weight: 700;
    }
    .badges {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }
    .badge.good { color: var(--ok); }
    .badge.warn { color: var(--warning); }
    .badge.bad { color: var(--danger); }
    .chat-scroll {
      overflow: auto;
      padding: 18px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.82), rgba(249,246,240,0.96)),
        linear-gradient(90deg, rgba(13,92,115,0.03), transparent);
    }
    .chat-seed, .message {
      display: grid;
      grid-template-columns: 52px minmax(0, 1fr) auto;
      gap: 12px;
      align-items: start;
      margin-bottom: 14px;
    }
    .chat-avatar, .chat-seed-icon, .message::before {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      font-weight: 700;
      color: var(--user-ink);
      background: var(--deep);
    }
    .chat-seed-icon {
      background: linear-gradient(180deg, var(--deep), #2f3d4b);
      font-size: 0.92rem;
      letter-spacing: 0.06em;
    }
    .message {
      margin-bottom: 18px;
    }
    .message::before {
      content: "AI";
      font-size: 0.92rem;
      letter-spacing: 0.06em;
    }
    .message.user::before {
      content: "YOU";
      background: linear-gradient(180deg, #47515b, #2e3740);
      font-size: 0.76rem;
    }
    .message-bubble {
      padding: 14px 16px;
      border: 1px solid var(--border);
      border-radius: 16px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .assistant-bubble {
      background: var(--assistant);
      color: var(--ink);
    }
    .user-bubble {
      background: var(--user);
      color: var(--user-ink);
      border-color: rgba(24,32,42,0.08);
    }
    .message-bubble strong {
      display: block;
      margin-bottom: 6px;
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .message-time, .chat-time {
      color: var(--muted);
      font-size: 0.82rem;
      white-space: nowrap;
      padding-top: 6px;
    }
    #transcript.transcript {
      min-height: 0;
    }
    #transcript.transcript:empty::after {
      content: "No messages yet.";
      color: var(--muted);
    }
    .composer {
      border-top: 1px solid var(--border);
      background: rgba(255,255,255,0.86);
      padding: 14px 18px 18px;
    }
    .composer-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: end;
    }
    .composer-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-top: 10px;
    }
    .composer-meta {
      color: var(--muted);
      font-size: 0.9rem;
    }
    .composer-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }
    .right-rail {
      min-height: 0;
      overflow: auto;
      display: grid;
      gap: 12px;
      align-content: start;
      padding-right: 2px;
    }
    .rail-panel {
      padding: 14px;
      overflow: hidden;
    }
    .rail-title {
      margin: 0 0 12px;
      color: var(--ink);
      font-size: 0.95rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .control-grid, .mini-grid, .library-list, .examples {
      display: grid;
      gap: 10px;
    }
    .controls-panel .rail-action {
      width: 100%;
      margin-top: 12px;
    }
    .answer, #handoff-panel, #source-inspector, .status-strip {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(255,255,255,0.82);
      padding: 12px;
      white-space: pre-wrap;
      word-break: break-word;
    }
    #answer {
      min-height: 140px;
    }
    #source-inspector {
      margin-top: 10px;
      min-height: 96px;
    }
    .status-strip {
      color: var(--muted);
      margin-top: 10px;
    }
    .muted, .hint {
      color: var(--muted);
    }
    .examples button, .library-list button {
      text-align: left;
      width: 100%;
    }
    .source-card {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(255,255,255,0.9);
      padding: 12px;
      margin-bottom: 10px;
    }
    .source-card strong {
      display: block;
      margin-bottom: 4px;
    }
    .source-card-meta {
      display: grid;
      gap: 4px;
      margin: 8px 0;
      font-size: 0.86rem;
      color: var(--muted);
    }
    .row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .status-bad { color: var(--danger); font-weight: 700; }
    .status-warn { color: var(--warning); font-weight: 700; }
    .status-ok { color: var(--ok); font-weight: 700; }
    .footerbar {
      display: grid;
      grid-template-columns: auto 1fr auto auto;
      gap: 14px;
      align-items: center;
      min-height: 44px;
      padding: 0 14px;
      border: 1px solid rgba(31,41,51,0.12);
      border-radius: 10px;
      background: rgba(255,255,255,0.78);
      color: var(--muted);
      font-size: 0.88rem;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    @media (max-width: 1240px) {
      .hero-copy h1 { font-size: 46px; }
      .main-stage { grid-template-columns: minmax(0, 1fr) 340px; }
    }
    @media (max-width: 1040px) {
      body {
        overflow-y: auto;
        overflow-x: hidden;
      }
      .app-shell {
        width: calc(100vw - 24px);
        max-width: 100%;
        height: auto;
        min-height: calc(100vh - 24px);
        margin: 6px;
      }
      .hero-banner {
        grid-template-columns: 1fr;
      }
      .main-stage {
        grid-template-columns: 1fr;
      }
      .right-rail {
        overflow: visible;
      }
      .footerbar {
        grid-template-columns: 1fr;
        gap: 6px;
        padding: 10px 14px;
      }
    }
    @media (max-width: 720px) {
      .hero-copy h1 {
        font-size: 24px;
        line-height: 1.02;
      }
      .app-shell { padding: 10px; gap: 10px; }
      .hero-banner { padding: 18px 16px; }
      .chat-header {
        display: grid;
        gap: 10px;
        justify-content: stretch;
      }
      .chat-header .pill {
        justify-self: start;
      }
      .chat-header, .chat-scroll, .composer, .rail-panel { padding-left: 14px; padding-right: 14px; }
      .composer-row { grid-template-columns: 1fr; }
      .composer-toolbar {
        display: grid;
        gap: 10px;
      }
      .composer-actions {
        justify-content: stretch;
      }
      .composer-actions button {
        flex: 1 1 auto;
      }
      .chat-seed, .message {
        grid-template-columns: 1fr;
      }
      .message-time, .chat-time {
        padding-top: 0;
      }
    }
  </style>
</head>
<body data-brand-kit="focaf_family_law_llm_brand_kit" data-ui-pass="v2.08">
  <div class="app-shell" id="focaf-brand-shell" data-ui-version="2.08.0-modern-constitutional-chat" data-brand-assets="/brand-assets">
    <header class="hero-banner" id="focaf-brand-hero" data-brand-kit-mounted="expected">
      <div class="hero-copy">
        <div class="eyebrow">WE THE PEOPLE</div>
        <h1>... establish JUSTICE ...</h1>
        <p class="hero-product">Maine Family Law LLM</p>
        <p class="hero-note">Justice does not belong to one institution or one profession, it belongs to the People which these institutions of government are meant to serve; it is Public.</p>
        <p class="hero-support">A local-first, source-grounded evidence and review workbench for Maine family-law records, filing questions, and serious source-cited review. Review required. Not legal advice.</p>
      </div>
      <div class="hero-seal">
        <img src="/brand-assets/assets/logo/focaf-family-law-llm-mark.svg" alt="Maine Family Law LLM mark" />
        <div class="seal-caption">Local-only runtime<br/>Source-cited when found</div>
      </div>
    </header>

    <div class="main-stage">
      <section class="chat-panel panel" aria-labelledby="chat-heading" data-chat-layout="primary">
        <div class="chat-header">
          <div>
            <div class="section-kicker">Modern AI Chat</div>
            <h2 id="chat-heading">Constitutional research workbench</h2>
          </div>
          <span id="health" class="pill">checking local API...</span>
        </div>
        <div class="chat-scroll" aria-label="Research chat messages">
          <div class="chat-seed">
            <div class="chat-seed-icon">AI</div>
            <div class="message-bubble assistant-bubble">
              <strong>Maine Family Law LLM</strong>
              Ask about filings, appeals, service, safety, parenting, evidence organization, record review, or source gaps. This workbench stays local, returns citations, and says not found in indexed corpus when it cannot ground an answer.
            </div>
            <div class="chat-time">Local</div>
          </div>
          <div id="transcript" class="transcript" aria-live="polite">No messages yet.</div>
        </div>
        <div class="composer" data-fixed-composer="true">
          <label class="sr-only" for="question">Question</label>
          <div class="composer-row">
            <textarea id="question" placeholder="Ask a grounded question about a Maine family-law record, filing, review issue, or source gap."></textarea>
            <button id="ask-button" class="primary-action">Ask</button>
          </div>
          <div class="composer-toolbar">
            <div class="composer-meta">Press <strong>Enter</strong> to submit. Use <strong>Shift+Enter</strong> for a new line.</div>
            <div class="composer-actions">
              <button id="clear-button" class="secondary">Clear</button>
              <button id="copy-button" class="secondary">Copy answer</button>
              <button id="download-button" class="secondary">Save transcript</button>
              <button id="download-json-button" class="secondary" style="display:none">Download JSON</button>
            </div>
          </div>
        </div>
      </section>

      <aside class="right-rail" aria-label="Research controls and evidence">
        <section class="rail-panel controls-panel">
          <div class="rail-title">Session controls</div>
          <div class="control-grid">
            <div>
              <label for="audience">Role</label>
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
                <option value="plain_language">Plain language</option>
                <option value="checklist">Checklist</option>
                <option value="source_first">Source-first</option>
                <option value="intake">Intake triage</option>
                <option value="professional_boundary">Professional boundary</option>
                <option value="source_card_table">Source-card table</option>
                <option value="questions_to_ask">Questions to ask</option>
                <option value="missing_information">Missing information</option>
              </select>
            </div>
            <div>
              <label for="topic-filter">Topic filter</label>
              <select id="topic-filter">
                <option value="all">All topics</option>
              </select>
            </div>
            <div>
              <label for="matter-context">Focus context</label>
              <input id="matter-context" placeholder="Parental rights, appeal, PFA, support..." />
            </div>
          </div>
          <button id="sources-button" class="secondary rail-action">Load source list</button>
        </section>

        <section class="rail-panel">
          <div class="rail-title">Latest answer</div>
          <div id="answer-badges" class="badges"><span class="badge">waiting</span></div>
          <div id="answer" class="answer" aria-live="polite">Ask a question to test the local source-grounded workbench.</div>
        </section>

        <section class="rail-panel">
          <div class="rail-title">Source cards</div>
          <div id="source-cards" class="muted">No source cards yet.</div>
          <div id="source-inspector" class="muted">Select "Inspect source" on a source card to view full local metadata.</div>
          <button id="copy-sources-bottom" class="secondary" type="button" style="margin-top:10px">Copy source cards</button>
        </section>

        <section class="rail-panel">
          <div class="rail-title">Reviewer handoff</div>
          <div id="handoff-panel" class="answer" aria-live="polite">Ask a question to see missing facts, follow-up questions, and reviewer handoff metadata.</div>
          <div id="runtime-diagnostics" class="status-strip" data-runtime-diagnostics="loading">Runtime diagnostics loading. Expected UI: v2.08 modern constitutional chat workbench.</div>
        </section>

        <section class="rail-panel">
          <div class="rail-title">Prompt packs</div>
          <label for="prompt-pack-select">Starter pack</label>
          <select id="prompt-pack-select">
            <option value="auto">Best pack for selected role</option>
          </select>
          <div id="prompt-pack-list" class="library-list" style="margin-top:10px">Loading starter prompt packs...</div>
        </section>

        <section class="rail-panel">
          <div class="rail-title">Prompt shortcuts</div>
          <div class="examples">
            <button class="secondary example" data-example="What are Maine's best-interest factors under 19-A M.R.S. § 1653?">Best-interest factors</button>
            <button class="secondary example" data-example="How do I use the best-interest factors in my parenting case?">Parent best-interest prep</button>
            <button class="secondary example" data-example="Can a therapist decide whether visits happen?">Therapist / contact boundary</button>
            <button class="secondary example" data-example="What should I gather for child support?">Child support checklist</button>
            <button class="secondary example" data-example="What if I need protection from abuse?">Safety / PFA routing</button>
            <button class="secondary example" data-example="I was served with family court papers. What should I do first?">Served papers</button>
            <button class="secondary example" data-example="How do I organize evidence for family court?">Organize evidence</button>
            <button class="secondary example" data-example="What court handles appeals?">Appeals routing</button>
          </div>
        </section>

        <section class="rail-panel">
          <div class="rail-title">Question library</div>
          <div class="mini-grid">
            <div>
              <label for="library-search">Search starter questions</label>
              <input id="library-search" placeholder="evidence, served papers, therapist, child support" />
            </div>
            <div>
              <label for="library-topic-search">Quick topic</label>
              <input id="library-topic-search" placeholder="safety_pfa, parental_rights, appeal" />
            </div>
          </div>
          <div id="library-list" class="library-list" style="margin-top:10px">Loading question library...</div>
        </section>
      </aside>
    </div>

    <div class="sr-only" id="compatibility-markers">Local source-backed chat workbench · Download transcript · Retrieved source cards · Brand assets loaded from /brand-assets · Best-interest factors · UI v2.08 modern constitutional chat workbench · /api/question-topics · /api/missing-information-prompts · fetch('/ask') · /brand-assets/assets/logo/focaf-family-law-llm-horizontal.svg · /brand-assets/assets/social/focaf-family-law-llm-social-card.svg</div>
    <div class="sr-only" id="viewport-proof">viewport proof pending</div>
    <img class="sr-only" src="/brand-assets/assets/logo/focaf-family-law-llm-horizontal.svg" alt="Maine Family Law LLM horizontal logo compatibility asset" />
    <div class="footerbar">
      <span>Local-only</span>
      <span>Source-cited when found&nbsp;&nbsp;|&nbsp;&nbsp;Review required&nbsp;&nbsp;|&nbsp;&nbsp;Not legal advice</span>
      <span>Maine Family Law LLM</span>
      <strong>UI v2.08 modern constitutional chat workbench.</strong>
    </div>
  </div>
  <script>
    const question = document.getElementById('question');
    const answer = document.getElementById('answer');
    const transcript = document.getElementById('transcript');
    const chatScroll = document.querySelector('.chat-scroll');
    const sourceCards = document.getElementById('source-cards');
    const askButton = document.getElementById('ask-button');
    const copyButton = document.getElementById('copy-button');
    const downloadButton = document.getElementById('download-button');
    const downloadJsonButton = document.getElementById('download-json-button');
    const clearButton = document.getElementById('clear-button');
    const sourcesButton = document.getElementById('sources-button');
    const copySourcesButton = document.getElementById('copy-sources-bottom');
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
    const viewportProof = document.getElementById('viewport-proof');
    window.__MFL_WORKBENCH_UI_VERSION = '2.08.0-modern-constitutional-chat';
    const messages = [];
    let libraryItems = [];
    let promptPacks = [];
    let lastPayload = null;
    let lastSources = [];
    let sending = false;

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[char]));
    }

    function formatLocalTime(value) {
      try {
        return new Date(value).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
      } catch (err) {
        return 'Local';
      }
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
        <p><strong>Matched item:</strong> ${escapeHtml(handoff.matched_library_id || 'none')} | <strong>Topic:</strong> ${escapeHtml(handoff.matched_topic || 'none')} | <strong>Sources:</strong> ${escapeHtml(handoff.source_card_count)}</p>
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
          <div class="muted">${escapeHtml(sourceType)} | ${escapeHtml(official)}</div>
          <div class="source-card-meta">
            <span><strong>Citation:</strong> ${escapeHtml(citation || 'not provided')}</span>
            <span><strong>Version:</strong> ${escapeHtml(version || 'verify current source')}</span>
            <span><strong>Effective:</strong> ${escapeHtml(effective || 'verify')}</span>
            <span><strong>ID:</strong> ${escapeHtml(sourceId || 'source')}</span>
          </div>
          <p>${escapeHtml(snippet)}</p>
          ${url ? `<code>${escapeHtml(url)}</code>` : ''}
          <div class="row" style="margin-top: 10px;"><button class="secondary" data-copy-source="${escapeHtml(sourceId)}">Copy source card</button><button class="secondary" data-inspect-source="${escapeHtml(sourceId)}">Inspect source</button></div>
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
      const at = new Date().toISOString();
      messages.push({role, text, at});
      transcript.innerHTML = messages.map((msg) => {
        const speaker = msg.role === 'user' ? 'You' : 'Maine Family Law LLM';
        const bubbleClass = msg.role === 'user' ? 'user-bubble' : 'assistant-bubble';
        return `<div class="message ${escapeHtml(msg.role)}">
          <div class="message-bubble ${bubbleClass}"><strong>${speaker}</strong><div>${escapeHtml(msg.text)}</div></div>
          <div class="message-time">${formatLocalTime(msg.at)}</div>
        </div>`;
      }).join('');
      if (chatScroll) {
        chatScroll.scrollTop = chatScroll.scrollHeight;
      }
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
      question.value = '';
      question.dataset.lastSubmitCleared = 'true';
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
        runtimeDiagnostics.innerHTML = `<strong>Runtime diagnostics:</strong> ${escapeHtml(payload.version)} | ${escapeHtml(payload.ui_version)} | Enter submit: ${payload.enter_to_submit ? 'on' : 'off'} | Appeals routing fix: ${payload.appeals_routing_fix ? 'on' : 'off'} | Brand assets mounted: ${payload.brand_assets_mounted ? 'yes' : 'no'} | Branding: ${escapeHtml(payload.branding || 'unknown')}`;
      } catch (err) {
        runtimeDiagnostics.dataset.runtimeDiagnostics = 'failed';
        runtimeDiagnostics.innerHTML = `<strong>Runtime diagnostics failed:</strong> ${escapeHtml(err.message)}. If the footer is not v2.08, stop the old server and restart from the current repo.`;
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
          <strong>${escapeHtml(row.title)}</strong><br><span class="muted">${escapeHtml(row.topic)} | ${escapeHtml(row.recommended_style || 'checklist')}</span>
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
          <strong>${escapeHtml(item.title)}</strong><br><span class="muted">${escapeHtml(item.audience)} | ${escapeHtml(item.topic)}</span>
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
    copySourcesButton?.addEventListener('click', async () => {
      await navigator.clipboard.writeText(JSON.stringify(lastSources || [], null, 2));
      copySourcesButton.textContent = 'Source cards copied';
      setTimeout(() => { copySourcesButton.textContent = 'Copy source cards'; }, 1100);
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
      sourceInspector.textContent = 'Select "Inspect source" on a source card to view full local metadata.';
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
    if (viewportProof) {
      window.addEventListener('load', () => {
        viewportProof.textContent = `innerWidth=${window.innerWidth}; scrollWidth=${document.documentElement.scrollWidth}; bodyClientWidth=${document.body.clientWidth}`;
      });
    }
    loadQuestionLibrary();
    loadPromptPacks();
    loadRuntimeDiagnostics();
    // v2.08 marker: modern_constitutional_chat, we_the_people_branding, chat_primary_layout, fixed_composer_outside_scroll, brand_kit_assets, appeals_routing_fix, enter_submit_clears_input, reviewer_handoff, local_chat_transcript_v3, organize_evidence_starter
  </script>
</body>
</html>
"""
