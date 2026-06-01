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
  <title>Maine Family Law LLM — Local Chat Workbench</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #14213d;
      --muted: #5c667a;
      --line: #d9e1f2;
      --accent: #0f5c8c;
      --accent-2: #0a7f6a;
      --danger: #8a1f11;
      --warn: #8a5a00;
      --shadow: 0 16px 40px rgba(20, 33, 61, 0.12);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0d1117;
        --panel: #151b23;
        --text: #e6edf3;
        --muted: #9ba7b4;
        --line: #30363d;
        --accent: #58a6ff;
        --accent-2: #56d364;
        --danger: #ff7b72;
        --warn: #e3b341;
        --shadow: 0 16px 40px rgba(0, 0, 0, 0.32);
      }
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    header {
      padding: 1.25rem;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    header .wrap, main { max-width: 1180px; margin: 0 auto; }
    h1 { margin: 0 0 0.25rem; font-size: clamp(1.45rem, 2vw, 2rem); }
    .subtitle { color: var(--muted); margin: 0; }
    main { padding: 1rem; display: grid; gap: 1rem; grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr); }
    @media (max-width: 860px) { main { grid-template-columns: 1fr; } }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .card h2 { margin: 0; font-size: 1.1rem; }
    .card-header { padding: 1rem; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; gap: 1rem; align-items: center; }
    .card-body { padding: 1rem; }
    .warning {
      border-left: 5px solid var(--warn);
      background: color-mix(in srgb, var(--warn) 12%, transparent);
      padding: 0.75rem 1rem;
      border-radius: 12px;
      margin-bottom: 1rem;
    }
    label { font-weight: 700; display: block; margin-bottom: 0.4rem; }
    textarea, input, select {
      width: 100%;
      border: 1px solid var(--line);
      background: var(--bg);
      color: var(--text);
      border-radius: 14px;
      padding: 0.85rem;
      font: inherit;
    }
    textarea { min-height: 150px; resize: vertical; }
    button {
      border: 0;
      border-radius: 999px;
      padding: 0.8rem 1rem;
      font-weight: 800;
      cursor: pointer;
      background: var(--accent);
      color: white;
    }
    button.secondary { background: transparent; color: var(--accent); border: 1px solid var(--line); }
    button:disabled { opacity: 0.55; cursor: wait; }
    .row { display: flex; gap: 0.6rem; flex-wrap: wrap; align-items: center; }
    .examples { display: grid; gap: 0.5rem; }
    .example { text-align: left; border-radius: 14px; padding: 0.7rem 0.85rem; }
    .answer {
      white-space: pre-wrap;
      background: var(--bg);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 1rem;
      min-height: 180px;
    }
    .pill { display: inline-flex; align-items: center; gap: 0.35rem; border: 1px solid var(--line); border-radius: 999px; padding: 0.3rem 0.6rem; font-size: 0.85rem; color: var(--muted); }
    .source-card {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 0.8rem;
      margin: 0.65rem 0;
      background: color-mix(in srgb, var(--accent) 5%, transparent);
    }
    .source-card strong { display: block; margin-bottom: 0.2rem; }
    .source-card code { overflow-wrap: anywhere; }
    .muted { color: var(--muted); }
    .status-ok { color: var(--accent-2); font-weight: 800; }
    .status-bad { color: var(--danger); font-weight: 800; }
    footer { max-width: 1180px; margin: 0 auto; padding: 0 1rem 2rem; color: var(--muted); }
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>Maine Family Law LLM</h1>
      <p class="subtitle">Local source-backed chat workbench. Runs on your machine. Review required. Not legal advice.</p>
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
        <label for="question">Question</label>
        <textarea id="question" placeholder="Example: What Maine sources should I check before drafting a parental rights motion?"></textarea>
        <div class="row" style="margin-top: 0.75rem;">
          <button id="ask-button">Ask</button>
          <button id="clear-button" class="secondary">Clear</button>
          <button id="sources-button" class="secondary">Load source list</button>
        </div>
        <h2 style="margin-top: 1.25rem;">Answer</h2>
        <div id="answer" class="answer" aria-live="polite">Ask a question to test the local source-grounded workbench.</div>
      </div>
    </section>

    <aside class="card" aria-labelledby="sources-heading">
      <div class="card-header">
        <h2 id="sources-heading">Sources & shortcuts</h2>
      </div>
      <div class="card-body">
        <p class="muted">Try these starter prompts:</p>
        <div class="examples">
          <button class="secondary example" data-example="What Maine sources should I check for parental rights and responsibilities?">Parental rights sources</button>
          <button class="secondary example" data-example="What should I review before drafting a child support checklist?">Child support checklist</button>
          <button class="secondary example" data-example="What court forms or rules should I check for a family matter?">Forms and rules</button>
          <button class="secondary example" data-example="I need protection from abuse and immediate danger help">Safety/PFA routing</button>
        </div>
        <h2 style="margin-top: 1.25rem;">Retrieved source cards</h2>
        <div id="source-cards" class="muted">No source cards yet.</div>
      </div>
    </aside>
  </main>
  <footer>
    <p>Useful local links: <a href="/docs">Swagger API docs</a> · <a href="/sources">Raw source manifest</a> · <a href="/api/health">Health</a></p>
  </footer>
  <script>
    const question = document.getElementById('question');
    const answer = document.getElementById('answer');
    const sourceCards = document.getElementById('source-cards');
    const askButton = document.getElementById('ask-button');
    const clearButton = document.getElementById('clear-button');
    const sourcesButton = document.getElementById('sources-button');
    const health = document.getElementById('health');

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[char]));
    }

    function renderSources(citations) {
      if (!citations || citations.length === 0) {
        sourceCards.innerHTML = '<span class="muted">No source cards returned.</span>';
        return;
      }
      sourceCards.innerHTML = citations.map((item, index) => {
        const metadata = item.metadata || {};
        const title = metadata.title || metadata.source_id || item.source_id || `Source ${index + 1}`;
        const sourceType = metadata.source_type || 'source';
        const official = metadata.official === true || metadata.official === 'true' ? 'official' : 'unverified/fixture';
        const url = metadata.url || '';
        const snippet = item.snippet || item.text || '';
        return `<article class="source-card" data-source-card="visible">
          <strong>${escapeHtml(title)}</strong>
          <div class="muted">${escapeHtml(sourceType)} · ${escapeHtml(official)}</div>
          <p>${escapeHtml(snippet)}</p>
          ${url ? `<code>${escapeHtml(url)}</code>` : ''}
        </article>`;
      }).join('');
    }

    async function ask() {
      const text = question.value.trim();
      if (!text) {
        answer.textContent = 'Type a Maine family-law question first.';
        return;
      }
      askButton.disabled = true;
      answer.textContent = 'Retrieving sources and composing a grounded answer...';
      sourceCards.textContent = '';
      try {
        const res = await fetch('/ask', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({question: text})
        });
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.detail || res.statusText);
        answer.textContent = payload.answer || JSON.stringify(payload, null, 2);
        renderSources(payload.citations || []);
      } catch (err) {
        answer.textContent = `Local workbench error: ${err.message}`;
        sourceCards.innerHTML = '<span class="status-bad">No response.</span>';
      } finally {
        askButton.disabled = false;
      }
    }

    async function loadSources() {
      sourcesButton.disabled = true;
      try {
        const res = await fetch('/sources');
        const payload = await res.json();
        const cards = payload.map((item) => ({metadata: item, snippet: item.description || item.url || item.id}));
        renderSources(cards);
      } catch (err) {
        sourceCards.innerHTML = `<span class="status-bad">Could not load sources: ${escapeHtml(err.message)}</span>`;
      } finally {
        sourcesButton.disabled = false;
      }
    }

    document.querySelectorAll('[data-example]').forEach((button) => {
      button.addEventListener('click', () => { question.value = button.dataset.example; ask(); });
    });
    askButton.addEventListener('click', ask);
    clearButton.addEventListener('click', () => { question.value = ''; answer.textContent = 'Ask a question to test the local source-grounded workbench.'; sourceCards.textContent = 'No source cards yet.'; });
    sourcesButton.addEventListener('click', loadSources);
    question.addEventListener('keydown', (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') ask();
    });

    fetch('/api/health').then((r) => r.json()).then((payload) => {
      health.textContent = payload.status === 'ok' ? 'local API online' : 'local API status unknown';
      health.className = payload.status === 'ok' ? 'pill status-ok' : 'pill status-bad';
    }).catch(() => {
      health.textContent = 'local API offline';
      health.className = 'pill status-bad';
    });
  </script>
</body>
</html>
"""
