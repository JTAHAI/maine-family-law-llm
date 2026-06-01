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
  <title>Maine Family Law LLM — FOCAF Local Chat Workbench</title>
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
    .input-grid { display: grid; grid-template-columns: 0.9fr 0.9fr 1.2fr; gap: 0.75rem; margin-bottom: 0.75rem; }
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
    .muted { color: var(--muted); }
    .status-ok { color: var(--accent-2); font-weight: 850; }
    .status-bad { color: var(--danger); font-weight: 850; }
    .status-warn { color: var(--warn); font-weight: 850; }
    details { border: 1px solid var(--line); border-radius: 16px; padding: 0.75rem; background: color-mix(in srgb, var(--panel-2) 68%, transparent); }
    details summary { cursor: pointer; font-weight: 850; }
    footer { padding: 0 1rem 2rem; color: var(--muted); }
  </style>
</head>
<body>
  <header>
    <div class="wrap brand-row">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">F</div>
        <div>
          <h1>Maine Family Law LLM</h1>
          <p class="subtitle">Local source-backed chat workbench for FOCAF. Runs on your machine. Review required. Not legal advice.</p>
        </div>
      </div>
      <a class="brand-link" href="https://focaf.jtforme.com" target="_blank" rel="noopener noreferrer">focaf.jtforme.com</a>
    </div>
  </header>
  <main>
    <section class="card" aria-labelledby="chat-heading">
      <div class="card-header">
        <h2 id="chat-heading">Ask Maine Family Law</h2>
        <span id="health" class="pill">checking local API...</span>
      </div>
      <div class="card-body">
        <div class="warning">
          This tool gives legal information from retrieved source snippets. It does not create an attorney-client relationship, and no answer is filing-ready.
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
            </select>
          </div>
          <div>
            <label for="matter-context">Optional context / facts to focus on</label>
            <input id="matter-context" placeholder="Example: parental rights, domestic abuse concern, post-judgment motion" />
          </div>
        </div>
        <label for="question">Question</label>
        <textarea id="question" placeholder="Example: What are Maine's best-interest factors under 19-A M.R.S. § 1653?"></textarea>
        <p class="hint">Press <strong>Enter</strong> to ask. Press <strong>Shift+Enter</strong> for a new line.</p>
        <div class="row" style="margin-top: 0.75rem;">
          <button id="ask-button">Ask</button>
          <button id="copy-button" class="secondary">Copy answer</button>
          <button id="download-button" class="secondary">Download transcript</button>
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
          <button class="secondary example" data-example="How do I use the best-interest factors in my parenting case?">Parent best-interest prep</button>
          <button class="secondary example" data-example="Can a therapist decide whether visits happen?">Therapist / contact boundary</button>
          <button class="secondary example" data-example="What should I gather for child support?">Child support checklist</button>
          <button class="secondary example" data-example="What if I need protection from abuse?">Safety/PFA routing</button>
          <button class="secondary example" data-example="I was served with family court papers. What should I do first?">Served papers</button>
          <button class="secondary example" data-example="How do I organize evidence for family court?">Organize evidence</button>
          <button class="secondary example" data-example="Should I write a court letter for a parent?">Counselor court letter</button>
        </div>
        <details style="margin-top: 1rem;" open>
          <summary>Browse question library</summary>
          <p class="muted">These are starter questions for parents, lawyers, caregivers, counselors, and therapists.</p>
          <label for="library-search">Search starter questions</label>
          <input id="library-search" placeholder="Example: evidence, served papers, therapist, child support" />
          <div id="library-list" class="library-list" style="margin-top: 0.7rem;">Loading question library...</div>
        </details>
        <h2 style="margin-top: 1.25rem;">Retrieved source cards</h2>
        <div id="source-cards" class="muted">No source cards yet.</div>
      </div>
    </aside>
  </main>
  <footer>
    <p>Useful local links: <a href="/docs">Swagger API docs</a> · <a href="/sources">Raw source manifest</a> · <a href="/api/question-library">Question library JSON</a> · <a href="/api/health">Health</a></p>
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
    const clearButton = document.getElementById('clear-button');
    const sourcesButton = document.getElementById('sources-button');
    const health = document.getElementById('health');
    const answerStyle = document.getElementById('answer-style');
    const matterContext = document.getElementById('matter-context');
    const audience = document.getElementById('audience');
    const answerBadges = document.getElementById('answer-badges');
    const libraryList = document.getElementById('library-list');
    const librarySearch = document.getElementById('library-search');
    const messages = [];
    let libraryItems = [];
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
      answerBadges.innerHTML = badges.join('');
    }

    function renderSources(items) {
      if (!items || !items.length) {
        sourceCards.innerHTML = '<span class="muted">No source cards returned.</span>';
        return;
      }
      sourceCards.innerHTML = items.map((item) => {
        const meta = item.metadata || item;
        const title = item.title || meta.title || meta.id || 'Source';
        const url = meta.url || '';
        const sourceType = meta.source_type || meta.source_class || 'source';
        const official = meta.official === false ? 'unofficial' : 'official/source-backed';
        const snippet = item.snippet || meta.description || meta.url || meta.id || '';
        return `<article class="source-card" data-source-card="visible">
          <strong>${escapeHtml(title)}</strong>
          <div class="muted">${escapeHtml(sourceType)} · ${escapeHtml(official)}</div>
          <p>${escapeHtml(snippet)}</p>
          ${url ? `<code>${escapeHtml(url)}</code>` : ''}
        </article>`;
      }).join('');
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
        const context = [matterContext.value.trim(), `Audience: ${audience.value}`].filter(Boolean).join('\n');
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
        renderBadges(payload);
        renderSources(payload.citations || []);
      } catch (err) {
        const message = `Local workbench error: ${err.message}`;
        answer.textContent = message;
        addMessage('assistant', message);
        answerBadges.innerHTML = '<span class="badge bad">error</span><span class="badge warn">server response handled</span>';
        sourceCards.innerHTML = '<span class="status-bad">No response. Check the terminal running START_LOCAL_CHAT.ps1 for details.</span>';
      } finally {
        sending = false;
        askButton.disabled = false;
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
        renderQuestionLibrary(payload);
      } catch (err) {
        libraryList.innerHTML = `<span class="status-bad">Could not load question library: ${escapeHtml(err.message)}</span>`;
      }
    }

    function renderQuestionLibrary(items) {
      const activeAudience = audience.value;
      const needle = (librarySearch?.value || '').toLowerCase().trim();
      const audienceMatches = items.filter((item) => item.audience === activeAudience);
      const searched = audienceMatches.filter((item) => {
        if (!needle) return true;
        const blob = [item.title, item.topic, item.audience, ...(item.prompts || []), ...(item.keywords || [])].join(' ').toLowerCase();
        return blob.includes(needle);
      });
      const display = (searched.length ? searched : audienceMatches.length ? audienceMatches : items).slice(0, 12);
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
      const content = messages.map((msg) => `[${msg.at}] ${msg.role.toUpperCase()}\n${msg.text}`).join('\n\n');
      const blob = new Blob([content || answer.textContent || 'No transcript yet.'], {type: 'text/plain'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'maine-family-law-llm-transcript.txt';
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
    });
    sourcesButton.addEventListener('click', loadSources);
    audience.addEventListener('change', () => renderQuestionLibrary(libraryItems));
    librarySearch?.addEventListener('input', () => renderQuestionLibrary(libraryItems));
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
  </script>
</body>
</html>
"""
