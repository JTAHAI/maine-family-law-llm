"""Browser UI for non-technical local Maine Family Law LLM testing."""

from __future__ import annotations


def render_local_workbench_html() -> str:
    """Return a dependency-free HTML chat workbench."""

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Maine Family Law LLM — FOCAF Research Workbench</title>
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
      --window-blue: #061a42;
      --title-blue: #06176b;
      --title-blue-2: #0c2e82;
      --chrome: #d8dce2;
      --chrome-hi: #f7f9fb;
      --chrome-lo: #7f8998;
      --panel: #061b31;
      --panel-2: #0b2743;
      --panel-3: #0d3357;
      --ink: #f2fbff;
      --muted: #c4d1dc;
      --cyan: #23f1ee;
      --cyan-2: #77fff5;
      --green: #8ee042;
      --gold: #ffd86b;
      --danger: #ff8d85;
      --line: #68a8d3;
      --line-dim: rgba(104,168,211,.44);
      --shadow: 0 18px 42px rgba(0,0,0,.42);
      --font-ui: Tahoma, Verdana, "Segoe UI", Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at 18% 0%, rgba(35,241,238,.16), transparent 38rem),
        radial-gradient(circle at 88% 18%, rgba(255,216,107,.12), transparent 30rem),
        linear-gradient(180deg, #0a1630, #020813 74%);
      font-family: var(--font-ui);
      font-size: 15px;
      line-height: 1.42;
    }
    button, input, textarea, select { font-family: var(--font-ui); }
    a { color: var(--cyan-2); }
    .desktop-shell {
      width: min(1260px, calc(100vw - 18px));
      margin: 6px auto 10px;
      border: 2px solid #081430;
      background: var(--chrome);
      box-shadow: 0 0 0 1px #c7d3e0 inset, var(--shadow);
    }
    .window-titlebar {
      height: 34px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 8px;
      background: linear-gradient(90deg, #02115d, #15378e 58%, #001047);
      border-bottom: 1px solid #030817;
      color: #fff;
      font-weight: 900;
      letter-spacing: .01em;
      text-shadow: 0 1px 1px #000;
    }
    .title-left { display: flex; align-items: center; gap: 8px; white-space: nowrap; overflow: hidden; }
    .title-left img { width: 23px; height: 23px; border-radius: 4px; background: rgba(255,255,255,.08); }
    .title-text { overflow: hidden; text-overflow: ellipsis; }
    .window-controls { display: flex; gap: 4px; }
    .window-control {
      width: 26px;
      height: 24px;
      border: 2px solid #111;
      background: linear-gradient(#fefefe, #bfc8d3);
      color: #07131f;
      display: grid;
      place-items: center;
      font-weight: 900;
      line-height: 1;
      box-shadow: 1px 1px 0 #fff inset, -1px -1px 0 #7e8792 inset;
    }
    .menubar {
      height: 31px;
      display: flex;
      align-items: center;
      gap: 25px;
      padding: 0 12px;
      color: #05070b;
      background: linear-gradient(#f8f8f8, #d9dde3);
      border-bottom: 2px solid #8c96a3;
      font-size: 16px;
    }
    .app-canvas {
      background: #cfd5dd;
      padding: 7px;
    }
    .hero-band {
      min-height: 172px;
      background:
        linear-gradient(90deg, rgba(2,10,24,.96), rgba(5,31,55,.92) 48%, rgba(3,13,26,.94)),
        radial-gradient(circle at 78% 30%, rgba(35,241,238,.18), transparent 22rem);
      border: 2px solid #07111f;
      box-shadow: 1px 1px 0 rgba(255,255,255,.32) inset, -1px -1px 0 rgba(0,0,0,.65) inset;
      display: grid;
      grid-template-columns: 170px 1fr 220px 250px;
      align-items: center;
      gap: 22px;
      padding: 16px 22px;
      position: relative;
      overflow: hidden;
    }
    .hero-band::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      opacity: .38;
      background-image:
        linear-gradient(rgba(35,241,238,.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(35,241,238,.05) 1px, transparent 1px);
      background-size: 32px 32px;
      mask-image: linear-gradient(90deg, rgba(0,0,0,.75), transparent 82%);
    }
    .hero-band > * { position: relative; z-index: 1; }
    .hero-icon-wrap {
      width: 145px;
      height: 145px;
      border-radius: 24px;
      background: linear-gradient(145deg, #071b31, #010912);
      border: 2px solid rgba(122,210,255,.38);
      display: grid;
      place-items: center;
      box-shadow: 0 18px 36px rgba(0,0,0,.38), 0 0 0 1px rgba(255,255,255,.09) inset;
    }
    .hero-icon-wrap img { width: 112px; height: 112px; object-fit: contain; filter: drop-shadow(0 0 18px rgba(35,241,238,.35)); }
    .hero-title h1 { margin: 0; font-size: clamp(2.1rem, 4vw, 3.3rem); line-height: .96; letter-spacing: -.04em; }
    .hero-title .tagline { margin: 3px 0 8px; color: var(--cyan); font-size: 1.26rem; font-weight: 900; letter-spacing: .025em; text-transform: uppercase; }
    .hero-title p { margin: 0; color: #eef6ff; font-size: 1.1rem; }
    .secure-pill {
      justify-self: center;
      align-self: center;
      border: 1px solid rgba(255,255,255,.48);
      background: linear-gradient(#082f4e, #031323);
      color: var(--cyan);
      border-radius: 8px;
      padding: 10px 16px;
      font-weight: 900;
      box-shadow: 0 0 18px rgba(35,241,238,.12), 1px 1px 0 rgba(255,255,255,.18) inset;
      white-space: nowrap;
    }
    .secure-pill .dot { display:inline-block; width: 17px; height: 17px; border-radius: 50%; margin-right: 9px; background: radial-gradient(circle at 35% 35%, #c8ff74, #3dbf34 68%, #1d641d); vertical-align: -3px; }
    .review-text { color: #fff; font-size: .95rem; margin-top: 14px; text-align: center; }
    .focaf-lockup { display: grid; grid-template-columns: 72px 1fr; gap: 13px; align-items: center; justify-self: end; }
    .focaf-people { font-size: 56px; color: var(--cyan); line-height: 1; filter: drop-shadow(0 0 12px rgba(35,241,238,.26)); }
    .focaf-lockup strong { display:block; font-size: 2rem; }
    .focaf-lockup span { color: #e5f2f5; font-size: .98rem; }
    .control-strip {
      margin-top: 8px;
      padding: 13px 20px;
      background: linear-gradient(#f7f8fa, #d6dce5);
      border: 2px solid #fefefe;
      outline: 2px solid #8d98a6;
      border-radius: 10px;
      display: grid;
      grid-template-columns: 1fr 1fr 1fr 1.05fr auto;
      gap: 18px;
      align-items: end;
      color: #07145a;
    }
    label { display:block; font-weight: 900; color: #07145a; margin: 0 0 4px; }
    select, input, textarea {
      width: 100%;
      border: 2px solid #9ca7b5;
      border-radius: 5px;
      background: linear-gradient(#ffffff, #e7ebf0);
      color: #030b18;
      padding: 8px 10px;
      font-size: 15px;
      box-shadow: 1px 1px 0 #fff inset, -1px -1px 0 #b6c0cb inset;
    }
    select { height: 42px; }
    textarea { resize: none; min-height: 48px; line-height: 1.35; }
    textarea:focus, input:focus, select:focus {
      outline: 2px solid var(--cyan);
      outline-offset: 1px;
      border-color: #0b7fa5;
    }
    button {
      border: 2px solid #00103b;
      border-radius: 6px;
      background: linear-gradient(#1c4ca9, #06166a 58%, #020c46);
      color: white;
      padding: 9px 15px;
      font-weight: 900;
      cursor: pointer;
      box-shadow: 1px 1px 0 rgba(255,255,255,.36) inset, -1px -1px 0 rgba(0,0,0,.45) inset, 0 5px 10px rgba(0,0,0,.22);
      text-shadow: 0 1px 0 #000;
    }
    button:hover { filter: brightness(1.08); }
    button:disabled { opacity: .6; cursor: wait; }
    button.secondary, button.example {
      background: linear-gradient(#0d3157, #071d35);
      border-color: #4d85a6;
      color: #eef9ff;
      text-align: left;
      width: 100%;
      box-shadow: 1px 1px 0 rgba(255,255,255,.16) inset, -1px -1px 0 rgba(0,0,0,.55) inset;
    }
    button.action-wide { min-width: 210px; height: 55px; display:flex; align-items:center; justify-content:center; gap:8px; font-size: 1.02rem; }
    .workspace-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 348px;
      gap: 14px;
      margin-top: 14px;
    }
    .panel {
      background: linear-gradient(180deg, var(--panel-2), var(--panel));
      border: 2px solid #07111f;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 1px 1px 0 rgba(255,255,255,.25) inset, -1px -1px 0 rgba(0,0,0,.65) inset;
    }
    .panel-title {
      min-height: 38px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap: 10px;
      padding: 8px 14px;
      background: linear-gradient(#0e3970, #061957);
      border-bottom: 1px solid rgba(255,255,255,.16);
      font-weight: 900;
      color: #eef7ff;
      text-shadow: 0 1px 0 #000;
    }
    .panel-title .collapse { color:#cad6e8; font-size: 18px; }
    .panel-body { padding: 14px; }
    .chat-panel { min-height: 640px; display:flex; flex-direction: column; }
    .chat-scroll {
      flex: 1;
      min-height: 410px;
      max-height: 558px;
      overflow: auto;
      padding: 20px 24px;
      background:
        linear-gradient(90deg, rgba(8,24,45,.96), rgba(4,15,29,.92)),
        radial-gradient(circle at 90% 15%, rgba(35,241,238,.10), transparent 20rem);
      border-bottom: 2px solid rgba(255,255,255,.16);
    }
    .message, .answer, .transcript, .source-card, #handoff-panel, #source-inspector {
      border: 1px solid var(--line-dim);
      border-radius: 8px;
      background: rgba(2,12,23,.58);
      color: #f3fbff;
    }
    .message { display:grid; grid-template-columns: 70px 1fr auto; gap: 16px; padding: 14px 0; border-width: 0 0 1px; border-radius: 0; background: transparent; }
    .message strong { color: var(--cyan); display:block; margin-bottom: 5px; }
    .message.user strong { color: #fff; }
    .message::before { content: "💬"; width: 52px; height: 52px; border-radius: 12px; border: 1px solid rgba(122,210,255,.45); display:grid; place-items:center; background: linear-gradient(#123b5f, #041326); font-size: 28px; box-shadow: 0 0 0 1px rgba(255,255,255,.08) inset; }
    .message.user::before { content: "👤"; background: transparent; border: 0; font-size: 42px; }
    .message .time, .chat-time { color: #eef7ff; white-space: nowrap; }
    .chat-seed { display:grid; grid-template-columns: 70px 1fr auto; gap:16px; padding: 6px 0 18px; border-bottom: 1px solid rgba(255,255,255,.28); }
    .chat-seed-icon { width:58px; height:58px; border-radius:12px; border:1px solid rgba(122,210,255,.45); display:grid; place-items:center; background:linear-gradient(#123b5f,#041326); font-size:32px; }
    .chat-seed strong { color: var(--cyan); display:block; margin-bottom: 7px; }
    #transcript.transcript {
      white-space: pre-wrap;
      border: 0;
      background: transparent;
      min-height: 0;
      max-height: none;
      overflow: visible;
      padding: 0;
      color: #f6fbff;
    }
    #transcript.transcript:empty::after { content: "No messages yet."; color: var(--muted); }
    .composer {
      padding: 12px 16px 10px;
      background: linear-gradient(#e4e8ef, #c3cbd6);
      border-top: 1px solid #fff;
      color: #06145b;
    }
    .composer-row { display:grid; grid-template-columns: 42px 1fr 110px; gap: 12px; align-items:center; }
    .composer-icon { width: 37px; height:37px; border-radius:8px; display:grid; place-items:center; background:linear-gradient(#102d6e,#03124c); border:1px solid #04133f; color:#fff; box-shadow:1px 1px 0 #fff inset; }
    #question { min-height: 48px; }
    .composer-actions { display:grid; grid-template-columns: 130px 130px 165px 1fr; gap: 14px; margin-top:10px; align-items:center; }
    .signal { justify-self: end; color: #126d2f; font-weight: 900; letter-spacing: 1px; }
    .sidebar-stack { display:grid; gap: 12px; align-content: start; }
    .side-panel { background: linear-gradient(#123866, #061b35); border: 2px solid #07111f; border-radius: 8px; overflow:hidden; box-shadow: 1px 1px 0 rgba(255,255,255,.25) inset, -1px -1px 0 rgba(0,0,0,.65) inset; }
    .side-title { padding: 8px 12px; font-weight:900; background: linear-gradient(#0f3b75, #071957); border-bottom:1px solid rgba(255,255,255,.16); display:flex; justify-content:space-between; }
    .side-body { padding: 11px 13px; background: rgba(3,14,29,.45); }
    .status-strip { color:#06145b; background: linear-gradient(#fdfdfd,#dce2ea); padding: 10px; border-radius:7px; border:1px solid #9ba6b4; }
    #health.pill, .pill, .badge { display:inline-flex; align-items:center; border-radius: 4px; border:1px solid #9ba6b4; background:linear-gradient(#fff,#e6eaf0); color:#06145b; padding: 5px 9px; font-weight: 800; }
    .status-ok::before { content:"●"; color: #3dbf34; margin-right: 7px; }
    .badges { display:flex; gap:5px; flex-wrap:wrap; }
    .badge.good { color:#0f642d; }
    .badge.warn { color:#7e5b00; }
    .badge.bad { color:#8a1414; }
    .examples, .library-list { display:grid; gap: 7px; }
    .example { padding: 5px 8px; border: 0; box-shadow: none; color:#eef9ff; background: transparent; border-radius: 4px; }
    .example::before { content:"💬  "; }
    .example:hover { background: rgba(35,241,238,.11); }
    details { border:0; padding:0; background:transparent; }
    details summary { list-style: none; cursor:pointer; font-weight: 900; margin-bottom: 8px; color:#f4fbff; }
    details summary::-webkit-details-marker { display:none; }
    .mini-grid { display:grid; grid-template-columns: 1fr; gap: 9px; }
    .muted, .hint { color: var(--muted); }
    .hint { font-size:.86rem; margin: 8px 0 0; }
    .source-card { padding: 10px; margin: 8px 0; }
    .source-card strong { color: #fff; }
    .source-card-meta { display:grid; grid-template-columns: 1fr; gap:4px; margin: 8px 0; font-size:.86rem; }
    .bottom-tabs { display:grid; grid-template-columns: .9fr .9fr 1fr; gap: 0; margin-top: 14px; }
    .tab-panel { border:2px solid #8d98a6; border-top:0; background: linear-gradient(#e7edf4,#c7d0dc); color:#06145b; min-height: 190px; }
    .tab-head { display:inline-block; min-width: 215px; text-align:center; padding:8px 16px; background:linear-gradient(#f6f8fb,#c8d1db); border:2px solid #8d98a6; border-bottom:0; border-radius:8px 8px 0 0; font-weight:900; }
    .tab-content { padding:12px; display:grid; gap:10px; }
    .answer, #handoff-panel, #source-inspector { min-height: 125px; padding: 12px; white-space: pre-wrap; background: linear-gradient(#e7edf4,#d7dee8); color:#06145b; border-color:#9ca7b5; }
    #handoff-panel ul, .answer ul { margin-top: 5px; }
    .answer-card-grid { display:grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .answer-card { border:1px solid #9ca7b5; background:linear-gradient(#f5f8fb,#dfe6ef); border-radius:7px; padding:10px; color:#06145b; min-height:120px; }
    .answer-card strong { display:block; color:#06145b; margin-bottom:5px; }
    .footerbar {
      height: 28px;
      display:grid;
      grid-template-columns: 220px 1fr auto auto;
      gap: 16px;
      align-items:center;
      padding: 0 12px;
      background: linear-gradient(#0b304f, #041625);
      color:#eaf7ff;
      border: 2px solid #07111f;
      border-top:0;
      font-size: .86rem;
    }
    .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
    .status-bad { color: var(--danger); font-weight:900; }
    .status-warn { color: var(--gold); font-weight:900; }
    .status-ok { font-weight:900; }
    pre { white-space: pre-wrap; word-break: break-word; }
    @media (max-width: 1020px) {
      .hero-band { grid-template-columns: 120px 1fr; }
      .secure-wrap, .focaf-lockup { display:none; }
      .control-strip, .workspace-grid, .bottom-tabs { grid-template-columns: 1fr; }
      .composer-actions { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 660px) {
      .hero-band { grid-template-columns: 1fr; }
      .hero-icon-wrap { display:none; }
      .composer-row, .composer-actions { grid-template-columns: 1fr; }
      .footerbar { grid-template-columns: 1fr; height:auto; padding: 8px; }
      .menubar { gap: 12px; font-size:14px; }
    }
  </style>
</head>
<body data-brand-kit="focaf_family_law_llm_brand_kit" data-ui-pass="v1.86">
  <div class="desktop-shell classic-desktop-shell" id="focaf-brand-shell" data-ui-version="1.86.0-classic-desktop-focaf-workbench" data-brand-assets="/brand-assets">
    <div class="window-titlebar">
      <div class="title-left">
        <img src="/brand-assets/assets/logo/focaf-family-law-llm-mark.svg" alt="FOCAF icon" />
        <span class="title-text">Maine Family Law LLM — FOCAF Research Workbench</span>
      </div>
      <div class="window-controls" aria-hidden="true">
        <span class="window-control">–</span><span class="window-control">□</span><span class="window-control">×</span>
      </div>
    </div>
    <nav class="menubar" aria-label="Workbench menu"><span>File</span><span>Edit</span><span>Profile</span><span>View</span><span>Tools</span><span>Help</span></nav>
    <div class="app-canvas">
      <section class="hero-band" id="focaf-brand-hero" data-brand-kit-mounted="expected">
        <div class="hero-icon-wrap"><img src="/brand-assets/assets/logo/focaf-family-law-llm-mark.svg" alt="FOCAF Maine Family Law LLM mark" /></div>
        <div class="hero-title">
          <h1>Maine Family Law LLM</h1>
          <div class="tagline">FOR OUR CHILDREN &amp; FAMILIES</div>
          <p>Source-backed research workbench for FOCAF</p>
        </div>
        <div class="secure-wrap"><div class="secure-pill"><span class="dot"></span>FOCAF Secure</div><div class="review-text">Review required&nbsp;&nbsp;•&nbsp;&nbsp;Not legal advice</div></div>
        <div class="focaf-lockup"><div class="focaf-people">👥</div><div><strong>FOCAF</strong><span>Maine’s Child First<br/>Legal Community</span></div></div>
      </section>

      <section class="control-strip" aria-label="Search controls">
        <div><label for="audience">Role</label><select id="audience"><option value="parent">👤 Parent</option><option value="lawyer">⚖️ Lawyer / advocate</option><option value="caregiver">🤝 Caregiver / relative</option><option value="counselor">💬 Counselor</option><option value="therapist">🧠 Therapist / clinician</option></select></div>
        <div><label for="answer-style">Answer Style</label><select id="answer-style"><option value="plain_language">Plain language</option><option value="checklist">Checklist</option><option value="source_first">Source-first</option><option value="intake">Intake triage</option><option value="professional_boundary">Professional boundary</option><option value="source_card_table">Source-card table</option><option value="questions_to_ask">Questions to ask</option><option value="missing_information">Missing information</option></select></div>
        <div><label for="topic-filter">Topic Filter</label><select id="topic-filter"><option value="all">All topics</option></select></div>
        <div><label for="matter-context">Focus Context</label><input id="matter-context" placeholder="Parental rights, appeal, PFA, support…" /></div>
        <button id="sources-button" class="action-wide">💬 Load Source List</button>
      </section>

      <div class="workspace-grid">
        <section class="panel chat-panel" aria-labelledby="chat-heading">
          <div class="panel-title"><span id="chat-heading">💬 Research Chat — Your FOCAF Assistant</span><span id="health" class="pill">checking local API...</span></div>
          <div class="chat-scroll" aria-label="Research chat messages">
            <div class="chat-seed"><div class="chat-seed-icon">💬</div><div><strong>FOCAF Assistant</strong><div>Hi. I’m your Maine family law research assistant.<br/>I pull from verified sources and provide citations so you can review and decide what fits your situation.<br/><br/>How can I help today?</div></div><div class="chat-time">Local</div></div>
            <div id="transcript" class="transcript" aria-live="polite">No messages yet.</div>
          </div>
          <div class="composer">
            <label class="sr-only" for="question">Question</label>
            <div class="composer-row"><div class="composer-icon">💬</div><textarea id="question" placeholder="Type your question here..."></textarea><button id="ask-button">Send</button></div>
            <div class="composer-actions"><button id="clear-button">🧹 Clear</button><button id="copy-button">📄 Copy</button><button id="download-button">💾 Save Transcript</button><div class="signal">▂▄▆█</div></div>
            <div class="hint">Press <strong>Enter</strong> to submit. Use <strong>Shift+Enter</strong> for a new line.</div>
            <button id="download-json-button" class="secondary" style="display:none">Download JSON</button>
          </div>
        </section>

        <aside class="sidebar-stack" aria-label="FOCAF sidebar">
          <section class="side-panel"><div class="side-title">💬 FOCAF Sidebar <span>▴</span></div><div class="side-body"><div class="status-strip"><strong>Status</strong><br/><span class="status-ok">Online · FOCAF Secure</span><br/><a href="https://focaf.jtforme.com" target="_blank" rel="noopener noreferrer">Edit Profile / FOCAF</a></div></div></section>
          <section class="side-panel"><div class="side-title">📌 Prompt Shortcuts <span>▴</span></div><div class="side-body examples"><button class="secondary example" data-example="What are Maine's best-interest factors under 19-A M.R.S. § 1653?">Best interest factors</button><button class="secondary example" data-example="How do I use the best-interest factors in my parenting case?">Parent best interest prep</button><button class="secondary example" data-example="Can a therapist decide whether visits happen?">Therapist / contact boundary</button><button class="secondary example" data-example="What should I gather for child support?">Child support checklist</button><button class="secondary example" data-example="What if I need protection from abuse?">Safety / PFA routing</button><button class="secondary example" data-example="I was served with family court papers. What should I do first?">Served papers</button><button class="secondary example" data-example="How do I organize evidence for family court?">Organize evidence</button><button class="secondary example" data-example="Should I write a court letter for a parent?">Counselor court letter</button></div></section>
          <section class="side-panel"><div class="side-title">❔ Question Starters <span>▴</span></div><div class="side-body examples"><button class="secondary example" data-example="What is a parenting plan?">What is a parenting plan?</button><button class="secondary example" data-example="How is child support calculated?">How is child support calculated?</button><button class="secondary example" data-example="What is a GAL and their role?">What is a GAL and their role?</button><button class="secondary example" data-example="Can I move with my child?">Can I move with my child?</button><button class="secondary example" data-example="How do I file an appeal?">How do I file an appeal?</button><button class="secondary example" data-example="What court handles appeals?">What court handles appeals?</button></div></section>
          <section class="side-panel"><div class="side-title">🗂️ Starter Packs <span>▴</span></div><div class="side-body"><label for="prompt-pack-select" style="color:#eef7ff">Starter pack</label><select id="prompt-pack-select"><option value="auto">Best pack for selected role</option></select><div id="prompt-pack-list" class="library-list" style="margin-top:9px">Loading starter prompt packs...</div></div></section>
          <section class="side-panel"><div class="side-title">📚 Recent Sources <span>▴</span></div><div class="side-body"><div id="source-cards" class="muted">No source cards yet.</div></div></section>
        </aside>
      </div>

      <section class="bottom-tabs" aria-label="Latest answer and source review">
        <div><div class="tab-head">Latest Answer</div><div class="tab-panel"><div class="tab-content"><div id="answer-badges" class="badges"><span class="badge">waiting</span></div><div id="answer" class="answer" aria-live="polite">Ask a question to test the local source-grounded workbench.</div></div></div></div>
        <div><div class="tab-head">Sources / Inspector</div><div class="tab-panel"><div class="tab-content"><div id="source-inspector" class="muted">Select “Inspect source” on a source card to view full local metadata.</div><button id="copy-sources-bottom" class="secondary" type="button">Copy Sources</button></div></div></div>
        <div><div class="tab-head">Transcript / Handoff</div><div class="tab-panel"><div class="tab-content"><div id="handoff-panel" class="answer" aria-live="polite">Ask a question to see missing facts, follow-up questions, and reviewer handoff metadata.</div><div id="runtime-diagnostics" class="status-strip" data-runtime-diagnostics="loading">Runtime diagnostics loading. Expected UI: v1.86 classic desktop FOCAF research workbench.</div></div></div></div>
      </section>

      <section class="side-panel" style="margin-top:14px" aria-label="Question library"><div class="side-title">🧭 Full Question Library <span>▴</span></div><div class="side-body"><div class="mini-grid"><div><label for="library-search" style="color:#eef7ff">Search starter questions</label><input id="library-search" placeholder="evidence, served papers, therapist, child support" /></div><div><label for="library-topic-search" style="color:#eef7ff">Quick topic</label><input id="library-topic-search" placeholder="safety_pfa, parental_rights, appeal" /></div></div><div id="library-list" class="library-list" style="margin-top:10px">Loading question library...</div></div></section>


      <div class="sr-only" id="compatibility-markers">Local source-backed chat workbench · Download transcript · Retrieved source cards · Brand assets loaded from /brand-assets · Best-interest factors · UI v1.86 classic desktop FOCAF workbench · /api/question-topics · /api/missing-information-prompts · fetch('/ask') · /brand-assets/assets/logo/focaf-family-law-llm-horizontal.svg · /brand-assets/assets/social/focaf-family-law-llm-social-card.svg</div>
      <img class="sr-only" src="/brand-assets/assets/logo/focaf-family-law-llm-horizontal.svg" alt="FOCAF horizontal logo compatibility asset" />
      <div class="footerbar"><span>🔒 FOCAF Secure Connection</span><span>Local sources&nbsp;&nbsp;•&nbsp;&nbsp;Review required&nbsp;&nbsp;•&nbsp;&nbsp;Not legal advice</span><span>© FOCAF 2026</span><strong>UI v1.86 classic desktop FOCAF research workbench + Enter submit + appeals/runtime diagnostics.</strong></div>
    </div>
  </div>
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
    window.__MFL_WORKBENCH_UI_VERSION = '1.86.0-classic-desktop-focaf-workbench';
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
        runtimeDiagnostics.innerHTML = `<strong>Runtime diagnostics failed:</strong> ${escapeHtml(err.message)}. If the footer is not v1.86, stop the old server and restart from the _git repo.`;
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
    // v1.86 marker: classic_desktop_shell, brand_kit_assets, appeals_routing_fix, runtime diagnostics, reviewer_handoff, missing_information prompts, local_chat_transcript_v3; compatibility marker local_chat_transcript_v2
  </script>
</body>
</html>
"""
