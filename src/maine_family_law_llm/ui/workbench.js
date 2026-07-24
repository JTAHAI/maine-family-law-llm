
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
    const clearDraftButton = document.getElementById('clear-draft-button');
    const stopButton = document.getElementById('stop-button');
    const childImpactLens = document.getElementById('child-impact-lens');
    const sourcesButton = document.getElementById('sources-button');
    const copySourcesButton = document.getElementById('copy-sources-bottom');
    const health = document.getElementById('health');
    const sessionSummary = document.getElementById('session-summary');
    const answerStyle = document.getElementById('answer-style');
    const searchMode = document.getElementById('search-mode');
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
    const corpusSelect = document.getElementById('corpus-select');
    const activateCorpusButton = document.getElementById('activate-corpus-button');
    const refreshCorpusButton = document.getElementById('refresh-corpus-button');
    const corpusStatus = document.getElementById('corpus-status');
    const inventoryStatus = document.getElementById('inventory-status');
    const ocrPrimaryAction = document.getElementById('ocr-primary-action');
    const ocrActionButton = document.getElementById('ocr-action-button');
    const ocrOverlay = document.getElementById('ocr-overlay');
    const ocrChoiceStatus = document.getElementById('ocr-choice-status');
    const ocrCandidateCount = document.getElementById('ocr-candidate-count');
    const ocrEngineStatus = document.getElementById('ocr-engine-status');
    const startOcrButton = document.getElementById('start-ocr-button');
    const installOcrPrerequisitesButton = document.getElementById('install-ocr-prerequisites-button');
    const openOcrInstallPageButton = document.getElementById('open-ocr-install-page-button');
    const recheckOcrButton = document.getElementById('recheck-ocr-button');
    const declineOcrButton = document.getElementById('decline-ocr-button');
    const cancelOcrChoiceButton = document.getElementById('cancel-ocr-choice-button');
    const reviewInventoryButton = document.getElementById('review-inventory-button');
    const rebuildIndexButton = document.getElementById('rebuild-index-button');
    const deleteIndexButton = document.getElementById('delete-index-button');
    const printableSearch = document.getElementById('printable-search');
    const printableSearchButton = document.getElementById('printable-search-button');
    const printableResults = document.getElementById('printable-results');
    const viewportProof = document.getElementById('viewport-proof');
    const welcomeButton = document.getElementById('welcome-button');
    const copyLinkButton = document.getElementById('copy-link-button');
    const focusModeButton = document.getElementById('focus-mode-button');
    const helpButton = document.getElementById('help-button');
    const newChatButton = document.getElementById('new-chat-button');
    const welcomeOverlay = document.getElementById('welcome-overlay');
    const helpOverlay = document.getElementById('help-overlay');
    const dismissWelcomeButton = document.getElementById('dismiss-welcome-button');
    const closeHelpButton = document.getElementById('close-help-button');
    const toast = document.getElementById('toast');
    const commandPaletteButton = document.getElementById('command-palette-button');
    const commandPalette = document.getElementById('command-palette');
    const commandSearch = document.getElementById('command-search');
    const commandList = document.getElementById('command-list');
    const closeCommandPaletteButton = document.getElementById('close-command-palette');
    const justiceOverlay = document.getElementById('justice-overlay');
    const closeJusticeButton = document.getElementById('close-justice-button');
    const constitutionalIdentity = document.getElementById('constitutional-identity');
    const constitutionalPopover = document.getElementById('constitutional-popover');
    const evidenceDrawer = document.getElementById('evidence-drawer');
    const closeDrawerButton = document.getElementById('close-drawer-button');
    const drawerBackdrop = document.getElementById('drawer-backdrop');
    const moreStartersButton = document.getElementById('more-starters-button');
    const activeMatterLabel = document.getElementById('active-matter-label');
    const matterShortcutButton = document.getElementById('matter-shortcut-button');
    const matterButton = document.getElementById('matter-button');
    const privacyButton = document.getElementById('privacy-button');
    const privacyOverlay = document.getElementById('privacy-overlay');
    const closePrivacyButton = document.getElementById('close-privacy-button');
    const shortcutsOverlay = document.getElementById('shortcuts-overlay');
    const closeShortcutsButton = document.getElementById('close-shortcuts-button');
    const buildOverlay = document.getElementById('build-overlay');
    const closeBuildButton = document.getElementById('close-build-button');
    const footerVersion = document.getElementById('footer-version');
    const footerPrivacyButton = document.getElementById('footer-privacy-button');
    const localStatusPopover = document.getElementById('local-status-popover');
    const closeLocalStatusPopoverButton = document.getElementById('close-local-status-popover');
    const closeConstitutionalPopoverButton = document.getElementById('close-constitutional-popover');
    const localStatusCopy = document.getElementById('local-status-copy');
    const commandResultsStatus = document.getElementById('command-results-status');
    const drawerActiveCorpus = document.getElementById('drawer-active-corpus');
    const drawerCorpusCount = document.getElementById('drawer-corpus-count');
    const drawerOcrPercent = document.getElementById('drawer-ocr-percent');
    const drawerOcrProgress = document.querySelector('.v5-progress i');
    const drawerRefreshCorpus = document.getElementById('drawer-refresh-corpus');
    const quickNewCorpus = document.getElementById('quick-new-corpus');
    const quickOpenWorkspace = document.getElementById('quick-open-workspace');
    const quickExportChat = document.getElementById('quick-export-chat');
    const openAllStarters = document.getElementById('open-all-starters');
    window.__MFL_WORKBENCH_UI_VERSION = window.__MFL_WORKBENCH_UI_VERSION || document.getElementById('focaf-brand-shell')?.dataset.uiVersion || 'unknown';
    const startupParams = new URLSearchParams(window.location.search);
    function createLocalSessionId() {
      return (window.crypto && typeof window.crypto.randomUUID === 'function')
        ? window.crypto.randomUUID()
        : `mfl-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }
    let localSessionId = createLocalSessionId();
    const messages = [];
    let libraryItems = [];
    let promptPacks = [];
    let lastPayload = null;
    let lastSources = [];
    let lastHandoffSources = [];
    let sending = false;
    let activeRequestController = null;
    let toastTimer = 0;
    let ocrPollTimer = 0;
    let ocrInstallPollTimer = 0;
    let ocrJobRunning = false;
    let ocrManualInstallUrl = 'https://tesseract-ocr.github.io/tessdoc/Downloads.html';
    const overlayReturnFocus = new WeakMap();

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[char]));
    }

    function hasPrivateRecordSources() {
      return lastSources.some((item) => String(item?.metadata?.source_lane || 'legal_authority') === 'private_record');
    }

    function confirmFullLocalExport() {
      const mode = String(lastPayload?.search_mode || lastPayload?.metadata?.search_mode || '').toLowerCase();
      const mayContainPrivateMatterContent = hasPrivateRecordSources() || mode === 'my_records' || mode === 'both';
      if (!mayContainPrivateMatterContent) return true;
      return window.confirm('This full local export includes private-record excerpts and may include sensitive information. Continue only if you intend to store or share the complete local transcript securely.');
    }

    function formatLocalTime(value) {
      try {
        return new Date(value).toLocaleTimeString([], {hour: 'numeric', minute: '2-digit'});
      } catch (err) {
        return 'Local';
      }
    }

    function showToast(message) {
      if (!toast || !message) return;
      toast.hidden = false;
      toast.textContent = message;
      toast.classList.add('visible');
      window.clearTimeout(toastTimer);
      toastTimer = window.setTimeout(() => {
        toast.classList.remove('visible');
        window.setTimeout(() => {
          toast.hidden = true;
        }, 160);
      }, 1500);
    }

    async function fetchJson(url, options = {}) {
      const res = await fetch(url, options);
      const text = await res.text();
      let payload = null;
      if (text) {
        try {
          payload = JSON.parse(text);
        } catch (err) {
          const preview = text.replace(/\s+/g, ' ').slice(0, 360);
          throw new Error(`${res.status} ${res.statusText || 'response'}: ${preview || 'non-JSON response'}`);
        }
      } else {
        payload = {};
      }
      if (!res.ok) {
        const detail = payload && typeof payload.detail === 'object' ? payload.detail : null;
        const message = payload.message || detail?.message || payload.detail || payload.recovery_hint || res.statusText || 'request failed';
        throw new Error(String(message));
      }
      return payload;
    }

    function selectedLabel(select) {
      if (!select) return '';
      const option = select.options?.[select.selectedIndex];
      return option ? option.textContent.trim() : '';
    }

    function currentQuestionOrFallback() {
      const draft = question.value.trim();
      if (draft) return draft;
      const latestUser = [...messages].reverse().find((item) => item.role === 'user');
      return latestUser ? latestUser.text : '';
    }

    function syncContextBar() {
      if (!sessionSummary) return;

      const corpusLabel =
        corpusSelect && corpusSelect.value
          ? selectedLabel(corpusSelect).split(' (')[0]
          : 'General Maine law';

      const modeLabel =
        selectedLabel(searchMode) || 'Maine law';

      document.querySelectorAll('[data-search-mode]').forEach((button) => {
        const selected = button.dataset.searchMode === (searchMode?.value || 'maine_law');
        button.classList.toggle('is-selected', selected);
        button.setAttribute('aria-checked', selected ? 'true' : 'false');
      });

      const parts = [
        modeLabel,
        selectedLabel(audience) || 'Parent',
        selectedLabel(answerStyle) || 'Plain language',
        corpusLabel,
        'Local-only',
      ];

      sessionSummary.textContent = parts.filter(Boolean).join(' · ');
      if (activeMatterLabel) activeMatterLabel.textContent = corpusLabel;
      if (drawerActiveCorpus) drawerActiveCorpus.textContent = corpusLabel;
      const matterLabel = `Open matter setup. Current matter: ${corpusLabel}`;
      matterShortcutButton?.setAttribute('aria-label', matterLabel);
      matterButton?.setAttribute('aria-label', matterLabel);
    }

    function overlayFocusableElements(element) {
      if (!element) return [];
      return Array.from(element.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], details > summary, [tabindex]:not([tabindex="-1"])'
      )).filter((node) => !node.hidden && node.getAttribute('aria-hidden') !== 'true');
    }

    function openOverlay(element) {
      if (!element) return;
      if (element.hidden) overlayReturnFocus.set(element, document.activeElement);
      element.hidden = false;
      element.setAttribute('aria-hidden', 'false');
      const focusable = overlayFocusableElements(element);
      window.setTimeout(() => focusable[0]?.focus(), 10);
    }

    function closeOverlay(element) {
      if (!element || element.hidden) return;
      const returnTarget = overlayReturnFocus.get(element) || newChatButton || focusModeButton;
      // A focused descendant must leave before aria-hidden is applied.
      if (returnTarget && typeof returnTarget.focus === 'function') {
        returnTarget.focus();
      }
      element.hidden = true;
      element.setAttribute('aria-hidden', 'true');
      overlayReturnFocus.delete(element);
    }

    function renderParagraphBlocks(text) {
      const blocks = String(text || '').split(/\n\s*\n/).map((block) => block.trim()).filter(Boolean);
      if (!blocks.length) return '<p>No answer was returned.</p>';
      return blocks.map((block) => {
        const lines = block.split('\n').map((line) => line.trim()).filter(Boolean);
        const isList = lines.length > 1 && lines.every((line) => /^(\[\s?\]|[-*]|\d+\.)\s+/.test(line));
        if (isList) {
          return `<ul class="answer-list">${lines.map((line) => `<li>${escapeHtml(line.replace(/^(\[\s?\]|[-*]|\d+\.)\s+/, ''))}</li>`).join('')}</ul>`;
        }
        return `<p>${lines.map((line) => escapeHtml(line)).join('<br>')}</p>`;
      }).join('');
    }

    function renderStructuredSection(title, values, className = '') {
      const rows = Array.isArray(values) ? values.filter(Boolean) : [];
      if (!rows.length) return '';
      return `<section class="answer-section ${className}"><h3>${escapeHtml(title)}</h3><ul class="answer-list">${rows.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul></section>`;
    }

    function renderCriticalDates(items) {
      const rows = Array.isArray(items) ? items.filter((item) => item && item.raw) : [];
      if (!rows.length) return '';
      const labels = {
        service_date: 'Service date',
        hearing_date: 'Hearing or court date',
        response_or_filing_deadline: 'Possible response or filing deadline',
        mentioned_date: 'Date mentioned'
      };
      return `<section class="answer-section deadline-summary"><h3>Dates and deadlines I heard</h3><ul class="answer-list">${rows.map((item) => {
        const label = labels[item.kind] || String(item.kind || 'Date').replaceAll('_', ' ');
        const normalized = item.normalized_date ? ` · normalized locally as ${item.normalized_date}` : '';
        const basis = item.normalization_basis === 'year_inferred_from_reference_date'
          ? ' · year inferred from the local date'
          : (item.normalization_basis === 'relative_to_local_reference_date' ? ' · calculated from the local date' : '');
        const reviewFlags = Array.isArray(item.review_flags) && item.review_flags.length
          ? ` · review: ${item.review_flags.map((value) => String(value).replaceAll('_', ' ')).join(', ')}`
          : '';
        return `<li><strong>${escapeHtml(label)}:</strong> ${escapeHtml(item.raw)}${escapeHtml(normalized)}${escapeHtml(basis)}${escapeHtml(reviewFlags)}</li>`;
      }).join('')}</ul><p class="muted">Confirm every date against the complete official paper or docket. This extraction is not a deadline calculation.</p></section>`;
    }

    function renderPrintableSuggestions(items) {
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) return '';
      return `<section class="answer-section printable-suggestions"><h3>Helpful family printables</h3><p class="muted">Optional family resources, not legal authority or official court forms.</p>${rows.map((item) => `<article class="printable-suggestion"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.why_relevant || item.description || '')}</p><div class="row"><span class="badge">${escapeHtml(item.category || 'family printable')}</span><span class="badge">${escapeHtml(item.page_count || 0)} pages</span><button class="secondary compact-action" data-open-printable="${escapeHtml(item.document_id)}" type="button">Open or print locally</button></div></article>`).join('')}</section>`;
    }

    function renderRecordGroups(groups) {
      const rows = Array.isArray(groups) ? groups : [];
      if (!rows.length) return '<p class="muted">No unique indexed documents matched this search.</p>';
      return `<section class="answer-section record-results" aria-label="Matching local records"><h3>Matching local records</h3>${rows.map((group, index) => {
        const pages = Array.isArray(group.pages) ? group.pages.filter((page) => Number(page) > 0).sort((a, b) => Number(a) - Number(b)) : [];
        const snippets = Array.isArray(group.snippets) ? group.snippets.slice(0, 12) : [];
        const token = escapeHtml(String(group.source_token || ''));
        const basename = escapeHtml(String(group.basename || 'Record'));
        const documentType = escapeHtml(String(group.document_type || 'record').replaceAll('_', ' '));
        const matches = Number(group.match_count || 0);
        const detailId = `record-matches-${index}`;
        return `<article class="record-result-card"><div class="record-result-head"><div><strong>${basename}</strong><p class="muted">${documentType} · ${matches} matching ${matches === 1 ? 'row' : 'rows'}${pages.length ? ` · pages ${escapeHtml(pages.join(', '))}` : ''}</p></div><div class="record-result-actions"><button class="secondary compact-action" data-open-record="${token}" type="button" aria-label="Open PDF for ${basename}">Open PDF</button>${pages.slice(0, 6).map((page) => `<button class="secondary compact-action" data-open-record-page="${token}" data-page="${escapeHtml(page)}" type="button" aria-label="Open ${basename} at page ${escapeHtml(page)}">Open at page ${escapeHtml(page)}</button>`).join('')}</div></div><details id="${detailId}" class="record-match-details"><summary>Show all matches in this document</summary><ul class="answer-list">${snippets.map((snippet) => `<li>${escapeHtml(String(snippet))}</li>`).join('')}</ul></details></article>`;
      }).join('')}</section>`;
    }

    function bindRecordOpenActions(container = answer) {
      container.querySelectorAll('[data-open-record], [data-open-record-page]').forEach((button) => button.addEventListener('click', () => {
        const token = button.dataset.openRecord || button.dataset.openRecordPage || '';
        const page = Number(button.dataset.page || 0);
        if (!/^[a-f0-9]{64}$/i.test(token)) return;
        const suffix = page > 0 ? `#page=${encodeURIComponent(String(page))}` : '';
        window.open(`/api/records/open/${encodeURIComponent(token)}?page=${encodeURIComponent(String(page || 0))}${suffix}`, '_blank', 'noopener,noreferrer');
      }));
    }

    function renderLatestAnswer(payload) {
      if (payload?.response_kind === 'corpus_inventory') {
        const summary = payload.inventory_summary || {};
        const sourceTypes = Object.entries(summary.source_types || {}).map(([key, value]) => `${key}: ${value}`).join(' · ');
        const parserStatuses = Object.entries(summary.parser_statuses || {}).map(([key, value]) => `${key}: ${value}`).join(' · ');
        answer.innerHTML = `<div class="answer-body corpus-inventory-result">
          <section class="answer-section"><h3>Indexed corpus inventory</h3>${renderParagraphBlocks(String(payload.answer || 'Inventory loaded.'))}</section>
          <section class="answer-section"><h3>Inventory breakdown</h3><p><strong>Top-level records:</strong> ${escapeHtml(summary.top_level_records || 0)} · <strong>Total index rows:</strong> ${escapeHtml(summary.records || 0)} · <strong>Searchable records:</strong> ${escapeHtml(summary.searchable_records || 0)}</p><p><strong>Source types:</strong> ${escapeHtml(sourceTypes || 'none')}</p><p><strong>Parser status:</strong> ${escapeHtml(parserStatuses || 'none')}</p><p><strong>OCR candidates:</strong> ${escapeHtml(summary.ocr_candidate_documents || 0)} document(s), ${escapeHtml(summary.ocr_candidate_pages || 0)} page(s)</p><p><button class="inline-source-link" data-open-evidence="records" type="button">Open first ${escapeHtml(payload.source_card_count || 0)} indexed record cards</button></p><p class="muted">This is an inventory of the selected private matter, not a Maine-law answer.</p></section>
        </div>`;
        answer.querySelector('[data-open-evidence]')?.addEventListener('click', () => setDrawerOpen(true, 'evidence'));
        return;
      }
      if (payload?.direct_record_search) {
        const summary = payload.search_summary || {};
        const target = summary.search_target || payload?.intake?.search_target || payload?.question || '';
        const uniqueDocuments = Number(summary.unique_document_count || (payload.record_groups || []).length || summary.document_count || 0);
        const countLine = summary.result_count !== undefined
          ? `${summary.result_count} matching index ${summary.result_count === 1 ? 'row' : 'rows'} across ${uniqueDocuments} unique ${uniqueDocuments === 1 ? 'document' : 'documents'}`
          : `${payload.source_card_count || 0} source card(s)`;
        answer.innerHTML = `<div class="answer-body compact-search-result">
          <section class="answer-section"><h3>Local record search</h3><p class="intake-heard"><strong>Searched for:</strong> ${escapeHtml(target)}</p>${renderParagraphBlocks(String(payload.answer || 'Search completed.'))}</section>
          <section class="answer-section source-lane-summary"><p><strong>Results:</strong> ${escapeHtml(countLine)}.</p><p class="muted">Private matter records only. No Maine-law search was substituted, and a text match is not a legal conclusion.</p></section>
          ${renderRecordGroups(payload.record_groups)}
        </div>`;
        bindRecordOpenActions();
        return;
      }
      const structured = payload?.structured_answer || null;
      if (structured) {
        const lawSources = structured.maine_law_sources || [];
        const recordSources = structured.private_record_sources || [];
        const safety = structured.safety_flags || {};
        const intake = structured.intake || payload.intake || {};
        const intakeDetails = [
          intake.procedural_posture && intake.procedural_posture !== 'unknown' ? `Stage: ${intake.procedural_posture.replaceAll('_', ' ')}` : '',
          Array.isArray(intake.issues) && intake.issues.length ? `Issues: ${intake.issues.slice(0, 3).map((value) => value.replaceAll('_', ' ')).join(', ')}` : '',
          Array.isArray(intake.requested_actions) && intake.requested_actions.length ? `Requested action: ${intake.requested_actions.slice(0, 2).map((value) => value.replaceAll('_', ' ')).join(', ')}` : '',
          intake.attention_level && intake.attention_level !== 'routine' ? `Attention: ${intake.attention_level.replaceAll('_', ' ')}` : ''
        ].filter(Boolean).join(' · ');
        const intakeBlock = structured.intake_label
          ? `<section class="answer-section intake-summary"><h3>What I heard</h3><p><strong>${escapeHtml(structured.intake_label)}</strong>${intake.user_goal ? ` — ${escapeHtml(intake.user_goal)}` : ''}</p>${intakeDetails ? `<p class="muted">${escapeHtml(intakeDetails)}</p>` : ''}${intake.context_inherited ? `<p class="status-warn"><strong>Conversation continuity used:</strong> ${escapeHtml(intake.continuity_reason || 'Only structured routing labels from the prior turn were reused.')}</p>` : ''}<p class="muted">Routing summary only—not a finding of fact or law.</p></section>`
          : '';
        const securityWarnings = payload?.security_warnings || payload?.metadata?.security_warnings || [];
        const securityBlock = securityWarnings.length
          ? `<section class="answer-section security-warning"><h3>Untrusted instruction warning</h3><ul class="answer-list">${securityWarnings.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul></section>`
          : '';
        const groundingIntegrity = structured.grounding_integrity || payload?.grounding_integrity || payload?.metadata?.grounding_integrity || {};
        const retrievalDiagnostics = payload?.retrieval_diagnostics || payload?.metadata?.retrieval_diagnostics || {};
        const retrievalConfidence = payload?.retrieval_confidence || payload?.metadata?.retrieval_confidence || retrievalDiagnostics.confidence || '';
        const retrievalSection = retrievalDiagnostics.schema_version
          ? `<section class="answer-section retrieval-integrity"><h3>Retrieval quality</h3><p><strong>Confidence:</strong> ${escapeHtml(String(retrievalConfidence || 'not assessed').replaceAll('_', ' '))} · ${escapeHtml(retrievalDiagnostics.distinct_source_count || 0)} distinct source(s) · ${escapeHtml(retrievalDiagnostics.official_result_count || 0)} official result(s)</p>${retrievalDiagnostics.recognized_references?.length ? `<p><strong>Recognized reference:</strong> ${escapeHtml(retrievalDiagnostics.recognized_references.map((row) => row.display).join(', '))}</p>` : ''}<p class="muted">${escapeHtml(retrievalDiagnostics.review_warning || 'Retrieval rank is a source-discovery aid, not a legal correctness or currentness determination.')}</p></section>`
          : '';
        const supportIntegrity = structured.answer_support_integrity || payload?.answer_support_integrity || payload?.metadata?.answer_support_integrity || {};
        const supportBlockers = Array.isArray(supportIntegrity.blockers) ? supportIntegrity.blockers : [];
        const supportWarnings = Array.isArray(supportIntegrity.warnings) ? supportIntegrity.warnings : [];
        const supportSection = Number(supportIntegrity.candidate_legal_claim_count || 0)
          ? `<section class="answer-section claim-support-review"><h3>Claim-to-source review</h3><p><strong>Status:</strong> ${escapeHtml(String(supportIntegrity.status || 'review required').replaceAll('_', ' '))} · ${escapeHtml(supportIntegrity.candidate_legal_claim_count || 0)} candidate legal claim(s) checked</p>${supportBlockers.length ? `<strong>Blockers</strong><ul class="answer-list">${supportBlockers.map((row) => `<li>${escapeHtml(String(row).replaceAll('_', ' '))}</li>`).join('')}</ul>` : ''}${supportWarnings.length ? `<ul class="answer-list">${supportWarnings.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>` : ''}<p class="muted">This lexical check is a review aid, not a legal-entailment or filing-readiness certification.</p></section>`
          : '';
        const freshnessWarnings = Array.isArray(groundingIntegrity.warnings) ? groundingIntegrity.warnings : [];
        const currentLawStatus = String(groundingIntegrity.current_law_status || 'not assessed').replaceAll('_', ' ');
        answer.innerHTML = `<div class="answer-body structured-answer">
          ${intakeBlock}
          ${securityBlock}
          ${renderCriticalDates(structured.critical_dates || intake.critical_dates)}
          <section id="answer-section-main" class="answer-section"><h3>What this means</h3>${renderParagraphBlocks(structured.what_this_means)}</section>
          ${retrievalSection}
          ${supportSection}
          ${renderStructuredSection('What to do right now', structured.what_to_do_right_now, safety.immediate_safety_concern ? 'safety-answer' : '')}
          ${renderStructuredSection('Your next three steps', structured.next_three_steps)}
          ${renderStructuredSection('What to gather', structured.what_to_gather)}
          ${renderStructuredSection('What may be missing', structured.what_may_be_missing)}
          ${renderStructuredSection('Questions that would sharpen the next answer', structured.suggested_questions)}
          ${renderStructuredSection('What this may mean for your child', structured.child_impact_lens, 'child-impact-answer')}
          <section id="answer-section-grounding" class="answer-section source-lane-summary"><h3>Where this information came from</h3>
            <p><strong>Maine-law research:</strong> ${structured.lane_grounding?.legal_authority ? 'source-backed' : 'not established by a retrieved legal source'} · <button class="inline-source-link" data-open-evidence="law" type="button">${lawSources.length} Law source${lawSources.length === 1 ? '' : 's'}</button></p>
            <p><strong>Matter records:</strong> ${structured.lane_grounding?.private_record ? 'source-backed' : 'not established by a selected matter record'} · <button class="inline-source-link" data-open-evidence="records" type="button">${recordSources.length} Record source${recordSources.length === 1 ? '' : 's'}</button></p>
            <p><strong>Current-law status:</strong> ${escapeHtml(currentLawStatus)}${groundingIntegrity.current_law_verified ? ' · verified for all retrieved legal cards' : ' · live official-source review still required'}</p>
            ${freshnessWarnings.length ? `<ul class="answer-list">${freshnessWarnings.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>` : ''}
            <p class="muted">Private records can support facts about a matter, not statements of law. Legal sources can support law, not disputed family facts. Source presence alone is not claim verification or filing readiness.</p>
          </section>
          ${renderPrintableSuggestions(payload.family_printables)}
          ${renderStructuredSection('When to get human help', structured.when_to_get_human_help)}
        </div>`;
        answer.querySelectorAll('[data-open-evidence]').forEach((button) => button.addEventListener('click', () => setDrawerOpen(true, 'evidence')));
        answer.querySelectorAll('[data-open-printable]').forEach((button) => button.addEventListener('click', () => window.open(`/api/printables/${encodeURIComponent(button.dataset.openPrintable)}/open`, '_blank', 'noopener,noreferrer')));
        return;
      }
      const responseText = String(payload?.answer || '').trim();
      const metadata = payload?.metadata || {};
      const fallbackStructured = payload?.structured_answer || {};
      const missing = fallbackStructured.what_may_be_missing || metadata.missing_information || [];
      const followups = fallbackStructured.suggested_questions || metadata.follow_up_questions || [];
      const nav = [
        '<a href="#answer-section-main">Answer</a>',
        '<a href="#answer-section-grounding">Grounding</a>',
      ];
      const reviewSection = missing.length || followups.length
        ? `<section id="answer-section-review" class="answer-section">
            <h3>Review next</h3>
            ${missing.length ? `<strong>Missing information</strong><ul class="answer-list">${missing.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>` : ''}
            ${followups.length ? `<strong>Follow-up questions</strong><ul class="answer-list">${followups.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>` : ''}
          </section>`
        : '';
      if (reviewSection) nav.push('<a href="#answer-section-review">Review next</a>');
      const corpusSummary = payload?.corpus_mode === 'active_case_corpus'
        ? `Active case corpus: ${escapeHtml(payload.active_case_label || 'selected case corpus')}`
        : 'General Maine law workbench';
      const failureLine = payload?.failure_class && payload.failure_class !== 'none'
        ? `<p><strong>Failure class:</strong> ${escapeHtml(payload.failure_class)}${payload.recovery_hint ? ` | <strong>Recovery hint:</strong> ${escapeHtml(payload.recovery_hint)}` : ''}</p>`
        : `<p><strong>Failure class:</strong> none${payload.recovery_hint ? ` | <strong>Recovery hint:</strong> ${escapeHtml(payload.recovery_hint)}` : ''}</p>`;
      answer.innerHTML = `<div class="answer-body">
        <div class="answer-callout">${escapeHtml(responseText.split(/\n\s*\n/)[0] || 'No answer returned yet.')}</div>
        <div class="section-nav">${nav.join('')}</div>
        <section id="answer-section-main" class="answer-section">
          <h3>Direct answer</h3>
          ${renderParagraphBlocks(responseText)}
        </section>
        <section id="answer-section-grounding" class="answer-section">
          <h3>Grounding and routing</h3>
          <p><strong>Grounded:</strong> ${payload?.grounded ? 'yes' : 'not fully grounded'} | <strong>Source cards:</strong> ${escapeHtml(payload?.source_card_count ?? 0)} | <strong>Review required:</strong> ${payload?.review_required === false ? 'no' : 'yes'}</p>
          ${failureLine}
          <p><strong>Active routing:</strong> ${corpusSummary}</p>
        </section>
        ${reviewSection}
        ${renderPrintableSuggestions(payload.family_printables)}
      </div>`;
      answer.querySelectorAll('[data-open-printable]').forEach((button) => button.addEventListener('click', () => window.open(`/api/printables/${encodeURIComponent(button.dataset.openPrintable)}/open`, '_blank', 'noopener,noreferrer')));
    }

    function renderBadges(payload) {
      const badges = [];
      badges.push(`<span class="badge ${payload.grounded ? 'good' : 'warn'}">${payload.grounded ? 'source grounded' : 'not grounded'}</span>`);
      if (payload.failure_class && payload.failure_class !== 'none') badges.push(`<span class="badge warn">${escapeHtml(payload.failure_class)}</span>`);
      if (payload.matter_context_used) badges.push('<span class="badge">context used</span>');
      if (payload.answer_style) badges.push(`<span class="badge">${escapeHtml(payload.answer_style)}</span>`);
      if (payload.review_required !== false) badges.push('<span class="badge warn">review required</span>');
      if (payload.metadata && payload.metadata.matched_library_topic) badges.push(`<span class="badge">${escapeHtml(payload.metadata.matched_library_topic)}</span>`);
      if (payload.intake_label || payload?.structured_answer?.intake_label) badges.push(`<span class="badge">${escapeHtml(payload.intake_label || payload.structured_answer.intake_label)}</span>`);
      if (payload.source_card_count !== undefined) badges.push(`<span class="badge">${escapeHtml(payload.source_card_count)} source cards</span>`);
      if (payload.corpus_mode === 'active_case_corpus') badges.push('<span class="badge good">active case corpus</span>');
      if (payload.active_case_label) badges.push(`<span class="badge">${escapeHtml(payload.active_case_label)}</span>`);
      if ((payload.security_warnings || payload?.metadata?.security_warnings || []).length) badges.push('<span class="badge warn">untrusted instructions flagged</span>');
      const retrievalConfidence = payload?.retrieval_confidence || payload?.metadata?.retrieval_confidence || payload?.retrieval_diagnostics?.confidence || payload?.metadata?.retrieval_diagnostics?.confidence;
      if (retrievalConfidence) badges.push(`<span class="badge ${retrievalConfidence === 'low' ? 'warn' : ''}">retrieval ${escapeHtml(retrievalConfidence)}</span>`);
      const groundingIntegrity = payload?.grounding_integrity || payload?.structured_answer?.grounding_integrity || payload?.metadata?.grounding_integrity || {};
      if (groundingIntegrity.legal_source_count > 0) badges.push(`<span class="badge ${groundingIntegrity.current_law_verified ? 'good' : 'warn'}">${groundingIntegrity.current_law_verified ? 'currentness verified' : 'verify current law'}</span>`);
      if (payload?.structured_answer?.intake?.context_inherited) badges.push('<span class="badge">safe continuity used</span>');
      answerBadges.innerHTML = badges.join('');
      syncContextBar();
    }

    function renderHandoff(payload) {
      const structured = payload?.structured_answer || {};
      const metadata = payload?.metadata || {};
      const missing = structured.what_may_be_missing || metadata.missing_information || [];
      const followups = structured.suggested_questions || metadata.follow_up_questions || [];
      const handoff = {
        review_required: payload?.review_required !== false,
        matched_library_id: metadata.matched_library_id || null,
        matched_topic: metadata.matched_library_topic || null,
        source_card_count: payload?.source_card_count || 0,
        answer_style: payload?.answer_style || metadata.answer_style || null,
        intake: structured.intake || payload?.intake || metadata.intake || null,
        intake_label: structured.intake_label || payload?.intake_label || null,
        missing_information: missing,
        follow_up_questions: followups
      };
      if ((!missing.length && !followups.length) || !payload) {
        handoffPanel.textContent = 'No handoff metadata yet. Try the Missing-info checklist answer style.';
        return;
      }
      handoffPanel.innerHTML = `<strong>Reviewer handoff summary</strong>
        <p class="muted">Review required. Not legal advice. Not filing-ready.</p>
        <p><strong>Understood as:</strong> ${escapeHtml(handoff.intake_label || 'not classified')} | <strong>Matched item:</strong> ${escapeHtml(handoff.matched_library_id || 'none')} | <strong>Topic:</strong> ${escapeHtml(handoff.matched_topic || 'none')} | <strong>Sources:</strong> ${escapeHtml(handoff.source_card_count)}</p>
        <strong>Missing information</strong>
        <ul>${missing.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>
        <strong>Follow-up questions</strong>
        <ul>${followups.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>
        <button class="secondary" id="copy-handoff-button">Copy reviewer handoff JSON</button>`;
      const copyHandoff = document.getElementById('copy-handoff-button');
      copyHandoff?.addEventListener('click', async () => {
        await navigator.clipboard.writeText(JSON.stringify(handoff, null, 2));
        copyHandoff.textContent = 'Handoff copied';
        showToast('Reviewer handoff copied.');
        setTimeout(() => { copyHandoff.textContent = 'Copy reviewer handoff JSON'; }, 1100);
      });
    }

    function renderSources(items) {
      if (!items || !items.length) {
        lastSources = [];
        sourceCards.innerHTML = '<span class="muted">No source cards returned.</span>';
        lastHandoffSources = [];
        return;
      }
      lastSources = items || [];
      sourceCards.innerHTML = items.map((item) => {
        const meta = item.metadata || item;
        const title = item.title || meta.title || meta.id || 'Source';
        const url = meta.url || '';
        const sourceType = meta.source_type || meta.source_class || 'source';
        const lane = meta.source_lane || 'legal_authority';
        const official = lane === 'private_record' ? 'private record' : (meta.official === false ? 'unofficial' : 'official/source-backed');
        const snippet = item.snippet || item.text_excerpt || meta.text_excerpt || meta.description || meta.url || meta.id || '';
        const citation = item.citation || meta.citation_hint || '';
        const version = meta.version_label || '';
        const effective = meta.effective_date || '';
        const sourceId = item.source_id || item.evidence_id || meta.source_id || meta.id || '';
        const pageNumber = meta.page_number || item.page_number || 0;
        const locator = meta.source_locator || item.source_locator || '';
        const matchType = meta.match_type || item.match_type || '';
        const matchedTerms = meta.matched_terms || item.matched_terms || [];
        const ocrDerived = Boolean(meta.ocr_derived || item.ocr_derived || meta.ocr_status === 'ocr_completed');
        const instructionLike = Boolean(meta.instruction_like_text_detected);
        const freshnessStatus = String(meta.freshness_status || (lane === 'private_record' ? 'not applicable' : 'needs currentness verification')).replaceAll('_', ' ');
        const badges = [
          `<span class="badge ${lane === 'private_record' ? 'warn' : 'good'}">${escapeHtml(lane === 'private_record' ? 'Record' : 'Law')}</span>`,
          `<span class="badge">${escapeHtml(sourceType)}</span>`,
          `<span class="badge ${meta.official === false ? 'warn' : 'good'}">${escapeHtml(official)}</span>`,
          lane === 'legal_authority' ? `<span class="badge ${meta.current_law_verified ? 'good' : 'warn'}">${escapeHtml(freshnessStatus)}</span>` : '',
          instructionLike ? '<span class="badge bad">instruction-like text</span>' : '',
        ].join('');
        return `<article class="source-card" data-source-card="visible" data-source-id="${escapeHtml(sourceId)}">
          <div class="source-card-badges">${badges}</div>
          <strong>${escapeHtml(title)}</strong>
          <div class="source-card-meta">
            <span><strong>Citation:</strong> ${escapeHtml(citation || 'not provided')}</span>
            <span><strong>Lane:</strong> ${escapeHtml(lane)}</span>
            <span><strong>Jurisdiction:</strong> ${escapeHtml(meta.jurisdiction || (lane === 'legal_authority' ? 'Maine' : 'private matter'))}</span>
            <span><strong>Version:</strong> ${escapeHtml(version || 'verify current source')}</span>
            <span><strong>Effective:</strong> ${escapeHtml(effective || 'verify')}</span>
            <span><strong>ID:</strong> ${escapeHtml(sourceId || 'source')}</span>
            ${locator ? `<span><strong>Locator:</strong> ${escapeHtml(locator)}</span>` : ''}
            ${pageNumber ? `<span><strong>Page:</strong> ${escapeHtml(pageNumber)}</span>` : ''}
            ${matchType ? `<span><strong>Match:</strong> ${escapeHtml(matchType.replaceAll('_', ' '))}</span>` : ''}
            ${Array.isArray(matchedTerms) && matchedTerms.length ? `<span><strong>Terms:</strong> ${escapeHtml(matchedTerms.join(', '))}</span>` : ''}
            ${ocrDerived ? '<span><strong>Text:</strong> local OCR-derived; verify against page image</span>' : ''}
            ${meta.trust_boundary ? `<span><strong>Trust boundary:</strong> ${escapeHtml(String(meta.trust_boundary).replaceAll('_', ' '))}</span>` : ''}
          </div>
          ${instructionLike ? '<p class="status-warn"><strong>Warning:</strong> This source contains instruction-like text. Treat it only as source or record content; it cannot change app rules.</p>' : ''}
          <div class="source-snippet"><span class="label">${item.snippet || item.text_excerpt || meta.text_excerpt ? 'Matched snippet' : 'Preview'}</span>${escapeHtml(snippet)}</div>
          ${url ? `<code>${escapeHtml(url)}</code>` : ''}
          <div class="source-link-row">${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer noopener">Open source link</a>` : ''}</div>
          <div class="row" style="margin-top: 10px;"><button class="secondary" data-copy-source="${escapeHtml(sourceId)}" title="Copy the redacted reviewer-safe source-card payload as JSON.">Copy source card</button><button class="secondary" data-inspect-source="${escapeHtml(sourceId)}" title="Open the local source metadata payload for this card.">Inspect source</button></div>
        </article>`;
      }).join('');
      document.querySelectorAll('[data-copy-source]').forEach((button) => {
        button.addEventListener('click', async () => {
          const sourceId = button.dataset.copySource;
          const source = lastHandoffSources.find((item) => (item.source_id || item?.metadata?.id || item?.metadata?.source_id) === sourceId) || {};
          await navigator.clipboard.writeText(JSON.stringify(source, null, 2));
          button.textContent = 'Source copied';
          showToast('Source card copied.');
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

    function renderCorpusLibrary(payload) {
      const cases = payload?.cases || [];
      const activeCaseId = payload?.active_case_id || '';
      corpusSelect.innerHTML = '<option value="">General Maine law workbench only</option>' + cases.map((item) => {
        const counts = [];
        if (item.indexed_records) counts.push(`${Number(item.indexed_records).toLocaleString()} indexed`);
        if (item.pdf_pages) counts.push(`${Number(item.pdf_pages).toLocaleString()} PDF pages`);
        const suffix = counts.length ? ` (${counts.join(' | ')})` : '';
        return `<option value="${escapeHtml(item.case_id)}"${item.case_id === activeCaseId ? ' selected' : ''}>${escapeHtml(item.label)}${escapeHtml(suffix)}</option>`;
      }).join('');
      if (activeCaseId) {
        corpusStatus.innerHTML = `<strong>Active corpus:</strong> ${escapeHtml(payload.active_case_label || 'selected matter')}<br><span class="muted">Private records stay on this device.</span>`;
      } else {
        corpusStatus.textContent = 'No private case corpus is active yet. The general Maine-law workbench remains available.';
      }
      if (drawerActiveCorpus) drawerActiveCorpus.textContent = activeCaseId ? (payload.active_case_label || 'Selected matter') : 'General Maine law';
      if (drawerCorpusCount) {
        const active = cases.find((item) => item.case_id === activeCaseId);
        drawerCorpusCount.textContent = active ? `${Number(active.indexed_records || 0).toLocaleString()} indexed · ${Number(active.pdf_pages || 0).toLocaleString()} pages` : 'No private corpus selected';
      }
    }

    async function loadCorpusLibrary() {
      try {
        const payload = await fetchJson('/api/corpus-library');
        renderCorpusLibrary(payload);
        const queryCorpus = startupParams.get('corpus');
        if (queryCorpus && Array.from(corpusSelect.options).some((option) => option.value === queryCorpus)) {
          corpusSelect.value = queryCorpus;
        }
        syncContextBar();
        loadInventoryStatus();
      } catch (err) {
        corpusStatus.innerHTML = `<span class="status-bad">Could not load the installed corpus library: ${escapeHtml(err.message)}</span>`;
      }
    }

    function setOcrPrimaryAction({visible = false, label = 'OCR scanned pages locally', running = false} = {}) {
      if (!ocrPrimaryAction || !ocrActionButton) return;
      ocrPrimaryAction.hidden = !visible;
      ocrActionButton.hidden = !visible;
      ocrActionButton.textContent = label;
      ocrActionButton.dataset.running = running ? 'true' : 'false';
      ocrActionButton.setAttribute('aria-label', label);
      ocrJobRunning = running;
    }

    function stopOcrPolling() {
      window.clearTimeout(ocrPollTimer);
      ocrPollTimer = 0;
    }

    function formatOcrDuration(seconds) {
      const value = Math.max(0, Number(seconds || 0));
      const hours = Math.floor(value / 3600);
      const minutes = Math.floor((value % 3600) / 60);
      const remainder = Math.floor(value % 60);
      return [hours, minutes, remainder].map((part) => String(part).padStart(2, '0')).join(':');
    }

    function renderOcrProgress(status) {
      const phase = String(status.display_status || status.status || 'queued');
      const docs = Number(status.processed_documents ?? status.current ?? 0);
      const total = Number(status.total || 0);
      const pages = Number(status.processed_pages || 0);
      const candidatePages = Number(status.candidate_pages || 0);
      const currentFile = String(status.current_file || 'Preparing the next local file').slice(0, 160);
      const elapsed = formatOcrDuration(status.elapsed_seconds);
      const secondsSinceUpdate = Math.max(0, Math.floor(Number(status.seconds_since_update ?? (status.last_progress_at ? Date.now() / 1000 - Number(status.last_progress_at) : 0))));
      const percent = total ? Math.min(100, Math.round((docs / total) * 100)) : 0;
      if (drawerOcrPercent) drawerOcrPercent.textContent = `${percent}%`;
      if (drawerOcrProgress) drawerOcrProgress.style.width = `${percent}%`;
      const phaseLabels = {queued: 'Local OCR is queued', running: 'Local OCR is running', cancelling: 'Local OCR is cancelling', cancelled: 'Local OCR was cancelled', completed: 'Local OCR is completed', completed_with_warnings: 'Local OCR completed with warnings', failed: 'Local OCR failed', stalled: 'Local OCR is stalled'};
      const phaseLabel = phaseLabels[phase] || `Local OCR is ${phase}`;
      const documentsRemaining = Math.max(0, total - docs);
      const pagesRemaining = Math.max(0, candidatePages - pages);
      inventoryStatus.innerHTML = `<strong>${escapeHtml(phaseLabel)}</strong><br><br>Documents: ${escapeHtml(docs.toLocaleString())} of ${escapeHtml(total.toLocaleString())} completed · ${escapeHtml(documentsRemaining.toLocaleString())} remaining<br><br>Pages: ${escapeHtml(pages.toLocaleString())} of ${escapeHtml(candidatePages.toLocaleString())} completed · ${escapeHtml(pagesRemaining.toLocaleString())} remaining<br><br>Current file: ${escapeHtml(currentFile)}<br><br>Elapsed: ${escapeHtml(elapsed)} · Last update: ${escapeHtml(secondsSinceUpdate.toLocaleString())} seconds ago<br><br><progress value="${percent}" max="100" aria-label="Local OCR progress">${percent}%</progress> ${percent}%<br><br><span class="muted">Large collections may take several minutes or longer. OCR remains entirely on this computer.</span>${status.stalled ? '<br><span class="status-warn">No progress update has been received for 60 seconds. The current file may still be processing; you can wait or cancel.</span>' : ''}`;
    }

    async function pollOcrStatus() {
      stopOcrPolling();
      try {
        const status = await fetchJson('/api/corpus-ocr/status');
        if (['queued', 'running', 'cancelling'].includes(status.status)) {
          renderOcrProgress(status);
          setOcrPrimaryAction({visible: true, label: 'Cancel local OCR', running: true});
          ocrPollTimer = window.setTimeout(pollOcrStatus, 900);
          return;
        }
        if (status.status === 'completed' || status.status === 'completed_with_warnings') {
          renderOcrProgress(status);
          showToast(status.status === 'completed' ? 'Local OCR completed.' : 'Local OCR completed with warnings.');
          setOcrPrimaryAction({visible: false});
          await loadInventoryStatus(false);
          return;
        }
        if (status.status === 'cancelled') {
          renderOcrProgress(status);
          showToast('Local OCR stopped. Completed pages remain indexed locally.');
          await loadInventoryStatus(false);
          return;
        }
        if (status.status === 'failed') {
          renderOcrProgress(status);
          setOcrPrimaryAction({visible: true, label: 'Review local OCR options', running: false});
          return;
        }
        ocrJobRunning = false;
      } catch (err) {
        ocrJobRunning = false;
      }
    }

    async function loadInventoryStatus(checkJob = true) {
      if (!inventoryStatus) return;
      try {
        if (checkJob) {
          const job = await fetchJson('/api/corpus-ocr/status').catch(() => null);
          if (job && ['queued', 'running', 'cancelling'].includes(job.status)) {
            renderOcrProgress(job);
            setOcrPrimaryAction({visible: true, label: 'Cancel local OCR', running: true});
            ocrPollTimer = window.setTimeout(pollOcrStatus, 900);
            return;
          }
        }
        const payload = await fetchJson('/api/corpus-inventory');
        if (drawerCorpusCount && payload.status === 'ok') drawerCorpusCount.textContent = `${Number(payload.records || 0).toLocaleString()} records · ${Number(payload.searchable_records || 0).toLocaleString()} searchable`;
        if (drawerOcrPercent && payload.status === 'ok' && !Number(payload.ocr_candidate_records ?? payload.ocr_candidates ?? 0)) drawerOcrPercent.textContent = '100%';
        if (drawerOcrProgress && payload.status === 'ok' && !Number(payload.ocr_candidate_records ?? payload.ocr_candidates ?? 0)) drawerOcrProgress.style.width = '100%';
        if (payload.status !== 'ok') {
          inventoryStatus.textContent = 'Local inventory: Not indexed. Use the desktop intake wizard to choose files and grant permission before they are read.';
          setOcrPrimaryAction({visible: false});
          return;
        }
        const statuses = payload.parser_statuses || {};
        const warnings = (statuses.unreadable || 0) + (statuses.unsupported || 0) + (statuses.metadata_only || 0);
        const ocrCandidateRecords = Number(payload.ocr_candidate_records ?? payload.ocr_candidates ?? 0);
        const ocrCandidatePages = Number(payload.ocr_candidate_pages || ocrCandidateRecords);
        const searchable = Number(payload.searchable_records || 0);
        if (ocrCandidateRecords) {
          inventoryStatus.textContent = `Local inventory: Partially searchable · ${Number(payload.records || 0).toLocaleString()} records · ${searchable.toLocaleString()} searchable · OCR choice required for ${ocrCandidatePages.toLocaleString()} scanned page(s).`;
          setOcrPrimaryAction({visible: true, label: `OCR ${ocrCandidatePages.toLocaleString()} scanned page${ocrCandidatePages === 1 ? '' : 's'} locally`, running: false});
        } else if (warnings) {
          inventoryStatus.textContent = `Local inventory: Ready with warnings · ${Number(payload.records || 0).toLocaleString()} records indexed locally · ${warnings.toLocaleString()} need review.`;
          setOcrPrimaryAction({visible: false});
        } else {
          inventoryStatus.textContent = `Local inventory: Ready · ${Number(payload.records || 0).toLocaleString()} records indexed locally · ${searchable.toLocaleString()} searchable.`;
          setOcrPrimaryAction({visible: false});
        }
      } catch (err) {
        inventoryStatus.textContent = 'Local inventory: status unavailable. Your source files were not opened by this status check.';
        setOcrPrimaryAction({visible: false});
      }
    }

    function setOcrPrerequisiteActions({missing = false, oneClick = false, running = false} = {}) {
      if (startOcrButton) startOcrButton.hidden = missing;
      if (installOcrPrerequisitesButton) {
        installOcrPrerequisitesButton.hidden = !missing || !oneClick;
        installOcrPrerequisitesButton.disabled = running;
        installOcrPrerequisitesButton.textContent = running ? 'Installing OCR prerequisites…' : 'Install OCR prerequisites';
      }
      if (openOcrInstallPageButton) openOcrInstallPageButton.hidden = !missing;
      if (recheckOcrButton) {
        recheckOcrButton.hidden = !missing;
        recheckOcrButton.disabled = running;
      }
    }

    async function pollOcrPrerequisiteInstall() {
      window.clearTimeout(ocrInstallPollTimer);
      try {
        const status = await fetchJson('/api/corpus-ocr/prerequisites/status');
        const prerequisites = status.prerequisites || {};
        if (prerequisites.manual_install_url) ocrManualInstallUrl = prerequisites.manual_install_url;
        if (status.running) {
          ocrChoiceStatus.textContent = status.message || 'Installing Tesseract through Windows Package Manager…';
          setOcrPrerequisiteActions({missing: true, oneClick: true, running: true});
          ocrInstallPollTimer = window.setTimeout(pollOcrPrerequisiteInstall, 1000);
          return;
        }
        showToast(status.installed ? 'OCR prerequisites installed. Rechecking local OCR.' : (status.message || 'OCR prerequisite installation finished.'));
        await openOcrChoice();
      } catch (err) {
        ocrChoiceStatus.textContent = `Could not check the OCR installer: ${err.message}`;
        setOcrPrerequisiteActions({missing: true, oneClick: false, running: false});
      }
    }

    async function installOcrPrerequisites() {
      if (!window.confirm('Install Tesseract locally through Windows Package Manager? This may connect to the package source, but it will not read or upload matter records.')) return;
      setOcrPrerequisiteActions({missing: true, oneClick: true, running: true});
      ocrChoiceStatus.textContent = 'Starting the local OCR prerequisite installer…';
      try {
        await fetchJson('/api/corpus-ocr/prerequisites/install', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({approved: true}),
        });
        ocrInstallPollTimer = window.setTimeout(pollOcrPrerequisiteInstall, 500);
      } catch (err) {
        ocrChoiceStatus.textContent = `One-click OCR installation did not start: ${err.message}`;
        setOcrPrerequisiteActions({missing: true, oneClick: false, running: false});
      }
    }

    async function openOcrChoice() {
      if (ocrJobRunning) {
        await cancelLocalOcr();
        return;
      }
      if (!ocrOverlay) return;
      ocrChoiceStatus.textContent = 'Checking scanned pages and local OCR availability…';
      ocrCandidateCount.textContent = 'Checking…';
      ocrEngineStatus.textContent = 'Checking…';
      startOcrButton.disabled = true;
      startOcrButton.dataset.mode = 'start';
      startOcrButton.textContent = 'OCR scanned pages locally';
      setOcrPrerequisiteActions({missing: false});
      openOverlay(ocrOverlay);
      try {
        const [payload, prerequisiteStatus] = await Promise.all([
          fetchJson('/api/corpus-ocr/candidates'),
          fetchJson('/api/corpus-ocr/prerequisites').catch(() => ({})),
        ]);
        const candidatePages = Number(payload.candidate_pages || payload.candidates || 0);
        const engine = payload.engine || {};
        const prerequisites = prerequisiteStatus.prerequisites || prerequisiteStatus || {};
        if (prerequisites.manual_install_url) ocrManualInstallUrl = prerequisites.manual_install_url;
        ocrCandidateCount.textContent = candidatePages ? `${candidatePages.toLocaleString()} scanned or image-only page(s)` : 'No OCR candidates';
        if (!candidatePages) {
          ocrChoiceStatus.textContent = 'All detected pages already contain searchable text. OCR is not needed.';
          ocrEngineStatus.textContent = engine.tesseract_version || 'Not needed';
          startOcrButton.disabled = true;
          setOcrPrerequisiteActions({missing: false});
          return;
        }
        if (!engine.available) {
          const oneClick = Boolean(prerequisites.one_click_available);
          ocrChoiceStatus.textContent = oneClick
            ? 'Tesseract is not installed. Use Install OCR prerequisites for a one-click local setup, or open the manual install page. Matter records are not read or uploaded by the installer.'
            : 'Tesseract is not installed. Open the manual install page, complete the local installation, then choose Recheck local OCR. Matter records are not uploaded.';
          ocrEngineStatus.textContent = `Tesseract not detected locally · ${engine.bundled_pdf_renderer ? 'bundled PDF renderer ready' : 'PDF renderer needs repair'}`;
          startOcrButton.disabled = true;
          setOcrPrerequisiteActions({missing: true, oneClick, running: Boolean(prerequisiteStatus.running)});
          return;
        }
        setOcrPrerequisiteActions({missing: false});
        const pdfNote = engine.pdf_ocr_available ? 'PDF and image OCR ready' : 'Image OCR ready; PDF renderer needs repair';
        ocrEngineStatus.textContent = `${engine.tesseract_version || 'Tesseract detected'} · ${pdfNote}`;
        ocrChoiceStatus.textContent = 'Ready to OCR only the pages that lack usable native text. Processing and the resulting index remain local.';
        startOcrButton.hidden = false;
        startOcrButton.disabled = !engine.pdf_ocr_available && candidatePages > 0;
      } catch (err) {
        ocrChoiceStatus.textContent = `Could not inspect local OCR candidates: ${err.message}`;
        ocrEngineStatus.textContent = 'Status unavailable';
        startOcrButton.disabled = true;
        setOcrPrerequisiteActions({missing: true, oneClick: false, running: false});
      }
    }

    async function startLocalOcr() {
      startOcrButton.disabled = true;
      ocrChoiceStatus.textContent = 'Starting local OCR. No document bytes or recognized text will leave this computer…';
      try {
        const payload = await fetchJson('/api/corpus-ocr/start', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({approved: true, language: 'eng'}),
        });
        closeOverlay(ocrOverlay);
        setOcrPrimaryAction({visible: true, label: 'Cancel local OCR', running: true});
        renderOcrProgress(payload);
        ocrPollTimer = window.setTimeout(pollOcrStatus, 250);
      } catch (err) {
        ocrChoiceStatus.textContent = `Local OCR did not start: ${err.message}`;
        startOcrButton.disabled = false;
      }
    }

    async function declineLocalOcr() {
      try {
        await fetchJson('/api/corpus-ocr/choice', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({approved: false, language: 'eng'}),
        });
        closeOverlay(ocrOverlay);
        await loadInventoryStatus(false);
        showToast('Scanned pages remain unsearchable for now.');
      } catch (err) {
        ocrChoiceStatus.textContent = `Could not record the local OCR choice: ${err.message}`;
      }
    }

    async function cancelLocalOcr() {
      try {
        await fetchJson('/api/corpus-ocr/cancel', {method: 'POST'});
        renderOcrProgress({status: 'cancelling', current_file: 'Finishing the current local page', local_only: true});
        setOcrPrimaryAction({visible: true, label: 'Stopping local OCR…', running: true});
        ocrPollTimer = window.setTimeout(pollOcrStatus, 350);
      } catch (err) {
        showToast(`Could not stop local OCR: ${err.message}`);
      }
    }

    function renderPrintableResults(payload) {
      const rows = payload?.results || [];
      if (!rows.length) {
        printableResults.innerHTML = '<span class="muted">No printable page-text match was found. This library is optional and does not replace official Maine sources or forms.</span>';
        return;
      }
      printableResults.innerHTML = rows.map((item) => `<article class="source-card printable-card"><div class="source-card-badges"><span class="badge warn">Family printable</span><span class="badge">Not legal authority</span></div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.description || '')}</p><p class="muted">${escapeHtml(item.category || '')} · ${escapeHtml(item.page_count || 0)} pages · matched page(s): ${escapeHtml((item.matched_pages || []).join(', ') || 'not available')}</p><div class="source-snippet">${escapeHtml(item.snippet || '')}</div><div class="row"><button class="secondary" data-open-printable="${escapeHtml(item.document_id)}" type="button">Open locally</button><button class="secondary" data-print-printable="${escapeHtml(item.document_id)}" type="button">Print</button></div></article>`).join('');
      printableResults.querySelectorAll('[data-open-printable], [data-print-printable]').forEach((button) => button.addEventListener('click', () => window.open(`/api/printables/${encodeURIComponent(button.dataset.openPrintable || button.dataset.printPrintable)}/open`, '_blank', 'noopener,noreferrer')));
    }

    async function searchFamilyPrintables(query = '') {
      const value = (query || printableSearch?.value || '').trim();
      if (!value) {
        printableResults.textContent = 'Type a family situation, county, title, or phrase to search the local printable page text.';
        return;
      }
      printableResults.textContent = 'Searching local printable page text...';
      try {
        renderPrintableResults(await fetchJson(`/api/printables/search?q=${encodeURIComponent(value)}&limit=6`));
      } catch (err) {
        printableResults.innerHTML = `<span class="status-bad">Printable search failed locally: ${escapeHtml(err.message)}</span>`;
      }
    }

    async function activateSelectedCorpus() {
      const caseId = corpusSelect.value || '';
      if (!caseId) {
        corpusStatus.textContent = 'General Maine law workbench mode remains active. Choose a saved case corpus to switch the private record layer.';
        syncContextBar();
        return;
      }
      activateCorpusButton.disabled = true;
      try {
        const payload = await fetchJson('/api/activate-corpus', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({case_id: caseId})
        });
        corpusStatus.innerHTML = `<strong>Active corpus switched:</strong> ${escapeHtml(payload.active_case_label || 'selected matter')}<br><span class="muted">Private records stay on this device.</span>`;
        showToast('Active corpus switched.');
        await loadCorpusLibrary();
      } catch (err) {
        corpusStatus.innerHTML = `<span class="status-bad">Could not switch the active corpus: ${escapeHtml(err.message)}</span>`;
      } finally {
        activateCorpusButton.disabled = false;
      }
    }

    function renderChatSourceSummary(payload) {
      if (!payload || typeof payload !== 'object') return '';
      const sources = Array.isArray(payload.citations) ? payload.citations : [];
      const legalCount = sources.filter((item) => String(item?.metadata?.source_lane || 'legal_authority') !== 'private_record').length;
      const recordCount = sources.filter((item) => String(item?.metadata?.source_lane || '') === 'private_record').length;
      const externalCount = Number(payload.external_source_count || 0);
      if (!legalCount && !recordCount && !externalCount) return '';
      return `<div class="chat-source-summary"><div><strong>Sources</strong><button class="inline-source-link" data-chat-open-evidence="all" type="button">View all sources</button></div><div class="chat-source-lanes"><button data-chat-open-evidence="law" type="button"><span aria-hidden="true">⚖</span> Maine law <strong>${legalCount}</strong></button><button data-chat-open-evidence="records" type="button"><span aria-hidden="true">▰</span> My records <strong>${recordCount}</strong></button><button data-chat-open-evidence="external" type="button"><span aria-hidden="true">◎</span> External <strong>${externalCount}</strong></button></div></div>`;
    }

    function addMessage(role, text, payload = null) {
      const at = new Date().toISOString();
      messages.push({role, text, at});
      const speaker = role === 'user' ? 'You' : 'Maine Family Law LLM';
      const bubbleClass = role === 'user' ? 'user-bubble' : 'assistant-bubble';
      const content = role === 'assistant'
        ? `${renderParagraphBlocks(text)}${payload?.direct_record_search ? renderRecordGroups(payload.record_groups) : ''}${renderChatSourceSummary(payload)}`
        : `<p>${escapeHtml(text)}</p>`;
      const wrapper = document.createElement('div');
      wrapper.className = `message ${role}`;
      wrapper.innerHTML = `<div class="message-bubble ${bubbleClass}"><div class="message-speaker"><strong>${speaker}</strong><span>${formatLocalTime(at)}${role === 'assistant' ? ' <span class="message-verified" aria-label="Response complete">✓</span>' : ''}</span></div><div class="message-content">${content}</div></div>`;
      transcript.appendChild(wrapper);
      wrapper.querySelectorAll('[data-chat-open-evidence]').forEach((button) => button.addEventListener('click', () => setDrawerOpen(true, 'evidence')));
      if (payload?.direct_record_search) bindRecordOpenActions(wrapper);
      if (chatScroll) chatScroll.scrollTop = chatScroll.scrollHeight;
    }

    function resetSession({preserveContext} = {preserveContext: false}) {
      question.value = '';
      if (!preserveContext) {
        matterContext.value = '';
      }
      messages.length = 0;
      transcript.textContent = '';
      answer.textContent = 'Ask a question to test the local source-grounded workbench.';
      answerBadges.innerHTML = '<span class="badge">waiting</span>';
      sourceCards.textContent = 'No source cards yet.';
      sourceInspector.textContent = 'Select "Inspect source" on a source card to view full local metadata.';
      handoffPanel.textContent = 'Ask a question to see missing facts, follow-up questions, and reviewer handoff metadata.';
      lastPayload = null;
      lastSources = [];
      lastHandoffSources = [];
      downloadJsonButton.style.display = 'none';
      syncContextBar();
    }

    function isSourceCardFollowUp(text) {
      const normalized = String(text || '').toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();
      return /^(give|show|open|display|list|where|which|what)\b/.test(normalized) &&
        /(source cards?|sources?|matches?|records?|snippets?|pages?|files?|where did you find|show all|open the)/.test(normalized);
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
      if (stopButton) { stopButton.hidden = false; stopButton.disabled = false; }
      activeRequestController = new AbortController();
      answer.textContent = 'Retrieving sources and composing a grounded answer...';
      sourceCards.textContent = '';
      addMessage('user', text);
      question.value = '';
      question.style.height = '';
      question.dataset.lastSubmitCleared = 'true';
      try {
        const context = [matterContext.value.trim(), `Audience: ${audience.value}`].filter(Boolean).join('\n');
        const payload = await fetchJson('/ask', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            question: text,
            answer_style: answerStyle.value,
            matter_context: context,
            search_mode: searchMode?.value || 'maine_law',
            child_impact_lens: Boolean(childImpactLens?.checked),
            session_id: localSessionId,
            last_search_id: lastPayload?.search_id || ''
          }),
          signal: activeRequestController.signal
        });
        const responseText = payload.answer || JSON.stringify(payload, null, 2);
        renderLatestAnswer(payload);
        addMessage('assistant', responseText, payload);
        lastPayload = payload;
        lastHandoffSources = payload.handoff_safe_source_cards || [];
        downloadJsonButton.style.display = '';
        renderBadges(payload);
        renderHandoff(payload);
        renderSources(payload.citations || []);
        if (payload.response_kind === 'source_card_followup') {
          setDrawerOpen(true, 'evidence');
          const sourceFollowupToast = payload.failure_class === 'no_recent_search_result'
            ? 'I do not have a recent search result to open.'
            : 'Prior source cards opened. No new corpus search was run.';
          showToast(sourceFollowupToast);
        } else {
          showToast(payload.grounded ? 'Grounded answer ready.' : 'Answer returned with review-needed flags.');
        }
      } catch (err) {
        if (err.name === 'AbortError') {
          answer.innerHTML = '<div class="answer-body"><div class="answer-callout">The request was stopped. Your draft and conversation remain local.</div></div>';
          showToast('Request stopped.');
          return;
        }
        const message = `Local workbench error: ${err.message}`;
        answer.innerHTML = `<div class="answer-body"><div class="answer-callout status-bad">${escapeHtml(message)}</div></div>`;
        addMessage('assistant', message);
        answerBadges.innerHTML = '<span class="badge bad">error</span><span class="badge warn">server response handled</span>';
        sourceCards.innerHTML = '<span class="status-bad">No response. Check the terminal running START_LOCAL_CHAT.ps1 for details.</span>';
        handoffPanel.textContent = 'No reviewer handoff metadata because the request failed.';
      } finally {
        sending = false;
        askButton.disabled = false;
        activeRequestController = null;
        if (stopButton) { stopButton.hidden = true; stopButton.disabled = true; }
      }
    }

    async function loadRuntimeDiagnostics() {
      try {
        const payload = await fetchJson('/api/runtime-diagnostics');
        runtimeDiagnostics.dataset.runtimeDiagnostics = 'loaded';
        runtimeDiagnostics.innerHTML = `<strong>Runtime diagnostics:</strong> ${escapeHtml(payload.version)} | ${escapeHtml(payload.ui_version)} | Enter submit: ${payload.enter_to_submit ? 'on' : 'off'} | Appeals routing fix: ${payload.appeals_routing_fix ? 'on' : 'off'} | Brand assets mounted: ${payload.brand_assets_mounted ? 'yes' : 'no'} | Branding: ${escapeHtml(payload.branding || 'unknown')} | Conversation settings: on | Evidence drawer: on | Ctrl+K: on | Ctrl+J: on`;
      } catch (err) {
        runtimeDiagnostics.dataset.runtimeDiagnostics = 'failed';
        runtimeDiagnostics.innerHTML = `<strong>Runtime diagnostics failed:</strong> ${escapeHtml(err.message)}. If the footer does not show the current v3 UI, stop the old server and restart from the current build.`;
      }
    }

    async function loadSources() {
      sourcesButton.disabled = true;
      try {
        const payload = await fetchJson('/sources');
        const cards = payload.map((item) => ({metadata: item, snippet: item.text_excerpt || item.description || item.url || item.id}));
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
        applyPendingTopicSelection();
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
      syncContextBar();
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
          syncContextBar();
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
          syncContextBar();
          ask();
        });
      });
    }

    function applyQueryParams() {
      const role = startupParams.get('role');
      const style = startupParams.get('style');
      const topic = startupParams.get('topic');
      const context = startupParams.get('context');
      const draftQuestion = startupParams.get('q');
      const mode = startupParams.get('mode');
      if (role && Array.from(audience.options).some((option) => option.value === role)) {
        audience.value = role;
      }
      if (style && Array.from(answerStyle.options).some((option) => option.value === style)) {
        answerStyle.value = style;
      }
      if (context) {
        matterContext.value = context;
      }
      if (draftQuestion) {
        question.value = draftQuestion;
      }
      if (mode && searchMode && Array.from(searchMode.options).some((option) => option.value === mode)) {
        searchMode.value = mode;
      }
      if (topic) {
        topicFilter.dataset.pendingTopic = topic;
      }
    }

    function applyPendingTopicSelection() {
      const pendingTopic = topicFilter.dataset.pendingTopic;
      if (pendingTopic && Array.from(topicFilter.options).some((option) => option.value === pendingTopic)) {
        topicFilter.value = pendingTopic;
        delete topicFilter.dataset.pendingTopic;
      }
      syncContextBar();
    }

    document.querySelectorAll('[data-example]').forEach((button) => {
      button.addEventListener('click', () => {
        question.value = button.dataset.example;
        syncContextBar();
        ask();
      });
    });
    askButton.addEventListener('click', ask);
    stopButton?.addEventListener('click', () => activeRequestController?.abort());
    newChatButton?.addEventListener('click', async () => {
      const previousSessionId = localSessionId;
      localSessionId = createLocalSessionId();
      resetSession({preserveContext: true});
      try {
        await fetchJson('/api/session/clear', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({session_id: previousSessionId})
        });
      } catch (_err) {
        // The new random session ID already prevents stale source reuse. The
        // server also expires any unreachable in-memory state after 30 minutes.
      }
      showToast('Started a fresh chat.');
    });
    copyButton.addEventListener('click', async () => {
      await navigator.clipboard.writeText((lastPayload && lastPayload.answer) || answer.textContent || '');
      copyButton.textContent = 'Copied';
      showToast('Latest answer copied.');
      setTimeout(() => { copyButton.textContent = 'Copy answer'; }, 1100);
    });
    copySourcesButton?.addEventListener('click', async () => {
      await navigator.clipboard.writeText(JSON.stringify(lastHandoffSources || [], null, 2));
      copySourcesButton.textContent = 'Source cards copied';
      showToast('Redacted reviewer-safe source cards copied.');
      setTimeout(() => { copySourcesButton.textContent = 'Copy source cards'; }, 1100);
    });
    downloadButton.addEventListener('click', () => {
      if (!confirmFullLocalExport()) return;
      const content = [
        'Maine Family Law LLM local transcript',
        'Review required. Not legal advice.',
        '',
        messages.map((msg) => `[${msg.at}] ${msg.role.toUpperCase()}\n${msg.text}`).join('\n\n'),
        '',
        'Latest payload metadata:',
        JSON.stringify(lastPayload || {}, null, 2),
        '',
        'Latest source cards (full local export):',
        JSON.stringify(lastSources || [], null, 2)
      ].join('\n');
      const blob = new Blob([content || answer.textContent || 'No transcript yet.'], {type: 'text/plain'});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'maine-family-law-llm-transcript.txt';
      a.click();
      URL.revokeObjectURL(url);
      showToast('Transcript saved.');
    });
    downloadJsonButton.addEventListener('click', () => {
      if (!confirmFullLocalExport()) return;
      const payload = {
        schema_version: 'local_chat_transcript_v3',
        generated_at: new Date().toISOString(),
        review_required: true,
        not_legal_advice: true,
        messages,
        latest_payload: lastPayload || null,
        latest_source_cards: lastSources || [],
        reviewer_safe_source_cards: lastHandoffSources || [],
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
      showToast('Transcript JSON saved.');
    });
    clearButton.addEventListener('click', () => {
      if (window.confirm('Clear the visible conversation from this workbench? This cannot erase browser, operating-system, backup, print, or external history.')) {
        resetSession();
        showToast('Visible conversation cleared.');
      }
    });
    clearDraftButton?.addEventListener('click', () => { question.value = ''; question.style.height = ''; question.focus(); showToast('Draft cleared.'); });
    sourcesButton.addEventListener('click', loadSources);
    activateCorpusButton?.addEventListener('click', activateSelectedCorpus);
    refreshCorpusButton?.addEventListener('click', loadCorpusLibrary);
    copyLinkButton?.addEventListener('click', async () => {
      const url = new URL(window.location.href);
      url.search = '';
      url.searchParams.set('role', audience.value);
      url.searchParams.set('style', answerStyle.value);
      url.searchParams.set('mode', searchMode?.value || 'maine_law');
      if (topicFilter.value && topicFilter.value !== 'all') {
        url.searchParams.set('topic', topicFilter.value);
      }
      await navigator.clipboard.writeText(url.toString());
      showToast('Privacy-safe settings link copied. Questions, context, records, and local paths were not included.');
    });
    drawerRefreshCorpus?.addEventListener('click', async () => { await loadCorpusLibrary(); showToast('Corpus status refreshed.'); });
    openAllStarters?.addEventListener('click', () => setDrawerOpen(true, 'starters'));
    quickNewCorpus?.addEventListener('click', () => { setDrawerOpen(true, 'setup'); showToast('Use the desktop launcher to create a new local case corpus.'); });
    quickOpenWorkspace?.addEventListener('click', () => setDrawerOpen(true, 'setup'));
    quickExportChat?.addEventListener('click', () => downloadButton?.click());

    let drawerReturnFocus = null;
    let drawerUserPreference = null;
    let responsiveLayoutMode = '';
    const inlineDrawerQuery = window.matchMedia('(min-width: 960px)');
    const fullWorkbenchQuery = window.matchMedia('(min-width: 1360px)');

    function currentResponsiveLayoutMode() {
      if (fullWorkbenchQuery.matches) return 'full';
      if (inlineDrawerQuery.matches) return 'compact';
      return 'overlay';
    }

    function setDrawerOpen(open, panel = '', options = {}) {
      const {manageFocus = true, userInitiated = false} = options;
      const wasOpen = document.body.dataset.drawer === 'open';
      if (userInitiated) drawerUserPreference = Boolean(open);
      if (open && !wasOpen && manageFocus) drawerReturnFocus = document.activeElement;
      if (!open && wasOpen && manageFocus) {
        const returnTarget = drawerReturnFocus || focusModeButton;
        // Move focus before hiding the drawer from assistive technology.
        if (returnTarget && typeof returnTarget.focus === 'function') {
          returnTarget.focus({preventScroll: true});
        }
        drawerReturnFocus = null;
      }
      document.body.dataset.drawer = open ? 'open' : 'closed';
      const overlayMode = currentResponsiveLayoutMode() === 'overlay';
      document.body.classList.toggle('drawer-modal-open', Boolean(open && overlayMode));
      if (evidenceDrawer) {
        evidenceDrawer.hidden = !open;
        evidenceDrawer.setAttribute('aria-hidden', open ? 'false' : 'true');
      }
      focusModeButton?.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (drawerBackdrop) drawerBackdrop.hidden = !(open && overlayMode);
      if (open && panel) selectDrawerTab(panel);
      if (open && overlayMode && manageFocus) {
        window.setTimeout(() => closeDrawerButton?.focus({preventScroll: true}), 40);
      }
    }

    function syncResponsiveLayout({initial = false} = {}) {
      const nextMode = currentResponsiveLayoutMode();
      const modeChanged = nextMode !== responsiveLayoutMode;
      responsiveLayoutMode = nextMode;
      document.body.dataset.layout = nextMode;

      if (initial) {
        setDrawerOpen(nextMode !== 'overlay', 'evidence', {manageFocus: false});
        return;
      }
      if (!modeChanged) {
        const open = document.body.dataset.drawer === 'open';
        document.body.classList.toggle('drawer-modal-open', open && nextMode === 'overlay');
        if (drawerBackdrop) drawerBackdrop.hidden = !(open && nextMode === 'overlay');
        return;
      }
      if (nextMode === 'overlay') {
        // Never let a desktop-open drawer suddenly cover the chat after a resize.
        setDrawerOpen(false, '', {manageFocus: false});
      } else {
        // Restore an explicit user preference; otherwise desktop layouts open by default.
        setDrawerOpen(drawerUserPreference !== false, 'evidence', {manageFocus: false});
      }
    }

    function selectDrawerTab(name) {
      document.querySelectorAll('[data-drawer-tab]').forEach((button) => {
        const active = button.dataset.drawerTab === name;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      document.querySelectorAll('[data-drawer-panel]').forEach((panel) => {
        panel.hidden = panel.dataset.drawerPanel !== name;
      });
    }

    focusModeButton?.addEventListener('click', () => setDrawerOpen(document.body.dataset.drawer !== 'open', '', {userInitiated: true}));
    closeDrawerButton?.addEventListener('click', () => setDrawerOpen(false, '', {userInitiated: true}));
    drawerBackdrop?.addEventListener('click', () => setDrawerOpen(false, '', {userInitiated: true}));
    document.querySelectorAll('[data-drawer-tab]').forEach((button) => {
      button.addEventListener('click', () => selectDrawerTab(button.dataset.drawerTab || 'setup'));
    });
    moreStartersButton?.addEventListener('click', () => setDrawerOpen(true, 'starters'));
    printableSearchButton?.addEventListener('click', () => searchFamilyPrintables());
    printableSearch?.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); searchFamilyPrintables(); } });
    ocrActionButton?.addEventListener('click', openOcrChoice);
    startOcrButton?.addEventListener('click', startLocalOcr);
    installOcrPrerequisitesButton?.addEventListener('click', installOcrPrerequisites);
    openOcrInstallPageButton?.addEventListener('click', () => window.open(ocrManualInstallUrl, '_blank', 'noopener,noreferrer'));
    recheckOcrButton?.addEventListener('click', openOcrChoice);
    declineOcrButton?.addEventListener('click', declineLocalOcr);
    cancelOcrChoiceButton?.addEventListener('click', () => closeOverlay(ocrOverlay));
    reviewInventoryButton?.addEventListener('click', async () => { await loadInventoryStatus(); showToast('Local inventory status refreshed.'); });
    rebuildIndexButton?.addEventListener('click', async () => {
      if (!window.confirm('Rebuild the derived local search index for the active matter? Original source documents will not be changed.')) return;
      rebuildIndexButton.disabled = true;
      try {
        await fetchJson('/api/corpus-rebuild-index', {method: 'POST'});
        await loadInventoryStatus();
        showToast('Local index rebuilt.');
      } catch (err) {
        showToast(`Local index rebuild failed: ${err.message}`);
      } finally {
        rebuildIndexButton.disabled = false;
      }
    });
    deleteIndexButton?.addEventListener('click', async () => {
      if (!window.confirm('Delete only the derived local search index for this matter? Your original source documents will remain unchanged.')) return;
      deleteIndexButton.disabled = true;
      try {
        const result = await fetchJson('/api/corpus-delete-index', {method: 'POST'});
        await loadInventoryStatus();
        showToast(`Deleted ${Number(result.removed?.length || 0)} local index file(s).`);
      } catch (err) {
        showToast(`Local index deletion failed: ${err.message}`);
      } finally {
        deleteIndexButton.disabled = false;
      }
    });
    helpButton?.addEventListener('click', () => openOverlay(helpOverlay));
    welcomeButton?.addEventListener('click', () => openOverlay(welcomeOverlay));
    closeHelpButton?.addEventListener('click', () => closeOverlay(helpOverlay));
    dismissWelcomeButton?.addEventListener('click', () => closeOverlay(welcomeOverlay));
    document.querySelectorAll('[data-welcome-role]').forEach((button) => {
      button.addEventListener('click', () => {
        const role = button.dataset.welcomeRole || 'parent';
        const style = button.dataset.welcomeStyle || 'plain_language';
        const prompt = button.dataset.welcomeQuestion || '';
        if (Array.from(audience.options).some((option) => option.value === role)) {
          audience.value = role;
        }
        if (Array.from(answerStyle.options).some((option) => option.value === style)) {
          answerStyle.value = style;
        }
        populatePromptPackSelect();
        renderPromptPacks();
        renderQuestionLibrary(libraryItems);
        if (prompt) {
          question.value = prompt;
        }
        syncContextBar();
        closeOverlay(welcomeOverlay);
        showToast(`Role lane set to ${selectedLabel(audience)}.`);
      });
    });
    audience.addEventListener('change', () => {
      const presets = {lawyer: 'intake', counselor: 'professional_boundary', therapist: 'professional_boundary', caregiver: 'missing_information', parent: 'plain_language'};
      answerStyle.value = presets[audience.value] || answerStyle.value;
      populatePromptPackSelect();
      renderPromptPacks();
      renderQuestionLibrary(libraryItems);
      syncContextBar();
    });
    searchMode?.addEventListener('change', syncContextBar);
    document.querySelectorAll('[data-search-mode]').forEach((button) => {
      button.addEventListener('click', () => setSearchMode(button.dataset.searchMode || 'maine_law'));
      button.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault();
          const options = Array.from(document.querySelectorAll('[data-search-mode]'));
          const current = options.indexOf(button);
          const next = event.key === 'ArrowRight' ? (current + 1) % options.length : (current - 1 + options.length) % options.length;
          options[next]?.focus(); options[next]?.click();
        }
      });
    });
    answerStyle.addEventListener('change', syncContextBar);
    promptPackSelect.addEventListener('change', () => {
      renderPromptPacks();
      syncContextBar();
    });
    topicFilter.addEventListener('change', () => {
      renderQuestionLibrary(libraryItems);
      syncContextBar();
    });
    librarySearch?.addEventListener('input', () => renderQuestionLibrary(libraryItems));
    libraryTopicSearch?.addEventListener('input', () => renderQuestionLibrary(libraryItems));
    matterContext.addEventListener('input', syncContextBar);
    corpusSelect?.addEventListener('change', syncContextBar);
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

    applyQueryParams();
    syncContextBar();
    fetchJson('/api/health').then((payload) => {
      const online = payload.status === 'ok';
      health.className = online ? 'health-indicator status-ok' : 'health-indicator status-bad';
      const copy = health.querySelector('.health-copy');
      if (copy) copy.textContent = online ? 'Local only' : 'Offline';
      health.title = online ? 'Local-only API is online.' : 'Local-only API status is unknown.';
      health.setAttribute('aria-label', online ? 'Local-only service online. Open privacy status.' : 'Local-only service status unknown. Open privacy status.');
      if (localStatusCopy) localStatusCopy.textContent = online ? 'Local service online' : 'Local service status unknown';
    }).catch(() => {
      health.className = 'health-indicator status-bad';
      const copy = health.querySelector('.health-copy');
      if (copy) copy.textContent = 'Offline';
      health.title = 'Local-only API is offline.';
      health.setAttribute('aria-label', 'Local-only service offline. Open privacy status.');
      if (localStatusCopy) localStatusCopy.textContent = 'Local service offline';
    });
    if (viewportProof) {
      window.addEventListener('load', () => {
        viewportProof.textContent = `innerWidth=${window.innerWidth}; scrollWidth=${document.documentElement.scrollWidth}; bodyClientWidth=${document.body.clientWidth}`;
      });
    }
    loadCorpusLibrary();
    loadQuestionLibrary();
    loadPromptPacks();
    loadRuntimeDiagnostics();


    const commandDefinitions = [
      {id: 'new_conversation', group: 'Conversation', label: 'New conversation', hint: 'Clear the transcript but keep the active matter', aliases: 'new chat reset start over', run: () => newChatButton?.click()},
      {id: 'focus_composer', group: 'Conversation', label: 'Focus the question box', hint: 'Start typing immediately', aliases: 'write ask compose message', run: () => question?.focus()},
      {id: 'change_answer_style', group: 'Conversation', label: 'Change conversation settings', hint: 'Role, answer style and issue context', aliases: 'role tone style settings', run: () => openOverlay(welcomeOverlay)},
      {id: 'copy_settings_link', group: 'Conversation', label: 'Copy privacy-safe settings link', hint: 'Excludes questions, matter context, records and local paths', aliases: 'share link safe', run: () => copyLinkButton?.click()},
      {id: 'research_maine_law', group: 'Research', label: 'Research Maine law', hint: 'Use official and source-backed Maine-law material', aliases: 'statute rule court authority', run: () => setSearchMode('maine_law')},
      {id: 'search_my_records', group: 'Research', label: 'Search my records', hint: 'Search only the active private matter', aliases: 'documents case corpus files', run: () => setSearchMode('my_records')},
      {id: 'search_both_separately', group: 'Research', label: 'Search law and records separately', hint: 'Keep authority and matter facts in distinct lanes', aliases: 'both combined compare', run: () => setSearchMode('both')},
      {id: 'choose_matter', group: 'Matter', label: 'Choose active matter', hint: 'Open the local corpus library', aliases: 'case family client corpus', run: () => setDrawerOpen(true, 'setup')},
      {id: 'toggle_evidence_drawer', group: 'Evidence', label: 'Open Evidence & tools', hint: 'Sources, matter controls, review and starters', aliases: 'drawer proof audit', run: () => setDrawerOpen(true, 'evidence')},
      {id: 'open_source_list', group: 'Evidence', label: 'Open source list', hint: 'Load available source cards and inspect the proof', aliases: 'citations authority evidence', run: async () => { setDrawerOpen(true, 'evidence'); await loadSources(); }},
      {id: 'search_family_printables', group: 'Resources', label: 'Search family printables', hint: 'Search bundled local FOCAF printable page text', aliases: 'printables worksheets guides family resources', run: () => { setDrawerOpen(true, 'printables'); printableSearch?.focus(); }},
      {id: 'browse_printables', group: 'Resources', label: 'Browse printables', hint: 'Open optional family resources and previews', aliases: 'focaf browse resources', run: async () => { setDrawerOpen(true, 'printables'); await searchFamilyPrintables('family'); }},
      {id: 'court_day_checklist', group: 'Resources', label: 'Court-day checklist', hint: 'Find court-day family printables', aliases: 'court hearing bag preparation', run: async () => { setDrawerOpen(true, 'printables'); await searchFamilyPrintables('court day'); }},
      {id: 'calm_communication_tools', group: 'Resources', label: 'Calm communication tools', hint: 'Find communication printables', aliases: 'calm message co parenting', run: async () => { setDrawerOpen(true, 'printables'); await searchFamilyPrintables('calm communication'); }},
      {id: 'child_routine_tools', group: 'Resources', label: 'Child routine tools', hint: 'Find routines and exchange printables', aliases: 'routine exchange medication child', run: async () => { setDrawerOpen(true, 'printables'); await searchFamilyPrintables('child routine'); }},
      {id: 'records_deadline_tools', group: 'Resources', label: 'Records and deadline tools', hint: 'Find record and date tracking printables', aliases: 'records dates deadlines tracker', run: async () => { setDrawerOpen(true, 'printables'); await searchFamilyPrintables('records deadlines'); }},
      {id: 'local_family_resources', group: 'Resources', label: 'Local family resources', hint: 'Search county and municipality printable sheets', aliases: 'portland cumberland york local resource', run: async () => { setDrawerOpen(true, 'printables'); await searchFamilyPrintables('Portland family resources'); }},
      {id: 'open_review_handoff', group: 'Evidence', label: 'Open reviewer handoff', hint: 'Missing facts, follow-up questions and review notes', aliases: 'review audit missing information', run: () => setDrawerOpen(true, 'review')},
      {id: 'open_privacy_information', group: 'Safety', label: 'Open privacy information', hint: 'Understand local storage, exports and external links', aliases: 'local only confidential security data', run: () => openOverlay(privacyOverlay)},
      {id: 'open_help', group: 'Help', label: 'Open help', hint: 'How to use the local workbench', aliases: 'tips support guide', run: () => openOverlay(helpOverlay)},
      {id: 'open_focaf_resources', group: 'Help', label: 'Open FOCAF family resources', hint: 'Optional external resource site; no matter details are sent', aliases: 'focaf family resources download library external', run: () => window.open('https://focaf.jtforme.com/', '_blank', 'noopener,noreferrer')},
      {id: 'open_focaf_downloads', group: 'Help', label: 'Open FOCAF download library', hint: 'Optional external downloads; opens separately in your browser', aliases: 'focaf downloads library external', run: () => window.open('https://focaf.jtforme.com/download-library/', '_blank', 'noopener,noreferrer')},
      {id: 'open_keyboard_shortcuts', group: 'Help', label: 'Open keyboard shortcuts', hint: 'Ctrl+K, Ctrl+J, Enter and Escape', aliases: 'keys hotkeys commands', run: () => openOverlay(shortcutsOverlay)},
      {id: 'open_justice_lens', group: 'Help', label: 'Open the Justice key', hint: 'Ctrl+J · constitutional civic delight', aliases: 'justice constitution we the people establish justice', run: () => openJustice()},
      {id: 'open_constitutional_principles', group: 'Help', label: 'Open constitutional principles', hint: 'Public service, source authority, privacy and dignity', aliases: 'we the people justice constitution public', run: () => openJustice()},
    ];
    let commandIndex = 0;
    let filteredCommands = [...commandDefinitions];
    let constitutionalPopoverPinned = false;
    let constitutionalCloseTimer = 0;

    function setSearchMode(mode) {
      if (!searchMode) return;
      if ((mode === 'my_records' || mode === 'both') && !corpusSelect?.value) {
        setDrawerOpen(true, 'setup');
        showToast('Choose an active matter before searching private records.');
        return;
      }
      searchMode.value = mode;
      document.querySelectorAll('[data-search-mode]').forEach((button) => {
        const selected = button.dataset.searchMode === mode;
        button.classList.toggle('is-selected', selected);
        button.setAttribute('aria-checked', selected ? 'true' : 'false');
      });
      syncContextBar();
      showToast(`Search mode: ${selectedLabel(searchMode)}.`);
      question?.focus();
    }

    function renderCommands(filter = '') {
      const needle = filter.trim().toLowerCase();
      filteredCommands = commandDefinitions.filter((command) => {
        const haystack = `${command.group} ${command.label} ${command.hint} ${command.aliases || ''}`.toLowerCase();
        return !needle || haystack.includes(needle);
      });
      commandIndex = Math.min(commandIndex, Math.max(0, filteredCommands.length - 1));
      const groups = [];
      filteredCommands.forEach((command, index) => {
        let group = groups.find((item) => item.name === command.group);
        if (!group) {
          group = {name: command.group, commands: []};
          groups.push(group);
        }
        group.commands.push({command, index});
      });
      commandList.innerHTML = groups.map((group) => `
        <div class="command-group" role="presentation">${escapeHtml(group.name)}</div>
        ${group.commands.map(({command, index}) => `
          <button class="command-item${index === commandIndex ? ' is-active' : ''}" id="command-option-${escapeHtml(command.id)}" type="button" role="option" aria-selected="${index === commandIndex ? 'true' : 'false'}" aria-posinset="${index + 1}" aria-setsize="${filteredCommands.length}" data-command-id="${escapeHtml(command.id)}">
            <span><strong>${escapeHtml(command.label)}</strong><br><small>${escapeHtml(command.hint)}</small></span>
            <span aria-hidden="true">↵</span>
          </button>`).join('')}
      `).join('') || '<p class="muted">No commands matched. Try “justice,” “privacy,” “sources,” or “new conversation.”</p>';
      const active = commandList.querySelector('.is-active');
      if (active) {
        commandSearch.setAttribute('aria-activedescendant', active.id);
        active.scrollIntoView({block: 'nearest'});
      } else {
        commandSearch.removeAttribute('aria-activedescendant');
      }
      if (commandResultsStatus) {
        const suffix = filteredCommands.length === 1 ? 'command' : 'commands';
        commandResultsStatus.textContent = `${filteredCommands.length} ${suffix} available`;
      }
      commandList.querySelectorAll('[data-command-id]').forEach((button) => {
        button.addEventListener('mousemove', () => {
          const nextIndex = filteredCommands.findIndex((item) => item.id === button.dataset.commandId);
          if (nextIndex >= 0 && nextIndex !== commandIndex) {
            commandIndex = nextIndex;
            renderCommands(commandSearch.value);
          }
        });
        button.addEventListener('click', () => runCommand(button.dataset.commandId));
      });
    }

    function openCommandPalette() {
      openOverlay(commandPalette);
      commandSearch.value = '';
      commandIndex = 0;
      renderCommands();
      window.setTimeout(() => commandSearch.focus(), 20);
    }

    function closeCommandPalette() {
      closeOverlay(commandPalette);
      commandPaletteButton?.focus();
    }

    function runCommand(id) {
      const command = commandDefinitions.find((item) => item.id === id);
      if (!command) return;
      closeOverlay(commandPalette);
      command.run();
    }

    function openJustice() {
      openOverlay(justiceOverlay);
      window.setTimeout(() => closeJusticeButton?.focus(), 20);
    }

    function showConstitutionalPopover({pinned = false} = {}) {
      window.clearTimeout(constitutionalCloseTimer);
      constitutionalPopoverPinned = pinned || constitutionalPopoverPinned;
      constitutionalPopover.hidden = false;
      constitutionalIdentity?.setAttribute('aria-expanded', 'true');
    }

    function hideConstitutionalPopover({force = false, delay = 0} = {}) {
      window.clearTimeout(constitutionalCloseTimer);
      if (constitutionalPopoverPinned && !force) return;
      const close = () => {
        constitutionalPopover.hidden = true;
        constitutionalIdentity?.setAttribute('aria-expanded', 'false');
        if (force) constitutionalPopoverPinned = false;
      };
      if (force && delay === 0) close();
      else constitutionalCloseTimer = window.setTimeout(close, delay);
    }

    let localStatusPinned = false;
    let localStatusCloseTimer = 0;
    let footerClickCount = 0;
    let footerClickTimer = 0;

    function showLocalStatus({pinned = false} = {}) {
      window.clearTimeout(localStatusCloseTimer);
      localStatusPinned = pinned || localStatusPinned;
      localStatusPopover.hidden = false;
      health?.setAttribute('aria-expanded', 'true');
    }

    function hideLocalStatus({force = false, delay = 0} = {}) {
      window.clearTimeout(localStatusCloseTimer);
      if (localStatusPinned && !force) return;
      const close = () => {
        localStatusPopover.hidden = true;
        health?.setAttribute('aria-expanded', 'false');
        if (force) localStatusPinned = false;
      };
      if (force && delay === 0) close();
      else localStatusCloseTimer = window.setTimeout(close, delay);
    }

    matterShortcutButton?.addEventListener('click', () => setDrawerOpen(true, 'setup'));
    matterButton?.addEventListener('click', () => setDrawerOpen(true, 'setup'));
    privacyButton?.addEventListener('click', () => openOverlay(privacyOverlay));
    footerPrivacyButton?.addEventListener('click', () => openOverlay(privacyOverlay));
    closePrivacyButton?.addEventListener('click', () => closeOverlay(privacyOverlay));
    closeShortcutsButton?.addEventListener('click', () => closeOverlay(shortcutsOverlay));
    closeBuildButton?.addEventListener('click', () => closeOverlay(buildOverlay));
    closeConstitutionalPopoverButton?.addEventListener('click', () => {
      constitutionalIdentity?.focus({preventScroll: true});
      hideConstitutionalPopover({force: true});
    });
    closeLocalStatusPopoverButton?.addEventListener('click', () => {
      health?.focus({preventScroll: true});
      hideLocalStatus({force: true});
    });
    health?.addEventListener('mouseenter', () => showLocalStatus());
    health?.addEventListener('mouseleave', () => hideLocalStatus({delay: 220}));
    health?.addEventListener('focus', () => showLocalStatus());
    health?.addEventListener('blur', () => hideLocalStatus({delay: 120}));
    health?.addEventListener('click', () => {
      if (localStatusPinned) hideLocalStatus({force: true});
      else showLocalStatus({pinned: true});
    });
    localStatusPopover?.addEventListener('mouseenter', () => showLocalStatus());
    localStatusPopover?.addEventListener('mouseleave', () => hideLocalStatus({delay: 220}));
    localStatusPopover?.addEventListener('focusin', () => showLocalStatus());
    localStatusPopover?.addEventListener('focusout', (event) => {
      if (!localStatusPopover.contains(event.relatedTarget)) hideLocalStatus({delay: 120});
    });
    footerVersion?.addEventListener('click', () => {
      footerClickCount += 1;
      window.clearTimeout(footerClickTimer);
      footerClickTimer = window.setTimeout(() => { footerClickCount = 0; }, 700);
      if (footerClickCount >= 3) {
        footerClickCount = 0;
        openOverlay(buildOverlay);
      }
    });

    commandPaletteButton?.addEventListener('click', openCommandPalette);
    closeCommandPaletteButton?.addEventListener('click', closeCommandPalette);
    commandSearch?.addEventListener('input', () => { commandIndex = 0; renderCommands(commandSearch.value); });
    commandSearch?.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') { event.preventDefault(); commandIndex = Math.min(commandIndex + 1, filteredCommands.length - 1); renderCommands(commandSearch.value); }
      if (event.key === 'ArrowUp') { event.preventDefault(); commandIndex = Math.max(commandIndex - 1, 0); renderCommands(commandSearch.value); }
      if (event.key === 'Home') { event.preventDefault(); commandIndex = 0; renderCommands(commandSearch.value); }
      if (event.key === 'End') { event.preventDefault(); commandIndex = Math.max(0, filteredCommands.length - 1); renderCommands(commandSearch.value); }
      if (event.key === 'Enter' && filteredCommands[commandIndex]) { event.preventDefault(); runCommand(filteredCommands[commandIndex].id); }
      if (event.key === 'Escape') { event.preventDefault(); closeCommandPalette(); }
    });
    closeJusticeButton?.addEventListener('click', () => closeOverlay(justiceOverlay));

    constitutionalIdentity?.addEventListener('mouseenter', () => showConstitutionalPopover());
    constitutionalIdentity?.addEventListener('mouseleave', () => hideConstitutionalPopover({delay: 220}));
    constitutionalIdentity?.addEventListener('focus', () => showConstitutionalPopover());
    constitutionalIdentity?.addEventListener('blur', () => hideConstitutionalPopover({delay: 120}));
    constitutionalIdentity?.addEventListener('click', () => {
      if (constitutionalPopoverPinned) hideConstitutionalPopover({force: true});
      else showConstitutionalPopover({pinned: true});
    });
    constitutionalPopover?.addEventListener('mouseenter', () => showConstitutionalPopover());
    constitutionalPopover?.addEventListener('mouseleave', () => hideConstitutionalPopover({delay: 220}));
    constitutionalPopover?.addEventListener('focusin', () => showConstitutionalPopover());
    constitutionalPopover?.addEventListener('focusout', (event) => {
      if (!constitutionalPopover.contains(event.relatedTarget)) hideConstitutionalPopover({delay: 120});
    });

    question?.addEventListener('input', () => {
      question.style.height = 'auto';
      question.style.height = `${Math.min(question.scrollHeight, 180)}px`;
    });

    document.querySelectorAll('.overlay-shell').forEach((overlay) => {
      overlay.addEventListener('mousedown', (event) => {
        if (event.target === overlay) closeOverlay(overlay);
      });
    });

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Tab') return;
      const activeOverlay = Array.from(document.querySelectorAll('.overlay-shell')).find((overlay) => !overlay.hidden);
      if (!activeOverlay) return;
      const focusable = overlayFocusableElements(activeOverlay);
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    document.addEventListener('click', (event) => {
      if (constitutionalPopoverPinned && !constitutionalIdentity?.contains(event.target) && !constitutionalPopover?.contains(event.target)) {
        hideConstitutionalPopover({force: true});
      }
      if (localStatusPinned && !health?.contains(event.target) && !localStatusPopover?.contains(event.target)) {
        hideLocalStatus({force: true});
      }
    });

    document.addEventListener('keydown', (event) => {
      const ctrlOrMeta = event.ctrlKey || event.metaKey;
      if (ctrlOrMeta && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        openCommandPalette();
        return;
      }
      if (ctrlOrMeta && event.key.toLowerCase() === 'j') {
        event.preventDefault();
        openJustice();
        return;
      }
      if (event.key === 'Escape') {
        closeOverlay(helpOverlay);
        closeOverlay(welcomeOverlay);
        closeOverlay(commandPalette);
        closeOverlay(justiceOverlay);
        closeOverlay(privacyOverlay);
        closeOverlay(shortcutsOverlay);
        closeOverlay(buildOverlay);
        setDrawerOpen(false);
        hideConstitutionalPopover({force: true});
        hideLocalStatus({force: true});
      }
    });

    selectDrawerTab('evidence');
    syncResponsiveLayout({initial: true});
    const scheduleResponsiveSync = (() => {
      let frame = 0;
      return () => {
        window.cancelAnimationFrame(frame);
        frame = window.requestAnimationFrame(() => syncResponsiveLayout());
      };
    })();
    [inlineDrawerQuery, fullWorkbenchQuery].forEach((query) => {
      if (typeof query.addEventListener === 'function') query.addEventListener('change', scheduleResponsiveSync);
      else if (typeof query.addListener === 'function') query.addListener(scheduleResponsiveSync);
    });
    window.addEventListener('resize', scheduleResponsiveSync, {passive: true});
    renderCommands();

    // v5.0 premium workbench marker: constitutional_bar, mission_popover_close, local_privacy_popover, evidence_drawer, grouped_ctrl_k_command_palette, ctrl_j_justice_key, privacy_overlay, shortcuts_overlay, civic_build_card
