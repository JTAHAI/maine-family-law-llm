
    const question = document.getElementById('question');
    const answer = document.getElementById('answer');
    const transcript = document.getElementById('transcript');
    const chatScroll = document.querySelector('.chat-scroll');
    const chatPanel = document.querySelector('.chat-panel');
    const sourceCards = document.getElementById('source-cards');
    const recordCardFilter = document.getElementById('record-card-filter');
    const recordCardFilterClear = document.getElementById('record-card-filter-clear');
    const recordCardFilterStatus = document.getElementById('record-card-filter-status');
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
    const authorityLibraryStatus = document.getElementById('authority-library-status');
    const authorityLibraryBuildId = document.getElementById('authority-library-build-id');
    const authorityLibraryLastUpdate = document.getElementById('authority-library-last-update');
    const authorityLibraryCounts = document.getElementById('authority-library-counts');
    const authorityLibraryClassCounts = document.getElementById('authority-library-class-counts');
    const authoritySearch = document.getElementById('authority-search');
    const authoritySourceClassFilter = document.getElementById('authority-source-class-filter');
    const authorityFreshnessFilter = document.getElementById('authority-freshness-filter');
    const authorityIssueFilter = document.getElementById('authority-issue-filter');
    const authorityFixtureMode = document.getElementById('authority-fixture-mode');
    const authorityDryRun = document.getElementById('authority-dry-run');
    const authorityForceRefresh = document.getElementById('authority-force-refresh');
    const authorityNetworkAck = document.getElementById('authority-network-ack');
    const authorityUpdateButton = document.getElementById('authority-update-button');
    const authorityUpdateCancelButton = document.getElementById('authority-update-cancel-button');
    const authorityUpdateRefreshButton = document.getElementById('authority-update-refresh-button');
    const authorityUpdateProgress = document.getElementById('authority-update-progress');
    // Engineering-only authority update switches stay in the mirrored markup
    // for fixture compatibility, but are never operable or exposed in the
    // production workbench. Public updates require a fresh, explicit network
    // acknowledgement and always use the canonical live path.
    [authorityFixtureMode, authorityDryRun, authorityForceRefresh].forEach((control) => {
      if (!control) return;
      control.checked = false;
      control.closest('label')?.setAttribute('hidden', '');
    });
    const health = document.getElementById('health');
    const connectionBanner = document.getElementById('connection-banner');
    const connectionRetry = document.getElementById('connection-retry');
    const sessionSummary = document.getElementById('session-summary');
    const trustStatusStrip = document.getElementById('trust-status-strip');
    const trustAuthorityStatus = document.getElementById('trust-authority-status');
    const trustAuthorityDetail = document.getElementById('trust-authority-detail');
    const trustAuthorityAction = document.getElementById('trust-authority-action');
    const trustRecordStatus = document.getElementById('trust-record-status');
    const trustRecordDetail = document.getElementById('trust-record-detail');
    const trustRecordAction = document.getElementById('trust-record-action');
    const trustReviewStatus = document.getElementById('trust-review-status');
    const trustReviewDetail = document.getElementById('trust-review-detail');
    const trustReviewAction = document.getElementById('trust-review-action');
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
    const sourcePreviewFlyout = document.getElementById('source-preview-flyout');
    const sourcePreviewTitle = document.getElementById('source-preview-title');
    const sourcePreviewBody = document.getElementById('source-preview-body');
    const sourcePreviewActions = document.getElementById('source-preview-actions');
    const sourcePreviewClose = document.getElementById('source-preview-close');
    const sourcePreviewBackdrop = document.getElementById('source-preview-backdrop');
    const recordInspector = document.getElementById('record-inspector');
    const recordInspectorBackdrop = document.getElementById('record-inspector-backdrop');
    const recordInspectorClose = document.getElementById('record-inspector-close');
    const recordInspectorTitle = document.getElementById('record-inspector-title');
    const recordInspectorSubtitle = document.getElementById('record-inspector-subtitle');
    const recordInspectorBadges = document.getElementById('record-inspector-badges');
    const recordInspectorViewer = document.getElementById('record-inspector-viewer');
    const recordInspectorDetails = document.getElementById('record-inspector-details');
    const recordInspectorPageControls = document.getElementById('record-inspector-page-controls');
    const recordInspectorPageInput = document.getElementById('record-inspector-page-input');
    const recordInspectorPageCount = document.getElementById('record-inspector-page-count');
    const recordInspectorPrevPage = document.getElementById('record-inspector-prev-page');
    const recordInspectorNextPage = document.getElementById('record-inspector-next-page');
    const recordInspectorZoomControls = document.getElementById('record-inspector-zoom-controls');
    const recordInspectorZoomIn = document.getElementById('record-inspector-zoom-in');
    const recordInspectorZoomOut = document.getElementById('record-inspector-zoom-out');
    const recordInspectorZoomFit = document.getElementById('record-inspector-zoom-fit');
    const recordInspectorOpenOriginal = document.getElementById('record-inspector-open-original');
    const recordInspectorDownload = document.getElementById('record-inspector-download');
    const recordInspectorCopyDetails = document.getElementById('record-inspector-copy-details');
    const recordInspectorDocumentIntelligence = document.getElementById('record-inspector-document-intelligence');
    const recordInspectorEvidenceWorkProduct = document.getElementById('record-inspector-evidence-work-product');
    const recordInspectorRetrievalWorkbench = document.getElementById('record-inspector-retrieval-workbench');
    const retrievalWorkbenchModal = document.getElementById('retrieval-workbench-modal');
    const retrievalWorkbenchBackdrop = document.getElementById('retrieval-workbench-backdrop');
    const retrievalWorkbenchClose = document.getElementById('retrieval-workbench-close');
    const retrievalWorkbenchStatus = document.getElementById('retrieval-workbench-status');
    const retrievalWorkbenchBackends = document.getElementById('retrieval-workbench-backends');
    const retrievalWorkbenchQuery = document.getElementById('retrieval-workbench-query');
    const retrievalWorkbenchPrivate = document.getElementById('retrieval-workbench-private');
    const retrievalWorkbenchAuthority = document.getElementById('retrieval-workbench-authority');
    const retrievalWorkbenchLimit = document.getElementById('retrieval-workbench-limit');
    const retrievalWorkbenchSearch = document.getElementById('retrieval-workbench-search');
    const retrievalWorkbenchEvalMin = document.getElementById('retrieval-workbench-eval-min');
    const retrievalWorkbenchEvaluate = document.getElementById('retrieval-workbench-evaluate');
    const retrievalWorkbenchResults = document.getElementById('retrieval-workbench-results');
    const recordInspectorReleasePilotHardening = document.getElementById('record-inspector-release-pilot-hardening');
    const releasePilotHardeningModal = document.getElementById('release-pilot-hardening-modal');
    const releasePilotHardeningBackdrop = document.getElementById('release-pilot-hardening-backdrop');
    const releasePilotHardeningClose = document.getElementById('release-pilot-hardening-close');
    const releasePilotHardeningStatus = document.getElementById('release-pilot-hardening-status');
    const releasePilotHardeningResults = document.getElementById('release-pilot-hardening-results');
    const releasePilotHardeningRefresh = document.getElementById('release-pilot-hardening-refresh');
    const releasePilotHardeningAudit = document.getElementById('release-pilot-hardening-audit');
    const releasePilotHardeningObservability = document.getElementById('release-pilot-hardening-observability');
    const releasePilotHardeningBackup = document.getElementById('release-pilot-hardening-backup');
    const releasePilotParticipantId = document.getElementById('release-pilot-participant-id');
    const releasePilotRole = document.getElementById('release-pilot-role');
    const releasePilotVerificationHash = document.getElementById('release-pilot-verification-hash');
    const releasePilotBarVerified = document.getElementById('release-pilot-bar-verified');
    const releasePilotTerms = document.getElementById('release-pilot-terms');
    const releasePilotTraining = document.getElementById('release-pilot-training');
    const releasePilotRegister = document.getElementById('release-pilot-register');
    const releasePilotSessionParticipant = document.getElementById('release-pilot-session-participant');
    const releasePilotDataClass = document.getElementById('release-pilot-data-class');
    const releasePilotStartSession = document.getElementById('release-pilot-start-session');
    const releasePilotFeedbackParticipant = document.getElementById('release-pilot-feedback-participant');
    const releasePilotFeedbackSession = document.getElementById('release-pilot-feedback-session');
    const releasePilotFeedbackCategory = document.getElementById('release-pilot-feedback-category');
    const releasePilotFeedbackSeverity = document.getElementById('release-pilot-feedback-severity');
    const releasePilotFeedbackDescription = document.getElementById('release-pilot-feedback-description');
    const releasePilotSubmitFeedback = document.getElementById('release-pilot-submit-feedback');
    const sandboxOperationsRefresh = document.getElementById('sandbox-operations-refresh');
    const sandboxOperationsProgramId = document.getElementById('sandbox-operations-program-id');
    const sandboxOperationsQuestionCount = document.getElementById('sandbox-operations-question-count');
    const sandboxOperationsCreateProgram = document.getElementById('sandbox-operations-create-program');
    const sandboxOperationsCohortId = document.getElementById('sandbox-operations-cohort-id');
    const sandboxOperationsCohortParticipants = document.getElementById('sandbox-operations-cohort-participants');
    const sandboxOperationsCreateCohort = document.getElementById('sandbox-operations-create-cohort');
    const sandboxOperationsAssignmentParticipant = document.getElementById('sandbox-operations-assignment-participant');
    const sandboxOperationsQuestionIds = document.getElementById('sandbox-operations-question-ids');
    const sandboxOperationsDataClass = document.getElementById('sandbox-operations-data-class');
    const sandboxOperationsCreateAssignment = document.getElementById('sandbox-operations-create-assignment');
    const sandboxOperationsReviewParticipant = document.getElementById('sandbox-operations-review-participant');
    const sandboxOperationsReviewSession = document.getElementById('sandbox-operations-review-session');
    const sandboxOperationsReviewQuestion = document.getElementById('sandbox-operations-review-question');
    const sandboxOperationsReviewDisposition = document.getElementById('sandbox-operations-review-disposition');
    const sandboxOperationsRatingGrounding = document.getElementById('sandbox-operations-rating-grounding');
    const sandboxOperationsRatingAccuracy = document.getElementById('sandbox-operations-rating-accuracy');
    const sandboxOperationsRatingUsefulness = document.getElementById('sandbox-operations-rating-usefulness');
    const sandboxOperationsRatingSafety = document.getElementById('sandbox-operations-rating-safety');
    const sandboxOperationsRatingCitations = document.getElementById('sandbox-operations-rating-citations');
    const sandboxOperationsFindingCodes = document.getElementById('sandbox-operations-finding-codes');
    const sandboxOperationsResponseHash = document.getElementById('sandbox-operations-response-hash');
    const sandboxOperationsVerifierHash = document.getElementById('sandbox-operations-verifier-hash');
    const sandboxOperationsComment = document.getElementById('sandbox-operations-comment');
    const sandboxOperationsSubmitReview = document.getElementById('sandbox-operations-submit-review');
    const sandboxOperationsCompleteSession = document.getElementById('sandbox-operations-complete-session');
    const sandboxOperationsBuildEvidence = document.getElementById('sandbox-operations-build-evidence');
    const gaReleaseCandidateRefresh = document.getElementById('ga-release-candidate-refresh');
    const gaReleaseCandidateId = document.getElementById('ga-release-candidate-id');
    const gaReleaseCandidateVersion = document.getElementById('ga-release-candidate-version');
    const gaReleaseCandidateSourceName = document.getElementById('ga-release-candidate-source-name');
    const gaReleaseCandidateSourceHash = document.getElementById('ga-release-candidate-source-hash');
    const gaReleaseCandidateCreate = document.getElementById('ga-release-candidate-create');
    const gaReleaseCandidateArtifactType = document.getElementById('ga-release-candidate-artifact-type');
    const gaReleaseCandidateArtifactVersion = document.getElementById('ga-release-candidate-artifact-version');
    const gaReleaseCandidateArtifactReference = document.getElementById('ga-release-candidate-artifact-reference');
    const gaReleaseCandidateArtifactHash = document.getElementById('ga-release-candidate-artifact-hash');
    const gaReleaseCandidateArtifactExternal = document.getElementById('ga-release-candidate-artifact-external');
    const gaReleaseCandidateRecordArtifact = document.getElementById('ga-release-candidate-record-artifact');
    const gaReleaseCandidateSignoffRole = document.getElementById('ga-release-candidate-signoff-role');
    const gaReleaseCandidateSigner = document.getElementById('ga-release-candidate-signer');
    const gaReleaseCandidateSignoffStatus = document.getElementById('ga-release-candidate-signoff-status');
    const gaReleaseCandidateSignedAt = document.getElementById('ga-release-candidate-signed-at');
    const gaReleaseCandidateSignoffHash = document.getElementById('ga-release-candidate-signoff-hash');
    const gaReleaseCandidateRecordSignoff = document.getElementById('ga-release-candidate-record-signoff');
    const gaReleaseCandidateBlockerId = document.getElementById('ga-release-candidate-blocker-id');
    const gaReleaseCandidateBlockerSeverity = document.getElementById('ga-release-candidate-blocker-severity');
    const gaReleaseCandidateBlockerStatus = document.getElementById('ga-release-candidate-blocker-status');
    const gaReleaseCandidateBlockerDescription = document.getElementById('ga-release-candidate-blocker-description');
    const gaReleaseCandidateBlockerHash = document.getElementById('ga-release-candidate-blocker-hash');
    const gaReleaseCandidateRecordBlocker = document.getElementById('ga-release-candidate-record-blocker');
    const gaReleaseCandidateReadiness = document.getElementById('ga-release-candidate-readiness');
    const gaReleaseCandidateFreeze = document.getElementById('ga-release-candidate-freeze');
    const gaReleaseCandidateBuildEvidence = document.getElementById('ga-release-candidate-build-evidence');
    const gaShipmentReadinessRefresh = document.getElementById('ga-shipment-readiness-refresh');
    const gaShipmentReadinessId = document.getElementById('ga-shipment-readiness-id');
    const gaShipmentReadinessVersion = document.getElementById('ga-shipment-readiness-version');
    const gaShipmentReadinessSourceName = document.getElementById('ga-shipment-readiness-source-name');
    const gaShipmentReadinessSourceHash = document.getElementById('ga-shipment-readiness-source-hash');
    const gaShipmentReadinessRcId = document.getElementById('ga-shipment-readiness-rc-id');
    const gaShipmentReadinessRcReportHash = document.getElementById('ga-shipment-readiness-rc-report-hash');
    const gaShipmentReadinessRcInventoryHash = document.getElementById('ga-shipment-readiness-rc-inventory-hash');
    const gaShipmentReadinessChannel = document.getElementById('ga-shipment-readiness-channel');
    const gaShipmentReadinessCreate = document.getElementById('ga-shipment-readiness-create');
    const gaShipmentReadinessArtifactType = document.getElementById('ga-shipment-readiness-artifact-type');
    const gaShipmentReadinessArtifactVersion = document.getElementById('ga-shipment-readiness-artifact-version');
    const gaShipmentReadinessArtifactReference = document.getElementById('ga-shipment-readiness-artifact-reference');
    const gaShipmentReadinessArtifactHash = document.getElementById('ga-shipment-readiness-artifact-hash');
    const gaShipmentReadinessArtifactExternal = document.getElementById('ga-shipment-readiness-artifact-external');
    const gaShipmentReadinessRecordArtifact = document.getElementById('ga-shipment-readiness-record-artifact');
    const gaShipmentReadinessControl = document.getElementById('ga-shipment-readiness-control');
    const gaShipmentReadinessControlSatisfied = document.getElementById('ga-shipment-readiness-control-satisfied');
    const gaShipmentReadinessControlHash = document.getElementById('ga-shipment-readiness-control-hash');
    const gaShipmentReadinessRecordControl = document.getElementById('ga-shipment-readiness-record-control');
    const gaShipmentReadinessChannelStatus = document.getElementById('ga-shipment-readiness-channel-status');
    const gaShipmentReadinessPackageHash = document.getElementById('ga-shipment-readiness-package-hash');
    const gaShipmentReadinessQualificationHash = document.getElementById('ga-shipment-readiness-qualification-hash');
    const gaShipmentReadinessRollbackHash = document.getElementById('ga-shipment-readiness-rollback-hash');
    const gaShipmentReadinessDistributionReference = document.getElementById('ga-shipment-readiness-distribution-reference');
    const gaShipmentReadinessReceiptHash = document.getElementById('ga-shipment-readiness-receipt-hash');
    const gaShipmentReadinessRecordChannel = document.getElementById('ga-shipment-readiness-record-channel');
    const gaShipmentReadinessBlockerId = document.getElementById('ga-shipment-readiness-blocker-id');
    const gaShipmentReadinessBlockerSeverity = document.getElementById('ga-shipment-readiness-blocker-severity');
    const gaShipmentReadinessBlockerStatus = document.getElementById('ga-shipment-readiness-blocker-status');
    const gaShipmentReadinessBlockerDescription = document.getElementById('ga-shipment-readiness-blocker-description');
    const gaShipmentReadinessBlockerHash = document.getElementById('ga-shipment-readiness-blocker-hash');
    const gaShipmentReadinessRecordBlocker = document.getElementById('ga-shipment-readiness-record-blocker');
    const gaShipmentReadinessRcStatus = document.getElementById('ga-shipment-readiness-rc-status');
    const gaShipmentReadinessRcFrozen = document.getElementById('ga-shipment-readiness-rc-frozen');
    const gaShipmentReadinessEvaluate = document.getElementById('ga-shipment-readiness-evaluate');
    const gaShipmentReadinessBuildEvidence = document.getElementById('ga-shipment-readiness-build-evidence');
    const realMatterPilotRefresh = document.getElementById('real-matter-pilot-refresh');
    const realMatterPilotProgramId = document.getElementById('real-matter-pilot-program-id');
    const realMatterPilotTenants = document.getElementById('real-matter-pilot-tenants');
    const realMatterPilotPass48Hash = document.getElementById('real-matter-pilot-pass48-hash');
    const realMatterPilotCreateProgram = document.getElementById('real-matter-pilot-create-program');
    const realMatterPilotMatterId = document.getElementById('real-matter-pilot-matter-id');
    const realMatterPilotTenantId = document.getElementById('real-matter-pilot-tenant-id');
    const realMatterPilotParticipantId = document.getElementById('real-matter-pilot-participant-id');
    const realMatterPilotConsentVersion = document.getElementById('real-matter-pilot-consent-version');
    const realMatterPilotConsentHash = document.getElementById('real-matter-pilot-consent-hash');
    const realMatterPilotPrivacyHash = document.getElementById('real-matter-pilot-privacy-hash');
    const realMatterPilotStoreHash = document.getElementById('real-matter-pilot-store-hash');
    const realMatterPilotIsolationHash = document.getElementById('real-matter-pilot-isolation-hash');
    const realMatterPilotEncryptionHash = document.getElementById('real-matter-pilot-encryption-hash');
    const realMatterPilotRetentionVersion = document.getElementById('real-matter-pilot-retention-version');
    const realMatterPilotConsentApproved = document.getElementById('real-matter-pilot-consent-approved');
    const realMatterPilotExportAck = document.getElementById('real-matter-pilot-export-ack');
    const realMatterPilotEnroll = document.getElementById('real-matter-pilot-enroll');
    const realMatterPilotArtifacts = document.getElementById('real-matter-pilot-artifacts');
    const realMatterPilotWorkProduct = document.getElementById('real-matter-pilot-work-product');
    const realMatterPilotReviewDate = document.getElementById('real-matter-pilot-review-date');
    const realMatterPilotUsefulness = document.getElementById('real-matter-pilot-usefulness');
    const realMatterPilotReviewHash = document.getElementById('real-matter-pilot-review-hash');
    const realMatterPilotBlockers = document.getElementById('real-matter-pilot-blockers');
    const realMatterPilotDailyReview = document.getElementById('real-matter-pilot-daily-review');
    const realMatterPilotSignoffHash = document.getElementById('real-matter-pilot-signoff-hash');
    const realMatterPilotSignoffComplete = document.getElementById('real-matter-pilot-signoff-complete');
    const realMatterPilotSignoff = document.getElementById('real-matter-pilot-signoff');
    const realMatterPilotBuildEvidence = document.getElementById('real-matter-pilot-build-evidence');
    const evidenceWorkProductModal = document.getElementById('evidence-work-product-modal');
    const evidenceWorkProductBackdrop = document.getElementById('evidence-work-product-backdrop');
    const evidenceWorkProductClose = document.getElementById('evidence-work-product-close');
    const evidenceWorkProductStatus = document.getElementById('evidence-work-product-status');
    const evidenceWorkProductScope = document.getElementById('evidence-work-product-scope');
    const evidenceWorkProductAllRecords = document.getElementById('evidence-work-product-all-records');
    const evidenceWorkProductFocus = document.getElementById('evidence-work-product-focus');
    const evidenceWorkProductApproved = document.getElementById('evidence-work-product-approved');
    const evidenceWorkProductBuild = document.getElementById('evidence-work-product-build');
    const evidenceWorkProductLoadActive = document.getElementById('evidence-work-product-load-active');
    const evidenceWorkProductResults = document.getElementById('evidence-work-product-results');
    const documentIntelligenceModal = document.getElementById('document-intelligence-modal');
    const documentIntelligenceBackdrop = document.getElementById('document-intelligence-backdrop');
    const documentIntelligenceClose = document.getElementById('document-intelligence-close');
    const documentIntelligenceStatus = document.getElementById('document-intelligence-status');
    const documentIntelligenceAdapters = document.getElementById('document-intelligence-adapters');
    const documentIntelligenceUseDocling = document.getElementById('document-intelligence-use-docling');
    const documentIntelligenceUsePresidio = document.getElementById('document-intelligence-use-presidio');
    const documentIntelligenceApproved = document.getElementById('document-intelligence-approved');
    const documentIntelligenceAnalyze = document.getElementById('document-intelligence-analyze');
    const documentIntelligenceOcrLanguage = document.getElementById('document-intelligence-ocr-language');
    const documentIntelligenceOcrApproved = document.getElementById('document-intelligence-ocr-approved');
    const documentIntelligenceOcr = document.getElementById('document-intelligence-ocr');
    const documentIntelligenceResults = document.getElementById('document-intelligence-results');
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
    const localWorkbenchButton = document.getElementById('local-workbench-button');
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
    const localStatusDot = document.getElementById('local-status-dot');
    const commandResultsStatus = document.getElementById('command-results-status');
    const drawerActiveCorpus = document.getElementById('drawer-active-corpus');
    const drawerCorpusCount = document.getElementById('drawer-corpus-count');
    const drawerOcrPercent = document.getElementById('drawer-ocr-percent');
    const drawerOcrProgress = document.querySelector('.v5-progress i');
    const drawerRefreshCorpus = document.getElementById('drawer-refresh-corpus');
    const quickNewCorpus = document.getElementById('quick-new-corpus');
    const quickOpenWorkspace = document.getElementById('quick-open-workspace');
    const quickLocalWorkbench = document.getElementById('quick-local-workbench');
    const localWorkbenchOverlay = document.getElementById('local-workbench-overlay');
    const localWorkbenchClose = document.getElementById('local-workbench-close');
    const localWorkbenchRefresh = document.getElementById('local-workbench-refresh');
    const localWorkbenchReleaseReadiness = document.getElementById('local-workbench-release-readiness');
    const localWorkbenchSavePreferences = document.getElementById('local-workbench-save-preferences');
    const localWorkbenchStatus = document.getElementById('local-workbench-status');
    const localWorkbenchSummary = document.getElementById('local-workbench-summary');
    const localWorkbenchReadingLevel = document.getElementById('local-workbench-reading-level');
    const localWorkbenchReducedMotion = document.getElementById('local-workbench-reduced-motion');
    const localWorkbenchScreenReader = document.getElementById('local-workbench-screen-reader');
    let localWorkbenchReturnFocus = null;
    const documentWorkspace = document.getElementById('document-workspace');
    const documentWorkspaceBackdrop = document.getElementById('document-workspace-backdrop');
    const documentWorkspaceClose = document.getElementById('document-workspace-close');
    const documentWorkspaceRefresh = document.getElementById('document-workspace-refresh');
    const documentWorkspaceNew = document.getElementById('document-workspace-new');
    const documentWorkspaceList = document.getElementById('document-workspace-list');
    const documentWorkspaceAudit = document.getElementById('document-workspace-audit');
    const documentReviewQueue = document.getElementById('document-review-queue');
    const documentReviewQueueRefresh = document.getElementById('document-review-queue-refresh');
    const documentWorkspaceTitle = document.getElementById('document-workspace-title');
    const documentWorkspaceType = document.getElementById('document-workspace-type');
    const documentWorkspaceEditor = document.getElementById('document-workspace-editor');
    const documentWorkspaceMeta = document.getElementById('document-workspace-meta');
    const documentWorkspaceStatus = document.getElementById('document-workspace-status');
    const documentWorkspaceSaveNew = document.getElementById('document-workspace-save-new');
    const documentWorkspacePropose = document.getElementById('document-workspace-propose');
    const documentWorkspaceCommit = document.getElementById('document-workspace-commit');
    const documentWorkspaceReject = document.getElementById('document-workspace-reject');
    const documentWorkspaceDiff = document.getElementById('document-workspace-diff');
    const documentWorkspaceReviewTitle = document.getElementById('document-workspace-review-title');
    const documentWorkspaceHistory = document.getElementById('document-workspace-history');
    const documentWorkspaceExportTxt = document.getElementById('document-workspace-export-txt');
    const documentWorkspaceExportMd = document.getElementById('document-workspace-export-md');
    const documentWorkspaceExportDocx = document.getElementById('document-workspace-export-docx');
    const documentWorkspaceDelete = document.getElementById('document-workspace-delete');
    const documentWorkspaceRestore = document.getElementById('document-workspace-restore');
    const documentWorkspaceDocxStatus = document.getElementById('document-workspace-docx-status');
    const documentWorkspaceDocxLoad = document.getElementById('document-workspace-docx-load');
    const documentWorkspaceDocxParagraph = document.getElementById('document-workspace-docx-paragraph');
    const documentWorkspaceDocxAction = document.getElementById('document-workspace-docx-action');
    const documentWorkspaceDocxFind = document.getElementById('document-workspace-docx-find');
    const documentWorkspaceDocxText = document.getElementById('document-workspace-docx-text');
    const documentWorkspaceDocxApply = document.getElementById('document-workspace-docx-apply');
    const documentWorkspaceDocxResult = document.getElementById('document-workspace-docx-result');
    const documentWorkspaceStages = Array.from(document.querySelectorAll('[data-document-stage]'));
    const documentReviewLedgerStatus = document.getElementById('document-review-ledger-status');
    const documentReviewFacts = document.getElementById('document-review-facts');
    const documentReviewPrepare = document.getElementById('document-review-prepare');
    const documentReviewPacket = document.getElementById('document-review-packet');
    const documentClaimAnnotations = document.getElementById('document-claim-annotations');
    const documentReviewerName = document.getElementById('document-reviewer-name');
    const documentReviewerRole = document.getElementById('document-reviewer-role');
    const documentReviewDecision = document.getElementById('document-review-decision');
    const documentReviewNotes = document.getElementById('document-review-notes');
    const documentReviewAttested = document.getElementById('document-review-attested');
    const documentReviewCommit = document.getElementById('document-review-commit');
    const documentReviewHistory = document.getElementById('document-review-history');
    const findingsFormsStatusBadge = document.getElementById('findings-forms-status-badge');
    const findingsFormsPosture = document.getElementById('findings-forms-posture');
    const findingsFormsCatalog = document.getElementById('findings-forms-catalog');
    const findingsFormsApproved = document.getElementById('findings-forms-approved');
    const findingsFormsBuild = document.getElementById('findings-forms-build');
    const findingsFormsResults = document.getElementById('findings-forms-results');
    const findingsFormsFields = document.getElementById('findings-forms-fields');
    const findingsFormsComplete = document.getElementById('findings-forms-complete');
    const findingsFormsArtifacts = document.getElementById('findings-forms-artifacts');
    const filingPacketStatusBadge = document.getElementById('filing-packet-status-badge');
    const filingPacketReviewerLabel = document.getElementById('filing-packet-reviewer-label');
    const filingPacketReviewerRole = document.getElementById('filing-packet-reviewer-role');
    const filingPacketExclusive = document.getElementById('filing-packet-exclusive');
    const filingPacketAssign = document.getElementById('filing-packet-assign');
    const filingPacketRefresh = document.getElementById('filing-packet-refresh');
    const filingPacketApproved = document.getElementById('filing-packet-approved');
    const filingPacketBuild = document.getElementById('filing-packet-build');
    const filingPacketResults = document.getElementById('filing-packet-results');
    const filingPacketArtifacts = document.getElementById('filing-packet-artifacts');
    const authorityImpactStatusBadge = document.getElementById('authority-impact-status-badge');
    const authorityImpactBase = document.getElementById('authority-impact-base');
    const authorityImpactTarget = document.getElementById('authority-impact-target');
    const authorityImpactRefresh = document.getElementById('authority-impact-refresh');
    const authorityImpactAnalyze = document.getElementById('authority-impact-analyze');
    const authorityImpactApproved = document.getElementById('authority-impact-approved');
    const authorityImpactBuild = document.getElementById('authority-impact-build');
    const authorityImpactResults = document.getElementById('authority-impact-results');
    const authorityImpactArtifacts = document.getElementById('authority-impact-artifacts');
    const localAgentModal = document.getElementById('local-agent-modal');
    const localAgentBackdrop = document.getElementById('local-agent-backdrop');
    const localAgentClose = document.getElementById('local-agent-close');
    const localAgentCancel = document.getElementById('local-agent-cancel');
    const localAgentProvider = document.getElementById('local-agent-provider');
    const localAgentEndpoint = document.getElementById('local-agent-endpoint');
    const localAgentModel = document.getElementById('local-agent-model');
    const localAgentRefreshPreview = document.getElementById('local-agent-refresh-preview');
    const localAgentRun = document.getElementById('local-agent-run');
    const localAgentPreviewSummary = document.getElementById('local-agent-preview-summary');
    const localAgentContextList = document.getElementById('local-agent-context-list');
    const localAgentSecurityReport = document.getElementById('local-agent-security-report');
    const localAgentStatus = document.getElementById('local-agent-status');
    const authorityVerificationModal = document.getElementById('authority-verification-modal');
    const authorityVerificationBackdrop = document.getElementById('authority-verification-backdrop');
    const authorityVerificationClose = document.getElementById('authority-verification-close');
    const authorityVerificationDone = document.getElementById('authority-verification-done');
    const authorityVerificationCopy = document.getElementById('authority-verification-copy');
    const authorityVerificationSummary = document.getElementById('authority-verification-summary');
    const authorityVerificationBody = document.getElementById('authority-verification-body');
    const authorityVerificationStatus = document.getElementById('authority-verification-status');
    const matterCommandCenterOverlay = document.getElementById('matter-command-center-overlay');
    const matterCommandCenterModal = document.getElementById('matter-command-center-modal');
    const matterCommandCenterClose = document.getElementById('matter-command-center-close');
    const matterCommandCenterStatus = document.getElementById('matter-command-center-status');
    const matterCommandCenterSnapshotRecords = document.getElementById('matter-command-center-snapshot-records');
    const matterCommandCenterVariant = document.getElementById('matter-command-center-variant');
    const matterCommandCenterApproved = document.getElementById('matter-command-center-approved');
    const matterCommandCenterFreeze = document.getElementById('matter-command-center-freeze');
    const matterCommandCenterBuild = document.getElementById('matter-command-center-build');
    const matterCommandCenterRefresh = document.getElementById('matter-command-center-refresh');
    const matterCommandCenterCompareLeft = document.getElementById('matter-command-center-compare-left');
    const matterCommandCenterCompareRight = document.getElementById('matter-command-center-compare-right');
    const matterCommandCenterCompare = document.getElementById('matter-command-center-compare');
    const matterCommandCenterCompareStatus = document.getElementById('matter-command-center-compare-status');
    const matterCommandCenterBody = document.getElementById('matter-command-center-body');
    const matterIntakeOverlay = document.getElementById('matter-intake-overlay');
    const matterIntakeClose = document.getElementById('matter-intake-close');
    const matterIntakeStatus = document.getElementById('matter-intake-status');
    const matterIntakeId = document.getElementById('matter-intake-id');
    const matterIntakeType = document.getElementById('matter-intake-type');
    const matterIntakeCourt = document.getElementById('matter-intake-court');
    const matterIntakeCounty = document.getElementById('matter-intake-county');
    const matterIntakePosture = document.getElementById('matter-intake-posture');
    const matterIntakeAnswerState = document.getElementById('matter-intake-answer-state');
    const matterIntakeWorkflow = document.getElementById('matter-intake-workflow');
    const matterIntakeConcern = document.getElementById('matter-intake-concern');
    const matterIntakeIssueId = document.getElementById('matter-intake-issue-id');
    const matterIntakeSourceId = document.getElementById('matter-intake-source-id');
    const matterIntakeSealed = document.getElementById('matter-intake-sealed');
    const matterIntakeLocalOnly = document.getElementById('matter-intake-local-only');
    const matterIntakeCreate = document.getElementById('matter-intake-create');
    const matterIntakeSave = document.getElementById('matter-intake-save');
    const matterIntakeCoverage = document.getElementById('matter-intake-coverage');
    const matterIntakeComplete = document.getElementById('matter-intake-complete');
    const matterIntakeReceipt = document.getElementById('matter-intake-receipt');
    const matterIntakeResults = document.getElementById('matter-intake-results');
    const ordersWorkspaceOverlay = document.getElementById('orders-workspace-overlay');
    const ordersWorkspaceClose = document.getElementById('orders-workspace-close');
    const ordersWorkspaceStatus = document.getElementById('orders-workspace-status');
    const ordersWorkspaceResults = document.getElementById('orders-workspace-results');
    const ordersOrderId = document.getElementById('orders-order-id');
    const ordersSourceId = document.getElementById('orders-source-id');
    const ordersTermId = document.getElementById('orders-term-id');
    const ordersTermSubject = document.getElementById('orders-term-subject');
    const ordersExactLanguage = document.getElementById('orders-exact-language');
    const ordersAdd = document.getElementById('orders-add');
    const ordersRefresh = document.getElementById('orders-refresh');
    const ordersReceipt = document.getElementById('orders-receipt');
    const calendarWorkspaceOverlay = document.getElementById('calendar-workspace-overlay');
    const calendarWorkspaceClose = document.getElementById('calendar-workspace-close');
    const calendarWorkspaceStatus = document.getElementById('calendar-workspace-status');
    const calendarWorkspaceResults = document.getElementById('calendar-workspace-results');
    const calendarEventId = document.getElementById('calendar-event-id');
    const calendarEventKind = document.getElementById('calendar-event-kind');
    const calendarDateTime = document.getElementById('calendar-date-time');
    const calendarSourceId = document.getElementById('calendar-source-id');
    const calendarDocument = document.getElementById('calendar-document');
    const calendarAdd = document.getElementById('calendar-add');
    const calendarRefresh = document.getElementById('calendar-refresh');
    const calendarReceipt = document.getElementById('calendar-receipt');
    const docketWorkspaceOverlay = document.getElementById('docket-workspace-overlay');
    const docketWorkspaceClose = document.getElementById('docket-workspace-close');
    const docketWorkspaceStatus = document.getElementById('docket-workspace-status');
    const docketWorkspaceResults = document.getElementById('docket-workspace-results');
    const docketEntryId = document.getElementById('docket-entry-id');
    const docketSourceId = document.getElementById('docket-source-id');
    const docketSequence = document.getElementById('docket-sequence');
    const docketDate = document.getElementById('docket-date');
    const docketDescription = document.getElementById('docket-description');
    const docketAdd = document.getElementById('docket-add');
    const docketReconcile = document.getElementById('docket-reconcile');
    const docketReceipt = document.getElementById('docket-receipt');
    const discoveryWorkspaceOverlay = document.getElementById('discovery-workspace-overlay');
    const discoveryWorkspaceClose = document.getElementById('discovery-workspace-close');
    const discoveryWorkspaceStatus = document.getElementById('discovery-workspace-status');
    const discoveryWorkspaceResults = document.getElementById('discovery-workspace-results');
    const discoveryItemId = document.getElementById('discovery-item-id');
    const discoveryKind = document.getElementById('discovery-kind');
    const discoverySourceId = document.getElementById('discovery-source-id');
    const discoveryItemNumber = document.getElementById('discovery-item-number');
    const discoveryRequestText = document.getElementById('discovery-request-text');
    const discoveryAdd = document.getElementById('discovery-add');
    const discoveryGaps = document.getElementById('discovery-gaps');
    const discoveryReceipt = document.getElementById('discovery-receipt');
    const exhibitsWorkspaceOverlay = document.getElementById('exhibits-workspace-overlay');
    const exhibitsWorkspaceClose = document.getElementById('exhibits-workspace-close');
    const exhibitsWorkspaceStatus = document.getElementById('exhibits-workspace-status');
    const exhibitsWorkspaceResults = document.getElementById('exhibits-workspace-results');
    const exhibitsId = document.getElementById('exhibits-id');
    const exhibitsRecordId = document.getElementById('exhibits-record-id');
    const exhibitsHash = document.getElementById('exhibits-hash');
    const exhibitsLabel = document.getElementById('exhibits-label');
    const exhibitsPages = document.getElementById('exhibits-pages');
    const exhibitsDescription = document.getElementById('exhibits-description');
    const exhibitsAdd = document.getElementById('exhibits-add');
    const exhibitsRefresh = document.getElementById('exhibits-refresh');
    const exhibitsReceipt = document.getElementById('exhibits-receipt');
    const statementsWorkspaceOverlay = document.getElementById('statements-workspace-overlay');
    const statementsWorkspaceClose = document.getElementById('statements-workspace-close');
    const statementsWorkspaceStatus = document.getElementById('statements-workspace-status');
    const statementsWorkspaceResults = document.getElementById('statements-workspace-results');
    const statementsId = document.getElementById('statements-id');
    const statementsSpeakerId = document.getElementById('statements-speaker-id');
    const statementsRole = document.getElementById('statements-role');
    const statementsSourceId = document.getElementById('statements-source-id');
    const statementsKind = document.getElementById('statements-kind');
    const statementsExactText = document.getElementById('statements-exact-text');
    const statementsRefresh = document.getElementById('statements-refresh');
    const statementsReceipt = document.getElementById('statements-receipt');
    const statementsAddPerson = document.getElementById('statements-add-person');
    const statementsAdd = document.getElementById('statements-add');
    const hearingWorkspaceOverlay=document.getElementById('hearing-workspace-overlay');
    const hearingWorkspaceClose=document.getElementById('hearing-workspace-close');
    const hearingWorkspaceStatus=document.getElementById('hearing-workspace-status');
    const hearingWorkspaceResults=document.getElementById('hearing-workspace-results');
    const hearingId=document.getElementById('hearing-id'); const hearingNoticeId=document.getElementById('hearing-notice-id'); const hearingWhen=document.getElementById('hearing-when'); const hearingType=document.getElementById('hearing-type');
    const hearingAdd=document.getElementById('hearing-add'); const hearingRefresh=document.getElementById('hearing-refresh'); const hearingReceipt=document.getElementById('hearing-receipt');
    const appellateWorkspaceOverlay=document.getElementById('appellate-workspace-overlay'),appellateWorkspaceClose=document.getElementById('appellate-workspace-close'),appellateWorkspaceStatus=document.getElementById('appellate-workspace-status'),appellateWorkspaceResults=document.getElementById('appellate-workspace-results');
    const appellateId=document.getElementById('appellate-id'),appellateJudgmentId=document.getElementById('appellate-judgment-id'),appellateDate=document.getElementById('appellate-date'),appellateAdd=document.getElementById('appellate-add'),appellateRefresh=document.getElementById('appellate-refresh'),appellateReceipt=document.getElementById('appellate-receipt');
    const uccjeaWorkspaceOverlay=document.getElementById('uccjea-workspace-overlay'),uccjeaWorkspaceClose=document.getElementById('uccjea-workspace-close'),uccjeaWorkspaceStatus=document.getElementById('uccjea-workspace-status'),uccjeaWorkspaceResults=document.getElementById('uccjea-workspace-results'),uccjeaConnectionId=document.getElementById('uccjea-connection-id'),uccjeaChildId=document.getElementById('uccjea-child-id'),uccjeaState=document.getElementById('uccjea-state'),uccjeaSourceId=document.getElementById('uccjea-source-id'),uccjeaAdd=document.getElementById('uccjea-add'),uccjeaRefresh=document.getElementById('uccjea-refresh'),uccjeaReceipt=document.getElementById('uccjea-receipt');
    const icwaWorkspaceOverlay=document.getElementById('icwa-workspace-overlay'),icwaWorkspaceClose=document.getElementById('icwa-workspace-close'),icwaWorkspaceStatus=document.getElementById('icwa-workspace-status'),icwaWorkspaceResults=document.getElementById('icwa-workspace-results'),icwaInquiryId=document.getElementById('icwa-inquiry-id'),icwaChildId=document.getElementById('icwa-child-id'),icwaPersonId=document.getElementById('icwa-person-id'),icwaSourceId=document.getElementById('icwa-source-id'),icwaQuestion=document.getElementById('icwa-question'),icwaAdd=document.getElementById('icwa-add'),icwaRefresh=document.getElementById('icwa-refresh'),icwaReceipt=document.getElementById('icwa-receipt');
    const careWorkspaceOverlay=document.getElementById('care-workspace-overlay'),careWorkspaceClose=document.getElementById('care-workspace-close'),careWorkspaceStatus=document.getElementById('care-workspace-status'),careWorkspaceResults=document.getElementById('care-workspace-results'),carePathwayId=document.getElementById('care-pathway-id'),careChildId=document.getElementById('care-child-id'),careKind=document.getElementById('care-kind'),careSourceId=document.getElementById('care-source-id'),careAdd=document.getElementById('care-add'),careRefresh=document.getElementById('care-refresh'),careReceipt=document.getElementById('care-receipt');
    const safetyWorkspaceOverlay=document.getElementById('safety-workspace-overlay'),safetyWorkspaceClose=document.getElementById('safety-workspace-close'),safetyWorkspaceStatus=document.getElementById('safety-workspace-status'),safetyWorkspaceResults=document.getElementById('safety-workspace-results'),safetyRecordId=document.getElementById('safety-record-id'),safetyKind=document.getElementById('safety-kind'),safetySourceId=document.getElementById('safety-source-id'),safetySummary=document.getElementById('safety-summary'),safetyAdd=document.getElementById('safety-add'),safetyRefresh=document.getElementById('safety-refresh'),safetyReceipt=document.getElementById('safety-receipt');
    const scheduleWorkspaceOverlay=document.getElementById('schedule-workspace-overlay'),scheduleWorkspaceClose=document.getElementById('schedule-workspace-close'),scheduleWorkspaceStatus=document.getElementById('schedule-workspace-status'),scheduleWorkspaceResults=document.getElementById('schedule-workspace-results'),scheduleTermId=document.getElementById('schedule-term-id'),scheduleTopic=document.getElementById('schedule-topic'),scheduleSourceId=document.getElementById('schedule-source-id'),scheduleLanguage=document.getElementById('schedule-language'),scheduleAdd=document.getElementById('schedule-add'),scheduleRefresh=document.getElementById('schedule-refresh'),scheduleReceipt=document.getElementById('schedule-receipt');
    const lateReviewOverlay=document.getElementById('late-review-overlay'),lateReviewClose=document.getElementById('late-review-close'),lateReviewDescription=document.getElementById('late-review-description'),lateReviewStatus=document.getElementById('late-review-status'),lateReviewResults=document.getElementById('late-review-results'),lateReviewRefresh=document.getElementById('late-review-refresh'),lateReviewReceipt=document.getElementById('late-review-receipt');let lateReviewConfig=null;
    const quickExportChat = document.getElementById('quick-export-chat');
    const openAllStarters = document.getElementById('open-all-starters');
    const workflowNavigator = document.getElementById('workflow-navigator');
    const workflowStatus = document.getElementById('workflow-status');
    const workflowActions = Array.from(document.querySelectorAll('[data-workflow-action]'));
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
    let matterIntakeRecord = null;
    let lastHandoffSources = [];
    let sourcePreviewPinned = false;
    let sourcePreviewOwner = null;
    let sourcePreviewHideTimer = 0;
    let sourcePreviewShowTimer = 0;
    let sourcePreviewSuppressUntil = 0;
    let recordInspectorState = null;
    let recordInspectorOwner = null;
    let recordInspectorZoom = 1;
    let documentIntelligenceOwner = null;
    let documentIntelligenceRecordId = '';
    let documentIntelligenceRuntime = null;
    let documentIntelligenceBusy = false;
    let lastDocumentIntelligenceReport = null;
    let evidenceWorkProductOwner = null;
    let evidenceWorkProductBusy = false;
    let evidenceWorkProductPayload = null;
    let matterCommandCenterPayload = null;
    let retrievalWorkbenchOwner = null;
    let retrievalWorkbenchBusy = false;
    let releasePilotHardeningOwner = null;
    let releasePilotHardeningBusy = false;
    let sending = false;
    let activeRequestController = null;
    let requestAbortReason = '';
    let toastTimer = 0;
    let ocrPollTimer = 0;
    let ocrInstallPollTimer = 0;
    let ocrJobRunning = false;
    let ocrManualInstallUrl = 'https://tesseract-ocr.github.io/tessdoc/Downloads.html';
    let localAgentPayload = null;
    let localAgentPreview = null;
    let localAgentOwner = null;
    let localAgentBusy = false;
    let authorityVerificationOwner = null;
    let authorityVerificationReceipt = null;
    let authorityVerificationBusy = false;
    let authorityTrustPayload = null;
    let activeWorkflow = 'research';
    const overlayReturnFocus = new WeakMap();

    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'}[char]));
    }

    function makeSafeLocalError({status = 0, code = '', message = '', recovery = ''} = {}) {
      const normalizedCode = String(code || `local_http_${status || 'unavailable'}`)
        .toLowerCase().replace(/[^a-z0-9_.:-]+/g, '_').slice(0, 80);
      const statusMessages = {
        400: 'The local service could not use that request.',
        401: 'This local session is no longer authorized.',
        403: 'This action is not allowed for the current local session.',
        404: 'The requested local item is not available in the active matter.',
        409: 'The action could not continue because its matter state or prerequisite changed.',
        413: 'The selected local file is too large for this action.',
        422: 'Some information needs correction before the local action can continue.',
        429: 'The local service is busy. Wait briefly, then retry.',
      };
      const error = new Error(statusMessages[status] || message || 'The local service could not complete this action.');
      error.safeCode = normalizedCode;
      error.safeScope = 'Only this local action was affected.';
      error.preserved = 'Your matter, draft, and original records were preserved.';
      error.recovery = recovery || (status === 404
        ? 'Confirm the active matter, then reopen the item from its source card.'
        : 'Review the active matter and prerequisites, then retry.');
      return error;
    }

    function safeErrorInfo(error) {
      return {
        message: String(error?.message || 'The local service could not complete this action.'),
        code: String(error?.safeCode || 'local_action_failed'),
        scope: String(error?.safeScope || 'Only this local action was affected.'),
        preserved: String(error?.preserved || 'Your matter, draft, and original records were preserved.'),
        recovery: String(error?.recovery || 'Review the active matter and prerequisites, then retry.'),
      };
    }

    function renderRecoverableError(error, {title = 'This local action could not finish'} = {}) {
      const info = safeErrorInfo(error);
      return `<section class="recoverable-error" role="alert"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(info.message)}</p><dl><div><dt>Affected scope</dt><dd>${escapeHtml(info.scope)}</dd></div><div><dt>What was preserved</dt><dd>${escapeHtml(info.preserved)}</dd></div><div><dt>Safe recovery</dt><dd>${escapeHtml(info.recovery)}</dd></div></dl><details><summary>Technical details</summary><p>Error code: <code>${escapeHtml(info.code)}</code></p></details></section>`;
    }

    function safeExternalUrl(value) {
      const raw = String(value || '').trim();
      if (!raw) return '';
      try {
        const parsed = new URL(raw);
        return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : '';
      } catch (err) {
        return '';
      }
    }

    function normalizedSourceLane(item) {
      const meta = item?.metadata || item || {};
      const explicit = String(meta.source_lane || '').toLowerCase();
      if (explicit === 'private_record' || explicit === 'records') return 'private_record';
      if (explicit === 'legal_authority' || explicit === 'law' || explicit === 'official_authority') return 'legal_authority';
      if (meta.record_open_token || item?.source_token || meta.parent_evidence_id || meta.canonical_document_key || meta.safe_filename) return 'private_record';
      if (meta.official === true || meta.official_url || item?.citation || meta.citation_hint) return 'legal_authority';
      const locator = String(meta.source_locator || meta.source_locator_basename || '');
      if (locator && !/^https?:\/\//i.test(locator)) return 'private_record';
      return 'unverified';
    }

    function hasPrivateRecordSources() {
      return lastSources.some((item) => normalizedSourceLane(item) === 'private_record');
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
      let res;
      try {
        res = await fetch(url, options);
      } catch (err) {
        if (err?.name === 'AbortError') throw err;
        throw makeSafeLocalError({code: 'local_service_unreachable', message: 'The local service could not be reached.', recovery: 'Restart or reconnect the local service, then retry.'});
      }
      const text = await res.text();
      let payload = null;
      if (text) {
        try {
          payload = JSON.parse(text);
        } catch (err) {
          throw makeSafeLocalError({status: res.status, code: 'local_response_invalid', recovery: 'Retry once. If the problem continues, restart the local service.'});
        }
      } else {
        payload = {};
      }
      if (!res.ok) {
        const detail = payload && typeof payload.detail === 'object' ? payload.detail : null;
        const rawCode = payload?.error_code || payload?.code || detail?.code || (typeof payload?.detail === 'string' ? payload.detail : '');
        const safeCode = /^[a-z0-9_.:-]{1,80}$/i.test(String(rawCode || '')) ? String(rawCode) : `local_http_${res.status}`;
        throw makeSafeLocalError({status: res.status, code: safeCode, recovery: payload?.recovery_hint && !/[\\/]|[A-Z]:/i.test(String(payload.recovery_hint)) ? String(payload.recovery_hint).slice(0, 240) : ''});
      }
      return payload;
    }

    let localServiceOnline = null;

    function renderLocalConnectionState(online, {announce = false} = {}) {
      const recovered = localServiceOnline === false && online;
      const disconnected = localServiceOnline !== false && !online;
      localServiceOnline = online;
      document.body.dataset.connection = online ? 'online' : 'offline';
      health?.classList.toggle('status-ok', online);
      health?.classList.toggle('status-bad', !online);
      const copy = health?.querySelector('.health-copy');
      if (copy) copy.textContent = online ? 'Local only' : 'Offline';
      if (health) {
        health.title = online ? 'Local-only API is online.' : 'Local-only API is offline.';
        health.setAttribute('aria-label', online ? 'Local-only service online. Open privacy status.' : 'Local-only service offline. Open privacy status.');
      }
      if (localStatusCopy) localStatusCopy.textContent = online ? 'Local service online' : 'Local service offline';
      if (online) localStatusDot?.classList.remove('is-offline');
      else localStatusDot?.classList.add('is-offline');
      if (connectionBanner) connectionBanner.hidden = online;
      if (!online && sending) {
        requestAbortReason = 'service_disconnected';
        activeRequestController?.abort();
      }
      if (announce && recovered) showToast('Local service reconnected.');
      if (announce && disconnected) showToast('Local service disconnected. Your draft is safe.');
    }

    async function checkLocalService({announce = false} = {}) {
      if (connectionRetry) {
        connectionRetry.disabled = true;
        connectionRetry.setAttribute('aria-busy', 'true');
      }
      try {
        const payload = await fetchJson('/api/health', {cache: 'no-store'});
        renderLocalConnectionState(payload?.status === 'ok', {announce});
        return payload?.status === 'ok';
      } catch (err) {
        renderLocalConnectionState(false, {announce});
        return false;
      } finally {
        if (connectionRetry) {
          connectionRetry.disabled = false;
          connectionRetry.removeAttribute('aria-busy');
        }
      }
    }

    function localWorkbenchCard(label, value, detail) {
      return `<section><strong>${escapeHtml(label)}</strong><span>${escapeHtml(value)}</span>${detail ? `<span>${escapeHtml(detail)}</span>` : ''}</section>`;
    }

    function renderLocalWorkbenchStatus(payload) {
      if (!localWorkbenchSummary || !localWorkbenchStatus) return;
      const readiness = payload?.readiness || {};
      const hardware = readiness.hardware || {};
      const planCounts = payload?.plan_counts || {};
      const preferences = payload?.preferences || {};
      const privacy = payload?.privacy || {};
      const tier = String(readiness.tier || 'checking').replaceAll('_', ' ');
      const mode = String(readiness.recommended_mode || 'local').replaceAll('_', ' ');
      const memoryGiB = Number(hardware.available_memory_bytes || 0) / (1024 ** 3);
      const cpu = Number(hardware.logical_cpu_count || 0);
      localWorkbenchStatus.textContent = `${tier} local readiness · ${mode} · ${readiness.cpu_baseline_supported ? 'CPU fallback ready' : 'review storage before model work'}`;
      localWorkbenchSummary.innerHTML = [
        localWorkbenchCard('This PC', `${cpu || 'Unknown'} logical CPU · ${memoryGiB ? `${memoryGiB.toFixed(1)} GiB available` : 'memory unavailable'}`, readiness.accelerator_detected ? 'Hardware acceleration detected; local CPU remains available.' : 'No accelerator required for core work.'),
        localWorkbenchCard('Local model fleet', `${Number(payload?.model_count || 0)} registered · ${Number(payload?.verified_artifact_count || 0)} verified artifact(s)`, 'Model artifacts must be checksum-verified under the external local model root.'),
        localWorkbenchCard('Work and performance', `${Number(payload?.open_work_item_count || 0)} open review item(s) · ${String(payload?.performance_policy?.mode || 'balanced').replaceAll('_', ' ')}`, `Policy caps: ${Number(payload?.performance_policy?.max_concurrent_jobs || 1)} job(s) · ${Number(payload?.performance_policy?.max_context_tokens || 0).toLocaleString()} tokens.`),
        localWorkbenchCard('Privacy boundary', String(privacy.network_mode || 'local_only').replaceAll('_', ' '), `Telemetry: ${String(privacy.telemetry || 'off').replaceAll('_', ' ')}`),
        localWorkbenchCard('Quality and release evidence', `${Number(payload?.evaluation_count || 0)} evaluation(s) · ${Number(payload?.release_evidence_count || 0)} release evidence record(s)`, 'The GA gate fails closed until verified evidence and human sign-offs are present.'),
        localWorkbenchCard('Extensions and automations', `${Number(payload?.extension_count || 0)} extension(s) · ${Number(payload?.automation_count || 0)} automation(s)`, 'Extensions are permission-scoped and automations require approval every run.'),
      ].join('');
      if (localWorkbenchReadingLevel) localWorkbenchReadingLevel.value = preferences.reading_level || 'plain_language';
      if (localWorkbenchReducedMotion) localWorkbenchReducedMotion.checked = preferences.motion === 'reduced';
      if (localWorkbenchScreenReader) localWorkbenchScreenReader.checked = Boolean(preferences.screen_reader_mode);
      applyLocalWorkbenchPreferences(preferences);
    }

    function applyLocalWorkbenchPreferences(preferences = {}) {
      const readingLevel = String(preferences.reading_level || 'plain_language');
      const motion = preferences.motion === 'reduced' ? 'reduced' : 'full';
      const screenReaderMode = Boolean(preferences.screen_reader_mode);
      document.body.dataset.readingLevel = readingLevel;
      document.body.dataset.motion = motion;
      document.body.dataset.screenReaderMode = String(screenReaderMode);
      document.documentElement.style.scrollBehavior = motion === 'reduced' ? 'auto' : '';
      [answer, transcript, localWorkbenchStatus].filter(Boolean).forEach((region) => {
        region.setAttribute('aria-live', screenReaderMode ? 'assertive' : 'polite');
      });
    }

    async function loadLocalWorkbenchStatus() {
      if (localWorkbenchStatus) localWorkbenchStatus.textContent = 'Checking local readiness…';
      try {
        renderLocalWorkbenchStatus(await fetchJson('/api/local-workbench/status'));
      } catch (err) {
        if (localWorkbenchStatus) localWorkbenchStatus.textContent = `Could not load local control status: ${err.message}`;
      }
    }

    async function inspectLocalWorkbenchReleaseReadiness() {
      if (localWorkbenchStatus) localWorkbenchStatus.textContent = 'Checking GA evidence…';
      try {
        const payload = await fetchJson('/api/local-workbench/release-readiness');
        const blockers = Array.isArray(payload.blockers) ? payload.blockers : [];
        const state = payload.status === 'pass' ? 'evidence complete' : 'blocked pending evidence';
        if (localWorkbenchStatus) localWorkbenchStatus.textContent = `GA readiness: ${state}${blockers.length ? ` · ${blockers.length} control(s) still need attention` : ''}.`;
      } catch (err) {
        if (localWorkbenchStatus) localWorkbenchStatus.textContent = `Could not check GA evidence: ${err.message}`;
      }
    }

    async function openLocalWorkbench() {
      if (!localWorkbenchOverlay) return;
      localWorkbenchReturnFocus = document.activeElement;
      openOverlay(localWorkbenchOverlay);
      await loadLocalWorkbenchStatus();
      const dialog = localWorkbenchOverlay.querySelector('[role="dialog"]');
      if (dialog) {
        dialog.scrollTop = 0;
        dialog.focus({preventScroll: true});
      }
    }

    function closeLocalWorkbench() {
      closeOverlay(localWorkbenchOverlay);
      const target = localWorkbenchReturnFocus || localWorkbenchButton || quickLocalWorkbench;
      if (target && typeof target.focus === 'function') target.focus({preventScroll: true});
      localWorkbenchReturnFocus = null;
    }

    async function saveLocalWorkbenchPreferences() {
      try {
        const preferences = {
          reading_level: String(localWorkbenchReadingLevel?.value || 'plain_language'),
          motion: localWorkbenchReducedMotion?.checked ? 'reduced' : 'full',
          screen_reader_mode: Boolean(localWorkbenchScreenReader?.checked),
        };
        await fetchJson('/api/local-workbench/preferences', {
          method: 'PUT',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({preferences}),
        });
        applyLocalWorkbenchPreferences(preferences);
        showToast('Local workbench preferences saved.');
        await loadLocalWorkbenchStatus();
      } catch (err) {
        if (localWorkbenchStatus) localWorkbenchStatus.textContent = `Could not save preferences: ${err.message}`;
      }
    }


    const documentWorkspaceState = {
      documents: [],
      active: null,
      proposal: null,
      returnFocus: null,
      docxAvailable: false,
      seedSourceRefs: [],
      seedNote: '',
      reviewRequest: null,
      reviewHistory: null,
      reviewQueue: null,
      findingsFormsStatus: null,
      findingsFormsReview: null,
      findingsFormsCompletion: null,
      filingPacketStatus: null,
      filingPacketBuild: null,
      authorityImpactStatus: null,
      authorityImpactBuild: null,
    };

    function setDocumentWorkspaceStatus(message, kind = '') {
      if (!documentWorkspaceStatus) return;
      documentWorkspaceStatus.className = `document-workspace-status${kind ? ` is-${kind}` : ''}`;
      documentWorkspaceStatus.textContent = String(message || 'Ready.');
    }

    function workspaceDownload(documentId, format) {
      if (!documentId) return;
      const link = document.createElement('a');
      link.href = `/api/document-workspace/documents/${encodeURIComponent(documentId)}/export?format=${encodeURIComponent(format)}`;
      link.download = '';
      document.body.appendChild(link);
      link.click();
      link.remove();
      showToast(`${format.toUpperCase()} export started.`);
    }

    function clearWorkspaceProposal() {
      documentWorkspaceState.proposal = null;
      if (documentWorkspaceReviewTitle) documentWorkspaceReviewTitle.textContent = 'No pending change';
      if (documentWorkspaceDiff) documentWorkspaceDiff.textContent = 'Edit the document, then choose “Propose revision” to see every changed line before committing.';
      if (documentWorkspaceCommit) documentWorkspaceCommit.disabled = true;
      if (documentWorkspaceReject) documentWorkspaceReject.disabled = true;
    }

    function renderWorkspaceHistory(documentRow) {
      if (!documentWorkspaceHistory) return;
      const revisions = Array.isArray(documentRow?.revisions) ? documentRow.revisions : [];
      if (!revisions.length) {
        documentWorkspaceHistory.textContent = 'No revision history is available.';
        return;
      }
      documentWorkspaceHistory.innerHTML = revisions.slice().reverse().map((revision) => `<article><div><strong>${escapeHtml(String(revision.operation || 'revision').replaceAll('_', ' '))}</strong><span class="badge ${revision.status === 'committed' ? 'good' : 'warn'}">${escapeHtml(revision.status || 'review')}</span></div><small>${escapeHtml(revision.created_at || '')} · ${escapeHtml(String(revision.revision_id || '').slice(0, 8))}</small>${revision.note ? `<p>${escapeHtml(revision.note)}</p>` : ''}</article>`).join('');
    }

    function renderWorkspaceDiff(proposal) {
      const diff = proposal?.diff || {};
      const rows = Array.isArray(diff.rows) ? diff.rows : [];
      if (documentWorkspaceReviewTitle) documentWorkspaceReviewTitle.textContent = diff.summary || 'Review proposed revision';
      if (!documentWorkspaceDiff) return;
      if (!rows.length) {
        documentWorkspaceDiff.textContent = 'No line-level changes were returned.';
        return;
      }
      documentWorkspaceDiff.innerHTML = `<div class="document-diff-summary"><span class="badge good">+${Number(diff.additions || 0)}</span><span class="badge bad">−${Number(diff.deletions || 0)}</span><span>${escapeHtml(diff.summary || '')}</span></div><div class="document-diff-lines">${rows.map((row) => `<div class="document-diff-line is-${escapeHtml(row.type || 'unchanged')}"><span>${row.type === 'add' ? '+' : row.type === 'delete' ? '−' : ' '}</span><code>${escapeHtml(row.content || '')}</code></div>`).join('')}</div>${diff.truncated ? '<p class="status-warn">Diff display was bounded for safety. Export or inspect the full draft before approval.</p>' : ''}`;
    }

    function updateWorkspaceControls() {
      const active = documentWorkspaceState.active;
      const deleted = active?.status === 'deleted';
      const hasActive = Boolean(active?.document_id);
      [documentWorkspacePropose, documentWorkspaceExportTxt, documentWorkspaceExportMd, documentWorkspaceExportDocx].forEach((button) => { if (button) button.disabled = !hasActive || deleted; });
      if (documentWorkspaceDelete) { documentWorkspaceDelete.disabled = !hasActive || deleted; documentWorkspaceDelete.hidden = deleted; }
      if (documentWorkspaceRestore) { documentWorkspaceRestore.disabled = !hasActive || !deleted; documentWorkspaceRestore.hidden = !deleted; }
      if (documentWorkspaceSaveNew) documentWorkspaceSaveNew.hidden = hasActive;
      if (documentWorkspaceEditor) documentWorkspaceEditor.disabled = deleted;
      if (documentWorkspaceTitle) documentWorkspaceTitle.disabled = hasActive || deleted;
      if (documentWorkspaceType) documentWorkspaceType.disabled = hasActive || deleted;
      const sourceRefs = Array.isArray(active?.source_refs) ? active.source_refs : [];
      const hasDocx = sourceRefs.some((row) => /docx/i.test(`${row?.source_class || ''} ${row?.title || ''}`));
      if (documentWorkspaceDocxLoad) documentWorkspaceDocxLoad.disabled = !hasActive || !hasDocx || !documentWorkspaceState.docxAvailable;
      if (documentReviewPrepare) documentReviewPrepare.disabled = !hasActive || deleted;
      if (documentReviewCommit) documentReviewCommit.disabled = !hasActive || deleted || !documentWorkspaceState.reviewRequest;
      if (findingsFormsBuild) findingsFormsBuild.disabled = !hasActive || deleted || !findingsFormsApproved?.checked;
      if (findingsFormsComplete) findingsFormsComplete.disabled = !hasActive || deleted || !documentWorkspaceState.findingsFormsReview;
      if (filingPacketAssign) filingPacketAssign.disabled = !hasActive || deleted;
      if (filingPacketRefresh) filingPacketRefresh.disabled = !hasActive || deleted;
      if (filingPacketBuild) filingPacketBuild.disabled = !hasActive || deleted || !filingPacketApproved?.checked;
      const authorityPairReady = Boolean(authorityImpactBase?.value && authorityImpactTarget?.value && authorityImpactBase?.value !== authorityImpactTarget?.value);
      if (authorityImpactRefresh) authorityImpactRefresh.disabled = !hasActive || deleted;
      if (authorityImpactAnalyze) authorityImpactAnalyze.disabled = !hasActive || deleted || !authorityPairReady;
      if (authorityImpactBuild) authorityImpactBuild.disabled = !hasActive || deleted || !authorityPairReady || !authorityImpactApproved?.checked;
    }

    function renderWorkspaceList() {
      if (!documentWorkspaceList) return;
      const rows = documentWorkspaceState.documents;
      if (!rows.length) {
        documentWorkspaceList.innerHTML = '<div class="document-workspace-empty"><strong>No drafts yet.</strong><span>Save an answer, import a record, or create a new document.</span></div>';
        return;
      }
      documentWorkspaceList.innerHTML = rows.map((row) => `<button class="document-workspace-list-item${documentWorkspaceState.active?.document_id === row.document_id ? ' is-active' : ''}" data-workspace-document-id="${escapeHtml(row.document_id)}" type="button"><strong>${escapeHtml(row.title)}</strong><span>${escapeHtml(String(row.document_type || 'draft').replaceAll('_', ' '))} · ${escapeHtml(row.revision_count || 1)} revision${Number(row.revision_count || 1) === 1 ? '' : 's'}</span><small>${row.status === 'deleted' ? 'In trash' : 'Review required'} · ${escapeHtml(row.updated_at || '')}</small></button>`).join('');
      documentWorkspaceList.querySelectorAll('[data-workspace-document-id]').forEach((button) => button.addEventListener('click', () => selectWorkspaceDocument(button.dataset.workspaceDocumentId)));
    }

    function newWorkspaceDraft(seed = {}) {
      documentWorkspaceState.active = null;
      documentWorkspaceState.seedSourceRefs = Array.isArray(seed.sourceRefs) ? seed.sourceRefs : [];
      documentWorkspaceState.seedNote = String(seed.note || '');
      clearWorkspaceProposal();
      if (documentWorkspaceTitle) { documentWorkspaceTitle.disabled = false; documentWorkspaceTitle.value = String(seed.title || ''); }
      if (documentWorkspaceType) { documentWorkspaceType.disabled = false; documentWorkspaceType.value = String(seed.documentType || 'draft'); }
      if (documentWorkspaceEditor) { documentWorkspaceEditor.disabled = false; documentWorkspaceEditor.value = String(seed.content || ''); }
      if (documentWorkspaceMeta) documentWorkspaceMeta.textContent = 'New local draft · review required · not filing-ready';
      if (documentWorkspaceHistory) documentWorkspaceHistory.textContent = 'The first save creates an immutable original revision.';
      if (documentWorkspaceDocxResult) documentWorkspaceDocxResult.textContent = 'Original Word files are never overwritten.';
      documentWorkspaceState.reviewRequest = null;
      documentWorkspaceState.reviewHistory = null;
      if (documentReviewPacket) documentReviewPacket.textContent = 'Save the draft before preparing a review packet.';
      if (documentReviewHistory) documentReviewHistory.textContent = 'No review decisions recorded.';
      if (documentClaimAnnotations) documentClaimAnnotations.textContent = 'Claim-by-claim review controls appear after a packet is built.';
      if (documentReviewLedgerStatus) { documentReviewLedgerStatus.className = 'badge warn'; documentReviewLedgerStatus.textContent = 'Not reviewed'; }
      documentWorkspaceState.findingsFormsStatus = null;
      documentWorkspaceState.findingsFormsReview = null;
      documentWorkspaceState.findingsFormsCompletion = null;
      if (findingsFormsCatalog) findingsFormsCatalog.textContent = 'Save the draft before loading the verified current-form catalog.';
      if (findingsFormsResults) findingsFormsResults.textContent = 'No findings/forms review built.';
      if (findingsFormsFields) findingsFormsFields.textContent = 'Required form fields appear after a review is built.';
      if (findingsFormsArtifacts) findingsFormsArtifacts.textContent = '';
      if (findingsFormsStatusBadge) { findingsFormsStatusBadge.className = 'badge warn'; findingsFormsStatusBadge.textContent = 'Not checked'; }
      documentWorkspaceState.filingPacketStatus = null;
      documentWorkspaceState.filingPacketBuild = null;
      if (filingPacketResults) filingPacketResults.textContent = 'Save the draft before inspecting incremental review units.';
      if (filingPacketArtifacts) filingPacketArtifacts.textContent = '';
      if (filingPacketStatusBadge) { filingPacketStatusBadge.className = 'badge warn'; filingPacketStatusBadge.textContent = 'Not built'; }
      documentWorkspaceState.authorityImpactStatus = null;
      documentWorkspaceState.authorityImpactBuild = null;
      if (authorityImpactResults) authorityImpactResults.textContent = 'Save the draft before comparing authority generations.';
      if (authorityImpactArtifacts) authorityImpactArtifacts.textContent = '';
      if (authorityImpactStatusBadge) { authorityImpactStatusBadge.className = 'badge warn'; authorityImpactStatusBadge.textContent = 'Not checked'; }
      renderWorkspaceList();
      updateWorkspaceControls();
      documentWorkspaceTitle?.focus();
    }

    async function loadDocumentWorkspaceDocuments(selectId = '') {
      if (!documentWorkspaceList) return;
      documentWorkspaceList.textContent = 'Loading local documents…';
      try {
        const payload = await fetchJson('/api/document-workspace/documents?include_deleted=true&limit=500');
        documentWorkspaceState.documents = Array.isArray(payload.documents) ? payload.documents : [];
        renderWorkspaceList();
        const audit = await fetchJson('/api/document-workspace/audit/verify');
        if (documentWorkspaceAudit) {
          documentWorkspaceAudit.className = `document-workspace-audit ${audit.valid ? 'is-good' : 'is-bad'}`;
          documentWorkspaceAudit.textContent = audit.valid ? `Audit chain verified · ${audit.event_count || 0} events` : 'Audit chain needs review';
        }
        const engine = await fetchJson('/api/document-workspace/docx/status');
        documentWorkspaceState.docxAvailable = Boolean(engine.tracked_changes_available);
        if (documentWorkspaceDocxStatus) {
          documentWorkspaceDocxStatus.className = `badge ${documentWorkspaceState.docxAvailable ? 'good' : 'warn'}`;
          documentWorkspaceDocxStatus.textContent = documentWorkspaceState.docxAvailable ? `docx-editor ${engine.version || ''}`.trim() : 'Word tracking unavailable';
        }
        await loadDocumentReviewQueue();
        if (selectId) await selectWorkspaceDocument(selectId);
        else if (documentWorkspaceState.active?.document_id) await selectWorkspaceDocument(documentWorkspaceState.active.document_id);
      } catch (err) {
        documentWorkspaceState.documents = [];
        documentWorkspaceList.innerHTML = `<div class="document-workspace-empty"><strong>Document workspace unavailable.</strong><span>${escapeHtml(err.message)}</span></div>`;
        setDocumentWorkspaceStatus(err.message, 'bad');
      }
    }

    function renderDocumentReviewQueue(payload) {
      documentWorkspaceState.reviewQueue = payload || null;
      if (!documentReviewQueue) return;
      const rows = Array.isArray(payload?.items) ? payload.items : [];
      documentReviewQueue.innerHTML = rows.length ? rows.map((row) => {
        const status = String(row.queue_status || 'needs_review').replaceAll('_', ' ');
        const packet = row.packet_summary || {};
        const details = [
          packet.procedural_posture ? `posture: ${String(packet.procedural_posture).replaceAll('_', ' ')}` : '',
          packet.form_status ? `forms: ${packet.form_status}` : '',
          packet.claim_count ? `${packet.claim_count} claim(s)` : '',
          row.blockers?.length ? `${row.blockers.length} blocker(s)` : ''
        ].filter(Boolean).join(' · ');
        return `<button class="document-review-queue-item" data-review-queue-document="${escapeHtml(row.document_id || '')}" type="button"><span><strong>${escapeHtml(row.title || 'Untitled')}</strong><small>${escapeHtml(row.document_type || 'draft')} · revision ${escapeHtml(String(row.current_revision_id || '').slice(0, 8))}</small></span><span class="badge ${row.filing_ready ? 'good' : 'warn'}">${escapeHtml(status)}</span>${details ? `<small>${escapeHtml(details)}</small>` : ''}</button>`;
      }).join('') : '<div class="document-workspace-empty"><strong>No documents are waiting in the review queue.</strong><span>Build a review packet or include completed items through the API.</span></div>';
      documentReviewQueue.querySelectorAll('[data-review-queue-document]').forEach((button) => button.addEventListener('click', () => selectWorkspaceDocument(button.dataset.reviewQueueDocument || '')));
    }

    async function loadDocumentReviewQueue() {
      if (!documentReviewQueue) return;
      try {
        const payload = await fetchJson('/api/document-workspace/review-queue?limit=200');
        renderDocumentReviewQueue(payload);
      } catch (err) {
        documentReviewQueue.textContent = err.message;
      }
    }

    function renderClaimAnnotations(claims) {
      if (!documentClaimAnnotations) return;
      const rows = Array.isArray(claims) ? claims : [];
      if (!rows.length) {
        documentClaimAnnotations.textContent = 'No material legal claims were extracted for individual annotation.';
        return;
      }
      documentClaimAnnotations.innerHTML = `<div class="document-claim-annotations-head"><strong>Claim-by-claim review</strong><span>${rows.length} claim(s)</span></div>${rows.map((row) => `<article data-review-claim="${escapeHtml(row.claim_id || '')}"><div><strong>${escapeHtml(row.statement || '')}</strong><span class="badge ${String(row.support_status || '').includes('supported') ? 'good' : 'warn'}">${escapeHtml(String(row.support_status || 'unverified').replaceAll('_', ' '))}</span></div><div class="document-claim-annotation-fields"><label>Reviewer finding<select data-claim-status><option value="">Choose…</option><option value="accepted">Accepted as supported</option><option value="not_material">Not material</option><option value="needs_revision">Needs revision</option><option value="unsupported">Unsupported</option><option value="contradicted">Contradicted</option><option value="needs_authority">Needs authority</option><option value="needs_fact_support">Needs fact support</option></select></label><label>Claim note<input data-claim-note maxlength="2000" placeholder="Why this claim passes or remains blocked"/></label></div><small>${escapeHtml((row.source_ids || []).join(' · ') || 'No source IDs supplied with this claim')}</small></article>`).join('')}`;
    }

    function collectClaimAnnotations() {
      if (!documentClaimAnnotations) return [];
      return Array.from(documentClaimAnnotations.querySelectorAll('[data-review-claim]')).map((row) => ({
        claim_id: row.dataset.reviewClaim || '',
        status: row.querySelector('[data-claim-status]')?.value || '',
        note: row.querySelector('[data-claim-note]')?.value || '',
        source_ids: []
      })).filter((row) => row.claim_id && row.status);
    }

    function renderDocumentReviewPacket(prepared) {
      const packet = prepared?.packet || {};
      const authority = packet.authority_verification || {};
      const facts = packet.fact_evidence_report || {};
      const procedure = packet.procedure_posture_report || {};
      const forms = packet.forms_report || {};
      const claims = packet.claims_for_review || [];
      const gate = packet.filing_gate_preflight || {};
      const blockers = Array.isArray(gate.blockers) ? gate.blockers : [];
      if (!documentReviewPacket) return;
      const procedureItems = Array.isArray(procedure.review_items) ? procedure.review_items : [];
      const formNotes = [
        ...(forms.current_forms || []).map((id) => `${id}: current`),
        ...(forms.stale_forms || []).map((id) => `${id}: stale`),
        ...(forms.unknown_forms || []).map((id) => `${id}: freshness unknown`)
      ];
      documentReviewPacket.innerHTML = `<div class="document-review-packet-summary"><span><strong>Revision</strong> ${escapeHtml(String(packet.revision_id || '').slice(0, 8))}</span><span><strong>Authority</strong> ${escapeHtml(authority.status || 'blocked')}</span><span><strong>Facts found</strong> ${escapeHtml(facts.supported_count || 0)} / ${escapeHtml(facts.fact_count || 0)}</span><span><strong>Claims</strong> ${escapeHtml(claims.length)}</span><span><strong>Procedure</strong> ${escapeHtml(String(procedure.procedural_posture || 'unknown').replaceAll('_', ' '))}</span><span><strong>Forms</strong> ${escapeHtml(forms.status || 'unknown')}</span><span><strong>Blockers</strong> ${blockers.length}</span></div>${blockers.length ? `<ul>${blockers.map((item) => `<li>${escapeHtml(String(item).replaceAll('_', ' '))}</li>`).join('')}</ul>` : '<p class="status-good">All automated preflight checks passed. Human review still must be recorded.</p>'}<details><summary>Procedure, forms, fact matches, and packet hash</summary><p><code>${escapeHtml(packet.packet_sha256 || '')}</code></p>${procedureItems.length ? `<article><strong>Procedure review checklist</strong><span class="badge ${procedure.status === 'checked' ? 'good' : 'warn'}">${escapeHtml(procedure.status || 'unknown')}</span><ul>${procedureItems.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></article>` : ''}${formNotes.length ? `<article><strong>Form review</strong><span class="badge ${forms.status === 'checked' ? 'good' : 'warn'}">${escapeHtml(forms.status || 'unknown')}</span><ul>${formNotes.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></article>` : '<article><strong>Form review</strong><small>No form IDs were identified. A required-form selection may still need confirmation.</small></article>'}${(facts.facts || []).map((item) => `<article><strong>${escapeHtml(item.fact || '')}</strong><span class="badge ${item.status === 'record_text_found' ? 'good' : 'warn'}">${escapeHtml(item.status || 'unknown')}</span><small>${escapeHtml((item.supporting_records || []).map((row) => row.source_locator || row.evidence_id).join(' · ') || 'No indexed record span found')}</small></article>`).join('')}</details>`;
      renderClaimAnnotations(claims);
    }

    function renderDocumentReviewHistory(payload) {
      documentWorkspaceState.reviewHistory = payload || null;
      const rows = Array.isArray(payload?.decisions) ? payload.decisions : [];
      const latest = payload?.latest || null;
      if (documentReviewLedgerStatus) {
        const ready = Boolean(latest?.filing_gate?.filing_ready);
        documentReviewLedgerStatus.className = `badge ${ready ? 'good' : 'warn'}`;
        documentReviewLedgerStatus.textContent = latest ? String(latest.status || 'reviewed').replaceAll('_', ' ') : 'Not reviewed';
      }
      if (!documentReviewHistory) return;
      documentReviewHistory.innerHTML = rows.length ? rows.map((row) => { const annotations = Array.isArray(row.claim_annotations) ? row.claim_annotations : []; return `<article><div><strong>${escapeHtml(String(row.decision || 'review').replaceAll('_', ' '))}</strong><span class="badge ${row?.filing_gate?.filing_ready ? 'good' : 'warn'}">${escapeHtml(String(row.status || 'review').replaceAll('_', ' '))}</span></div><small>${escapeHtml(row.committed_at || '')} · revision ${escapeHtml(String(row.revision_id || '').slice(0, 8))} · ${escapeHtml(row?.reviewer?.name || '')}</small>${row.notes ? `<p>${escapeHtml(row.notes)}</p>` : ''}${annotations.length ? `<details><summary>${annotations.length} claim finding(s)</summary><ul>${annotations.map((item) => `<li><strong>${escapeHtml(item.claim_id || '')}</strong>: ${escapeHtml(String(item.status || '').replaceAll('_', ' '))}${item.note ? ` — ${escapeHtml(item.note)}` : ''}</li>`).join('')}</ul></details>` : ''}<code>${escapeHtml(String(row.decision_sha256 || '').slice(0, 24))}…</code></article>`; }).join('') : 'No review decisions recorded.';
    }

    async function loadDocumentReviewHistory(documentId) {
      if (!documentId) return;
      try {
        const payload = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(documentId)}/reviews`);
        renderDocumentReviewHistory(payload);
      } catch (err) {
        if (documentReviewHistory) documentReviewHistory.textContent = err.message;
      }
    }

    async function prepareDocumentReview() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      const facts = String(documentReviewFacts?.value || '').split(/\r?\n/).map((row) => row.trim()).filter(Boolean).slice(0, 128);
      setDocumentWorkspaceStatus('Building a revision-bound authority and evidence review packet…');
      try {
        const payload = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/review/prepare`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({facts, quotes: [], claims: [], auto_extract_claims: true})});
        documentWorkspaceState.reviewRequest = payload;
        renderDocumentReviewPacket(payload);
        if (documentReviewCommit) documentReviewCommit.disabled = false;
        await loadDocumentReviewQueue();
        setDocumentWorkspaceStatus('Review packet prepared. It is bound to this exact revision and expires if the draft changes.', 'good');
      } catch (err) {
        documentWorkspaceState.reviewRequest = null;
        if (documentReviewCommit) documentReviewCommit.disabled = true;
        setDocumentWorkspaceStatus(err.message, 'bad');
      }
    }

    async function commitDocumentReview() {
      const active = documentWorkspaceState.active;
      const prepared = documentWorkspaceState.reviewRequest;
      if (!active?.document_id || !prepared?.request_id || !prepared?.confirmation_token) return;
      const reviewerName = documentReviewerName?.value.trim() || '';
      if (!reviewerName) { setDocumentWorkspaceStatus('Enter a reviewer name or local reviewer ID.', 'bad'); documentReviewerName?.focus(); return; }
      const decision = documentReviewDecision?.value || 'approve_review';
      const attested = Boolean(documentReviewAttested?.checked);
      if (decision === 'approve_review' && !attested) { setDocumentWorkspaceStatus('Review completion requires the exact-revision attestation.', 'bad'); return; }
      if (!window.confirm('Record this immutable review decision for the exact revision and packet shown? A review decision cannot override unresolved filing blockers.')) return;
      try {
        const result = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/review/commit`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({request_id: prepared.request_id, confirmation_token: prepared.confirmation_token, confirmed: true, decision, reviewer_name: reviewerName, reviewer_role: documentReviewerRole?.value || 'other_reviewer', attested, notes: documentReviewNotes?.value || '', claim_annotations: collectClaimAnnotations()})});
        documentWorkspaceState.reviewRequest = null;
        if (documentReviewCommit) documentReviewCommit.disabled = true;
        await loadDocumentReviewHistory(active.document_id);
        await loadDocumentReviewQueue();
        const blockers = result?.filing_gate?.blockers || [];
        renderDocumentReviewPacket({packet: {...prepared.packet, filing_gate_preflight: result.filing_gate}});
        setDocumentWorkspaceStatus(blockers.length ? `Review recorded. Export remains blocked by ${blockers.length} gate item(s).` : 'Review recorded and all filing-gate checks passed.', blockers.length ? 'warn' : 'good');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }


    function findingsFormsSelectedIds() {
      if (!findingsFormsCatalog) return [];
      return Array.from(findingsFormsCatalog.querySelectorAll('[data-findings-form-id]:checked')).map((input) => input.dataset.findingsFormId || '').filter(Boolean);
    }

    function renderFindingsFormsCatalog(payload) {
      documentWorkspaceState.findingsFormsStatus = payload || null;
      const rows = Array.isArray(payload?.catalog?.entries) ? payload.catalog.entries : [];
      if (findingsFormsStatusBadge) {
        findingsFormsStatusBadge.className = `badge ${rows.length ? 'good' : 'warn'}`;
        findingsFormsStatusBadge.textContent = rows.length ? `${rows.length} verified form${rows.length === 1 ? '' : 's'}` : 'Catalog unavailable';
      }
      if (!findingsFormsCatalog) return;
      findingsFormsCatalog.innerHTML = rows.length ? rows.map((row) => {
        const current = ['current', 'fresh', 'verified_current'].includes(String(row.freshness_status || '').toLowerCase());
        const fields = Array.isArray(row.required_fields) ? row.required_fields.length : 0;
        return `<label class="findings-form-choice"><input data-findings-form-id="${escapeHtml(row.form_id || '')}" type="checkbox" ${current ? '' : 'disabled'}/><span><strong>${escapeHtml(row.form_id || 'Form')}</strong> ${escapeHtml(row.title || '')}<small>${escapeHtml(row.freshness_status || 'unknown')} · version ${escapeHtml(row.version_date || 'unknown')} · ${fields} detected field${fields === 1 ? '' : 's'}</small></span></label>`;
      }).join('') : '<div class="document-workspace-empty"><strong>No verified current forms are available.</strong><span>Configure and verify the external Maine authority generation before selecting forms.</span></div>';
    }

    async function loadFindingsFormsStatus(documentId) {
      if (!documentId || !findingsFormsCatalog) return;
      findingsFormsCatalog.textContent = 'Loading the verified current-form catalog…';
      try {
        const payload = await fetchJson(`/api/findings-forms/status?document_id=${encodeURIComponent(documentId)}`);
        renderFindingsFormsCatalog(payload);
        if (payload.active?.packet) renderFindingsFormsReview(payload.active);
      } catch (err) {
        findingsFormsCatalog.textContent = err.message;
        if (findingsFormsStatusBadge) { findingsFormsStatusBadge.className = 'badge warn'; findingsFormsStatusBadge.textContent = 'Unavailable'; }
      }
      updateWorkspaceControls();
    }

    function findingsFormsArtifactLinks(rows) {
      const artifacts = Array.isArray(rows) ? rows : [];
      return artifacts.map((row) => `<a class="secondary compact-action" href="${escapeHtml(row.download_url || '#')}" download>${escapeHtml(String(row.name || 'artifact').replaceAll('-', ' '))}</a>`).join('');
    }

    function renderFindingsFormsReview(payload) {
      const packet = payload?.packet || {};
      documentWorkspaceState.findingsFormsReview = payload?.build_id ? payload : null;
      const findings = packet.findings_review || {};
      const factors = Array.isArray(findings.factor_matrix) ? findings.factor_matrix : [];
      const selected = Array.isArray(packet?.form_plan?.selected_forms) ? packet.form_plan.selected_forms : [];
      const blockers = Array.isArray(packet.blockers) ? packet.blockers : [];
      if (findingsFormsResults) {
        findingsFormsResults.innerHTML = `<div class="document-review-packet-summary"><span><strong>Revision</strong> ${escapeHtml(String(packet.revision_id || '').slice(0, 8))}</span><span><strong>Factors addressed</strong> ${factors.filter((row) => row.status === 'addressed').length} / ${factors.length}</span><span><strong>Selected forms</strong> ${selected.length}</span><span><strong>Blockers</strong> ${blockers.length}</span></div>${blockers.length ? `<ul>${blockers.slice(0, 40).map((item) => `<li>${escapeHtml(String(item).replaceAll('_', ' '))}</li>`).join('')}</ul>` : '<p class="status-good">Automated findings and form checks are complete. Human review remains required.</p>'}<details open><summary>Best-interest findings matrix</summary><div class="findings-factor-matrix">${factors.map((row) => `<article><div><strong>${escapeHtml(row.label || row.factor_id || '')}</strong><span class="badge ${row.status === 'addressed' ? 'good' : 'warn'}">${escapeHtml(row.status || 'unknown')}</span></div><small>${(row.draft_spans || []).length} draft span(s) · ${(row.supporting_record_spans || []).length} candidate record span(s)</small></article>`).join('')}</div></details>`;
      }
      if (findingsFormsFields) {
        findingsFormsFields.innerHTML = selected.length ? selected.map((form) => `<fieldset data-findings-form-values="${escapeHtml(form.form_id || '')}"><legend>${escapeHtml(form.form_id || '')} · ${escapeHtml(form.title || '')}</legend>${(form.required_fields || []).map((field) => `<label>${escapeHtml(String(field).replaceAll('_', ' '))}<input data-findings-field="${escapeHtml(field)}" maxlength="5000"/></label>`).join('') || '<p>No required fields were extracted from the admitted source text. Review the official form manually.</p>'}</fieldset>`).join('') : 'Select one or more verified current forms and rebuild the review.';
      }
      if (findingsFormsArtifacts) findingsFormsArtifacts.innerHTML = findingsFormsArtifactLinks(payload?.artifacts);
      if (findingsFormsComplete) findingsFormsComplete.disabled = !payload?.build_id || !selected.length;
      if (findingsFormsStatusBadge) { findingsFormsStatusBadge.className = `badge ${blockers.length ? 'warn' : 'good'}`; findingsFormsStatusBadge.textContent = blockers.length ? `${blockers.length} blocker(s)` : 'Checked'; }
    }

    async function buildFindingsFormsReview() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      if (!findingsFormsApproved?.checked) { setDocumentWorkspaceStatus('Approve the exact-revision findings and form review first.', 'bad'); return; }
      setDocumentWorkspaceStatus('Building an immutable Rule 52, best-interest, restriction, PFA, and current-form review…');
      try {
        const payload = await fetchJson(`/api/findings-forms/documents/${encodeURIComponent(active.document_id)}/review`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({selected_form_ids: findingsFormsSelectedIds(), posture: findingsFormsPosture?.value || 'final_order', approved: true})});
        renderFindingsFormsReview(payload);
        setDocumentWorkspaceStatus('Findings and forms review built for this exact revision.', payload.blockers?.length ? 'warn' : 'good');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
      updateWorkspaceControls();
    }

    function collectFindingsFormsValues() {
      const output = {};
      findingsFormsFields?.querySelectorAll('[data-findings-form-values]').forEach((fieldset) => {
        const formId = fieldset.dataset.findingsFormValues || '';
        const values = {};
        fieldset.querySelectorAll('[data-findings-field]').forEach((input) => {
          const name = input.dataset.findingsField || '';
          const value = input.value.trim();
          if (name && value) values[name] = value;
        });
        if (formId) output[formId] = values;
      });
      return output;
    }

    async function completeFindingsFormsWorkingCopy() {
      const review = documentWorkspaceState.findingsFormsReview;
      if (!review?.build_id) return;
      if (!window.confirm('Create a structured, review-required working copy from the displayed values? This will not create or overwrite an official court PDF.')) return;
      try {
        const payload = await fetchJson('/api/findings-forms/complete', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({build_id: review.build_id, form_values: collectFindingsFormsValues(), confirmed: true})});
        documentWorkspaceState.findingsFormsCompletion = payload;
        if (findingsFormsArtifacts) findingsFormsArtifacts.innerHTML = `<strong>Working-copy artifacts</strong>${findingsFormsArtifactLinks(payload.artifacts)}${payload?.completion?.blockers?.length ? `<ul>${payload.completion.blockers.map((item) => `<li>${escapeHtml(String(item).replaceAll('_', ' '))}</li>`).join('')}</ul>` : ''}`;
        setDocumentWorkspaceStatus(payload?.completion?.blockers?.length ? 'Working copy created. Missing fields or other blockers remain.' : 'Working copy created. Human review and official-form transfer remain required.', payload?.completion?.blockers?.length ? 'warn' : 'good');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    function filingPacketArtifactLinks(rows) {
      return (Array.isArray(rows) ? rows : []).map((row) => `<a class="secondary compact-action" href="${escapeHtml(row.download_url || '#')}" download>${escapeHtml(String(row.name || 'artifact').replaceAll('-', ' '))}</a>`).join('');
    }

    function renderFilingPacketStatus(payload) {
      documentWorkspaceState.filingPacketStatus = payload || null;
      const incremental = payload?.incremental_review || payload?.packet?.incremental_review || {};
      const diff = incremental.diff || {};
      const reviewUnits = incremental.review_units || {};
      const units = Array.isArray(reviewUnits.units) ? reviewUnits.units : [];
      const assignments = payload?.assignments || payload?.packet?.reviewer_assignments || {};
      const activeAssignments = Array.isArray(assignments.active) ? assignments.active : [];
      const active = payload?.active || (payload?.packet ? payload : null);
      const packet = active?.packet || payload?.packet || {};
      const filingGate = packet.filing_gate || {};
      const gateReport = filingGate.gate_report || filingGate.immutable_gate_report || {};
      const canonicalBlockers = Array.isArray(filingGate.blockers) ? filingGate.blockers : [];
      const blockers = canonicalBlockers.length ? canonicalBlockers : (Array.isArray(packet.blockers) ? packet.blockers : []);
      if (filingPacketStatusBadge) {
        const label = active?.build_id ? (blockers.length ? `${blockers.length} blocker(s)` : 'Packet verified') : `${reviewUnits.changed_unit_count || 0} changed unit(s)`;
        filingPacketStatusBadge.className = `badge ${active?.build_id && !blockers.length ? 'good' : 'warn'}`;
        filingPacketStatusBadge.textContent = label;
      }
      if (filingPacketResults) {
        const gateHash = String(filingGate?.gate_report?.immutable_report_hash || filingGate?.immutable_gate_report?.immutable_report_hash || '');
        const gatePanel = active?.build_id ? `<section class="authority-verification-section"><h3>Canonical filing gate</h3><div class="authority-verification-card ${blockers.length ? 'is-blocked' : 'is-supported'}"><header><strong>${escapeHtml(filingGate?.blocker_panel?.panel_title || 'Filing gate blockers')}</strong><span class="authority-verification-status-pill ${blockers.length ? 'is-blocked' : 'is-supported'}">${escapeHtml(String(filingGate.export_status || 'unknown').replaceAll('_', ' '))}</span></header><p><strong>Immutable hash:</strong> <code>${escapeHtml(gateHash || 'not recorded')}</code></p><p><strong>Review required:</strong> ${escapeHtml(String(filingGate.review_required ?? true))} · <strong>Filing ready:</strong> ${escapeHtml(String(filingGate.filing_ready ?? false))}</p>${blockers.length ? `<ul class="authority-verification-blockers">${blockers.slice(0, 50).map((item) => `<li>${escapeHtml(String(item).replaceAll('_', ' '))}</li>`).join('')}</ul>` : '<p>All canonical gate checks passed.</p>'}</div></section>` : '';
        filingPacketResults.innerHTML = `<div class="document-review-packet-summary"><span><strong>Diff</strong> ${escapeHtml(diff.summary || 'No comparison')}</span><span><strong>Changed units</strong> ${escapeHtml(reviewUnits.changed_unit_count || 0)}</span><span><strong>Historical units</strong> ${escapeHtml(reviewUnits.unchanged_historical_count || 0)}</span><span><strong>Active assignments</strong> ${escapeHtml(activeAssignments.length)}</span><span><strong>Packet blockers</strong> ${escapeHtml(blockers.length)}</span><span><strong>Prior approval stale</strong> ${incremental.prior_approval_stale ? 'yes' : 'no'}</span></div>${gatePanel}${blockers.length ? `<ul>${blockers.slice(0, 50).map((item) => `<li>${escapeHtml(String(item).replaceAll('_', ' '))}</li>`).join('')}</ul>` : ''}<div class="filing-packet-unit-grid">${units.length ? units.map((row) => `<article class="filing-packet-unit"><strong>${escapeHtml(row.label || row.unit_id || '')}</strong><span class="badge ${row.status === 'changed_requires_review' ? 'warn' : 'good'}">${escapeHtml(String(row.status || '').replaceAll('_', ' '))}</span><small>${escapeHtml(row.unit_type || '')} · prior approval not carried forward</small>${(row.source_ids || []).map((sourceId) => `<button class="secondary compact-action" data-filing-packet-source-id="${escapeHtml(sourceId)}" type="button">Open ${escapeHtml(sourceId)}</button>`).join('')}</article>`).join('') : '<p>No prior review units were available. A full review remains required.</p>'}</div><p>${escapeHtml(reviewUnits.notice || packet.notice || 'Human review remains required.')}</p>`;
      }
      if (filingPacketArtifacts) filingPacketArtifacts.innerHTML = filingPacketArtifactLinks(active?.artifacts || payload?.artifacts);
      filingPacketResults?.querySelectorAll('[data-filing-packet-source-id]').forEach((button) => button.addEventListener('click', () => {
        const sourceId = button.dataset.filingPacketSourceId || '';
        const item = lastSources.find((row) => sourceIdentity(row) === sourceId || String(row.source_id || '') === sourceId);
        if (item) showSourcePreview(item, button, {pin: true});
        else showToast(`Source ${sourceId} is not in the current answer context.`);
      }));
    }

    async function loadFilingPacketStatus(documentId) {
      if (!documentId) return;
      if (filingPacketResults) filingPacketResults.textContent = 'Loading incremental review and reviewer assignments…';
      try {
        const payload = await fetchJson(`/api/reviewed-filing-packet/status?document_id=${encodeURIComponent(documentId)}`);
        renderFilingPacketStatus(payload);
      } catch (err) {
        if (filingPacketResults) filingPacketResults.textContent = err.message;
        if (filingPacketStatusBadge) { filingPacketStatusBadge.className = 'badge warn'; filingPacketStatusBadge.textContent = 'Unavailable'; }
      }
      updateWorkspaceControls();
    }

    async function assignFilingPacketReviewer() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      const reviewerLabel = filingPacketReviewerLabel?.value.trim() || '';
      if (!reviewerLabel) { setDocumentWorkspaceStatus('Enter a local reviewer label before assignment.', 'bad'); return; }
      try {
        await fetchJson(`/api/reviewed-filing-packet/documents/${encodeURIComponent(active.document_id)}/assignments`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({reviewer_label: reviewerLabel, role: filingPacketReviewerRole?.value || 'other_reviewer', capabilities: ['review','annotate_claims','request_changes','export_packet'], expected_revision_id: active.current_revision_id, exclusive: Boolean(filingPacketExclusive?.checked), note: 'Assigned in the local reviewed filing packet workspace.'})});
        await loadFilingPacketStatus(active.document_id);
        setDocumentWorkspaceStatus('Reviewer assignment recorded for this exact revision. Identity is locally entered metadata.', 'good');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function buildReviewedFilingPacket() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      if (!filingPacketApproved?.checked) { setDocumentWorkspaceStatus('Approve packet generation for this exact revision first.', 'bad'); return; }
      try {
        const payload = await fetchJson(`/api/reviewed-filing-packet/documents/${encodeURIComponent(active.document_id)}/build`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({approved: true})});
        documentWorkspaceState.filingPacketBuild = payload;
        renderFilingPacketStatus(payload);
        setDocumentWorkspaceStatus(payload?.packet?.blockers?.length ? 'Reviewed filing packet built with visible blockers.' : 'Reviewed filing packet built and independently verifiable. Human review remains required.', payload?.packet?.blockers?.length ? 'warn' : 'good');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }


    function authorityImpactArtifactLinks(rows) {
      return (rows || []).map((row) => `<a class="secondary compact-action" href="${escapeHtml(row.download_url || '#')}" download>${escapeHtml(row.name || 'artifact')}</a>`).join('');
    }

    function populateAuthorityImpactGenerations(payload) {
      const generations = payload?.generations || [];
      const priorBase = authorityImpactBase?.value || '';
      const priorTarget = authorityImpactTarget?.value || '';
      const options = generations.map((row) => `<option value="${escapeHtml(row.build_id || '')}">${escapeHtml(row.build_id || '')} · ${escapeHtml(row.product_version || 'unknown')} · ${escapeHtml(row.generated_at || '')}${row.active ? ' · active' : ''}</option>`).join('');
      if (authorityImpactBase) authorityImpactBase.innerHTML = `<option value="">Select reviewed generation</option>${options}`;
      if (authorityImpactTarget) authorityImpactTarget.innerHTML = `<option value="">Select target generation</option>${options}`;
      const active = generations.find((row) => row.active)?.build_id || generations[0]?.build_id || '';
      const previous = generations.find((row) => row.build_id !== active)?.build_id || '';
      if (authorityImpactBase) authorityImpactBase.value = generations.some((row) => row.build_id === priorBase) ? priorBase : previous;
      if (authorityImpactTarget) authorityImpactTarget.value = generations.some((row) => row.build_id === priorTarget) ? priorTarget : active;
    }

    function renderAuthorityImpact(payload) {
      documentWorkspaceState.authorityImpactStatus = payload || null;
      if (payload?.generations) populateAuthorityImpactGenerations(payload);
      const packet = payload?.packet || payload || {};
      const blockers = packet.blockers || [];
      const impacted = packet.impacted_changes || [];
      const counts = packet.generation_diff?.counts || {};
      if (authorityImpactStatusBadge) {
        authorityImpactStatusBadge.className = `badge ${blockers.length ? 'warn' : (packet.target_build_id ? 'good' : 'warn')}`;
        authorityImpactStatusBadge.textContent = blockers.length ? `${blockers.length} blocker${blockers.length === 1 ? '' : 's'}` : (packet.target_build_id ? 'Compared' : (payload?.status === 'available' ? 'Ready' : 'Unavailable'));
      }
      if (authorityImpactResults) {
        if (!packet.target_build_id) {
          const count = (payload?.generations || []).length;
          authorityImpactResults.innerHTML = `<p>${escapeHtml(count)} verified generation${count === 1 ? '' : 's'} available. Select the generation used for review and the target generation.</p>${(payload?.blockers || []).length ? `<ul>${payload.blockers.map((item) => `<li>${escapeHtml(String(item).replaceAll('_',' '))}</li>`).join('')}</ul>` : ''}`;
        } else {
          authorityImpactResults.innerHTML = `<div class="document-review-packet-summary"><span><strong>Added</strong> ${escapeHtml(counts.added || 0)}</span><span><strong>Removed</strong> ${escapeHtml(counts.removed || 0)}</span><span><strong>Content changed</strong> ${escapeHtml(counts.content_hash_changed || 0)}</span><span><strong>Directly impacted</strong> ${escapeHtml((packet.impacted_source_ids || []).length)}</span><span><strong>Prior approval valid</strong> no</span></div>${blockers.length ? `<ul>${blockers.slice(0,50).map((item) => `<li>${escapeHtml(String(item).replaceAll('_',' '))}</li>`).join('')}</ul>` : '<p>No direct source-ID overlap was detected. Full human revalidation still remains required.</p>'}<div class="authority-impact-source-grid">${impacted.length ? impacted.map((row) => `<article class="authority-impact-source"><strong>${escapeHtml(row.source_id || '')}</strong><span class="badge warn">${escapeHtml(String(row.change_type || '').replaceAll('_',' '))}</span><small>Source change is a review signal, not a legal conclusion.</small></article>`).join('') : ''}</div><p>${escapeHtml(packet.notice || '')}</p>`;
        }
      }
      if (authorityImpactArtifacts) authorityImpactArtifacts.innerHTML = authorityImpactArtifactLinks(payload?.artifacts || []);
      updateWorkspaceControls();
    }

    async function loadAuthorityImpactStatus(documentId) {
      if (!documentId) return;
      if (authorityImpactResults) authorityImpactResults.textContent = 'Loading verified authority generations…';
      try {
        const payload = await fetchJson(`/api/authority-change-impact/status?document_id=${encodeURIComponent(documentId)}`);
        renderAuthorityImpact(payload);
      } catch (err) {
        if (authorityImpactResults) authorityImpactResults.textContent = err.message;
        if (authorityImpactStatusBadge) { authorityImpactStatusBadge.className = 'badge warn'; authorityImpactStatusBadge.textContent = 'Unavailable'; }
      }
      updateWorkspaceControls();
    }

    async function analyzeAuthorityImpact() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      try {
        const payload = await fetchJson('/api/authority-change-impact/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({document_id:active.document_id, base_build_id:authorityImpactBase?.value || '', target_build_id:authorityImpactTarget?.value || ''})});
        renderAuthorityImpact(payload);
        setDocumentWorkspaceStatus(payload.blockers?.length ? 'Authority impact analyzed with visible revalidation blockers.' : 'Authority generations compared. Human revalidation remains required.', payload.blockers?.length ? 'warn' : 'good');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function buildAuthorityImpactPacket() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      if (!authorityImpactApproved?.checked) { setDocumentWorkspaceStatus('Approve the authority revalidation packet first.', 'bad'); return; }
      try {
        const payload = await fetchJson('/api/authority-change-impact/build', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({document_id:active.document_id, base_build_id:authorityImpactBase?.value || '', target_build_id:authorityImpactTarget?.value || '', approved:true})});
        documentWorkspaceState.authorityImpactBuild = payload;
        renderAuthorityImpact(payload);
        setDocumentWorkspaceStatus('Immutable authority revalidation packet built. It does not establish current law or legal materiality.', payload?.packet?.blockers?.length ? 'warn' : 'good');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function selectWorkspaceDocument(documentId) {
      if (!documentId) return;
      setDocumentWorkspaceStatus('Opening local document…');
      try {
        const payload = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(documentId)}`);
        const row = payload.document || {};
        documentWorkspaceState.active = row;
        clearWorkspaceProposal();
        if (documentWorkspaceTitle) documentWorkspaceTitle.value = row.title || '';
        if (documentWorkspaceType) documentWorkspaceType.value = row.document_type || 'draft';
        if (documentWorkspaceEditor) documentWorkspaceEditor.value = row.content || '';
        if (documentWorkspaceMeta) documentWorkspaceMeta.textContent = `${String(row.document_type || 'draft').replaceAll('_', ' ')} · ${row.revision_count || 1} revision${Number(row.revision_count || 1) === 1 ? '' : 's'} · ${row.status === 'deleted' ? 'in trash' : 'review required'} · original preserved`;
        renderWorkspaceHistory(row);
        documentWorkspaceState.reviewRequest = null;
        documentWorkspaceState.findingsFormsReview = null;
        documentWorkspaceState.findingsFormsCompletion = null;
        documentWorkspaceState.filingPacketStatus = null;
        documentWorkspaceState.filingPacketBuild = null;
        documentWorkspaceState.authorityImpactStatus = null;
        documentWorkspaceState.authorityImpactBuild = null;
        if (documentReviewPacket) documentReviewPacket.textContent = 'Build a new packet for this exact revision before recording a decision.';
        if (findingsFormsResults) findingsFormsResults.textContent = 'Build or load a findings/forms review for this exact revision.';
        if (findingsFormsFields) findingsFormsFields.textContent = 'Required form fields appear after a review is built.';
        await loadDocumentReviewHistory(row.document_id);
        await loadFindingsFormsStatus(row.document_id);
        await loadFilingPacketStatus(row.document_id);
        await loadAuthorityImpactStatus(row.document_id);
        renderWorkspaceList();
        updateWorkspaceControls();
        setDocumentWorkspaceStatus('Document opened. Changes remain local until you review and commit them.', 'good');
      } catch (err) {
        setDocumentWorkspaceStatus(err.message, 'bad');
      }
    }

    async function openDocumentWorkspace(options = {}) {
      if (!documentWorkspace) return;
      setWorkflowFocus('draft');
      documentWorkspaceState.returnFocus = document.activeElement;
      documentWorkspace.hidden = false;
      documentWorkspaceBackdrop.hidden = false;
      documentWorkspace.setAttribute('aria-hidden', 'false');
      documentWorkspaceBackdrop.setAttribute('aria-hidden', 'false');
      document.body.classList.add('document-workspace-open');
      await loadDocumentWorkspaceDocuments(options.documentId || '');
      if (options.seedContent !== undefined || options.seedTitle !== undefined) newWorkspaceDraft({title: options.seedTitle, content: options.seedContent, documentType: options.documentType, sourceRefs: options.sourceRefs, note: options.note});
      if (!options.documentId && options.seedContent === undefined && !documentWorkspaceState.active) newWorkspaceDraft();
      documentWorkspaceClose?.focus({preventScroll: true});
    }

    function closeDocumentWorkspace() {
      if (!documentWorkspace) return;
      documentWorkspace.hidden = true;
      documentWorkspaceBackdrop.hidden = true;
      documentWorkspace.setAttribute('aria-hidden', 'true');
      documentWorkspaceBackdrop.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('document-workspace-open');
      const target = documentWorkspaceState.returnFocus;
      if (target && typeof target.focus === 'function') target.focus({preventScroll: true});
      documentWorkspaceState.returnFocus = null;
    }

    function openDocumentWorkspaceStage(stageName) {
      const stage = String(stageName || 'compose');
      documentWorkspaceStages.forEach((button) => button.classList.toggle('is-active', button.dataset.documentStage === stage));
      if (stage === 'compose') {
        documentWorkspaceEditor?.focus({preventScroll: true});
        return;
      }
      const target = documentWorkspace?.querySelector(`[data-document-stage-target="${stage}"]`);
      if (!target) return;
      target.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
      target.focus({preventScroll: true});
    }

    function matterCommandCenterMatterId() {
      return String(corpusSelect?.value || '').trim();
    }

    function matterCommandCenterSelectedRecordIds() {
      const value = String(matterCommandCenterSnapshotRecords?.value || '').trim();
      if (!value) return [];
      return value.split(/[\s,]+/).map((item) => item.trim()).filter(Boolean);
    }

    function matterCommandCenterRecordIdsFromPayload(payload) {
      const snapshot = payload?.snapshot || {};
      const selected = Array.isArray(snapshot.selected_record_ids) ? snapshot.selected_record_ids : [];
      if (selected.length) return selected.map((item) => String(item || '').trim()).filter(Boolean);
      return (Array.isArray(snapshot.included_records) ? snapshot.included_records : [])
        .map((row) => String(row?.evidence_id || row?.record_id || '').trim())
        .filter(Boolean);
    }

    function matterCommandCenterPacketOptions(payload) {
      const packets = Array.isArray(payload?.packet_list) ? payload.packet_list : [];
      return packets.map((packet) => {
        const labelBits = [
          packet.packet_id || 'packet',
          packet.snapshot_id ? `snapshot ${String(packet.snapshot_id).slice(0, 8)}` : '',
          packet.variant ? String(packet.variant).replaceAll('_', ' ') : '',
          packet.generated_at ? String(packet.generated_at).slice(0, 19).replace('T', ' ') : ''
        ].filter(Boolean);
        return `<option value="${escapeHtml(packet.packet_id || '')}">${escapeHtml(labelBits.join(' · '))}</option>`;
      }).join('');
    }

    function intakeSafeId(value) {
      const text = String(value || '').trim().toLowerCase();
      return /^[a-z][a-z0-9_-]{2,79}$/.test(text) ? text : '';
    }

    function newIntakeId() {
      const suffix = window.crypto?.randomUUID ? window.crypto.randomUUID().replaceAll('-', '').slice(0, 16) : `${Date.now()}${Math.random().toString(16).slice(2, 10)}`;
      return `matter_${suffix}`;
    }

    function intakeMatterId() {
      const safe = intakeSafeId(matterIntakeId?.value);
      if (safe && matterIntakeId) matterIntakeId.value = safe;
      return safe;
    }

    function intakeSourceRefs() {
      const recordId = intakeSafeId(matterIntakeSourceId?.value);
      return recordId ? [{record_id: recordId}] : [];
    }

    function renderMatterIntake(record) {
      matterIntakeRecord = record || null;
      if (!record) return;
      if (matterIntakeId) matterIntakeId.value = record.matter_id || matterIntakeId.value;
      if (matterIntakeType) matterIntakeType.value = record.matter_type_candidates?.[0] || 'unknown_other';
      if (matterIntakeCourt) matterIntakeCourt.value = record.court?.court || '';
      if (matterIntakeCounty) matterIntakeCounty.value = record.court?.county || '';
      if (matterIntakePosture) matterIntakePosture.value = record.procedural_posture?.state || 'unknown';
      if (matterIntakeWorkflow) matterIntakeWorkflow.value = record.requested_workflow || '';
      const history = Array.isArray(record.history) ? record.history : [];
      if (matterIntakeStatus) matterIntakeStatus.textContent = `${record.matter_id} · revision ${record.revision || 0} · encrypted local intake · review required`;
      if (matterIntakeResults) matterIntakeResults.innerHTML = `<strong>Review summary</strong><p>Status: ${escapeHtml(String(record.status || 'in_progress').replaceAll('_', ' '))}. Matter type: ${escapeHtml(String(record.matter_type_candidates?.[0] || 'unknown other').replaceAll('_', ' '))}. Posture: ${escapeHtml(String(record.procedural_posture?.state || 'unknown').replaceAll('_', ' '))}.</p><p>Unknown and disputed answers remain visible. ${escapeHtml(String(history.length))} append-only history event(s) are available. External sharing remains disabled by default.</p>`;
    }

    async function openMatterIntake(owner = null) {
      if (!matterIntakeOverlay) return;
      openOverlay(matterIntakeOverlay);
      if (!corpusSelect?.value) {
        if (matterIntakeStatus) matterIntakeStatus.textContent = 'Select or create a local matter corpus first. Intake records never accept a filesystem path.';
      } else if (matterIntakeStatus) {
        matterIntakeStatus.textContent = 'Create a new encrypted intake or enter its safe ID to resume it.';
      }
      if (matterIntakeId && !intakeMatterId()) matterIntakeId.value = newIntakeId();
      matterIntakeId?.focus({preventScroll: true});
    }

    async function createOrResumeMatterIntake() {
      if (!corpusSelect?.value) { if (matterIntakeStatus) matterIntakeStatus.textContent = 'Select a local matter corpus before creating an intake.'; return; }
      const matterId = intakeMatterId();
      if (!matterId) { if (matterIntakeStatus) matterIntakeStatus.textContent = 'Use a safe intake ID: lowercase letters, numbers, underscores, or hyphens.'; return; }
      if (matterIntakeStatus) matterIntakeStatus.textContent = 'Opening encrypted local intake…';
      try {
        const existing = await fetchJson(`/api/intake/matters/${encodeURIComponent(matterId)}`);
        renderMatterIntake(existing);
        return;
      } catch (_) { /* A missing intake is expected on first use. */ }
      try {
        const created = await fetchJson('/api/intake/matters', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({matter_id: matterId, matter_type_candidates: [String(matterIntakeType?.value || 'unknown_other')], court: matterIntakeCourt?.value || '', county: matterIntakeCounty?.value || '', requested_workflow: matterIntakeWorkflow?.value || ''})});
        renderMatterIntake(created);
      } catch (err) { if (matterIntakeStatus) matterIntakeStatus.textContent = err.message; }
    }

    async function saveMatterIntakeStep() {
      const matterId = intakeMatterId();
      if (!matterId) { await createOrResumeMatterIntake(); return; }
      if (matterIntakeStatus) matterIntakeStatus.textContent = 'Saving review-required intake step…';
      const refs = intakeSourceRefs();
      try {
        let record = await fetchJson(`/api/intake/matters/${encodeURIComponent(matterId)}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({matter_type_candidates: [String(matterIntakeType?.value || 'unknown_other')], court: {court: matterIntakeCourt?.value || '', county: matterIntakeCounty?.value || '', docket_safe_identifier: ''}, requested_workflow: matterIntakeWorkflow?.value || '', external_sharing_policy: matterIntakeLocalOnly?.checked ? 'local_only_no_external_sharing' : 'needs_reviewer', record_scope: {selected_record_roots: [], included_records: refs, excluded_records: [], privacy_indicators: matterIntakeSealed?.checked ? ['sealed'] : []}})});
        record = await fetchJson(`/api/intake/matters/${encodeURIComponent(matterId)}/posture`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({state: String(matterIntakePosture?.value || 'unknown'), entry_status: String(matterIntakeAnswerState?.value || 'unknown'), source_refs: refs})});
        record = await fetchJson(`/api/intake/matters/${encodeURIComponent(matterId)}/classify`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({answers: {primary_concern: {state: String(matterIntakeAnswerState?.value || 'unknown'), value: matterIntakeConcern?.value || '', source_refs: refs}}})});
        const issueId = intakeSafeId(matterIntakeIssueId?.value);
        if (issueId && String(matterIntakeConcern?.value || '').trim()) record = await fetchJson(`/api/intake/matters/${encodeURIComponent(matterId)}/issue-tree`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({issues: [{issue_id: issueId, issue_label: issueId.replaceAll('_', ' '), posture: String(matterIntakePosture?.value || 'unknown'), user_stated_concern: matterIntakeConcern.value, factual_claims: [], supporting_records: refs, contradicting_records: [], applicable_authority_candidates: [], missing_facts: [], missing_records: [], forms: [], deadlines_requiring_review: [], reviewer_notes: '', status: 'review_required'}]})});
        renderMatterIntake(record);
      } catch (err) { if (matterIntakeStatus) matterIntakeStatus.textContent = err.message; }
    }

    async function inspectMatterIntakeCoverage() {
      const matterId = intakeMatterId(); if (!matterId) return;
      try { const payload = await fetchJson(`/api/intake/matters/${encodeURIComponent(matterId)}/coverage`); if (matterIntakeResults) matterIntakeResults.innerHTML = `<strong>Record scope — review required</strong><p>Included: ${escapeHtml(payload.records_included?.length || 0)} · Excluded: ${escapeHtml(payload.records_excluded?.length || 0)} · Not classified: ${escapeHtml(payload.unclassified_record_ids?.length || 0)}</p><p>Missing records: ${escapeHtml((payload.missing_record_checklist || []).join(', ') || 'none automatically identified')}. Coverage does not establish completeness.</p>`; } catch (err) { if (matterIntakeStatus) matterIntakeStatus.textContent = err.message; }
    }

    async function completeMatterIntake() {
      const matterId = intakeMatterId(); if (!matterId) return;
      try { const record = await fetchJson(`/api/intake/matters/${encodeURIComponent(matterId)}/complete`, {method: 'POST'}); renderMatterIntake(record); } catch (err) { if (matterIntakeStatus) matterIntakeStatus.textContent = err.message; }
    }

    async function showMatterIntakeReceipt() {
      const matterId = intakeMatterId(); if (!matterId) return;
      try { const receipt = await fetchJson(`/api/intake/matters/${encodeURIComponent(matterId)}/receipt`); if (matterIntakeResults) matterIntakeResults.innerHTML = `<strong>Intake receipt</strong><p>Revision ${escapeHtml(receipt.revision)} · intake hash <code>${escapeHtml(receipt.intake_hash)}</code></p><p>Receipt hash <code>${escapeHtml(receipt.receipt_hash)}</code>. This receipt is review-required and is not a filing or legal conclusion.</p>`; } catch (err) { if (matterIntakeStatus) matterIntakeStatus.textContent = err.message; }
    }

    function renderOrdersInventory(payload) {
      const orders = Array.isArray(payload?.orders) ? payload.orders : [];
      if (ordersWorkspaceStatus) ordersWorkspaceStatus.textContent = `${orders.length} source-bound order candidate(s) · review required · no operative determination`;
      if (ordersWorkspaceResults) ordersWorkspaceResults.innerHTML = `<strong>Order inventory</strong><ul>${orders.map((item) => `<li><strong>${escapeHtml(item.order_id)}</strong> · ${escapeHtml(String(item.order_type || 'unknown').replaceAll('_', ' '))} · ${escapeHtml(item.source_ref?.record_id || 'source required')} · ${escapeHtml(item.terms?.length || 0)} term(s)</li>`).join('') || '<li>No orders recorded yet.</li>'}</ul><p>Superseded, missing, and conflicting orders remain visible for review.</p>`;
    }

    async function openOrdersWorkspace() {
      if (!ordersWorkspaceOverlay) return;
      openOverlay(ordersWorkspaceOverlay);
      if (!corpusSelect?.value) { if (ordersWorkspaceStatus) ordersWorkspaceStatus.textContent = 'Select a local matter before recording order candidates.'; return; }
      await refreshOrdersWorkspace();
      ordersOrderId?.focus({preventScroll: true});
    }

    async function refreshOrdersWorkspace() {
      try { renderOrdersInventory(await fetchJson('/api/orders/inventory')); } catch (err) { if (ordersWorkspaceStatus) ordersWorkspaceStatus.textContent = err.message; }
    }

    async function addOrderCandidate() {
      const orderId = intakeSafeId(ordersOrderId?.value), sourceId = intakeSafeId(ordersSourceId?.value), termId = intakeSafeId(ordersTermId?.value), language = String(ordersExactLanguage?.value || '').trim();
      if (!orderId || !sourceId || !termId || !language) { if (ordersWorkspaceStatus) ordersWorkspaceStatus.textContent = 'Add safe IDs and exact source language before saving an order candidate.'; return; }
      try { renderOrdersInventory(await fetchJson('/api/orders', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({orders: [{order_id: orderId, source_ref: {record_id: sourceId}, order_type: 'unknown', terms: [{term_id: termId, subject: String(ordersTermSubject?.value || 'other'), exact_language: language, source_ref: {record_id: sourceId}}]}]})})); } catch (err) { if (ordersWorkspaceStatus) ordersWorkspaceStatus.textContent = err.message; }
    }

    async function showOrdersReceipt() {
      try { const receipt = await fetchJson('/api/orders/receipt'); if (ordersWorkspaceResults) ordersWorkspaceResults.innerHTML = `<strong>Order-intelligence receipt</strong><p>Orders hash <code>${escapeHtml(receipt.orders_hash)}</code></p><p>Graph hash <code>${escapeHtml(receipt.graph_hash)}</code></p><p>Review-required receipt hash <code>${escapeHtml(receipt.receipt_hash)}</code>.</p>`; } catch (err) { if (ordersWorkspaceStatus) ordersWorkspaceStatus.textContent = err.message; }
    }

    function renderCalendarTimeline(payload) {
      const events = Array.isArray(payload?.events) ? payload.events : [];
      if (calendarWorkspaceStatus) calendarWorkspaceStatus.textContent = `${events.length} local event candidate(s) · review required · no account calendar writes`;
      if (calendarWorkspaceResults) calendarWorkspaceResults.innerHTML = `<strong>Event timeline</strong><ul>${events.map((item) => `<li><strong>${escapeHtml(item.event_id)}</strong> · ${escapeHtml(String(item.kind || '').replaceAll('_', ' '))} · ${escapeHtml(item.date_time || 'date unknown')} · ${escapeHtml(item.source_ref?.record_id || 'source required')}</li>`).join('') || '<li>No events recorded yet.</li>'}</ul><p>Service is not treated as legally sufficient, and dates are not treated as definitive deadlines.</p>`;
    }
    async function openCalendarWorkspace() { if (!calendarWorkspaceOverlay) return; openOverlay(calendarWorkspaceOverlay); if (!corpusSelect?.value) { if (calendarWorkspaceStatus) calendarWorkspaceStatus.textContent = 'Select a local matter before recording dates.'; return; } await refreshCalendarWorkspace(); calendarEventId?.focus({preventScroll: true}); }
    async function refreshCalendarWorkspace() { try { renderCalendarTimeline(await fetchJson('/api/calendar/events')); } catch (err) { if (calendarWorkspaceStatus) calendarWorkspaceStatus.textContent = err.message; } }
    async function addCalendarEvent() { const eventId=intakeSafeId(calendarEventId?.value), sourceId=intakeSafeId(calendarSourceId?.value); if (!eventId || !sourceId) { if (calendarWorkspaceStatus) calendarWorkspaceStatus.textContent = 'Add safe event and source record IDs before saving.'; return; } try { renderCalendarTimeline(await fetchJson('/api/calendar/events', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({events:[{event_id:eventId,kind:String(calendarEventKind?.value||'unknown'),date_time:calendarDateTime?.value||'',time_zone:'unknown',document_or_notice:calendarDocument?.value||'',source_ref:{record_id:sourceId}}]})})); } catch (err) { if (calendarWorkspaceStatus) calendarWorkspaceStatus.textContent = err.message; } }
    async function showCalendarReceipt() { try { const receipt=await fetchJson('/api/calendar/receipt'); if (calendarWorkspaceResults) calendarWorkspaceResults.innerHTML = `<strong>Calendar review receipt</strong><p>Events hash <code>${escapeHtml(receipt.events_hash)}</code></p><p>Rules hash <code>${escapeHtml(receipt.rules_hash)}</code></p><p>No calendar account was changed. Receipt <code>${escapeHtml(receipt.receipt_hash)}</code>.</p>`; } catch (err) { if (calendarWorkspaceStatus) calendarWorkspaceStatus.textContent = err.message; } }

    function renderDocketReconciliation(payload) { const decisions=Array.isArray(payload?.decisions)?payload.decisions:[]; if (docketWorkspaceStatus) docketWorkspaceStatus.textContent = `${decisions.length} entry decision(s) · review required · court portal access disabled`; if (docketWorkspaceResults) docketWorkspaceResults.innerHTML = `<strong>Reconciliation decisions</strong><ul>${decisions.map((item) => `<li><strong>${escapeHtml(item.entry_id)}</strong> · ${escapeHtml(String(item.status || '').replaceAll('_', ' '))} · confidence ${escapeHtml(String(item.confidence ?? 0))}</li>`).join('') || '<li>No entries reconciled yet.</li>'}</ul><p>Local-only records: ${escapeHtml((payload?.local_only_record_ids || []).join(', ') || 'none identified')}. Official-record completeness is not determined.</p>`; }
    async function openDocketWorkspace() { if (!docketWorkspaceOverlay) return; openOverlay(docketWorkspaceOverlay); if (!corpusSelect?.value) { if (docketWorkspaceStatus) docketWorkspaceStatus.textContent = 'Select a local matter before importing docket entries.'; return; } await reconcileDocketWorkspace(); docketEntryId?.focus({preventScroll: true}); }
    async function reconcileDocketWorkspace() { try { renderDocketReconciliation(await fetchJson('/api/docket/reconcile')); } catch (err) { if (docketWorkspaceStatus) docketWorkspaceStatus.textContent = err.message; } }
    async function addDocketEntry() { const entryId=intakeSafeId(docketEntryId?.value), sourceId=intakeSafeId(docketSourceId?.value), description=String(docketDescription?.value || '').trim(); if (!entryId || !sourceId || !description) { if (docketWorkspaceStatus) docketWorkspaceStatus.textContent = 'Add safe entry and source IDs plus an exact description before importing.'; return; } try { await fetchJson('/api/docket/import', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({entries:[{entry_id:entryId,sequence:docketSequence?.value || '',filed_or_entered_date:docketDate?.value || '',description,source_ref:{record_id:sourceId}}]})}); await reconcileDocketWorkspace(); } catch (err) { if (docketWorkspaceStatus) docketWorkspaceStatus.textContent = err.message; } }
    async function showDocketReceipt() { try { const receipt=await fetchJson('/api/docket/receipt'); if (docketWorkspaceResults) docketWorkspaceResults.innerHTML = `<strong>Docket reconciliation receipt</strong><p>Entries hash <code>${escapeHtml(receipt.entries_hash)}</code></p><p>Local records hash <code>${escapeHtml(receipt.local_records_hash)}</code></p><p>Official record completeness: not determined. Receipt <code>${escapeHtml(receipt.receipt_hash)}</code>.</p>`; } catch (err) { if (docketWorkspaceStatus) docketWorkspaceStatus.textContent = err.message; } }

    function renderDiscoveryGaps(payload) { const unanswered=payload?.unanswered_items || [], objectionOnly=payload?.objection_only_items || [], missing=payload?.items_without_production || []; if (discoveryWorkspaceStatus) discoveryWorkspaceStatus.textContent = `Review required · ${unanswered.length} unanswered · ${objectionOnly.length} objection-only · no automatic service`; if (discoveryWorkspaceResults) discoveryWorkspaceResults.innerHTML = `<strong>Discovery gap review</strong><ul><li>Unanswered: ${escapeHtml(unanswered.join(', ') || 'none identified')}</li><li>Objection only: ${escapeHtml(objectionOnly.join(', ') || 'none identified')}</li><li>Without production: ${escapeHtml(missing.join(', ') || 'none identified')}</li><li>Privilege candidates: ${escapeHtml((payload?.privilege_candidates || []).join(', ') || 'none identified')}</li></ul><p>Compliance and privilege are not determined.</p>`; }
    async function openDiscoveryWorkspace() { if (!discoveryWorkspaceOverlay) return; openOverlay(discoveryWorkspaceOverlay); if (!corpusSelect?.value) { if (discoveryWorkspaceStatus) discoveryWorkspaceStatus.textContent = 'Select a local matter before recording discovery items.'; return; } await refreshDiscoveryGaps(); discoveryItemId?.focus({preventScroll: true}); }
    async function refreshDiscoveryGaps() { try { renderDiscoveryGaps(await fetchJson('/api/discovery/gaps')); } catch (err) { if (discoveryWorkspaceStatus) discoveryWorkspaceStatus.textContent = err.message; } }
    async function addDiscoveryItem() { const itemId=intakeSafeId(discoveryItemId?.value), sourceId=intakeSafeId(discoverySourceId?.value), exactRequestText=String(discoveryRequestText?.value || '').trim(); if (!itemId || !sourceId || !exactRequestText) { if (discoveryWorkspaceStatus) discoveryWorkspaceStatus.textContent = 'Add safe item and source IDs plus exact request text before saving.'; return; } try { await fetchJson('/api/discovery/items', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:[{item_id:itemId,kind:String(discoveryKind?.value || 'unknown'),item_number:discoveryItemNumber?.value || '',exact_request_text:exactRequestText,source_ref:{record_id:sourceId}}]})}); await refreshDiscoveryGaps(); } catch (err) { if (discoveryWorkspaceStatus) discoveryWorkspaceStatus.textContent = err.message; } }
    async function showDiscoveryReceipt() { try { const receipt=await fetchJson('/api/discovery/receipt'); if (discoveryWorkspaceResults) discoveryWorkspaceResults.innerHTML = `<strong>Discovery review receipt</strong><p>Items hash <code>${escapeHtml(receipt.items_hash)}</code></p><p>Productions hash <code>${escapeHtml(receipt.productions_hash)}</code></p><p>Nothing was served or filed. Receipt <code>${escapeHtml(receipt.receipt_hash)}</code>.</p>`; } catch (err) { if (discoveryWorkspaceStatus) discoveryWorkspaceStatus.textContent = err.message; } }

    function renderExhibitsInventory(payload) { const candidates=Array.isArray(payload?.candidates)?payload.candidates:[]; if (exhibitsWorkspaceStatus) exhibitsWorkspaceStatus.textContent = `${candidates.length} candidate record(s) · originals immutable · review required`; if (exhibitsWorkspaceResults) exhibitsWorkspaceResults.innerHTML = `<strong>Exhibit candidates</strong><ul>${candidates.map((item) => `<li><strong>${escapeHtml(item.exhibit_id)}</strong> · ${escapeHtml(item.proposed_label || 'no proposed label')} · ${escapeHtml(item.original_record_id)} · ${escapeHtml(item.redaction_state)}</li>`).join('') || '<li>No exhibit candidates recorded yet.</li>'}</ul><p>Authenticity and admissibility are not determined. Any labeling or numbering applies only to a separate derivative.</p>`; }
    async function openExhibitsWorkspace() { if (!exhibitsWorkspaceOverlay) return; openOverlay(exhibitsWorkspaceOverlay); if (!corpusSelect?.value) { if (exhibitsWorkspaceStatus) exhibitsWorkspaceStatus.textContent = 'Select a local matter before adding exhibit candidates.'; return; } await refreshExhibitsWorkspace(); exhibitsId?.focus({preventScroll: true}); }
    async function refreshExhibitsWorkspace() { try { renderExhibitsInventory(await fetchJson('/api/exhibits/inventory')); } catch (err) { if (exhibitsWorkspaceStatus) exhibitsWorkspaceStatus.textContent = err.message; } }
    async function addExhibitCandidate() { const exhibitId=intakeSafeId(exhibitsId?.value), recordId=intakeSafeId(exhibitsRecordId?.value), sourceHash=String(exhibitsHash?.value || '').trim().toLowerCase(); if (!exhibitId || !recordId || !/^[a-f0-9]{64}$/.test(sourceHash)) { if (exhibitsWorkspaceStatus) exhibitsWorkspaceStatus.textContent = 'Add safe exhibit and original-record IDs plus a valid SHA-256 source hash.'; return; } try { await fetchJson('/api/exhibits/candidates', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({candidates:[{exhibit_id:exhibitId,original_record_id:recordId,original_hash:sourceHash,proposed_label:exhibitsLabel?.value || '',description:exhibitsDescription?.value || '',page_count:Number(exhibitsPages?.value || 0)}]})}); await refreshExhibitsWorkspace(); } catch (err) { if (exhibitsWorkspaceStatus) exhibitsWorkspaceStatus.textContent = err.message; } }
    async function showExhibitsReceipt() { try { const receipt=await fetchJson('/api/exhibits/receipt'); if (exhibitsWorkspaceResults) exhibitsWorkspaceResults.innerHTML = `<strong>Exhibit preparation receipt</strong><p>Candidate hash <code>${escapeHtml(receipt.candidates_hash)}</code></p><p>Provenance ledger hash <code>${escapeHtml(receipt.ledger_hash)}</code></p><p>Originals remain immutable. Receipt <code>${escapeHtml(receipt.receipt_hash)}</code>.</p>`; } catch (err) { if (exhibitsWorkspaceStatus) exhibitsWorkspaceStatus.textContent = err.message; } }

    function renderStatementsInventory(payload) { const rows=Array.isArray(payload?.statements)?payload.statements:[]; if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = `${rows.length} statement(s) · exact source text · review required`; if (statementsWorkspaceResults) statementsWorkspaceResults.innerHTML = `<strong>Statement inventory</strong><ul>${rows.map((item) => `<li><strong>${escapeHtml(item.statement_id)}</strong> · ${escapeHtml(item.statement_type)} · ${escapeHtml(item.source_ref?.record_id || 'source required')} · ${item.ocr_or_translation_warning ? 'OCR/translation warning' : 'source review required'}</li>`).join('') || '<li>No statements recorded yet.</li>'}</ul><p>No credibility, deception, or identity inference is available.</p>`; }
    async function openStatementsWorkspace() { if (!statementsWorkspaceOverlay) return; openOverlay(statementsWorkspaceOverlay); if (!corpusSelect?.value) { if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = 'Select a local matter before recording a statement.'; return; } await refreshStatementsWorkspace(); statementsId?.focus({preventScroll: true}); }
    async function refreshStatementsWorkspace() { try { renderStatementsInventory(await fetchJson('/api/statements/inventory')); } catch (err) { if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = err.message; } }
    async function addStatementPerson() { const personId=intakeSafeId(statementsSpeakerId?.value); if (!personId) { if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = 'Add a safe person ID before confirming a role.'; return; } try { await fetchJson('/api/statements/people', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({people:[{person_id:personId,role:statementsRole?.value || '',user_confirmed:true}]})}); if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = 'Person and role saved as user-confirmed, pending review.'; } catch (err) { if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = err.message; } }
    async function addStatement() { const statementId=intakeSafeId(statementsId?.value), speakerId=intakeSafeId(statementsSpeakerId?.value), sourceId=intakeSafeId(statementsSourceId?.value), exactText=String(statementsExactText?.value || '').trim(); if (!statementId || !speakerId || !sourceId || !exactText) { if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = 'Add safe statement, speaker, and source IDs plus exact source text.'; return; } try { await fetchJson('/api/statements', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({statements:[{statement_id:statementId,speaker_id:speakerId,role:statementsRole?.value || '',statement_type:statementsKind?.value || 'unknown',exact_text:exactText,source_ref:{record_id:sourceId}}]})}); await refreshStatementsWorkspace(); } catch (err) { if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = err.message; } }
    async function showStatementsReceipt() { try { const receipt=await fetchJson('/api/statements/receipt'); if (statementsWorkspaceResults) statementsWorkspaceResults.innerHTML = `<strong>Statement review receipt</strong><p>Statement hash <code>${escapeHtml(receipt.statements_hash)}</code></p><p>History hash <code>${escapeHtml(receipt.history_hash)}</code></p><p>Review-required receipt <code>${escapeHtml(receipt.receipt_hash)}</code>.</p>`; } catch (err) { if (statementsWorkspaceStatus) statementsWorkspaceStatus.textContent = err.message; } }
    function renderHearings(p) { const rows=Array.isArray(p?.hearings)?p.hearings:[];if(hearingWorkspaceStatus)hearingWorkspaceStatus.textContent=`${rows.length} hearing(s) · review required · no filing`;if(hearingWorkspaceResults)hearingWorkspaceResults.innerHTML=`<strong>Hearing inventory</strong><ul>${rows.map(x=>`<li><strong>${escapeHtml(x.hearing_id)}</strong> · ${escapeHtml(x.hearing_type_candidate||'type unknown')} · ${escapeHtml(x.notice_ref?.record_id||'notice required')}</li>`).join('')||'<li>No hearing plans yet.</li>'}</ul><p>No outcome prediction or courtroom tactic is available.</p>`; }
    async function openHearingWorkspace(){if(!hearingWorkspaceOverlay)return;openOverlay(hearingWorkspaceOverlay);if(!corpusSelect?.value){if(hearingWorkspaceStatus)hearingWorkspaceStatus.textContent='Select a local matter before adding a hearing.';return;}await refreshHearings();hearingId?.focus({preventScroll:true});}
    async function refreshHearings(){try{renderHearings(await fetchJson('/api/hearings/inventory'));}catch(e){if(hearingWorkspaceStatus)hearingWorkspaceStatus.textContent=e.message;}}
    async function addHearing(){const id=intakeSafeId(hearingId?.value),notice=intakeSafeId(hearingNoticeId?.value);if(!id||!notice){if(hearingWorkspaceStatus)hearingWorkspaceStatus.textContent='Add safe hearing and notice IDs.';return;}try{await fetchJson('/api/hearings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({hearings:[{hearing_id:id,notice_ref:{record_id:notice},date_time_location:hearingWhen?.value||'',hearing_type_candidate:hearingType?.value||''}]})});await refreshHearings();}catch(e){if(hearingWorkspaceStatus)hearingWorkspaceStatus.textContent=e.message;}}
    async function showHearingReceipt(){try{const r=await fetchJson('/api/hearings/receipt');if(hearingWorkspaceResults)hearingWorkspaceResults.innerHTML=`<strong>Hearing-pack receipt</strong><p>Hearings hash <code>${escapeHtml(r.hearings_hash)}</code></p><p>Receipt <code>${escapeHtml(r.receipt_hash)}</code>.</p>`;}catch(e){if(hearingWorkspaceStatus)hearingWorkspaceStatus.textContent=e.message;}}
    function renderAppellate(p){const r=Array.isArray(p?.appeals)?p.appeals:[];if(appellateWorkspaceStatus)appellateWorkspaceStatus.textContent=`${r.length} appellate record(s) · review required · no merit prediction`;if(appellateWorkspaceResults)appellateWorkspaceResults.innerHTML=`<strong>Appellate records</strong><ul>${r.map(x=>`<li><strong>${escapeHtml(x.appeal_id)}</strong> · judgment ${escapeHtml(x.judgment_ref?.record_id||'required')}</li>`).join('')||'<li>No appellate records yet.</li>'}</ul><p>Preservation, waiver, reversal, and deadline determinations remain unavailable.</p>`;}
    async function openAppellateWorkspace(){if(!appellateWorkspaceOverlay)return;openOverlay(appellateWorkspaceOverlay);if(!corpusSelect?.value)return;await refreshAppellate();appellateId?.focus({preventScroll:true});} async function refreshAppellate(){try{renderAppellate(await fetchJson('/api/appellate/inventory'));}catch(e){if(appellateWorkspaceStatus)appellateWorkspaceStatus.textContent=e.message;}} async function addAppellate(){const id=intakeSafeId(appellateId?.value),j=intakeSafeId(appellateJudgmentId?.value);if(!id||!j){if(appellateWorkspaceStatus)appellateWorkspaceStatus.textContent='Add safe appeal and judgment IDs.';return;}try{await fetchJson('/api/appellate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({appeals:[{appeal_id:id,judgment_ref:{record_id:j},entry_date:appellateDate?.value||''}]})});await refreshAppellate();}catch(e){if(appellateWorkspaceStatus)appellateWorkspaceStatus.textContent=e.message;}} async function showAppellateReceipt(){try{const r=await fetchJson('/api/appellate/receipt');if(appellateWorkspaceResults)appellateWorkspaceResults.innerHTML=`<strong>Appellate review receipt</strong><p><code>${escapeHtml(r.receipt_hash)}</code></p>`;}catch(e){if(appellateWorkspaceStatus)appellateWorkspaceStatus.textContent=e.message;}}
    function renderUccjea(p){const r=Array.isArray(p?.connections)?p.connections:[];if(uccjeaWorkspaceStatus)uccjeaWorkspaceStatus.textContent=`${r.length} state connection(s) · addresses masked · review required`;if(uccjeaWorkspaceResults)uccjeaWorkspaceResults.innerHTML=`<strong>State timeline</strong><ul>${r.map(x=>`<li><strong>${escapeHtml(x.child_id)}</strong> · ${escapeHtml(x.state_territory_country)} · ${escapeHtml(x.source_ref?.record_id||'source required')}</li>`).join('')||'<li>No state connections yet.</li>'}</ul><p>Jurisdiction and relocation legality are not determined.</p>`;}async function openUccjeaWorkspace(){if(!uccjeaWorkspaceOverlay)return;openOverlay(uccjeaWorkspaceOverlay);if(!corpusSelect?.value)return;await refreshUccjea();uccjeaConnectionId?.focus({preventScroll:true});}async function refreshUccjea(){try{renderUccjea(await fetchJson('/api/uccjea/inventory'));}catch(e){if(uccjeaWorkspaceStatus)uccjeaWorkspaceStatus.textContent=e.message;}}async function addUccjea(){const id=intakeSafeId(uccjeaConnectionId?.value),child=intakeSafeId(uccjeaChildId?.value),source=intakeSafeId(uccjeaSourceId?.value);if(!id||!child||!source||!uccjeaState?.value){if(uccjeaWorkspaceStatus)uccjeaWorkspaceStatus.textContent='Add safe IDs, state, and source record.';return;}try{await fetchJson('/api/uccjea/connections',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({connections:[{connection_id:id,child_id:child,state_territory_country:uccjeaState.value,source_ref:{record_id:source}}]})});await refreshUccjea();}catch(e){if(uccjeaWorkspaceStatus)uccjeaWorkspaceStatus.textContent=e.message;}}async function showUccjeaReceipt(){try{const r=await fetchJson('/api/uccjea/receipt');if(uccjeaWorkspaceResults)uccjeaWorkspaceResults.innerHTML=`<strong>Interstate review receipt</strong><p><code>${escapeHtml(r.receipt_hash)}</code></p>`;}catch(e){if(uccjeaWorkspaceStatus)uccjeaWorkspaceStatus.textContent=e.message;}}
    function renderIcwa(p){const r=Array.isArray(p?.inquiries)?p.inquiries:[];if(icwaWorkspaceStatus)icwaWorkspaceStatus.textContent=`${r.length} documented inquiry item(s) · review required · no automatic notice`;if(icwaWorkspaceResults)icwaWorkspaceResults.innerHTML=`<strong>Inquiry inventory</strong><ul>${r.map(x=>`<li><strong>${escapeHtml(x.inquiry_id)}</strong> · ${escapeHtml(x.source_ref?.record_id||'source required')}</li>`).join('')||'<li>No inquiry records yet.</li>'}</ul><p>Membership, eligibility, identity, tribal status, and record completeness are not determined.</p>`;}async function openIcwaWorkspace(){if(!icwaWorkspaceOverlay)return;openOverlay(icwaWorkspaceOverlay);if(!corpusSelect?.value)return;await refreshIcwa();icwaInquiryId?.focus({preventScroll:true});}async function refreshIcwa(){try{renderIcwa(await fetchJson('/api/icwa/inventory'));}catch(e){if(icwaWorkspaceStatus)icwaWorkspaceStatus.textContent=e.message;}}async function addIcwa(){const id=intakeSafeId(icwaInquiryId?.value),child=intakeSafeId(icwaChildId?.value),person=intakeSafeId(icwaPersonId?.value),source=intakeSafeId(icwaSourceId?.value);if(!id||!child||!person||!source){if(icwaWorkspaceStatus)icwaWorkspaceStatus.textContent='Add safe inquiry, child, person, and source IDs.';return;}try{await fetchJson('/api/icwa/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({inquiries:[{inquiry_id:id,child_id:child,person_safe_id:person,question:icwaQuestion?.value||'',source_ref:{record_id:source}}]})});await refreshIcwa();}catch(e){if(icwaWorkspaceStatus)icwaWorkspaceStatus.textContent=e.message;}}async function showIcwaReceipt(){try{const r=await fetchJson('/api/icwa/receipt');if(icwaWorkspaceResults)icwaWorkspaceResults.innerHTML=`<strong>ICWA review receipt</strong><p><code>${escapeHtml(r.receipt_hash)}</code></p>`;}catch(e){if(icwaWorkspaceStatus)icwaWorkspaceStatus.textContent=e.message;}}
    function renderCare(p){const r=Array.isArray(p?.pathways)?p.pathways:[];if(careWorkspaceStatus)careWorkspaceStatus.textContent=`${r.length} pathway record(s) · review required`;if(careWorkspaceResults)careWorkspaceResults.innerHTML=`<strong>Care pathways</strong><ul>${r.map(x=>`<li><strong>${escapeHtml(x.pathway_id)}</strong> · ${escapeHtml(x.kind)} · ${escapeHtml(x.source_ref?.record_id||'source required')}</li>`).join('')||'<li>No pathway records yet.</li>'}</ul><p>Eligibility, consent validity, fitness, best interests, and outcome are not determined.</p>`;}async function openCareWorkspace(){if(!careWorkspaceOverlay)return;openOverlay(careWorkspaceOverlay);if(!corpusSelect?.value)return;await refreshCare();carePathwayId?.focus({preventScroll:true});}async function refreshCare(){try{renderCare(await fetchJson('/api/care-pathways/inventory'));}catch(e){if(careWorkspaceStatus)careWorkspaceStatus.textContent=e.message;}}async function addCare(){const id=intakeSafeId(carePathwayId?.value),child=intakeSafeId(careChildId?.value),source=intakeSafeId(careSourceId?.value);if(!id||!child||!source){if(careWorkspaceStatus)careWorkspaceStatus.textContent='Add safe pathway, child, and source IDs.';return;}try{await fetchJson('/api/care-pathways',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pathways:[{pathway_id:id,child_id:child,kind:careKind?.value||'unknown',source_ref:{record_id:source}}]})});await refreshCare();}catch(e){if(careWorkspaceStatus)careWorkspaceStatus.textContent=e.message;}}async function showCareReceipt(){try{const r=await fetchJson('/api/care-pathways/receipt');if(careWorkspaceResults)careWorkspaceResults.innerHTML=`<strong>Care-pathway receipt</strong><p><code>${escapeHtml(r.receipt_hash)}</code></p>`;}catch(e){if(careWorkspaceStatus)careWorkspaceStatus.textContent=e.message;}}
    function renderSafety(p){const r=Array.isArray(p?.records)?p.records:[];if(safetyWorkspaceStatus)safetyWorkspaceStatus.textContent=`${r.length} safety record(s) · review required · not an emergency service`;if(safetyWorkspaceResults)safetyWorkspaceResults.innerHTML=`<strong>Safety records</strong><ul>${r.map(x=>`<li><strong>${escapeHtml(x.record_id)}</strong> · ${escapeHtml(x.kind)} · ${escapeHtml(x.source_ref?.record_id||'source required')}</li>`).join('')||'<li>No safety records yet.</li>'}</ul><p>No abuse conclusion, risk score, or confrontation guidance is available.</p>`;}async function openSafetyWorkspace(){if(!safetyWorkspaceOverlay)return;openOverlay(safetyWorkspaceOverlay);if(!corpusSelect?.value)return;await refreshSafety();safetyRecordId?.focus({preventScroll:true});}async function refreshSafety(){try{renderSafety(await fetchJson('/api/safety/inventory'));}catch(e){if(safetyWorkspaceStatus)safetyWorkspaceStatus.textContent=e.message;}}async function addSafety(){const id=intakeSafeId(safetyRecordId?.value),source=intakeSafeId(safetySourceId?.value);if(!id||!source){if(safetyWorkspaceStatus)safetyWorkspaceStatus.textContent='Add safe record and source IDs.';return;}try{await fetchJson('/api/safety/records',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({records:[{record_id:id,kind:safetyKind?.value||'',summary:safetySummary?.value||'',source_ref:{record_id:source}}]})});await refreshSafety();}catch(e){if(safetyWorkspaceStatus)safetyWorkspaceStatus.textContent=e.message;}}async function showSafetyReceipt(){try{const r=await fetchJson('/api/safety/receipt');if(safetyWorkspaceResults)safetyWorkspaceResults.innerHTML=`<strong>Safety review receipt</strong><p><code>${escapeHtml(r.receipt_hash)}</code></p>`;}catch(e){if(safetyWorkspaceStatus)safetyWorkspaceStatus.textContent=e.message;}}
    function renderSchedule(p){const r=Array.isArray(p?.terms)?p.terms:[];if(scheduleWorkspaceStatus)scheduleWorkspaceStatus.textContent=`${r.length} source term(s) · review required · no calendar write`;if(scheduleWorkspaceResults)scheduleWorkspaceResults.innerHTML=`<strong>Source schedule terms</strong><ul>${r.map(x=>`<li><strong>${escapeHtml(x.term_id)}</strong> · ${escapeHtml(x.topic)} · ${escapeHtml(x.source_ref?.record_id||'source required')}</li>`).join('')||'<li>No schedule terms yet.</li>'}</ul><p>This app does not decide operative meaning or provide legal advice.</p>`;}async function openScheduleWorkspace(){if(!scheduleWorkspaceOverlay)return;openOverlay(scheduleWorkspaceOverlay);if(!corpusSelect?.value)return;await refreshSchedule();scheduleTermId?.focus({preventScroll:true});}async function refreshSchedule(){try{renderSchedule(await fetchJson('/api/parenting-schedule/inventory'));}catch(e){if(scheduleWorkspaceStatus)scheduleWorkspaceStatus.textContent=e.message;}}async function addSchedule(){const id=intakeSafeId(scheduleTermId?.value),source=intakeSafeId(scheduleSourceId?.value),text=String(scheduleLanguage?.value||'').trim();if(!id||!source||!text){if(scheduleWorkspaceStatus)scheduleWorkspaceStatus.textContent='Add safe term and source IDs plus exact language.';return;}try{await fetchJson('/api/parenting-schedule/terms',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({terms:[{term_id:id,topic:scheduleTopic?.value||'',exact_language:text,source_ref:{record_id:source}}]})});await refreshSchedule();}catch(e){if(scheduleWorkspaceStatus)scheduleWorkspaceStatus.textContent=e.message;}}async function showScheduleReceipt(){try{const r=await fetchJson('/api/parenting-schedule/receipt');if(scheduleWorkspaceResults)scheduleWorkspaceResults.innerHTML=`<strong>Schedule receipt</strong><p><code>${escapeHtml(r.receipt_hash)}</code></p>`;}catch(e){if(scheduleWorkspaceStatus)scheduleWorkspaceStatus.textContent=e.message;}}
    async function openLateReview(title,inventory,receipt,description){lateReviewConfig={title,inventory,receipt};if(!lateReviewOverlay)return;openOverlay(lateReviewOverlay);if(lateReviewDescription)lateReviewDescription.textContent=description;if(!corpusSelect?.value){if(lateReviewStatus)lateReviewStatus.textContent='Select a local matter before reviewing local records.';return;}await refreshLateReview();}async function refreshLateReview(){if(!lateReviewConfig)return;try{const p=await fetchJson(lateReviewConfig.inventory);if(lateReviewStatus)lateReviewStatus.textContent='Local inventory · review required · no external action';if(lateReviewResults)lateReviewResults.innerHTML=`<strong>${escapeHtml(lateReviewConfig.title)}</strong><pre>${escapeHtml(JSON.stringify(p,null,2))}</pre>`;}catch(e){if(lateReviewStatus)lateReviewStatus.textContent=e.message;}}async function showLateReviewReceipt(){if(!lateReviewConfig)return;try{const r=await fetchJson(lateReviewConfig.receipt);if(lateReviewResults)lateReviewResults.innerHTML=`<strong>${escapeHtml(lateReviewConfig.title)} receipt</strong><p><code>${escapeHtml(r.receipt_hash||'receipt unavailable')}</code></p>`;}catch(e){if(lateReviewStatus)lateReviewStatus.textContent=e.message;}}
    const openNegotiationWorkspace=()=>openLateReview('Mediation, negotiation and proposals','/api/negotiation/inventory','/api/negotiation/receipt','Compare local source-bound proposals; nothing is sent or accepted.');const openPropertyWorkspace=()=>openLateReview('Property, debt and valuation','/api/property/inventory','/api/property/receipt','Values, characterization, and division require review.');const openModificationWorkspace=()=>openLateReview('Modification review','/api/modification/inventory','/api/modification/receipt','Material change and outcome are not determined.');const openFoaaWorkspace=()=>openLateReview('FOAA request manager','/api/foaa/inventory','/api/foaa/receipt','Drafts are local only and are never submitted.');const openFilingWorkspace=()=>openLateReview('Filing readiness','/api/filing-readiness/inventory','/api/filing-readiness/receipt','Blockers require review; this app never files.');const openImageEvidenceWorkspace=()=>openLateReview('Image evidence review','/api/image-evidence/inventory','/api/image-evidence/receipt','Originals remain immutable; authenticity is not determined.');const openEmailIntegrityWorkspace=()=>openLateReview('Email export integrity','/api/email-integrity/inventory','/api/email-integrity/receipt','No mail is sent and authenticity remains review-required.');const openHandoffWorkspace=()=>openLateReview('Secure reviewer handoff','/api/reviewer-handoff/inventory','/api/reviewer-handoff/receipt','No sharing or upload is automatic.');const openLanguageWorkspace=()=>openLateReview('Language access','/api/language-access/inventory','/api/language-access/receipt','Working copies are not certified translations.');const openResourceWorkspace=()=>openLateReview('Maine family resource navigator','/api/resources/inventory','/api/resources/receipt','Resource availability and outreach remain reviewer questions.');

    function renderMatterCommandCenter(payload) {
      matterCommandCenterPayload = payload || null;
      const snapshot = payload?.snapshot || null;
      const coverage = snapshot?.coverage || {};
      const fullCoverage = snapshot?.full_record_coverage || {};
      const included = Array.isArray(snapshot?.included_records) ? snapshot.included_records : [];
      const excluded = Array.isArray(snapshot?.excluded_records) ? snapshot.excluded_records : [];
      const packets = Array.isArray(payload?.packet_list) ? payload.packet_list : [];
      const staleReasons = Array.isArray(payload?.stale_reasons) ? payload.stale_reasons : [];
      const selectedIds = matterCommandCenterSelectedRecordIds();
      const defaultIds = matterCommandCenterRecordIdsFromPayload(payload);
      if (matterCommandCenterSnapshotRecords && !matterCommandCenterSnapshotRecords.value.trim()) {
        matterCommandCenterSnapshotRecords.value = defaultIds.join('\n');
      }
      if (matterCommandCenterVariant && snapshot?.variant) matterCommandCenterVariant.value = String(snapshot.variant);
      if (matterCommandCenterStatus) {
        const matterId = payload?.matter_id || matterCommandCenterMatterId() || 'matter';
        matterCommandCenterStatus.textContent = payload
          ? `${matterId} · ${Number(coverage.record_count || included.length || 0).toLocaleString()} included records · ${Number(coverage.excluded_record_count || excluded.length || 0).toLocaleString()} excluded records · ${payload.stale_snapshot_detected ? 'stale snapshot detected' : 'snapshot current'}`
          : 'Open a local matter to inspect coverage, snapshots, and packet history.';
      }
      if (matterCommandCenterCompareLeft) matterCommandCenterCompareLeft.innerHTML = `<option value="">Select packet</option>${matterCommandCenterPacketOptions(payload)}`;
      if (matterCommandCenterCompareRight) matterCommandCenterCompareRight.innerHTML = `<option value="">Select packet</option>${matterCommandCenterPacketOptions(payload)}`;
      if (matterCommandCenterCompareStatus) {
        matterCommandCenterCompareStatus.textContent = packets.length >= 2
          ? `Choose two packet versions to compare. ${packets.length} packet${packets.length === 1 ? '' : 's'} are available.`
          : 'Build at least two packets before comparing versions.';
      }
      if (matterCommandCenterBody) {
        const includedMarkup = included.slice(0, 100).map((row) => `<article class="matter-command-center-record"><div><strong>${escapeHtml(row.evidence_id || row.record_id || 'record')}</strong><span class="badge">${escapeHtml(String(row.source_type || '').replaceAll('_', ' ')) || 'record'}</span></div><small>${escapeHtml(String(row.title || row.safe_filename || 'No title'))}</small><p>${escapeHtml(String(row.source_hash || row.text_sha256 || '').slice(0, 20))}${row.source_hash || row.text_sha256 ? '…' : ''}</p></article>`).join('');
        const excludedMarkup = excluded.slice(0, 60).map((row) => `<li><strong>${escapeHtml(row.evidence_id || row.record_id || 'record')}</strong> — ${escapeHtml(String(row.reason || '').replaceAll('_', ' '))}</li>`).join('');
        const packetMarkup = packets.slice().reverse().slice(0, 12).map((packet) => `<article class="matter-command-center-packet"><div><strong>${escapeHtml(packet.packet_id || '')}</strong><span class="badge ${packet.review_required ? 'warn' : 'good'}">${packet.review_required ? 'review required' : 'reviewed'}</span></div><small>Snapshot ${escapeHtml(packet.snapshot_id || '')} · ${escapeHtml(String(packet.variant || '').replaceAll('_', ' '))}</small><small>${escapeHtml(packet.generated_at || '')}</small></article>`).join('') || '<p class="muted">No packets have been built for this matter yet.</p>';
        const warningMarkup = staleReasons.length
          ? `<div class="matter-command-center-warning"><strong>Stale snapshot warning</strong><ul>${staleReasons.map((item) => `<li>${escapeHtml(String(item).replaceAll('_', ' '))}</li>`).join('')}</ul></div>`
          : '<div class="matter-command-center-warning status-ok">The current snapshot still matches the selected record set.</div>';
        matterCommandCenterBody.innerHTML = `
          <section class="answer-section">
            <h3>Overview</h3>
            <p><strong>Matter:</strong> ${escapeHtml(payload?.matter_id || matterCommandCenterMatterId() || 'not selected')}</p>
            <p><strong>Latest snapshot:</strong> ${escapeHtml(payload?.latest_snapshot_id || 'none')}</p>
            <p><strong>Latest packet:</strong> ${escapeHtml(payload?.latest_packet_id || 'none')}</p>
            <p><strong>Variant:</strong> ${escapeHtml(String(snapshot?.variant || 'metadata_only').replaceAll('_', ' '))}</p>
            <p><strong>Review required:</strong> yes</p>
            ${warningMarkup}
          </section>
          <section class="answer-section">
            <h3>Coverage</h3>
            <dl class="matter-command-center-grid">
              <div><dt>Included records</dt><dd>${escapeHtml(coverage.record_count || included.length || 0)}</dd></div>
              <div><dt>Excluded records</dt><dd>${escapeHtml(coverage.excluded_record_count || excluded.length || 0)}</dd></div>
              <div><dt>With text</dt><dd>${escapeHtml(coverage.with_text_count || 0)}</dd></div>
              <div><dt>With source hash</dt><dd>${escapeHtml(coverage.with_source_hash_count || 0)}</dd></div>
              <div><dt>Privacy flags</dt><dd>${escapeHtml(coverage.privacy_flag_count || 0)}</dd></div>
              <div><dt>Selected scope</dt><dd>${fullCoverage.selected_scope ? 'yes' : 'no'}</dd></div>
            </dl>
            <p class="muted">Full-record coverage stays visible in the snapshot receipt, not hidden in a single opaque export.</p>
          </section>
          <section class="answer-section">
            <h3>Snapshot scope</h3>
            <div class="matter-command-center-record-list">${includedMarkup || '<p class="muted">No included records were returned.</p>'}</div>
            ${excludedMarkup ? `<details><summary>Excluded records (${escapeHtml(excluded.length)})</summary><ul>${excludedMarkup}</ul></details>` : ''}
          </section>
          <section class="answer-section">
            <h3>Packet history</h3>
            <div class="matter-command-center-record-list">${packetMarkup}</div>
          </section>`;
      }
      if (matterCommandCenterCompareLeft && selectedIds.length) matterCommandCenterCompareLeft.value = matterCommandCenterCompareLeft.value || packets.at(-1)?.packet_id || '';
      if (matterCommandCenterCompareRight && selectedIds.length) matterCommandCenterCompareRight.value = matterCommandCenterCompareRight.value || packets.at(-2)?.packet_id || packets.at(-1)?.packet_id || '';
    }

    async function loadMatterCommandCenter({preserveScope = true} = {}) {
      const matterId = matterCommandCenterMatterId();
      if (!matterId) {
        matterCommandCenterPayload = null;
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Select a private matter before opening the command center.';
        if (matterCommandCenterBody) matterCommandCenterBody.textContent = 'Open a local matter to inspect coverage, snapshots, and packet history.';
        if (matterCommandCenterCompareStatus) matterCommandCenterCompareStatus.textContent = 'Compare output appears here after you select two packet versions.';
        return;
      }
      if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Loading whole-matter command center…';
      try {
        const payload = await fetchJson(`/api/matters/${encodeURIComponent(matterId)}/command-center`);
        renderMatterCommandCenter(payload);
        if (!preserveScope && matterCommandCenterSnapshotRecords) {
          matterCommandCenterSnapshotRecords.value = matterCommandCenterRecordIdsFromPayload(payload).join('\n');
        }
        if (matterCommandCenterStatus) {
          matterCommandCenterStatus.textContent = payload.stale_snapshot_detected
            ? `Loaded ${matterId}. Snapshot is stale and needs a new freeze before packet comparisons are reliable.`
            : `Loaded ${matterId}. Snapshot and packet history are available.`;
        }
      } catch (err) {
        matterCommandCenterPayload = null;
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = err.message;
        if (matterCommandCenterBody) matterCommandCenterBody.textContent = `The command center could not load: ${err.message}`;
      }
      updateMatterCommandCenterControls();
    }

    function updateMatterCommandCenterControls() {
      const matterId = matterCommandCenterMatterId();
      const hasMatter = Boolean(matterId);
      const approved = Boolean(matterCommandCenterApproved?.checked);
      const packetId = String(matterCommandCenterPayload?.latest_packet_id || '');
      const compareReady = Boolean(String(matterCommandCenterCompareLeft?.value || '') && String(matterCommandCenterCompareRight?.value || '') && matterCommandCenterCompareLeft?.value !== matterCommandCenterCompareRight?.value);
      if (matterCommandCenterFreeze) matterCommandCenterFreeze.disabled = !hasMatter || !approved;
      if (matterCommandCenterBuild) matterCommandCenterBuild.disabled = !hasMatter || !approved || !String(matterCommandCenterPayload?.latest_snapshot_id || '');
      if (matterCommandCenterCompare) matterCommandCenterCompare.disabled = !hasMatter || !compareReady;
      if (matterCommandCenterSnapshotRecords) matterCommandCenterSnapshotRecords.disabled = !hasMatter;
      if (matterCommandCenterVariant) matterCommandCenterVariant.disabled = !hasMatter;
      if (matterCommandCenterApproved) matterCommandCenterApproved.disabled = !hasMatter;
      if (matterCommandCenterRefresh) matterCommandCenterRefresh.disabled = !hasMatter && !matterCommandCenterPayload;
      if (matterCommandCenterCompareStatus && !hasMatter) matterCommandCenterCompareStatus.textContent = 'Select a private matter before comparing packet versions.';
      if (matterCommandCenterBody && !hasMatter && !matterCommandCenterPayload) {
        matterCommandCenterBody.textContent = 'Open a local matter to inspect coverage, snapshots, and packet history.';
      }
      if (matterCommandCenterCompareLeft && !matterCommandCenterCompareLeft.value && packetId) matterCommandCenterCompareLeft.value = packetId;
      if (matterCommandCenterCompareRight && !matterCommandCenterCompareRight.value && packetId) matterCommandCenterCompareRight.value = packetId;
    }

    async function openMatterCommandCenter(owner = null) {
      if (!matterCommandCenterOverlay) return;
      setWorkflowFocus('command');
      openOverlay(matterCommandCenterOverlay);
      matterCommandCenterSnapshotRecords?.focus({preventScroll: true});
      await loadMatterCommandCenter();
      matterCommandCenterSnapshotRecords?.focus({preventScroll: true});
    }

    async function freezeMatterCommandCenterSnapshot() {
      const matterId = matterCommandCenterMatterId();
      if (!matterId) {
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Select a private matter before freezing a snapshot.';
        return;
      }
      if (!matterCommandCenterApproved?.checked) {
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Approve the exact matter scope before freezing a snapshot.';
        return;
      }
      const selected = matterCommandCenterSelectedRecordIds();
      const variant = String(matterCommandCenterVariant?.value || 'metadata_only');
      if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Freezing review snapshot…';
      try {
        await fetchJson(`/api/matters/${encodeURIComponent(matterId)}/review-snapshot`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({selected_record_ids: selected, variant, approved: true})
        });
        await loadMatterCommandCenter({preserveScope: true});
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Review snapshot frozen. Packet generation remains review required.';
      } catch (err) {
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = err.message;
      }
    }

    async function buildMatterCommandCenterPacket() {
      const matterId = matterCommandCenterMatterId();
      if (!matterId) {
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Select a private matter before building a packet.';
        return;
      }
      if (!matterCommandCenterApproved?.checked) {
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Approve the exact matter scope before building a packet.';
        return;
      }
      const selected = matterCommandCenterSelectedRecordIds();
      const variant = String(matterCommandCenterVariant?.value || 'metadata_only');
      const snapshotId = String(matterCommandCenterPayload?.latest_snapshot_id || matterCommandCenterPayload?.snapshot?.snapshot_id || '');
      if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Building evidence packet…';
      try {
        await fetchJson(`/api/matters/${encodeURIComponent(matterId)}/evidence-packet`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({selected_record_ids: selected, snapshot_id: snapshotId, variant, approved: true})
        });
        await loadMatterCommandCenter({preserveScope: true});
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = 'Evidence packet built. Review and comparison remain separate actions.';
      } catch (err) {
        if (matterCommandCenterStatus) matterCommandCenterStatus.textContent = err.message;
      }
    }

    async function compareMatterCommandCenterPackets() {
      const leftPacketId = String(matterCommandCenterCompareLeft?.value || '').trim();
      const rightPacketId = String(matterCommandCenterCompareRight?.value || '').trim();
      if (!leftPacketId || !rightPacketId || leftPacketId === rightPacketId) {
        if (matterCommandCenterCompareStatus) matterCommandCenterCompareStatus.textContent = 'Choose two different packet versions before comparing them.';
        return;
      }
      if (matterCommandCenterCompareStatus) matterCommandCenterCompareStatus.textContent = 'Comparing packet versions…';
      try {
        const payload = await fetchJson(`/api/evidence-packets/${encodeURIComponent(leftPacketId)}/compare`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({right_packet_id: rightPacketId})
        });
        if (matterCommandCenterCompareStatus) {
          matterCommandCenterCompareStatus.innerHTML = `<strong>Comparison ready.</strong> Same packet: ${payload.same_packet ? 'yes' : 'no'} · Same record scope: ${payload.same_record_scope ? 'yes' : 'no'} · Added records: ${escapeHtml((payload.added_record_ids || []).join(', ') || 'none')} · Removed records: ${escapeHtml((payload.removed_record_ids || []).join(', ') || 'none')}`;
        }
      } catch (err) {
        if (matterCommandCenterCompareStatus) matterCommandCenterCompareStatus.textContent = err.message;
      }
    }

    async function saveWorkspaceNewDraft() {
      const title = documentWorkspaceTitle?.value.trim() || 'Untitled local draft';
      const content = documentWorkspaceEditor?.value || '';
      setDocumentWorkspaceStatus('Saving immutable first revision…');
      try {
        const note = documentWorkspaceState.seedNote || 'Created in the in-app document workspace.';
        const sourceRefs = Array.isArray(documentWorkspaceState.seedSourceRefs) ? documentWorkspaceState.seedSourceRefs : [];
        const payload = await fetchJson('/api/document-workspace/documents', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({title, content, document_type: documentWorkspaceType?.value || 'draft', note, tags: [], source_refs: sourceRefs})});
        documentWorkspaceState.seedSourceRefs = [];
        documentWorkspaceState.seedNote = '';
        await loadDocumentWorkspaceDocuments(payload.document?.document_id || '');
        showToast('Draft saved locally.');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function saveAnswerAsDraft(text, payload = null) {
      const structuredTitle = payload?.structured_answer?.intake_label || payload?.question || 'Chat answer draft';
      const sourceRefs = sourceItemsFromPayload(payload).slice(0, 60).map((item) => {
        const meta = item?.metadata || item || {};
        return {
          source_id: item?.source_id || item?.evidence_id || meta.source_id || meta.id || '',
          title: item?.title || meta.title || sourceBasename(item),
          citation: item?.citation || meta.citation_hint || '',
          source_class: meta.source_class || meta.source_type || (sourceLane(item) === 'records' ? 'private_record' : 'legal_authority'),
          hash: meta.source_hash || '',
          page: Number(meta.page_number || 0),
          safe_locator: meta.source_locator_basename || meta.safe_locator || ''
        };
      });
      const receipt = payload?.provenance_receipt || payload?.metadata?.provenance_receipt || null;
      if (receipt?.receipt_sha256) {
        sourceRefs.push({
          source_id: receipt.run_id || 'answer-provenance',
          title: payload?.local_agent_result ? 'Loopback local model provenance receipt' : 'Host answer provenance receipt',
          citation: `Context manifest ${receipt.context_manifest_sha256 || ''}`,
          source_class: 'answer_provenance_receipt',
          hash: receipt.receipt_sha256,
          safe_locator: `answer sha256 ${receipt.answer_sha256 || ''}`
        });
      }
      const note = receipt?.receipt_sha256
        ? `Created from chat answer with provenance receipt ${receipt.receipt_sha256}. Review required.`
        : 'Created from chat answer. Review required.';
      await openDocumentWorkspace({seedTitle: String(structuredTitle).slice(0, 200), seedContent: String(text || ''), documentType: 'memo', sourceRefs, note});
      setDocumentWorkspaceStatus('Answer copied with its source and provenance references. Review the text, then save it.', 'good');
    }

    async function importRecordToWorkspace(binding, title = '') {
      const token = recordToken(binding);
      if (!token) { showToast('A secure local record token is not available.'); return; }
      setDocumentWorkspaceStatus('Importing a verified copy while preserving the original…');
      try {
        const payload = await fetchJson('/api/document-workspace/import-record', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({source_token: token, page: 0, title: title || binding?.basename || '', document_type: 'draft'})});
        await openDocumentWorkspace({documentId: payload.document?.document_id || ''});
        setDocumentWorkspaceStatus('Verified record imported. The original is immutable; edit the working draft or create tracked Word changes.', 'good');
        showToast('Record imported into drafting.');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); showToast(err.message); }
    }

    async function proposeWorkspaceRevision() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      setDocumentWorkspaceStatus('Building line-by-line review…');
      try {
        const payload = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/proposals`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content: documentWorkspaceEditor?.value || '', base_revision_id: active.current_revision_id, note: 'Proposed in the in-app drafting workspace.'})});
        documentWorkspaceState.proposal = payload.proposal;
        renderWorkspaceDiff(payload.proposal);
        documentWorkspaceCommit.disabled = false;
        documentWorkspaceReject.disabled = false;
        setDocumentWorkspaceStatus('Proposal ready. Review every change before committing.', 'good');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function commitWorkspaceRevision() {
      const active = documentWorkspaceState.active;
      const proposal = documentWorkspaceState.proposal;
      if (!active?.document_id || !proposal?.confirmation_token) return;
      if (!window.confirm('Commit this reviewed revision as the current working draft? The prior revision and imported original will remain preserved.')) return;
      try {
        const payload = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/commit`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({revision_id: proposal.revision_id, confirmation_token: proposal.confirmation_token, confirmed: true})});
        await loadDocumentWorkspaceDocuments(payload.document?.document_id || active.document_id);
        showToast('Reviewed revision committed.');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function rejectWorkspaceRevision() {
      const active = documentWorkspaceState.active;
      const proposal = documentWorkspaceState.proposal;
      if (!active?.document_id || !proposal?.revision_id) return;
      try {
        await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/reject`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({revision_id: proposal.revision_id})});
        clearWorkspaceProposal();
        await selectWorkspaceDocument(active.document_id);
        showToast('Proposal rejected; current draft unchanged.');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function softDeleteWorkspaceDocument() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      try {
        const request = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/delete-request`, {method: 'POST'});
        if (!window.confirm(`Move “${active.title}” to the local trash? Revisions and imported originals remain recoverable.`)) return;
        await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/delete`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({confirmation_token: request.confirmation_token, confirmed: true})});
        await loadDocumentWorkspaceDocuments(active.document_id);
        showToast('Document moved to trash.');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function restoreWorkspaceDocument() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      try {
        await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/restore`, {method: 'POST'});
        await loadDocumentWorkspaceDocuments(active.document_id);
        showToast('Document restored.');
      } catch (err) { setDocumentWorkspaceStatus(err.message, 'bad'); }
    }

    async function loadWorkspaceDocxParagraphs() {
      const active = documentWorkspaceState.active;
      if (!active?.document_id) return;
      if (documentWorkspaceDocxResult) documentWorkspaceDocxResult.textContent = 'Reading hash-anchored Word paragraphs…';
      try {
        const payload = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/docx/paragraphs?start=1&limit=300`);
        const rows = Array.isArray(payload.paragraphs) ? payload.paragraphs : [];
        documentWorkspaceDocxParagraph.innerHTML = rows.map((row) => `<option value="${escapeHtml(row.ref)}">${escapeHtml(row.ref)} · ${escapeHtml(String(row.text || '').slice(0, 110))}</option>`).join('') || '<option value="">No paragraphs found</option>';
        [documentWorkspaceDocxParagraph, documentWorkspaceDocxAction, documentWorkspaceDocxFind, documentWorkspaceDocxText, documentWorkspaceDocxApply].forEach((control) => { if (control) control.disabled = !rows.length; });
        documentWorkspaceDocxResult.textContent = `${rows.length} of ${payload.total || rows.length} paragraphs loaded. Select the exact hash-anchored paragraph.`;
      } catch (err) { documentWorkspaceDocxResult.textContent = err.message; }
    }

    async function applyWorkspaceTrackedDocxEdit() {
      const active = documentWorkspaceState.active;
      const paragraph = documentWorkspaceDocxParagraph?.value || '';
      const action = documentWorkspaceDocxAction?.value || 'replace';
      if (!active?.document_id || !paragraph) return;
      const find = documentWorkspaceDocxFind?.value || '';
      const text = documentWorkspaceDocxText?.value || '';
      const operation = {action, paragraph, occurrence: 0};
      if (action === 'replace') { operation.find = find; operation.replace_with = text; }
      else if (action === 'delete') operation.text = find || text;
      else if (action === 'insert_after') { operation.find = find; operation.text = text; }
      else if (action === 'rewrite_paragraph') operation.text = text;
      else if (action === 'add_comment') { operation.find = find; operation.comment = text; delete operation.paragraph; }
      if (!window.confirm('Create a NEW Word copy with this tracked change? The imported original will not be overwritten.')) return;
      documentWorkspaceDocxApply.disabled = true;
      try {
        const payload = await fetchJson(`/api/document-workspace/documents/${encodeURIComponent(active.document_id)}/docx/tracked-edit`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({operations: [operation], author: 'Maine Family Law LLM User', confirmed: true})});
        documentWorkspaceDocxResult.innerHTML = `<strong>Tracked review copy created.</strong><span>Original preserved · SHA-256 ${escapeHtml(String(payload.sha256 || '').slice(0, 16))}…</span><a class="primary-action compact-action" href="${escapeHtml(payload.download_url)}" download>Download tracked Word copy</a>`;
        showToast('Tracked Word copy created.');
      } catch (err) { documentWorkspaceDocxResult.textContent = err.message; }
      finally { documentWorkspaceDocxApply.disabled = false; }
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
      updateTrustStatus();
      updateWorkflowStatus();
    }

    function updateTrustStatus() {
      if (!trustStatusStrip) return;
      const hasMatter = Boolean(corpusSelect?.value);
      const matterLabel = hasMatter ? selectedLabel(corpusSelect).split(' (')[0] : 'General Maine law';
      if (trustRecordStatus) trustRecordStatus.textContent = matterLabel;
      if (trustRecordDetail) trustRecordDetail.textContent = hasMatter
        ? 'Active local matter. Record statements are evidence—not legal authority or findings.'
        : 'No private matter selected. Record-only actions remain unavailable.';
      const recordLane = trustRecordStatus?.closest('.trust-lane');
      if (recordLane) recordLane.dataset.trustState = hasMatter ? 'available' : 'neutral';
      if (trustRecordAction) trustRecordAction.textContent = hasMatter ? 'Review matter' : 'Choose matter';

      const authorityActive = Boolean(authorityTrustPayload?.active) && Number(authorityTrustPayload?.source_count || authorityTrustPayload?.count || 0) > 0;
      const authorityBlockers = Array.isArray(authorityTrustPayload?.blockers) ? authorityTrustPayload.blockers : [];
      if (trustAuthorityStatus) trustAuthorityStatus.textContent = authorityActive
        ? `${Number(authorityTrustPayload?.source_count || authorityTrustPayload?.count || 0).toLocaleString()} official sources available`
        : authorityTrustPayload ? 'Official authority unavailable' : 'Checking local authority…';
      if (trustAuthorityDetail) trustAuthorityDetail.textContent = authorityActive
        ? `Build ${authorityTrustPayload?.build_id || 'active'} · freshness and exact spans still require review.`
        : authorityTrustPayload ? `${authorityBlockers.length || 1} blocker${authorityBlockers.length === 1 ? '' : 's'} · current-law wording remains blocked.` : 'Freshness and verifier state will appear here.';
      const authorityLane = trustAuthorityStatus?.closest('.trust-lane');
      if (authorityLane) authorityLane.dataset.trustState = authorityTrustPayload ? (authorityActive ? 'available' : 'blocked') : 'checking';

      const answerBlockers = Array.isArray(lastPayload?.blockers) ? lastPayload.blockers : [];
      const blockerCount = authorityActive ? answerBlockers.length : answerBlockers.length + 1;
      if (trustReviewStatus) trustReviewStatus.textContent = 'Review required before reliance or export';
      if (trustReviewDetail) trustReviewDetail.textContent = blockerCount
        ? `${blockerCount} current blocker${blockerCount === 1 ? '' : 's'} · open the relevant source or review panel, correct the issue, then rerun.`
        : 'No automated blocker is currently listed, but human review is still required.';
    }

    function updateWorkflowStatus() {
      if (!workflowStatus) return;
      const hasActiveMatter = Boolean(corpusSelect?.value);
      const messagesByWorkflow = {
        research: 'Ask a Maine-law question, then inspect the source cards placed with the answer.',
        matter: hasActiveMatter
          ? 'A private matter is selected. Review the inventory or run local OCR only when you approve it.'
          : 'Select a private matter to inspect records locally. General Maine-law research remains available without one.',
        authority: 'Open the Maine Authority Library, verify official sources, and check freshness before relying on a citation.',
        intelligence: hasActiveMatter
          ? 'Inspect a verified record, preserve the original, and create OCR or privacy derivatives only when approved.'
          : 'Open a private matter or record first. Document intelligence stays local and review required.',
        timeline: hasActiveMatter
          ? 'Build or inspect a dated evidence timeline, then review contradictions and missing records.'
          : 'Open a private matter before building the evidence timeline.',
        claims: hasActiveMatter
          ? 'Enter claims, scope, support, contradictions, qualification, and reviewer decisions in the filing review.'
          : 'Open a private matter before entering claims and contradiction review.',
        coverage: hasActiveMatter
          ? 'Freeze a whole-matter snapshot, confirm included and excluded records, and compare packet versions.'
          : 'Open a private matter before freezing a whole-matter snapshot.',
        enforcement: hasActiveMatter
          ? 'Review the operative order, alleged conduct, notice, and ability-to-comply gaps without deciding contempt.'
          : 'Open a private matter before reviewing the enforcement ledger.',
        findings: hasActiveMatter
          ? 'Check Rule 52 findings, restrictions, and supporting evidence before drafting a working copy.'
          : 'Open a private matter before building findings review.',
        forms: hasActiveMatter
          ? 'Load the verified form catalog, complete a working copy, and keep the original form immutable.'
          : 'Open a private matter before reviewing current forms.',
        command: hasActiveMatter
          ? 'Freeze the matter scope, compare packet versions, and review snapshot history from one place.'
          : 'Open a private matter before using the whole-matter command center.',
        draft: hasActiveMatter
          ? 'Create or revise a working draft. Originals stay immutable and Word review creates a separate copy.'
          : 'Drafting is available after you open a local matter. Review gates remain visible before every export.',
        privacy: 'Private records stay on this device. Opening an external source or exporting a file is always a separate action.',
      };
      workflowStatus.textContent = messagesByWorkflow[activeWorkflow] || messagesByWorkflow.research;
    }

    function setWorkflowFocus(workflow) {
      activeWorkflow = workflow || 'research';
      document.body.dataset.workflow = activeWorkflow;
      workflowActions.forEach((button) => {
        const selected = button.dataset.workflowAction === activeWorkflow;
        button.classList.toggle('is-active', selected);
        button.setAttribute('aria-pressed', selected ? 'true' : 'false');
      });
      updateWorkflowStatus();
    }

    function overlayFocusableElements(element) {
      if (!element) return [];
      return Array.from(element.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], details > summary, [tabindex]:not([tabindex="-1"])'
      )).filter((node) => !node.hidden && !node.closest('[hidden]') && node.getAttribute('aria-hidden') !== 'true');
    }

    function openOverlay(element) {
      if (!element) return;
      if (element.hidden) overlayReturnFocus.set(element, document.activeElement);
      element.hidden = false;
      element.setAttribute('aria-hidden', 'false');
      const dialog = element.matches('[role="dialog"]') ? element : element.querySelector('[role="dialog"]');
      if (dialog && !dialog.hasAttribute('tabindex')) dialog.setAttribute('tabindex', '-1');
      const focusable = overlayFocusableElements(element);
      window.setTimeout(() => {
        if (dialog) {
          dialog.scrollTop = 0;
          dialog.focus({preventScroll: true});
        } else {
          focusable[0]?.focus({preventScroll: true});
        }
      }, 10);
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

    function renderSuggestedQuestionSection(values) {
      const rows = Array.isArray(values) ? values.filter(Boolean) : [];
      if (!rows.length) return '';
      return `<section class="answer-section follow-up-questions"><h3>Questions that would sharpen the next answer</h3><p class="muted">Choose one to place it in the composer. Review or adapt it before sending.</p><div class="follow-up-question-list">${rows.map((row) => `<button class="secondary compact-action" data-use-followup="${escapeHtml(row)}" type="button">Use as draft: ${escapeHtml(row)}</button>`).join('')}</div></section>`;
    }

    function bindAnswerFollowUps(container = answer) {
      container?.querySelectorAll('[data-use-followup]').forEach((button) => button.addEventListener('click', () => {
        const draft = String(button.dataset.useFollowup || '').trim();
        if (!draft) return;
        question.value = draft;
        question.style.height = 'auto';
        question.style.height = `${Math.min(question.scrollHeight, 180)}px`;
        question.focus({preventScroll: true});
        syncContextBar();
        showToast('Follow-up drafted. Review it, then send when ready.');
      }));
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
        const duplicateCopies = Math.max(1, Number(group.duplicate_copy_count || 1));
        const duplicateNote = duplicateCopies > 1 ? ` · ${duplicateCopies} identical copies grouped` : '';
        const detailId = `record-matches-${index}`;
        const pagePicker = pages.length ? `<span class="record-page-picker"><label class="sr-only" for="record-page-${index}">Matching page</label><select id="record-page-${index}" data-record-page-select="${token}">${pages.map((page) => `<option value="${escapeHtml(page)}">Page ${escapeHtml(page)}</option>`).join('')}</select><button class="secondary compact-action" data-inspect-selected-page="${token}" type="button">Inspect page</button></span>` : '';
        return `<article class="record-result-card"><div class="record-result-head"><div><strong>${basename}</strong><p class="muted">${documentType} · ${matches} matching ${matches === 1 ? 'row' : 'rows'}${pages.length ? ` · ${pages.length} matching ${pages.length === 1 ? 'page' : 'pages'}` : ''}${duplicateNote}</p></div><div class="record-result-actions"><button class="primary-action compact-action" data-inspect-record="${token}" type="button" aria-label="Inspect ${basename}">Inspect</button><button class="secondary compact-action" data-draft-record="${token}" data-record-title="${basename}" type="button" aria-label="Draft from ${basename}">Draft from record</button><button class="secondary compact-action" data-open-record="${token}" type="button" aria-label="Open original ${basename}">Open original</button>${pagePicker}</div></div><details id="${detailId}" class="record-match-details"><summary>Show all matches in this document</summary><ul class="answer-list">${snippets.map((snippet) => `<li>${escapeHtml(String(snippet))}</li>`).join('')}</ul></details></article>`;
      }).join('')}</section>`;
    }

    function bindRecordOpenActions(container = answer) {
      container.querySelectorAll('[data-inspect-record]').forEach((button) => button.addEventListener('click', () => {
        openRecordInspector({source_token: button.dataset.inspectRecord}, 0, button);
      }));
      container.querySelectorAll('[data-draft-record]').forEach((button) => button.addEventListener('click', () => {
        importRecordToWorkspace({source_token: button.dataset.draftRecord, basename: button.dataset.recordTitle || ''}, button.dataset.recordTitle || 'Imported record draft');
      }));
      container.querySelectorAll('[data-open-record]').forEach((button) => button.addEventListener('click', () => {
        openRecordOriginal({source_token: button.dataset.openRecord}, 0);
      }));
      container.querySelectorAll('[data-inspect-selected-page]').forEach((button) => button.addEventListener('click', () => {
        const token = button.dataset.inspectSelectedPage || '';
        const select = container.querySelector(`[data-record-page-select="${CSS.escape(token)}"]`);
        openRecordInspector({source_token: token}, Number(select?.value || 0), button);
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
        const duplicateCount = Number(summary.duplicate_copy_count_collapsed || 0);
        const countLine = summary.result_count !== undefined
          ? `${summary.result_count} matching index ${summary.result_count === 1 ? 'row' : 'rows'} across ${uniqueDocuments} unique ${uniqueDocuments === 1 ? 'document' : 'documents'}${duplicateCount ? `; ${duplicateCount} duplicate ${duplicateCount === 1 ? 'copy' : 'copies'} collapsed` : ''}`
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
        const researchBrief = structured.answer_style === 'research_brief' ? (structured.research_brief || {}) : null;
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
        const researchBlock = researchBrief
          ? `<section class="answer-section research-brief"><h3>Research brief</h3><p><strong>Scope:</strong> ${escapeHtml(researchBrief.scope || 'Selected local research lane.')}</p><p class="muted">${escapeHtml(researchBrief.review_standard || 'Inspect original source cards before relying on any result.')}</p>${researchBrief.source_review_order?.length ? `<strong>Review sources in this order</strong><ol class="answer-list">${researchBrief.source_review_order.map((item) => `<li><strong>${escapeHtml(item.lane || 'Source')}:</strong> ${escapeHtml(item.title || 'Source')} — ${escapeHtml(item.review_focus || 'Open the source card and inspect the original text.')}</li>`).join('')}</ol>` : '<p class="status-warn">No source cards were returned for this research lane.</p>'}${researchBrief.open_issues?.length ? `<strong>Open research issues</strong><ul class="answer-list">${researchBrief.open_issues.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}</section>`
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
        const recoveryBlock = payload?.failure_class && payload.failure_class !== 'none'
          ? `<section class="answer-section answer-recovery"><h3>What could not be established</h3><p><strong>Status:</strong> ${escapeHtml(String(payload.failure_class).replaceAll('_', ' '))}</p><p>${escapeHtml(payload.recovery_hint || 'The available local sources did not establish a reliable answer. Refine the question or inspect the source lane before relying on it.')}</p><p class="muted">This is a recovery path, not a conclusion about the facts, deadline, outcome, or legal strategy.</p></section>`
          : '';
        const freshnessWarnings = Array.isArray(groundingIntegrity.warnings) ? groundingIntegrity.warnings : [];
        const currentLawStatus = String(groundingIntegrity.current_law_status || 'not assessed').replaceAll('_', ' ');
        answer.innerHTML = `<div class="answer-body structured-answer">
          ${intakeBlock}
          ${securityBlock}
          ${researchBlock}
          ${renderCriticalDates(structured.critical_dates || intake.critical_dates)}
          <section id="answer-section-main" class="answer-section"><h3>What this means</h3>${renderParagraphBlocks(structured.what_this_means)}</section>
          ${retrievalSection}
          ${supportSection}
          ${recoveryBlock}
          ${renderStructuredSection('What to do right now', structured.what_to_do_right_now, safety.immediate_safety_concern ? 'safety-answer' : '')}
          ${renderStructuredSection('Your next three steps', structured.next_three_steps)}
          ${renderStructuredSection('What to gather', structured.what_to_gather)}
          ${renderStructuredSection('What may be missing', structured.what_may_be_missing)}
          ${renderSuggestedQuestionSection(structured.suggested_questions)}
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
        bindAnswerFollowUps(answer);
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
      if (payload?.local_agent_result) badges.push('<span class="badge good">loopback local model</span>');
      else if (payload?.local_agent_available) badges.push('<span class="badge">local model available</span>');
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
      const researchBrief = structured.research_brief || {};
      const researchHandoff = researchBrief.schema_version
        ? {
            schema_version: researchBrief.schema_version,
            scope: researchBrief.scope || 'Selected local research lane.',
            source_counts: {
              maine_law: Array.isArray(structured.maine_law_sources) ? structured.maine_law_sources.length : 0,
              private_records: Array.isArray(structured.private_record_sources) ? structured.private_record_sources.length : 0,
            },
            open_issues: Array.isArray(researchBrief.open_issues) ? researchBrief.open_issues : [],
            review_standard: researchBrief.review_standard || 'Inspect original source cards before relying on any result.',
          }
        : null;
      const handoff = {
        review_required: payload?.review_required !== false,
        matched_library_id: metadata.matched_library_id || null,
        matched_topic: metadata.matched_library_topic || null,
        source_card_count: payload?.source_card_count || 0,
        answer_style: payload?.answer_style || metadata.answer_style || null,
        intake: structured.intake || payload?.intake || metadata.intake || null,
        intake_label: structured.intake_label || payload?.intake_label || null,
        missing_information: missing,
        follow_up_questions: followups,
        research_handoff: researchHandoff,
      };
      if ((!missing.length && !followups.length && !researchHandoff) || !payload) {
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
        ${researchHandoff ? `<strong>Research handoff</strong><p><strong>Scope:</strong> ${escapeHtml(researchHandoff.scope)}<br><strong>Source lanes:</strong> ${escapeHtml(researchHandoff.source_counts.maine_law)} Maine-law · ${escapeHtml(researchHandoff.source_counts.private_records)} private-record<br><span class="muted">${escapeHtml(researchHandoff.review_standard)}</span></p>${researchHandoff.open_issues.length ? `<strong>Open research issues</strong><ul>${researchHandoff.open_issues.map((row) => `<li>${escapeHtml(row)}</li>`).join('')}</ul>` : ''}` : ''}
        <button class="secondary" id="copy-handoff-button" type="button">Copy reviewer handoff JSON</button>`;
      const copyHandoff = document.getElementById('copy-handoff-button');
      copyHandoff?.addEventListener('click', async () => {
        await navigator.clipboard.writeText(JSON.stringify(handoff, null, 2));
        copyHandoff.textContent = 'Handoff copied';
        showToast('Reviewer handoff copied.');
        setTimeout(() => { copyHandoff.textContent = 'Copy reviewer handoff JSON'; }, 1100);
      });
    }

    function sourceIdentity(item) {
      const meta = item?.metadata || item || {};
      return String(item?.source_id || item?.evidence_id || meta.source_id || meta.id || '');
    }

    function sourceBasename(item) {
      const meta = item?.metadata || item || {};
      const raw = String(meta.source_locator || meta.source_locator_basename || item?.title || meta.title || 'Source')
        .split('!').pop().split('#page=', 1)[0].replaceAll('\\', '/');
      return raw.split('/').pop() || 'Source';
    }

    function draftSourceQuestion(item) {
      const meta = item?.metadata || item || {};
      const lane = normalizedSourceLane(item);
      const title = String(item?.title || meta.title || sourceBasename(item) || 'this source').slice(0, 180);
      const draft = lane === 'private_record'
        ? `What does the private record “${title}” say about this issue? Keep the record's facts separate from legal conclusions, and identify the surrounding context I should review.`
        : `How does “${title}” apply to my question? Explain the matched passage, identify what still needs current-law verification, and do not assume missing facts.`;
      question.value = draft;
      question.style.height = 'auto';
      question.style.height = `${Math.min(question.scrollHeight, 180)}px`;
      question.focus({preventScroll: true});
      syncContextBar();
      showToast('Source-focused follow-up drafted. Review it, then send when ready.');
    }

    function recordOpenBindingForPayload(item, payload = lastPayload) {
      const meta = item?.metadata || item || {};
      if (normalizedSourceLane(item) !== 'private_record' && !meta.record_open_token && !item?.source_token) return null;
      const directToken = String(meta.record_open_token || item?.source_token || '');
      if (/^[a-f0-9]{64}$/i.test(directToken)) {
        return {
          source_token: directToken,
          source_id: String(meta.parent_evidence_id || item?.source_id || ''),
          basename: String(meta.record_open_basename || sourceBasename(item)),
          pages: Number(meta.record_open_page || meta.page_number || 0) ? [Number(meta.record_open_page || meta.page_number)] : [],
        };
      }
      const groups = Array.isArray(payload?.record_groups) ? payload.record_groups : [];
      const sourceId = sourceIdentity(item);
      const parentId = String(meta.parent_evidence_id || sourceId || '');
      const basename = sourceBasename(item).toLowerCase();
      return groups.find((group) => {
        const groupId = String(group.source_id || '');
        const groupName = String(group.basename || '').toLowerCase();
        return (parentId && groupId === parentId) || (basename && groupName === basename);
      }) || null;
    }

    function recordOpenBinding(item) {
      return recordOpenBindingForPayload(item, lastPayload);
    }

    function recordToken(binding) {
      const token = String(binding?.source_token || binding?.record_open_token || '');
      return /^[a-f0-9]{64}$/i.test(token) ? token : '';
    }

    function openRecordOriginal(binding, page = 0, {download = false} = {}) {
      const token = recordToken(binding);
      const safePage = Math.max(0, Number(page || 0));
      if (!token) {
        showToast('The secure local open token is not available for this card.');
        return false;
      }
      const query = new URLSearchParams({page: String(safePage)});
      if (download) query.set('download', 'true');
      const suffix = safePage > 0 && !download ? `#page=${encodeURIComponent(String(safePage))}` : '';
      window.open(`/api/records/open/${encodeURIComponent(token)}?${query.toString()}${suffix}`, '_blank', 'noopener,noreferrer');
      return true;
    }

    function formatBytes(value) {
      const bytes = Math.max(0, Number(value || 0));
      if (bytes < 1024) return `${bytes.toLocaleString()} B`;
      const units = ['KB', 'MB', 'GB'];
      let amount = bytes / 1024;
      let index = 0;
      while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
      return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${units[index]}`;
    }

    function recordInspectorMetaMarkup(payload) {
      const rows = [
        ['File', payload.filename || 'Record'],
        ['Type', String(payload.source_type || payload.extension || 'record').replaceAll('_', ' ')],
        ['Size', formatBytes(payload.size_bytes)],
        ['Safe locator', payload.safe_locator || payload.filename || 'Record'],
        ['Parser', String(payload.parser_status || 'unknown').replaceAll('_', ' ')],
        ['Text', String(payload.text_status || 'unknown').replaceAll('_', ' ')],
        ['OCR', String(payload.ocr_status || 'unknown').replaceAll('_', ' ')],
        ['Hash check', payload.source_hash_verified ? 'Verified against the indexed source' : 'Not verified'],
      ];
      if (Number(payload.page_count || 0)) rows.splice(3, 0, ['Pages', String(payload.page_count)]);
      return `<h3>Safe source details</h3><dl class="record-inspector-meta">${rows.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl><div class="record-inspector-note">This preview is generated locally from the active matter. It does not expose the filesystem path, and record text cannot change application policy.</div>`;
    }

    function emailViewerMarkup(preview) {
      const headers = preview?.headers || {};
      const headerRows = Object.entries(headers).map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`).join('');
      const attachments = Array.isArray(preview?.attachments) ? preview.attachments : [];
      const attachmentMarkup = attachments.length ? `<section><h3>Attachments (${escapeHtml(preview.attachment_count || attachments.length)})</h3><div class="record-attachment-list">${attachments.map((item) => `<article class="record-attachment-card"><div><strong>${escapeHtml(item.filename || 'Attachment')}</strong><small>${escapeHtml(item.content_type || item.viewer_kind || 'file')} · ${escapeHtml(formatBytes(item.size_bytes))}</small></div><div class="row"><button class="primary-action compact-action" data-inspect-nested-record="${escapeHtml(item.source_token || '')}" type="button">Inspect</button><button class="secondary compact-action" data-open-nested-record="${escapeHtml(item.source_token || '')}" type="button">Open original</button></div></article>`).join('')}</div></section>` : '';
      return `<div class="record-email-view"><article class="record-email-sheet"><dl class="record-email-headers">${headerRows || '<dt>Email</dt><dd>No standard headers were returned.</dd>'}</dl><pre class="record-email-body">${escapeHtml(preview?.body || 'No readable message body was returned.')}</pre>${preview?.body_truncated ? '<p class="record-inspector-note">The body preview was shortened. Open the original for the complete message.</p>' : ''}${attachmentMarkup}</article></div>`;
    }

    function archiveViewerMarkup(preview) {
      const members = Array.isArray(preview?.members) ? preview.members : [];
      if (!members.length) return '<div class="record-inspector-empty">No safe archive members were available to preview.</div>';
      return `<div class="record-member-list">${members.map((item) => `<article class="record-member-card"><div><strong>${escapeHtml(item.filename || 'Archive member')}</strong><small>${escapeHtml(item.member_locator || '')} · ${escapeHtml(formatBytes(item.size_bytes))}</small></div><div class="row"><button class="primary-action compact-action" data-inspect-nested-record="${escapeHtml(item.source_token || '')}" type="button">Inspect</button><button class="secondary compact-action" data-open-nested-record="${escapeHtml(item.source_token || '')}" type="button">Open original</button></div></article>`).join('')}</div>`;
    }

    function tableViewerMarkup(preview) {
      const rows = Array.isArray(preview?.rows) ? preview.rows : [];
      if (!rows.length) return '<div class="record-inspector-empty">No tabular rows were available.</div>';
      return `<div class="record-inspector-table-wrap"><table class="record-inspector-table"><tbody>${rows.map((row) => `<tr>${(Array.isArray(row) ? row : []).map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table>${preview.rows_truncated ? '<p class="record-inspector-note">The table preview was shortened.</p>' : ''}</div>`;
    }

    function renderRecordInspector(payload) {
      recordInspectorState = payload;
      recordInspectorZoom = 1;
      const kind = String(payload?.viewer_kind || 'binary');
      const page = Math.max(1, Number(payload?.page || 1));
      const pageCount = Math.max(0, Number(payload?.page_count || 0));
      recordInspectorTitle.textContent = payload?.filename || 'Document inspector';
      recordInspectorSubtitle.textContent = `${String(payload?.extension || payload?.mime_type || 'record').replace('.', '').toUpperCase()} · ${formatBytes(payload?.size_bytes)} · verified local source`;
      recordInspectorBadges.innerHTML = `<span class="badge good">Hash verified</span><span class="badge">${escapeHtml(kind.replaceAll('_', ' '))}</span><span class="badge warn">Private record</span>`;
      recordInspectorDetails.innerHTML = recordInspectorMetaMarkup(payload);
      recordInspectorPageControls.hidden = kind !== 'pdf' || !pageCount;
      recordInspectorZoomControls.hidden = kind !== 'image';
      if (!recordInspectorPageControls.hidden) {
        recordInspectorPageInput.value = String(Math.min(pageCount, page));
        recordInspectorPageInput.max = String(pageCount);
        recordInspectorPageCount.textContent = `of ${pageCount.toLocaleString()}`;
        recordInspectorPrevPage.disabled = page <= 1;
        recordInspectorNextPage.disabled = page >= pageCount;
      }
      const openUrl = String(payload?.open_url || '');
      const preview = payload?.preview || {};
      if (kind === 'pdf') {
        const initialPage = Math.max(1, Number(payload.page || 1));
        recordInspectorViewer.innerHTML = `<iframe class="record-inspector-frame" title="PDF preview of ${escapeHtml(payload.filename || 'record')}" src="${escapeHtml(openUrl)}#page=${encodeURIComponent(String(initialPage))}&zoom=page-width"></iframe>`;
        if (preview.page_text) recordInspectorDetails.insertAdjacentHTML('beforeend', `<h3>Indexed text for page ${escapeHtml(initialPage)}</h3><pre class="record-text-preview">${escapeHtml(preview.page_text)}</pre>`);
      } else if (kind === 'image') {
        recordInspectorViewer.innerHTML = `<div class="record-image-stage"><img alt="Preview of ${escapeHtml(payload.filename || 'image record')}" id="record-inspector-image" src="${escapeHtml(openUrl)}"/></div>`;
        if (preview.ocr_text) recordInspectorDetails.insertAdjacentHTML('beforeend', `<h3>Local OCR text</h3><pre class="record-text-preview">${escapeHtml(preview.ocr_text)}</pre>`);
      } else if (kind === 'email') {
        recordInspectorViewer.innerHTML = emailViewerMarkup(preview);
      } else if (kind === 'archive') {
        recordInspectorViewer.innerHTML = archiveViewerMarkup(preview);
      } else if (kind === 'table') {
        recordInspectorViewer.innerHTML = tableViewerMarkup(preview);
      } else if (kind === 'text' || kind === 'office_text') {
        recordInspectorViewer.innerHTML = `<pre class="record-text-preview">${escapeHtml(preview.text || 'No readable text was returned.')}</pre>${preview.text_truncated ? '<p class="record-inspector-note">The text preview was shortened. Open the verified original for the complete file.</p>' : ''}`;
      } else if (kind === 'audio') {
        recordInspectorViewer.innerHTML = `<div class="record-media-view"><audio controls preload="metadata" src="${escapeHtml(openUrl)}"></audio></div>`;
      } else if (kind === 'video') {
        recordInspectorViewer.innerHTML = `<div class="record-media-view"><video controls preload="metadata" src="${escapeHtml(openUrl)}"></video></div>`;
      } else {
        recordInspectorViewer.innerHTML = `<div class="record-inspector-empty"><div><strong>No safe embedded viewer is available for this format.</strong><p>${escapeHtml(preview.message || 'Use Open original or Download verified copy.')}</p></div></div>`;
      }
      recordInspectorViewer.querySelectorAll('[data-inspect-nested-record]').forEach((button) => button.addEventListener('click', () => openRecordInspector({source_token: button.dataset.inspectNestedRecord}, 0, button)));
      recordInspectorViewer.querySelectorAll('[data-open-nested-record]').forEach((button) => button.addEventListener('click', () => openRecordOriginal({source_token: button.dataset.openNestedRecord}, 0)));
    }

    async function openRecordInspector(binding, page = 0, owner = null) {
      const token = recordToken(binding);
      const safePage = Math.max(0, Number(page || 0));
      if (!token) {
        showToast('This source does not have a current secure inspection token.');
        return false;
      }
      closeSourcePreview({force: true});
      recordInspectorOwner = owner || document.activeElement;
      recordInspector.hidden = false;
      recordInspectorBackdrop.hidden = false;
      recordInspector.setAttribute('aria-hidden', 'false');
      recordInspectorBackdrop.setAttribute('aria-hidden', 'false');
      document.body.classList.add('record-inspector-open');
      recordInspectorTitle.textContent = 'Document inspector';
      recordInspectorSubtitle.textContent = 'Loading verified local source…';
      recordInspectorViewer.innerHTML = '<div class="record-inspector-loading">Loading verified local source…</div>';
      recordInspectorDetails.innerHTML = '<div class="record-inspector-loading">Checking source hash and preparing a safe preview…</div>';
      recordInspectorPageControls.hidden = true;
      recordInspectorZoomControls.hidden = true;
      try {
        const payload = await fetchJson(`/api/records/inspect/${encodeURIComponent(token)}?page=${encodeURIComponent(String(safePage))}`);
        renderRecordInspector(payload);
        recordInspectorClose?.focus();
        return true;
      } catch (err) {
        recordInspectorViewer.innerHTML = `<div class="record-inspector-empty"><div><strong>The verified source could not be inspected.</strong><p>${escapeHtml(err.message)}</p></div></div>`;
        recordInspectorDetails.innerHTML = '<div class="record-inspector-note">The app failed closed. No filesystem path or unverified file was opened.</div>';
        return false;
      }
    }

    function closeRecordInspector() {
      if (!recordInspector || recordInspector.hidden) return;
      recordInspector.hidden = true;
      recordInspectorBackdrop.hidden = true;
      recordInspector.setAttribute('aria-hidden', 'true');
      recordInspectorBackdrop.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('record-inspector-open');
      const owner = recordInspectorOwner;
      recordInspectorOwner = null;
      recordInspectorState = null;
      if (owner && typeof owner.focus === 'function') owner.focus();
    }

    function changeInspectorPage(delta = 0, explicitPage = null) {
      if (!recordInspectorState || recordInspectorState.viewer_kind !== 'pdf') return;
      const total = Math.max(1, Number(recordInspectorState.page_count || 1));
      const current = Math.max(1, Number(recordInspectorState.page || 1));
      const target = Math.min(total, Math.max(1, explicitPage == null ? current + delta : Number(explicitPage || current)));
      openRecordInspector({source_token: recordInspectorState.token}, target, recordInspectorOwner);
    }

    function changeInspectorZoom(delta = 0, fit = false) {
      const image = document.getElementById('record-inspector-image');
      if (!image) return;
      recordInspectorZoom = fit ? 1 : Math.min(4, Math.max(.25, recordInspectorZoom + delta));
      image.style.transform = `scale(${recordInspectorZoom})`;
      image.style.maxWidth = fit ? '100%' : 'none';
      image.style.maxHeight = fit ? '100%' : 'none';
    }

    function sourcePreviewMarkup(item, payload = null) {
      const meta = item?.metadata || item || {};
      const title = item?.title || meta.title || meta.id || sourceIdentity(item) || 'Source';
      const lane = normalizedSourceLane(item);
      const sourceType = String(meta.source_type || meta.source_class || 'source');
      const citation = item?.citation || meta.citation_hint || '';
      const snippet = item?.snippet || item?.text_excerpt || meta.text_excerpt || meta.description || '';
      const pageNumber = Number(meta.page_number || item?.page_number || 0);
      const fields = [
        ['Citation', citation || 'not provided'],
        ['Lane', lane.replaceAll('_', ' ')],
        ['Jurisdiction', meta.jurisdiction || (lane === 'private_record' ? 'private matter' : 'Maine')],
        ['Source type', sourceType.replaceAll('_', ' ')],
        ['Version', meta.version_label || 'verify current source'],
        ['Effective', meta.effective_date || 'verify'],
        ['Freshness status', meta.freshness_status || meta.currentness_status || 'verify current source'],
        ['Source ID', sourceIdentity(item) || 'source'],
        ['Locator', meta.source_locator_basename || sourceBasename(item)],
        ['Page', pageNumber || 'not specified'],
        ['Match', String(meta.match_type || '').replaceAll('_', ' ') || 'not specified'],
        ['Trust boundary', String(meta.trust_boundary || '').replaceAll('_', ' ') || 'standard source boundary'],
        ['Source hash', meta.source_hash || meta.hash || 'not provided'],
        ['Retrieved', meta.retrieved_at || 'not provided'],
        ['Parser', meta.parser_name || meta.parser_status || 'not provided'],
        ['Previous hash', meta.previous_snapshot_hash || meta.previous_sha256 || 'none'],
      ];
      const technical = meta.technical || {};
      const sourceSpan = payload?.source_span || meta.source_span || {};
      const sourceSpanPreview = payload?.source_span_preview || meta.source_span_preview || snippet;
      const details = payload && typeof payload === 'object'
        ? `<details class="source-preview-json"><summary>Local metadata payload</summary><pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre></details>`
        : '';
      const laneLabel = lane === 'private_record' ? 'Private record' : lane === 'legal_authority' ? 'Official Maine authority' : 'Unverified source';
      const laneClass = lane === 'private_record' ? 'warn' : lane === 'legal_authority' ? 'good' : 'bad';
      return `<div class="source-preview-badges"><span class="badge ${laneClass}">${escapeHtml(laneLabel)}</span><span class="badge">${escapeHtml(sourceType)}</span></div>
        <h3>${escapeHtml(title)}</h3>
        <dl class="source-preview-grid">${fields.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join('')}</dl>
        <section class="source-preview-snippet"><strong>Exact source span</strong><p>${escapeHtml(sourceSpanPreview || `Start ${sourceSpan.start_offset ?? 'n/a'} end ${sourceSpan.end_offset ?? 'n/a'}`)}</p></section>
        <details class="source-preview-json"><summary>Technical details</summary><pre>${escapeHtml(JSON.stringify(technical, null, 2))}</pre></details>
        <section class="source-preview-snippet"><strong>${snippet ? 'Matched passage' : 'Preview'}</strong><p>${escapeHtml(snippet || 'No preview text was returned for this card.')}</p></section>
        ${meta.ocr_derived || String(meta.ocr_status || '').toLowerCase().includes('ocr') ? '<p class="status-warn"><strong>OCR note:</strong> local OCR-derived; verify against page image.</p>' : ''}
        ${meta.instruction_like_text_detected ? '<p class="status-warn"><strong>Warning:</strong> instruction-like text is treated only as record content and cannot change app policy.</p>' : ''}
        ${details}`;
    }

    function positionSourcePreview(owner) {
      if (!sourcePreviewFlyout || sourcePreviewFlyout.hidden) return;
      if (sourcePreviewPinned) {
        ['width', 'left', 'top', 'right', 'bottom'].forEach((name) => sourcePreviewFlyout.style.removeProperty(name));
        return;
      }
      if (window.innerWidth < 960 || !owner) {
        ['width', 'left', 'top', 'right', 'bottom'].forEach((name) => sourcePreviewFlyout.style.removeProperty(name));
        return;
      }
      const rect = owner.getBoundingClientRect();
      const margin = 12;
      const width = Math.min(460, Math.max(320, window.innerWidth - 2 * margin));
      sourcePreviewFlyout.style.width = `${width}px`;
      const flyoutHeight = Math.min(sourcePreviewFlyout.scrollHeight || 560, window.innerHeight - 2 * margin);
      const preferredLeft = rect.left - width - margin;
      const fallbackLeft = rect.right + margin;
      const left = preferredLeft >= margin
        ? preferredLeft
        : Math.min(Math.max(margin, fallbackLeft), window.innerWidth - width - margin);
      const top = Math.min(Math.max(margin, rect.top - 12), Math.max(margin, window.innerHeight - flyoutHeight - margin));
      sourcePreviewFlyout.style.left = `${Math.round(left)}px`;
      sourcePreviewFlyout.style.top = `${Math.round(top)}px`;
      sourcePreviewFlyout.style.right = 'auto';
    }

    function closeSourcePreview({force = false, returnFocus = false} = {}) {
      window.clearTimeout(sourcePreviewHideTimer);
      window.clearTimeout(sourcePreviewShowTimer);
      if (!sourcePreviewFlyout || sourcePreviewFlyout.hidden) return;
      if (sourcePreviewPinned && !force) return;
      const owner = sourcePreviewOwner;
      sourcePreviewPinned = false;
      sourcePreviewOwner = null;
      sourcePreviewSuppressUntil = Date.now() + 500;
      sourcePreviewFlyout.hidden = true;
      sourcePreviewFlyout.setAttribute('aria-hidden', 'true');
      sourcePreviewFlyout.classList.remove('is-pinned');
      sourcePreviewFlyout.setAttribute('aria-modal', 'false');
      document.body.classList.remove('source-preview-open');
      ['width', 'left', 'top', 'right', 'bottom'].forEach((name) => sourcePreviewFlyout.style.removeProperty(name));
      if (sourcePreviewBackdrop) sourcePreviewBackdrop.hidden = true;
      if (returnFocus && owner && typeof owner.focus === 'function') owner.focus();
    }

    function showSourcePreview(item, owner, {pin = false, payload = null} = {}) {
      if (!sourcePreviewFlyout || !sourcePreviewBody || !sourcePreviewActions) return;
      if (!pin && Date.now() < sourcePreviewSuppressUntil) return;
      window.clearTimeout(sourcePreviewHideTimer);
      const meta = item?.metadata || item || {};
      const title = item?.title || meta.title || sourceIdentity(item) || 'Source details';
      const lane = normalizedSourceLane(item);
      const binding = recordOpenBinding(item);
      const pageNumber = Number(meta.page_number || item?.page_number || 0);
      const url = safeExternalUrl(item?.url || meta.url || meta.official_url);
      sourcePreviewOwner = owner || sourcePreviewOwner;
      sourcePreviewPinned = Boolean(pin);
      sourcePreviewTitle.textContent = title;
      sourcePreviewBody.innerHTML = sourcePreviewMarkup(item, payload);
      sourcePreviewActions.innerHTML = `${lane === 'private_record' && binding ? `<button class="primary-action" data-preview-inspect-record type="button">Inspect document</button><button class="secondary" data-preview-open-record type="button">Open original</button>${pageNumber > 0 ? '<button class="secondary" data-preview-inspect-page type="button">Inspect matching page</button>' : ''}` : ''}${lane === 'legal_authority' && url ? `<a class="primary-action" href="${escapeHtml(url)}" target="_blank" rel="noreferrer noopener">Open official source</a>` : ''}<button class="secondary" data-preview-copy type="button">Copy source card</button>`;
      sourcePreviewFlyout.hidden = false;
      sourcePreviewFlyout.setAttribute('aria-hidden', 'false');
      sourcePreviewFlyout.classList.toggle('is-pinned', sourcePreviewPinned);
      sourcePreviewFlyout.setAttribute('aria-modal', sourcePreviewPinned ? 'true' : 'false');
      document.body.classList.toggle('source-preview-open', sourcePreviewPinned);
      if (sourcePreviewBackdrop) sourcePreviewBackdrop.hidden = !sourcePreviewPinned;
      positionSourcePreview(sourcePreviewOwner);
      sourcePreviewActions.querySelector('[data-preview-inspect-record]')?.addEventListener('click', () => openRecordInspector(binding, 0, sourcePreviewOwner));
      sourcePreviewActions.querySelector('[data-preview-open-record]')?.addEventListener('click', () => openRecordOriginal(binding, 0));
      sourcePreviewActions.querySelector('[data-preview-inspect-page]')?.addEventListener('click', () => openRecordInspector(binding, pageNumber, sourcePreviewOwner));
      sourcePreviewActions.querySelector('[data-preview-copy]')?.addEventListener('click', async (event) => {
        const safe = lastHandoffSources.find((row) => sourceIdentity(row) === sourceIdentity(item)) || item;
        await navigator.clipboard.writeText(JSON.stringify(safe, null, 2));
        event.currentTarget.textContent = 'Copied';
        showToast('Source card copied.');
      });
      if (sourcePreviewPinned) sourcePreviewClose?.focus();
    }

    function scheduleSourcePreview(item, owner) {
      if (sourcePreviewPinned || Date.now() < sourcePreviewSuppressUntil) return;
      window.clearTimeout(sourcePreviewShowTimer);
      sourcePreviewShowTimer = window.setTimeout(() => showSourcePreview(item, owner), 170);
    }

    function scheduleSourcePreviewClose() {
      window.clearTimeout(sourcePreviewHideTimer);
      sourcePreviewHideTimer = window.setTimeout(() => {
        const hovered = sourcePreviewFlyout?.matches(':hover') || sourcePreviewOwner?.matches(':hover');
        const focused = sourcePreviewFlyout?.contains(document.activeElement) || sourcePreviewOwner?.contains(document.activeElement);
        if (!hovered && !focused) closeSourcePreview();
      }, 180);
    }

    function applyRecordCardFilter() {
      if (!sourceCards) return;
      const query = String(recordCardFilter?.value || '').trim().toLocaleLowerCase();
      const cards = Array.from(sourceCards.querySelectorAll('.source-card'));
      let visibleCount = 0;
      cards.forEach((card) => {
        const matches = !query || card.textContent.toLocaleLowerCase().includes(query);
        card.hidden = !matches;
        card.dataset.sourceCard = matches ? 'visible' : 'filtered';
        if (matches) visibleCount += 1;
      });
      if (recordCardFilterClear) recordCardFilterClear.disabled = !query;
      if (recordCardFilterStatus) {
        recordCardFilterStatus.textContent = cards.length
          ? `${visibleCount} of ${cards.length} source card${cards.length === 1 ? '' : 's'} shown.`
          : 'No source cards to filter.';
      }
    }

    function renderSources(items) {
      if (!items || !items.length) {
        lastSources = [];
        sourceCards.innerHTML = '<span class="muted">No source cards returned.</span>';
        lastHandoffSources = [];
        closeSourcePreview({force: true});
        applyRecordCardFilter();
        return;
      }
      lastSources = items || [];
      sourceCards.innerHTML = items.map((item, index) => {
        const meta = item.metadata || item;
        const title = item.title || meta.title || meta.id || 'Source';
        const sourceType = meta.source_type || meta.source_class || 'source';
        const lane = normalizedSourceLane(item);
        const snippet = item.snippet || item.text_excerpt || meta.text_excerpt || meta.description || '';
        const spanPreview = item.source_span_preview || meta.source_span_preview || '';
        const citation = item.citation || meta.citation_hint || '';
        const sourceId = sourceIdentity(item);
        const pageNumber = Number(meta.page_number || item.page_number || 0);
        const url = safeExternalUrl(item?.url || meta.url || meta.official_url);
        const binding = recordOpenBinding(item);
        const previewId = `source-preview-${index}`;
        const freshness = String(meta.freshness_status || meta.currentness_status || 'unknown').toLowerCase();
        const laneLabel = lane === 'private_record' ? 'Private record' : lane === 'legal_authority' ? 'Official authority' : 'Unverified source';
        const laneClass = lane === 'private_record' ? 'warn' : lane === 'legal_authority' ? 'good' : 'bad';
        const badges = [
          `<span class="badge ${laneClass}">${escapeHtml(laneLabel)}</span>`,
          `<span class="badge">${escapeHtml(sourceType)}</span>`,
          `<span class="badge ${freshness === 'fresh' || freshness === 'current' ? 'good' : freshness === 'stale' || freshness === 'superseded' ? 'warn' : 'bad'}">${escapeHtml(freshness)}</span>`,
          meta.official === false ? '<span class="badge warn">unofficial</span>' : '',
        ].join('');
        const openAction = lane === 'private_record' && binding
          ? `<button class="primary-action compact-action" data-inspect-source-record="${escapeHtml(sourceId)}" type="button">Inspect</button><button class="secondary compact-action" data-open-source-record="${escapeHtml(sourceId)}" type="button">Open original</button>${pageNumber > 0 ? `<button class="secondary compact-action" data-inspect-source-page="${escapeHtml(sourceId)}" data-page="${escapeHtml(pageNumber)}" type="button">Inspect page ${escapeHtml(pageNumber)}</button>` : ''}`
          : (url ? `<a class="primary-action compact-action" href="${escapeHtml(url)}" target="_blank" rel="noreferrer noopener">Open official source</a>` : '');
        const sourceQuestionAction = sourceId
          ? `<button class="secondary compact-action" data-draft-source-question="${escapeHtml(sourceId)}" type="button">Ask about source</button>`
          : '';
        return `<article aria-controls="source-preview-flyout" aria-label="${escapeHtml(laneLabel)}: ${escapeHtml(title)}" class="source-card source-preview-anchor" data-source-card="visible" data-source-id="${escapeHtml(sourceId)}" data-source-lane="${escapeHtml(lane)}" data-preview-id="${previewId}" tabindex="0">
          <div class="source-card-badges">${badges}</div>
          <strong>${escapeHtml(title)}</strong>
          <div class="source-card-compact-meta">${citation ? `<span>${escapeHtml(citation)}</span>` : ''}${pageNumber ? `<span>Page ${escapeHtml(pageNumber)}</span>` : ''}<span>Retrieved: ${escapeHtml(meta.retrieved_at || 'n/a')}</span><span>Hash: ${escapeHtml(meta.source_hash || meta.hash || 'n/a')}</span><span>Locator: ${escapeHtml(sourceBasename(item))}</span></div>
          <div class="source-snippet"><span class="label">${spanPreview ? 'Exact span' : snippet ? 'Matched passage' : 'Preview'}</span><span>${escapeHtml(spanPreview || snippet || 'Open the preview for complete local source details.')}</span></div>
          <details class="source-card-technical"><summary>Technical</summary><pre>${escapeHtml(JSON.stringify({retrieved_at: meta.retrieved_at, source_hash: meta.source_hash || meta.hash, parser_status: meta.parser_status, parser_name: meta.parser_name, previous_snapshot_hash: meta.previous_snapshot_hash, source_span: meta.source_span}, null, 2))}</pre></details>
          <div class="source-card-actions">${openAction}${sourceQuestionAction}<button class="secondary compact-action" data-inspect-source="${escapeHtml(sourceId)}" type="button">Quick preview</button><button class="secondary compact-action" data-copy-source="${escapeHtml(sourceId)}" type="button">Copy card</button></div>
        </article>`;
      }).join('');
      sourceCards.querySelectorAll('.source-preview-anchor').forEach((card, index) => {
        const item = items[index];
        card.addEventListener('pointerenter', () => scheduleSourcePreview(item, card));
        card.addEventListener('pointerleave', scheduleSourcePreviewClose);
        card.addEventListener('focusin', () => { if (!sourcePreviewPinned) showSourcePreview(item, card); });
        card.addEventListener('focusout', scheduleSourcePreviewClose);
        card.addEventListener('click', (event) => {
          if (event.target.closest('button, a')) return;
          showSourcePreview(item, card, {pin: true});
        });
      });
      sourceCards.querySelectorAll('[data-copy-source]').forEach((button) => {
        button.addEventListener('click', async () => {
          const sourceId = button.dataset.copySource;
          const source = lastHandoffSources.find((item) => sourceIdentity(item) === sourceId) || lastSources.find((item) => sourceIdentity(item) === sourceId) || {};
          await navigator.clipboard.writeText(JSON.stringify(source, null, 2));
          button.textContent = 'Copied';
          showToast('Source card copied.');
          setTimeout(() => { button.textContent = 'Copy card'; }, 1100);
        });
      });
      sourceCards.querySelectorAll('[data-inspect-source]').forEach((button) => {
        button.addEventListener('click', () => inspectSource(button.dataset.inspectSource, {pin: true, owner: button.closest('.source-card')}));
      });
      sourceCards.querySelectorAll('[data-draft-source-question]').forEach((button) => {
        button.addEventListener('click', () => {
          const item = lastSources.find((row) => sourceIdentity(row) === button.dataset.draftSourceQuestion);
          if (item) draftSourceQuestion(item);
        });
      });
      sourceCards.querySelectorAll('[data-inspect-source-record], [data-inspect-source-page]').forEach((button) => {
        button.addEventListener('click', () => {
          const sourceId = button.dataset.inspectSourceRecord || button.dataset.inspectSourcePage || '';
          const item = lastSources.find((row) => sourceIdentity(row) === sourceId);
          openRecordInspector(recordOpenBinding(item), Number(button.dataset.page || 0), button);
        });
      });
      sourceCards.querySelectorAll('[data-open-source-record]').forEach((button) => {
        button.addEventListener('click', () => {
          const item = lastSources.find((row) => sourceIdentity(row) === button.dataset.openSourceRecord);
          openRecordOriginal(recordOpenBinding(item), 0);
        });
      });
      applyRecordCardFilter();
    }

    async function inspectSource(sourceId, {pin = true, owner = null} = {}) {
      if (!sourceId) return;
      const local = lastSources.find((item) => sourceIdentity(item) === sourceId) || {};
      const binding = recordOpenBinding(local);
      if (binding) {
        await openRecordInspector(binding, Number(local?.metadata?.page_number || local?.page_number || 0), owner);
        return;
      }
      showSourcePreview(local, owner, {pin});
      try {
        const span = local?.metadata?.source_span || {};
        const spanQuery = Number.isInteger(span.start_offset) && Number.isInteger(span.end_offset)
          ? `?start_offset=${encodeURIComponent(span.start_offset)}&end_offset=${encodeURIComponent(span.end_offset)}`
          : '';
        const payload = await fetchJson(`/inspect-source/${encodeURIComponent(sourceId)}${spanQuery}`);
        if (!sourcePreviewFlyout?.hidden && sourceIdentity(local) === sourceId) {
          showSourcePreview(local, owner || sourcePreviewOwner, {pin: sourcePreviewPinned, payload});
        }
      } catch (err) {
        if (sourcePreviewBody && !sourcePreviewFlyout?.hidden) {
          sourcePreviewBody.insertAdjacentHTML('beforeend', `<p class="status-warn">Full local metadata was not available: ${escapeHtml(err.message)}</p>`);
        }
      }
    }

    function closeDocumentIntelligence() {
      if (!documentIntelligenceModal) return;
      documentIntelligenceModal.hidden = true;
      documentIntelligenceModal.setAttribute('aria-hidden', 'true');
      if (documentIntelligenceBackdrop) documentIntelligenceBackdrop.hidden = true;
      document.body.classList.remove('document-intelligence-open');
      const owner = documentIntelligenceOwner;
      documentIntelligenceOwner = null;
      owner?.focus?.();
    }

    function renderDocumentIntelligenceAdapters(payload) {
      documentIntelligenceRuntime = payload || {};
      const adapters = Array.isArray(payload?.adapters) ? payload.adapters : [];
      if (documentIntelligenceAdapters) {
        documentIntelligenceAdapters.innerHTML = adapters.map((item) => `<article class="document-intelligence-adapter"><div><strong>${escapeHtml(String(item.adapter_id || 'adapter').replaceAll('_', ' '))}</strong><span class="badge ${item.available ? 'good' : 'warn'}">${item.available ? 'Available' : 'Not installed'}</span></div><small>${escapeHtml(item.version || 'unknown')} · ${escapeHtml(item.license || 'license not reported')}</small><small>${escapeHtml(item.detail || '')}</small></article>`).join('') || '<span class="muted">No adapter status was returned.</span>';
      }
      const byId = Object.fromEntries(adapters.map((item) => [String(item.adapter_id || ''), item]));
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'The deterministic parser is ready. Optional adapters run only when installed and selected.';
      if (documentIntelligenceUseDocling) {
        documentIntelligenceUseDocling.disabled = !byId.docling?.available;
        if (!byId.docling?.available) documentIntelligenceUseDocling.checked = false;
      }
      if (documentIntelligenceUsePresidio) {
        documentIntelligenceUsePresidio.disabled = !byId.presidio?.available;
        if (!byId.presidio?.available) documentIntelligenceUsePresidio.checked = false;
      }
      const isPdf = String(recordInspectorState?.extension || '').toLowerCase() === '.pdf';
      if (documentIntelligenceOcr) documentIntelligenceOcr.disabled = documentIntelligenceBusy || !isPdf || !documentIntelligenceOcrApproved?.checked || !byId.ocrmypdf?.available;
    }

    function activeDocumentIntelligenceRecordId() {
      return String(documentIntelligenceRecordId || recordInspectorState?.evidence_id || '').trim();
    }

    function renderDocumentIntelligenceReport(payload) {
      lastDocumentIntelligenceReport = payload || null;
      const source = payload?.source || {};
      const integrity = payload?.integrity || {};
      const structured = payload?.structured_document || {};
      const privacy = payload?.privacy_review || {};
      const provenance = payload?.provenance || {};
      const comparison = structured?.comparison || payload?.comparison || {};
      const blocks = Array.isArray(structured.blocks) ? structured.blocks.slice(0, 120) : [];
      const findings = Array.isArray(privacy.findings) ? privacy.findings.slice(0, 120) : [];
      const parserHistory = Array.isArray(provenance.parser_history) ? provenance.parser_history : [];
      const derivedArtifacts = Array.isArray(provenance.derived_artifacts) ? provenance.derived_artifacts : [];
      const exactDuplicates = Array.isArray(payload?.duplicate_report?.exact_duplicates) ? payload.duplicate_report.exact_duplicates : [];
      const nearDuplicates = Array.isArray(payload?.duplicate_report?.near_duplicate_candidates) ? payload.duplicate_report.near_duplicate_candidates : [];
      const changedCopies = Array.isArray(payload?.duplicate_report?.changed_copy_candidates) ? payload.duplicate_report.changed_copy_candidates : [];
      const artifact = payload?.artifact || {};
      const recordId = activeDocumentIntelligenceRecordId();
      const analysisActionButtons = `
        <div class="row">
          <button class="secondary compact-action" data-di-action="refresh-parse" type="button">Refresh structure</button>
          <button class="secondary compact-action" data-di-action="privacy-scan" type="button">Privacy scan</button>
          <button class="secondary compact-action" data-di-action="redaction-proposal" type="button">Redaction proposal</button>
          <button class="secondary compact-action" data-di-action="redacted-copy" type="button">Create redacted copy</button>
          <button class="secondary compact-action" data-di-action="ocr-comparison" type="button">OCR comparison</button>
          <button class="secondary compact-action" data-di-action="duplicate-report" type="button">Duplicate report</button>
        </div>`;
      documentIntelligenceResults.innerHTML = `
        <section>
          <h3>Integrity</h3>
          <dl>
            <div><dt>File</dt><dd>${escapeHtml(source.filename || recordInspectorState?.filename || 'Record')}</dd></div>
            <div><dt>Record ID</dt><dd><code>${escapeHtml(recordId || integrity.record_id || 'n/a')}</code></dd></div>
            <div><dt>Source hash</dt><dd><code>${escapeHtml(String(source.sha256 || integrity.original_sha256 || '').slice(0, 24))}…</code></dd></div>
            <div><dt>Pages</dt><dd>${escapeHtml(integrity.page_count || structured.page_count || 0)}</dd></div>
            <div><dt>Parser</dt><dd>${escapeHtml(String(integrity.parser_status || 'unknown').replaceAll('_', ' '))}</dd></div>
            <div><dt>OCR</dt><dd>${escapeHtml(String(integrity.ocr_status || 'not run').replaceAll('_', ' '))}</dd></div>
            <div><dt>Duplicate group</dt><dd><code>${escapeHtml(String(integrity.duplicate_group_id || payload?.duplicate_report?.duplicate_group_id || '').slice(0, 20))}…</code></dd></div>
            <div><dt>Privacy flags</dt><dd>${escapeHtml((integrity.confidentiality_labels || []).join(', ') || 'none detected')}</dd></div>
          </dl>
          <p class="record-inspector-note">Immutable original: ${integrity.immutable_original ? 'yes' : 'no'} · text status: ${escapeHtml(String(integrity.text_availability_status || 'unknown').replaceAll('_', ' '))} · retention: ${escapeHtml(String(integrity.retention_status || 'unknown').replaceAll('_', ' '))}</p>
          ${analysisActionButtons}
        </section>
        <section>
          <h3>Structure</h3>
          <p>${escapeHtml(structured.block_count || 0)} total blocks; showing up to ${blocks.length}.</p>
          <p class="record-inspector-note">Selection reason: ${escapeHtml(structured.selection_reason || payload.selection_reason || 'deterministic baseline')}</p>
          <div class="document-intelligence-blocks">${blocks.map((block) => `<article class="document-intelligence-block" tabindex="0"><div class="row"><small>${escapeHtml(String(block.kind || 'text').replaceAll('_', ' '))}${Number(block.page_number || 0) ? ` · page ${escapeHtml(block.page_number)}` : ''} · ${escapeHtml(block.block_id || '')}</small><button class="secondary compact-action" data-di-open-page="${escapeHtml(block.page_number || 0)}" type="button">Open page</button></div><div>${escapeHtml(block.text || '')}</div><button class="secondary compact-action" data-di-copy-span="${escapeHtml(block.block_id || '')}" data-di-span-text="${escapeHtml(block.text || '')}" type="button">Copy span</button></article>`).join('') || '<span class="muted">No readable blocks were returned.</span>'}</div>
        </section>
        <section>
          <h3>OCR</h3>
          <dl>
            <div><dt>Source page count</dt><dd>${escapeHtml(payload.source_page_count || integrity.page_count || 0)}</dd></div>
            <div><dt>Output page count</dt><dd>${escapeHtml(payload.output_page_count || 0)}</dd></div>
            <div><dt>Similarity</dt><dd>${escapeHtml(Number(comparison.similarity || 0).toFixed ? Number(comparison.similarity || 0).toFixed(3) : comparison.similarity || 0)}</dd></div>
            <div><dt>Warnings</dt><dd>${escapeHtml((comparison.warnings || []).join(', ') || 'none')}</dd></div>
          </dl>
          <p>${escapeHtml((comparison.added_line_count || 0))} added lines · ${escapeHtml((comparison.removed_line_count || 0))} removed lines</p>
          <p class="record-inspector-note">Use the OCR action to create a separate searchable copy. The original never changes in place.</p>
        </section>
        <section>
          <h3>Privacy</h3>
          <p>${escapeHtml(privacy.warning || 'Automated privacy review requires human confirmation.')}</p>
          <div class="document-intelligence-finding-list">${findings.map((item) => `<div class="document-intelligence-finding"><strong>${escapeHtml(String(item.entity_type || 'finding').replaceAll('_', ' '))}</strong><span>Characters ${escapeHtml(item.start)}–${escapeHtml(item.end)} · ${escapeHtml(item.recognizer || 'detector')} · text hash ${escapeHtml(String(item.text_sha256 || '').slice(0, 12) || 'not retained')}</span></div>`).join('') || '<span class="muted">No automated privacy findings were returned. This does not prove that the record contains no sensitive information.</span>'}</div>
          <div class="row">
            <button class="secondary compact-action" data-di-action="privacy-scan" type="button">Re-run privacy scan</button>
            <button class="secondary compact-action" data-di-action="redaction-proposal" type="button">Show proposal</button>
            <button class="secondary compact-action" data-di-action="redacted-copy" type="button">Create redacted copy</button>
          </div>
        </section>
        <section>
          <h3>Versions</h3>
          <p>Exact duplicates: ${escapeHtml(exactDuplicates.length)} · near-duplicate candidates: ${escapeHtml(nearDuplicates.length)} · changed copies: ${escapeHtml(changedCopies.length)}</p>
          <div class="document-intelligence-blocks">${exactDuplicates.map((item) => `<article class="document-intelligence-block"><div class="row"><small><strong>${escapeHtml(item.record_id || 'record')}</strong> · exact duplicate</small>${item.record_id && item.record_id !== recordId ? `<button class="secondary compact-action" data-di-action="compare" data-di-compare-record="${escapeHtml(item.record_id)}" type="button">Compare</button>` : ''}</div><div>Hash ${escapeHtml(String(item.source_hash || '').slice(0, 20))}… · pages ${escapeHtml(item.page_count || 0)}</div></article>`).join('') || '<span class="muted">No exact duplicate group was found.</span>'}
          ${nearDuplicates.length ? `<details><summary>Near-duplicate candidates</summary><div class="document-intelligence-blocks">${nearDuplicates.map((item) => `<article class="document-intelligence-block"><small>${escapeHtml(item.record_id || 'record')} · similarity ${escapeHtml(Number(item.similarity || 0).toFixed(3))}</small><div>Pages ${escapeHtml(item.page_count || 0)} · parser ${escapeHtml(item.parser_status || 'unknown')} · OCR ${escapeHtml(item.ocr_status || 'unknown')}</div></article>`).join('')}</div></details>` : ''}
          ${changedCopies.length ? `<details><summary>Changed-copy candidates</summary><div class="document-intelligence-blocks">${changedCopies.map((item) => `<article class="document-intelligence-block"><small>${escapeHtml(item.record_id || 'record')}</small><div>Hash ${escapeHtml(String(item.source_hash || '').slice(0, 20))}… · pages ${escapeHtml(item.page_count || 0)}</div></article>`).join('')}</div></details>` : ''}
        </section>
        <section>
          <h3>Provenance</h3>
          <dl>
            <div><dt>Receipt</dt><dd><code>${escapeHtml(String(payload.receipt_sha256 || '').slice(0, 24))}…</code></dd></div>
            <div><dt>Artifact</dt><dd>${escapeHtml(String(artifact.artifact_type || 'analysis report').replaceAll('_', ' '))}</dd></div>
            <div><dt>Derived artifacts</dt><dd>${escapeHtml(derivedArtifacts.length)}</dd></div>
            <div><dt>Parser history</dt><dd>${escapeHtml(parserHistory.length)}</dd></div>
          </dl>
          <details>
            <summary>Parser history</summary>
            <div class="document-intelligence-blocks">${parserHistory.map((item) => `<article class="document-intelligence-block"><small>${escapeHtml(item.component_id || 'component')} · ${escapeHtml(item.component_version || 'unknown')}</small><div>Status: ${escapeHtml(item.status || 'unknown')} · warnings: ${escapeHtml((item.warnings || []).join(', ') || 'none')}</div></article>`).join('')}</div>
          </details>
          <details>
            <summary>Derived artifacts</summary>
            <div class="document-intelligence-blocks">${derivedArtifacts.map((item) => `<article class="document-intelligence-block"><small>${escapeHtml(item.artifact_type || 'artifact')}</small><div><code>${escapeHtml(String(item.output_sha256 || '').slice(0, 20))}…</code> · receipt <code>${escapeHtml(String(item.receipt_sha256 || '').slice(0, 20))}…</code></div></article>`).join('') || '<span class="muted">No derived artifacts were recorded yet.</span>'}</div>
          </details>
          <p>${artifact.download_url ? `<a class="secondary compact-action" href="${escapeHtml(artifact.download_url)}">Download analysis JSON</a>` : ''}${artifact.receipt_url ? ` <a class="secondary compact-action" href="${escapeHtml(artifact.receipt_url)}">Open receipt</a>` : ''}</p>
          <p class="record-inspector-note">Original modified: ${source.original_modified ? 'yes' : 'no'} · local only · human review required</p>
        </section>`;
      if (documentIntelligenceResults) {
        documentIntelligenceResults.querySelectorAll('[data-di-open-page]').forEach((button) => {
        button.addEventListener('click', () => openRecordInspector(recordInspectorState, Number(button.dataset.diOpenPage || 0), button));
      });
        documentIntelligenceResults.querySelectorAll('[data-di-copy-span]').forEach((button) => {
          button.addEventListener('click', async () => {
            await navigator.clipboard.writeText(String(button.dataset.diSpanText || ''));
            button.textContent = 'Copied';
            setTimeout(() => { button.textContent = 'Copy span'; }, 1100);
          });
        });
        documentIntelligenceResults.querySelectorAll('[data-di-action]').forEach((button) => {
          button.addEventListener('click', async () => {
            const action = String(button.dataset.diAction || '');
            if (action === 'refresh-parse') {
              await runDocumentIntelligence();
              return;
            }
            if (action === 'privacy-scan') {
              await runDocumentIntelligencePrivacyScan();
              return;
            }
            if (action === 'redaction-proposal') {
              await runDocumentIntelligenceRedactionProposal();
              return;
            }
            if (action === 'redacted-copy') {
              await runDocumentIntelligenceRedactedCopy();
              return;
            }
            if (action === 'ocr-comparison') {
              await runDocumentIntelligenceOcrComparison();
              return;
            }
            if (action === 'duplicate-report') {
              await runDocumentIntelligenceDuplicateReport();
              return;
            }
            if (action === 'compare') {
              const peer = String(button.dataset.diCompareRecord || '');
              if (peer) await runDocumentComparison(peer);
            }
          });
        });
      }
    }

    async function openDocumentIntelligence(owner = null) {
      if (!recordInspectorState?.token || !documentIntelligenceModal) {
        showToast('Open a verified private record first.');
        return;
      }
      documentIntelligenceRecordId = String(recordInspectorState?.evidence_id || '');
      lastDocumentIntelligenceReport = null;
      documentIntelligenceOwner = owner || document.activeElement;
      documentIntelligenceModal.hidden = false;
      documentIntelligenceModal.setAttribute('aria-hidden', 'false');
      if (documentIntelligenceBackdrop) documentIntelligenceBackdrop.hidden = false;
      document.body.classList.add('document-intelligence-open');
      if (documentIntelligenceResults) documentIntelligenceResults.textContent = 'Choose the approved local checks, then analyze this record.';
      if (documentIntelligenceApproved) documentIntelligenceApproved.checked = false;
      if (documentIntelligenceOcrApproved) documentIntelligenceOcrApproved.checked = false;
      if (documentIntelligenceAnalyze) documentIntelligenceAnalyze.disabled = true;
      if (documentIntelligenceOcr) documentIntelligenceOcr.disabled = true;
      try {
        const payload = await fetchJson('/api/document-intelligence/status');
        renderDocumentIntelligenceAdapters(payload);
      } catch (err) {
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = `Document-intelligence status failed: ${err.message}`;
      }
      documentIntelligenceClose?.focus();
    }

    function updateDocumentIntelligenceButtons() {
      if (documentIntelligenceAnalyze) documentIntelligenceAnalyze.disabled = documentIntelligenceBusy || !documentIntelligenceApproved?.checked || !activeDocumentIntelligenceRecordId();
      const adapters = Array.isArray(documentIntelligenceRuntime?.adapters) ? documentIntelligenceRuntime.adapters : [];
      const ocrAvailable = adapters.some((item) => item.adapter_id === 'ocrmypdf' && item.available);
      const isPdf = String(recordInspectorState?.extension || '').toLowerCase() === '.pdf';
      if (documentIntelligenceOcr) documentIntelligenceOcr.disabled = documentIntelligenceBusy || !documentIntelligenceOcrApproved?.checked || !ocrAvailable || !isPdf;
    }

    async function runDocumentIntelligence() {
      const recordId = activeDocumentIntelligenceRecordId();
      if (!recordId || !documentIntelligenceApproved?.checked || documentIntelligenceBusy) return;
      documentIntelligenceBusy = true;
      updateDocumentIntelligenceButtons();
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Analyzing the verified local copy…';
      try {
        const payload = await fetchJson(`/api/records/${encodeURIComponent(recordId)}/parse`, {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source_token: recordInspectorState.token, approved: true, run_docling: Boolean(documentIntelligenceUseDocling?.checked), run_presidio: Boolean(documentIntelligenceUsePresidio?.checked)}),
        });
        renderDocumentIntelligenceReport(payload);
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Analysis complete. Review every structure and privacy finding before use.';
      } catch (err) {
        if (documentIntelligenceResults) documentIntelligenceResults.innerHTML = `<section><h3>Analysis blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'The local analysis did not complete.';
      } finally {
        documentIntelligenceBusy = false;
        updateDocumentIntelligenceButtons();
      }
    }

    async function runDocumentIntelligenceOcr() {
      const recordId = activeDocumentIntelligenceRecordId();
      if (!recordId || !documentIntelligenceOcrApproved?.checked || documentIntelligenceBusy) return;
      documentIntelligenceBusy = true;
      updateDocumentIntelligenceButtons();
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Creating a separate searchable preservation copy…';
      try {
        const payload = await fetchJson(`/api/records/${encodeURIComponent(recordId)}/ocr`, {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source_token: recordInspectorState.token, approved: true, language: String(documentIntelligenceOcrLanguage?.value || 'eng')}),
        });
        const pdf = payload?.artifacts?.pdf || {};
        const sidecar = payload?.artifacts?.sidecar || {};
        if (payload.status !== 'pass') {
          documentIntelligenceResults.innerHTML = `<section><h3>Searchable copy blocked</h3><p>${escapeHtml((payload.blockers || []).join(', ') || 'OCRmyPDF did not complete.')}</p><p>The original was not modified.</p></section>`;
        } else {
          documentIntelligenceResults.innerHTML = `<section><h3>Searchable preservation copy created</h3><dl><div><dt>Source hash</dt><dd><code>${escapeHtml(String(payload.source_sha256 || '').slice(0, 24))}…</code></dd></div><div><dt>Output hash</dt><dd><code>${escapeHtml(String(payload.output_sha256 || '').slice(0, 24))}…</code></dd></div><div><dt>Engine</dt><dd>OCRmyPDF ${escapeHtml(payload.engine_version || '')}</dd></div><div><dt>Original modified</dt><dd>${payload.original_modified ? 'Yes' : 'No'}</dd></div></dl><p>${pdf.download_url ? `<a class="primary-action compact-action" href="${escapeHtml(pdf.download_url)}">Download searchable PDF</a>` : ''}${sidecar?.download_url ? ` <a class="secondary compact-action" href="${escapeHtml(sidecar.download_url)}">Download OCR text</a>` : ''}</p><p class="record-inspector-note">OCR text may contain errors. Compare it with the verified original.</p></section>`;
        }
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = payload.status === 'pass' ? 'Searchable copy ready for review.' : 'Searchable copy was not created.';
      } catch (err) {
        if (documentIntelligenceResults) documentIntelligenceResults.innerHTML = `<section><h3>Searchable copy blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      } finally {
        documentIntelligenceBusy = false;
        updateDocumentIntelligenceButtons();
      }
    }

    async function runDocumentIntelligencePrivacyScan() {
      const recordId = activeDocumentIntelligenceRecordId();
      if (!recordId || documentIntelligenceBusy) return;
      documentIntelligenceBusy = true;
      updateDocumentIntelligenceButtons();
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Scanning privacy candidates…';
      try {
        const payload = await fetchJson(`/api/records/${encodeURIComponent(recordId)}/privacy-scan`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source_token: recordInspectorState.token, approved: true, run_presidio: Boolean(documentIntelligenceUsePresidio?.checked)}),
        });
        renderDocumentIntelligenceReport({...(lastDocumentIntelligenceReport || {}), ...payload});
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Privacy scan complete.';
      } catch (err) {
        if (documentIntelligenceResults) documentIntelligenceResults.innerHTML = `<section><h3>Privacy scan blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      } finally {
        documentIntelligenceBusy = false;
        updateDocumentIntelligenceButtons();
      }
    }

    async function runDocumentIntelligenceRedactionProposal() {
      const recordId = activeDocumentIntelligenceRecordId();
      if (!recordId || documentIntelligenceBusy) return;
      documentIntelligenceBusy = true;
      updateDocumentIntelligenceButtons();
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Preparing a review-only redaction proposal…';
      try {
        const payload = await fetchJson(`/api/records/${encodeURIComponent(recordId)}/redaction-proposal`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source_token: recordInspectorState.token, approved: true, reviewer: 'local_operator', run_presidio: Boolean(documentIntelligenceUsePresidio?.checked)}),
        });
        renderDocumentIntelligenceReport({...(lastDocumentIntelligenceReport || {}), ...payload});
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Redaction proposal ready for review.';
      } catch (err) {
        if (documentIntelligenceResults) documentIntelligenceResults.innerHTML = `<section><h3>Redaction proposal blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      } finally {
        documentIntelligenceBusy = false;
        updateDocumentIntelligenceButtons();
      }
    }

    async function runDocumentIntelligenceRedactedCopy() {
      const recordId = activeDocumentIntelligenceRecordId();
      if (!recordId || documentIntelligenceBusy) return;
      documentIntelligenceBusy = true;
      updateDocumentIntelligenceButtons();
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Creating a separate redacted derivative…';
      try {
        const payload = await fetchJson(`/api/records/${encodeURIComponent(recordId)}/redacted-copy`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({source_token: recordInspectorState.token, approved: true, reviewer: 'local_operator', run_presidio: Boolean(documentIntelligenceUsePresidio?.checked)}),
        });
        renderDocumentIntelligenceReport({...(lastDocumentIntelligenceReport || {}), ...payload});
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Redacted copy created.';
      } catch (err) {
        if (documentIntelligenceResults) documentIntelligenceResults.innerHTML = `<section><h3>Redacted copy blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      } finally {
        documentIntelligenceBusy = false;
        updateDocumentIntelligenceButtons();
      }
    }

    async function runDocumentIntelligenceOcrComparison() {
      const recordId = activeDocumentIntelligenceRecordId();
      if (!recordId || documentIntelligenceBusy) return;
      documentIntelligenceBusy = true;
      updateDocumentIntelligenceButtons();
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Checking OCR comparison…';
      try {
        const payload = await fetchJson(`/api/records/${encodeURIComponent(recordId)}/ocr-comparison`);
        renderDocumentIntelligenceReport({...(lastDocumentIntelligenceReport || {}), ...payload});
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = payload.status === 'pass' ? 'OCR comparison loaded.' : 'OCR comparison unavailable.';
      } catch (err) {
        if (documentIntelligenceResults) documentIntelligenceResults.innerHTML = `<section><h3>OCR comparison blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      } finally {
        documentIntelligenceBusy = false;
        updateDocumentIntelligenceButtons();
      }
    }

    async function runDocumentIntelligenceDuplicateReport() {
      const recordId = activeDocumentIntelligenceRecordId();
      if (!recordId || documentIntelligenceBusy) return;
      documentIntelligenceBusy = true;
      updateDocumentIntelligenceButtons();
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Loading duplicate relationships…';
      try {
        const payload = await fetchJson(`/api/records/${encodeURIComponent(recordId)}/duplicates`);
        renderDocumentIntelligenceReport({...(lastDocumentIntelligenceReport || {}), duplicate_report: payload});
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Duplicate report loaded.';
      } catch (err) {
        if (documentIntelligenceResults) documentIntelligenceResults.innerHTML = `<section><h3>Duplicate report blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      } finally {
        documentIntelligenceBusy = false;
        updateDocumentIntelligenceButtons();
      }
    }

    async function runDocumentComparison(otherRecordId) {
      const recordId = activeDocumentIntelligenceRecordId();
      if (!recordId || !otherRecordId || documentIntelligenceBusy) return;
      documentIntelligenceBusy = true;
      updateDocumentIntelligenceButtons();
      if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Comparing copies…';
      try {
        const payload = await fetchJson('/api/records/compare', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({left_record_id: recordId, right_record_id: otherRecordId}),
        });
        documentIntelligenceResults.insertAdjacentHTML('afterbegin', `<section><h3>Changed-copy comparison</h3><dl><div><dt>Same</dt><dd>${payload.same ? 'Yes' : 'No'}</dd></div><div><dt>Similarity</dt><dd>${escapeHtml(Number(payload.similarity || 0).toFixed(3))}</dd></div><div><dt>Page delta</dt><dd>${escapeHtml(payload.page_count_delta || 0)}</dd></div></dl><p><strong>Field differences:</strong> ${escapeHtml(Object.keys(payload.field_differences || {}).join(', ') || 'none')}</p></section>`);
        if (documentIntelligenceStatus) documentIntelligenceStatus.textContent = 'Comparison loaded.';
      } catch (err) {
        if (documentIntelligenceResults) documentIntelligenceResults.innerHTML = `<section><h3>Comparison blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      } finally {
        documentIntelligenceBusy = false;
        updateDocumentIntelligenceButtons();
      }
    }


    function closeRetrievalWorkbench() {
      if (!retrievalWorkbenchModal || retrievalWorkbenchModal.hidden) return;
      retrievalWorkbenchModal.hidden = true;
      retrievalWorkbenchModal.setAttribute('aria-hidden', 'true');
      if (retrievalWorkbenchBackdrop) retrievalWorkbenchBackdrop.hidden = true;
      document.body.classList.remove('retrieval-workbench-open');
      const owner = retrievalWorkbenchOwner;
      retrievalWorkbenchOwner = null;
      if (owner && typeof owner.focus === 'function') owner.focus({preventScroll: true});
    }

    function renderRetrievalBackendStatus(payload) {
      const rows = payload?.backends?.backends || [];
      if (retrievalWorkbenchBackends) {
        retrievalWorkbenchBackends.innerHTML = rows.map((row) => `<article><div><strong>${escapeHtml(String(row.backend_id || '').replaceAll('_', ' '))}</strong><span class="badge ${row.enabled ? 'good' : row.available ? 'warn' : ''}">${row.enabled ? 'active' : row.available ? 'available' : 'not installed'}</span></div><small>${escapeHtml(row.mode || '')}${row.version ? ` · ${escapeHtml(row.version)}` : ''}</small><p>${escapeHtml(row.details || '')}</p></article>`).join('') || '<p class="muted">No optional backend status was returned.</p>';
      }
      if (retrievalWorkbenchStatus) {
        retrievalWorkbenchStatus.textContent = `Embedded search ready · ${payload?.private_record_count || 0} private records · authority ${payload?.authority_index_configured ? 'configured' : 'not configured'} · attorney gold ${payload?.attorney_gold_dataset_configured ? 'configured' : 'not configured'}`;
      }
    }

    function renderRetrievalResults(payload) {
      if (!retrievalWorkbenchResults) return;
      const results = Array.isArray(payload?.results) ? payload.results : [];
      const diagnostics = payload?.diagnostics || {};
      const cards = results.map((row) => {
        const card = row.source_card || {};
        const why = row.why_this_matched || {};
        const scores = Object.entries(why.component_scores || {}).map(([key,value]) => `${escapeHtml(key)} ${escapeHtml(Number(value).toFixed(4))}`).join(' · ');
        return `<article class="retrieval-result-card"><div><strong>${escapeHtml(card.title || row.source_id || 'Source')}</strong><span class="badge ${why.source_lane === 'legal_authority' ? 'good' : 'warn'}">${escapeHtml(String(why.source_lane || 'source').replaceAll('_', ' '))}</span></div><p>${escapeHtml(why.summary || row.explanation || '')}</p><small>Rank ${escapeHtml(row.rank || '')} · score ${escapeHtml(Number(row.score || 0).toFixed(4))}${card.citation ? ` · ${escapeHtml(card.citation)}` : ''}</small>${(why.matched_terms || []).length ? `<p><strong>Matched:</strong> ${escapeHtml(why.matched_terms.join(', '))}</p>` : ''}${scores ? `<code>${scores}</code>` : ''}</article>`;
      }).join('') || `<section><h3>No ranked result</h3><p>${escapeHtml((payload?.blockers || []).join(', ') || 'No indexed source matched the query.')}</p></section>`;
      retrievalWorkbenchResults.innerHTML = `<section class="retrieval-summary"><div><span class="badge ${payload.status === 'pass' ? 'good' : 'warn'}">${escapeHtml(String(payload.status || 'review required').replaceAll('_', ' '))}</span><span class="badge warn">Review required</span></div><p>${escapeHtml(payload.what_this_does_not_prove || 'Retrieval rank is not a legal or factual finding.')}</p><small>${escapeHtml(diagnostics.lexical_backend || 'local')} + ${escapeHtml(diagnostics.semantic_backend || 'fallback')} · ${escapeHtml(diagnostics.document_count || 0)} documents · network used: ${diagnostics.network_used ? 'yes' : 'no'}</small></section><div class="retrieval-result-list">${cards}</div>`;
    }

    function renderRetrievalEvaluation(payload) {
      if (!retrievalWorkbenchResults) return;
      const metrics = payload?.metrics || {};
      const failures = Array.isArray(payload?.failures) ? payload.failures : [];
      const clusters = payload?.failure_triage?.clusters || {};
      retrievalWorkbenchResults.innerHTML = `<section class="retrieval-summary"><div><span class="badge ${payload.status === 'pass' ? 'good' : 'warn'}">${escapeHtml(String(payload.status || 'blocked'))}</span><span class="badge warn">Attorney gold only</span></div><div class="evidence-work-product-metrics"><strong>Recall@20 ${escapeHtml(metrics.recall_at_20 ?? 0)}</strong><strong>MRR ${escapeHtml(metrics.mrr ?? 0)}</strong><strong>nDCG@20 ${escapeHtml(metrics.ndcg_at_20 ?? 0)}</strong><strong>${escapeHtml(payload.evaluated_rows || 0)} evaluated rows</strong></div><p>${escapeHtml(payload.basis || '')}</p><p><strong>Dataset:</strong> <code>${escapeHtml(String(payload.dataset_sha256 || '').slice(0, 24))}…</code></p>${(payload.blockers || []).length ? `<p class="status-warn">${escapeHtml(payload.blockers.join(', '))}</p>` : ''}</section><details open><summary>Failure clusters</summary><ul>${Object.entries(clusters).map(([key,value]) => `<li>${escapeHtml(String(key).replaceAll('_', ' '))}: ${escapeHtml(value)}</li>`).join('') || '<li>No failures.</li>'}</ul></details><details><summary>Misses (${escapeHtml(failures.length)})</summary><div class="retrieval-result-list">${failures.slice(0, 100).map((row) => `<article class="retrieval-result-card"><strong>${escapeHtml(row.query || '')}</strong><p>Expected: ${escapeHtml((row.expected_source_ids || []).join(', '))}</p><small>Retrieved: ${escapeHtml((row.retrieved_source_ids || []).join(', '))}</small></article>`).join('') || '<p>No misses.</p>'}</div></details>`;
    }

    async function openRetrievalWorkbench(owner) {
      if (!retrievalWorkbenchModal) return;
      retrievalWorkbenchOwner = owner || document.activeElement;
      retrievalWorkbenchModal.hidden = false;
      retrievalWorkbenchModal.setAttribute('aria-hidden', 'false');
      if (retrievalWorkbenchBackdrop) retrievalWorkbenchBackdrop.hidden = false;
      document.body.classList.add('retrieval-workbench-open');
      if (retrievalWorkbenchQuery && !retrievalWorkbenchQuery.value && question?.value) retrievalWorkbenchQuery.value = question.value;
      try {
        const payload = await fetchJson('/api/retrieval-workbench/status');
        renderRetrievalBackendStatus(payload);
      } catch (err) {
        if (retrievalWorkbenchStatus) retrievalWorkbenchStatus.textContent = err.message;
      }
      retrievalWorkbenchClose?.focus({preventScroll: true});
    }

    async function runRetrievalWorkbenchSearch() {
      if (retrievalWorkbenchBusy) return;
      const queryText = String(retrievalWorkbenchQuery?.value || '').trim();
      if (!queryText) { retrievalWorkbenchQuery?.focus(); return; }
      retrievalWorkbenchBusy = true;
      if (retrievalWorkbenchSearch) retrievalWorkbenchSearch.disabled = true;
      if (retrievalWorkbenchResults) retrievalWorkbenchResults.textContent = 'Running bounded local hybrid retrieval…';
      try {
        const payload = await fetchJson('/api/retrieval-workbench/search', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:queryText, include_private_records:Boolean(retrievalWorkbenchPrivate?.checked), include_authority:Boolean(retrievalWorkbenchAuthority?.checked), top_k:Number(retrievalWorkbenchLimit?.value || 10)})});
        renderRetrievalResults(payload);
      } catch (err) {
        if (retrievalWorkbenchResults) retrievalWorkbenchResults.innerHTML = `<section><h3>Retrieval blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      } finally {
        retrievalWorkbenchBusy = false;
        if (retrievalWorkbenchSearch) retrievalWorkbenchSearch.disabled = false;
      }
    }

    async function runRetrievalWorkbenchEvaluation() {
      if (retrievalWorkbenchBusy) return;
      retrievalWorkbenchBusy = true;
      if (retrievalWorkbenchEvaluate) retrievalWorkbenchEvaluate.disabled = true;
      if (retrievalWorkbenchResults) retrievalWorkbenchResults.textContent = 'Running configured attorney-reviewed retrieval evaluation…';
      try {
        const payload = await fetchJson('/api/retrieval-workbench/evaluate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({min_attorney_rows:Number(retrievalWorkbenchEvalMin?.value || 1), top_k:20})});
        renderRetrievalEvaluation(payload);
      } catch (err) {
        if (retrievalWorkbenchResults) retrievalWorkbenchResults.innerHTML = `<section><h3>Evaluation blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p><p>Configure an external verified authority index and attorney-reviewed JSONL eval root.</p></section>`;
      } finally {
        retrievalWorkbenchBusy = false;
        if (retrievalWorkbenchEvaluate) retrievalWorkbenchEvaluate.disabled = false;
      }
    }


    function closeReleasePilotHardening() {
      if (!releasePilotHardeningModal || releasePilotHardeningModal.hidden) return;
      releasePilotHardeningModal.hidden = true;
      releasePilotHardeningModal.setAttribute('aria-hidden', 'true');
      if (releasePilotHardeningBackdrop) releasePilotHardeningBackdrop.hidden = true;
      document.body.classList.remove('release-pilot-hardening-open');
      const owner = releasePilotHardeningOwner;
      releasePilotHardeningOwner = null;
      if (owner && typeof owner.focus === 'function') owner.focus({preventScroll: true});
    }

    function releaseStatusCard(title, payload) {
      const data = payload || {};
      const blockers = Array.isArray(data.blockers) ? data.blockers : [];
      const status = String(data.status || 'blocked');
      return `<section><div class="release-hardening-heading"><strong>${escapeHtml(title)}</strong><span class="badge ${status === 'pass' || status === 'ready' || status === 'operational' ? 'good' : 'warn'}">${escapeHtml(status.replaceAll('_', ' '))}</span></div>${blockers.length ? `<ul>${blockers.slice(0, 50).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : '<p>No blocker reported by this control.</p>'}</section>`;
    }

    function renderReleasePilotHardening(payload) {
      if (!releasePilotHardeningResults) return;
      const supply = payload?.supply_chain_and_msix || payload;
      const observability = payload?.observability || {};
      const backup = payload?.backup_restore || {};
      const pilot = payload?.attorney_sandbox || {};
      const operations = payload?.attorney_sandbox_operations || {};
      const realMatterPilot = payload?.limited_real_matter_pilot || {};
      const gaCandidate = payload?.ga_release_candidate || {};
      const gaShipment = payload?.ga_shipment_readiness || {};
      const files = Array.isArray(supply?.files) ? supply.files : [];
      const fileRows = files.map((row) => `<article><div><strong>${escapeHtml(row.filename || '')}</strong><span class="badge ${row.status === 'pass' ? 'good' : 'warn'}">${escapeHtml(row.status || 'missing')}</span></div><small>${row.present ? `${escapeHtml(row.size_bytes || 0)} bytes · ${escapeHtml(String(row.sha256 || '').slice(0, 18))}${row.sha256 ? '…' : ''}` : 'Not present'}</small>${(row.blockers || []).length ? `<p>${escapeHtml(row.blockers.join(', '))}</p>` : ''}</article>`).join('');
      releasePilotHardeningResults.innerHTML = `<section class="release-hardening-summary"><div><span class="badge ${payload?.status === 'pass' ? 'good' : 'warn'}">${escapeHtml(String(payload?.status || supply?.status || 'blocked').replaceAll('_', ' '))}</span><span class="badge warn">Legal GA remains blocked</span></div><p>Store qualification and attorney-pilot status are based only on external evidence actually present. This workbench does not manufacture certification.</p></section>${releaseStatusCard('Supply chain and signed MSIX', supply)}${fileRows ? `<section><h3>Required external evidence</h3><div class="release-hardening-file-list">${fileRows}</div></section>` : ''}${releaseStatusCard('Privacy-safe observability', observability)}${releaseStatusCard('Backup and restore', backup)}${releaseStatusCard('Attorney sandbox', pilot)}${releaseStatusCard('Pass 48 attorney operations', operations)}${releaseStatusCard('Pass 49 limited real-matter pilot', realMatterPilot)}${releaseStatusCard('Pass 50 GA release candidate', gaCandidate)}${releaseStatusCard('Pass 51 GA shipment readiness', gaShipment)}<section><h3>Pilot boundary</h3><p>Eligible sandbox participants may use synthetic or public-authority data only. Application records do not independently establish licensing and do not count as GA pilot evidence without external audit.</p><dl><div><dt>Eligible participants</dt><dd>${escapeHtml(pilot.eligible_participant_count || 0)}</dd></div><div><dt>Sessions</dt><dd>${escapeHtml(pilot.session_count || 0)}</dd></div><div><dt>Feedback</dt><dd>${escapeHtml(pilot.feedback_count || 0)}</dd></div></dl></section>`;
      if (releasePilotHardeningStatus) releasePilotHardeningStatus.textContent = `Release evidence ${supply?.status || 'blocked'} · backup ${backup?.status || 'blocked'} · sandbox ${pilot?.status || 'blocked'} · Pass 48 ${operations?.status || 'blocked'} · Pass 49 ${realMatterPilot?.status || 'blocked'} · Pass 50 ${gaCandidate?.status || 'blocked'} · Pass 51 ${gaShipment?.status || 'blocked'}`;
    }

    async function loadReleasePilotHardeningStatus() {
      const [payload, operations, realMatterPilot, gaCandidate, gaShipment] = await Promise.all([
        fetchJson('/api/release-pilot-hardening/status'),
        fetchJson('/api/attorney-sandbox-operations/status'),
        fetchJson('/api/limited-real-matter-pilot/status'),
        fetchJson('/api/ga-release-candidate/status'),
        fetchJson('/api/ga-shipment-readiness/status'),
      ]);
      payload.attorney_sandbox_operations = operations;
      payload.limited_real_matter_pilot = realMatterPilot;
      payload.ga_release_candidate = gaCandidate;
      payload.ga_shipment_readiness = gaShipment;
      renderReleasePilotHardening(payload);
      return payload;
    }

    async function openReleasePilotHardening(owner) {
      if (!releasePilotHardeningModal) return;
      releasePilotHardeningOwner = owner || document.activeElement;
      releasePilotHardeningModal.hidden = false;
      releasePilotHardeningModal.setAttribute('aria-hidden', 'false');
      if (releasePilotHardeningBackdrop) releasePilotHardeningBackdrop.hidden = false;
      document.body.classList.add('release-pilot-hardening-open');
      try { await loadReleasePilotHardeningStatus(); }
      catch (err) {
        if (releasePilotHardeningStatus) releasePilotHardeningStatus.textContent = err.message;
        if (releasePilotHardeningResults) releasePilotHardeningResults.innerHTML = `<section><h3>Status blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
      }
      releasePilotHardeningClose?.focus({preventScroll: true});
    }

    async function runReleasePilotAction(endpoint, body, progress) {
      if (releasePilotHardeningBusy) return null;
      releasePilotHardeningBusy = true;
      if (releasePilotHardeningStatus) releasePilotHardeningStatus.textContent = progress;
      try {
        const payload = await fetchJson(endpoint, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body || {})});
        if (releasePilotHardeningResults) releasePilotHardeningResults.innerHTML = `<section><h3>Operation result</h3><pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre></section>`;
        await loadReleasePilotHardeningStatus();
        return payload;
      } catch (err) {
        if (releasePilotHardeningResults) releasePilotHardeningResults.innerHTML = `<section><h3>Operation blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
        return null;
      } finally {
        releasePilotHardeningBusy = false;
      }
    }

    async function registerReleasePilotParticipant() {
      const trainingModules = releasePilotTraining?.checked ? ['data_boundaries','source_grounding','citation_quote_verification','review_required_exports','feedback_and_error_reporting'] : [];
      const payload = await runReleasePilotAction('/api/release-pilot-hardening/pilot/participants', {
        participant_id:String(releasePilotParticipantId?.value || '').trim(),
        role:String(releasePilotRole?.value || 'attorney_reviewer').trim(),
        bar_status_verified:Boolean(releasePilotBarVerified?.checked),
        verification_reference_sha256:String(releasePilotVerificationHash?.value || '').trim(),
        terms_accepted:Boolean(releasePilotTerms?.checked),
        training_modules:trainingModules,
      }, 'Recording append-only participant eligibility…');
      if (payload?.participant_id) {
        if (releasePilotSessionParticipant) releasePilotSessionParticipant.value = payload.participant_id;
        if (releasePilotFeedbackParticipant) releasePilotFeedbackParticipant.value = payload.participant_id;
      }
    }

    async function startReleasePilotSession() {
      const payload = await runReleasePilotAction('/api/release-pilot-hardening/pilot/sessions', {
        participant_id:String(releasePilotSessionParticipant?.value || '').trim(),
        data_classification:String(releasePilotDataClass?.value || 'synthetic'),
        approved:true,
      }, 'Starting bounded attorney sandbox session…');
      if (payload?.session_id && releasePilotFeedbackSession) releasePilotFeedbackSession.value = payload.session_id;
    }

    async function submitReleasePilotFeedback() {
      await runReleasePilotAction('/api/release-pilot-hardening/pilot/feedback', {
        participant_id:String(releasePilotFeedbackParticipant?.value || '').trim(),
        session_id:String(releasePilotFeedbackSession?.value || '').trim(),
        category:String(releasePilotFeedbackCategory?.value || 'workflow'),
        severity:String(releasePilotFeedbackSeverity?.value || 'medium'),
        description:String(releasePilotFeedbackDescription?.value || '').trim(),
      }, 'Recording review-required sandbox feedback…');
    }

    function csvValues(control) {
      return String(control?.value || '').split(',').map((value) => value.trim()).filter(Boolean);
    }

    async function createSandboxOperationsProgram() {
      const payload = await runReleasePilotAction('/api/attorney-sandbox-operations/programs', {
        program_id:String(sandboxOperationsProgramId?.value || '').trim(),
        max_questions:Number(sandboxOperationsQuestionCount?.value || 12),
        approved:true,
      }, 'Creating bounded Pass 48 review program…');
      if (payload?.questions?.length && sandboxOperationsQuestionIds) {
        sandboxOperationsQuestionIds.value = payload.questions.map((row) => row.question_id).slice(0, 12).join(', ');
      }
    }

    async function createSandboxOperationsCohort() {
      await runReleasePilotAction('/api/attorney-sandbox-operations/cohorts', {
        program_id:String(sandboxOperationsProgramId?.value || '').trim(),
        cohort_id:String(sandboxOperationsCohortId?.value || '').trim(),
        participant_ids:csvValues(sandboxOperationsCohortParticipants),
        approved:true,
      }, 'Creating approved attorney sandbox cohort…');
    }

    async function createSandboxOperationsAssignment() {
      const payload = await runReleasePilotAction('/api/attorney-sandbox-operations/assignments', {
        program_id:String(sandboxOperationsProgramId?.value || '').trim(),
        cohort_id:String(sandboxOperationsCohortId?.value || '').trim(),
        participant_id:String(sandboxOperationsAssignmentParticipant?.value || '').trim(),
        question_ids:csvValues(sandboxOperationsQuestionIds),
        data_classification:String(sandboxOperationsDataClass?.value || 'synthetic'),
        approved:true,
      }, 'Creating bounded review assignment and session…');
      if (payload?.session_id) {
        if (sandboxOperationsReviewParticipant) sandboxOperationsReviewParticipant.value = payload.participant_id || '';
        if (sandboxOperationsReviewSession) sandboxOperationsReviewSession.value = payload.session_id;
        if (sandboxOperationsReviewQuestion) sandboxOperationsReviewQuestion.value = (payload.question_ids || [])[0] || '';
      }
    }

    async function submitSandboxOperationsReview() {
      await runReleasePilotAction('/api/attorney-sandbox-operations/reviews', {
        participant_id:String(sandboxOperationsReviewParticipant?.value || '').trim(),
        session_id:String(sandboxOperationsReviewSession?.value || '').trim(),
        question_id:String(sandboxOperationsReviewQuestion?.value || '').trim(),
        disposition:String(sandboxOperationsReviewDisposition?.value || 'needs_fix'),
        source_grounding_rating:Number(sandboxOperationsRatingGrounding?.value || 1),
        legal_accuracy_rating:Number(sandboxOperationsRatingAccuracy?.value || 1),
        usefulness_rating:Number(sandboxOperationsRatingUsefulness?.value || 1),
        boundary_safety_rating:Number(sandboxOperationsRatingSafety?.value || 1),
        citation_quality_rating:Number(sandboxOperationsRatingCitations?.value || 1),
        finding_codes:csvValues(sandboxOperationsFindingCodes),
        response_artifact_sha256:String(sandboxOperationsResponseHash?.value || '').trim(),
        verifier_report_sha256:String(sandboxOperationsVerifierHash?.value || '').trim(),
        comment:String(sandboxOperationsComment?.value || '').trim(),
        approved:true,
      }, 'Recording structured, hash-bound attorney review…');
    }

    async function completeSandboxOperationsSession() {
      await runReleasePilotAction('/api/attorney-sandbox-operations/sessions/complete', {
        participant_id:String(sandboxOperationsReviewParticipant?.value || '').trim(),
        session_id:String(sandboxOperationsReviewSession?.value || '').trim(),
        approved:true,
      }, 'Checking assignment coverage and completing session…');
    }

    async function buildSandboxOperationsEvidence() {
      const payload = await runReleasePilotAction('/api/attorney-sandbox-operations/evidence/build', {approved:true}, 'Building immutable Pass 48 operations evidence…');
      const artifacts = Array.isArray(payload?.artifacts) ? payload.artifacts : [];
      if (payload && releasePilotHardeningResults) {
        const links = artifacts.map((row) => `<a class="secondary button-link" href="${escapeHtml(row.download_url || '#')}">${escapeHtml(row.filename || 'artifact')}</a>`).join(' ');
        releasePilotHardeningResults.insertAdjacentHTML('afterbegin', `<section><h3>Pass 48 evidence packet</h3><p>Generation <code>${escapeHtml(payload.generation_id || '')}</code></p><div class="artifact-links">${links}</div><p class="status-warn">External launch evidence review is still required; this packet does not complete Pass 48.</p></section>`);
      }
    }


    function parsedArtifactHashes() {
      const raw = String(realMatterPilotArtifacts?.value || '').trim();
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('Work-product hashes must be a JSON object.');
      return parsed;
    }

    async function createRealMatterPilotProgram() {
      await runReleasePilotAction('/api/limited-real-matter-pilot/programs', {
        program_id:String(realMatterPilotProgramId?.value || '').trim(),
        allowed_tenant_ids:csvValues(realMatterPilotTenants),
        pass48_evidence_sha256:String(realMatterPilotPass48Hash?.value || '').trim(),
        approved:true,
      }, 'Creating approved Pass 49 limited-pilot program…');
    }

    async function enrollRealMatterPilotMatter() {
      await runReleasePilotAction('/api/limited-real-matter-pilot/matters', {
        matter_id:String(realMatterPilotMatterId?.value || '').trim(),
        tenant_id:String(realMatterPilotTenantId?.value || '').trim(),
        participant_id:String(realMatterPilotParticipantId?.value || '').trim(),
        consent_version:String(realMatterPilotConsentVersion?.value || '').trim(),
        client_consent_evidence_sha256:String(realMatterPilotConsentHash?.value || '').trim(),
        privacy_notice_sha256:String(realMatterPilotPrivacyHash?.value || '').trim(),
        matter_store_sha256:String(realMatterPilotStoreHash?.value || '').trim(),
        tenant_isolation_evidence_sha256:String(realMatterPilotIsolationHash?.value || '').trim(),
        encryption_evidence_sha256:String(realMatterPilotEncryptionHash?.value || '').trim(),
        retention_policy_version:String(realMatterPilotRetentionVersion?.value || '').trim(),
        explicit_real_matter_consent:Boolean(realMatterPilotConsentApproved?.checked),
        training_use_allowed:false,
        export_restriction_acknowledged:Boolean(realMatterPilotExportAck?.checked),
        human_review_required:true,
        approved:true,
      }, 'Recording consent-bound, opaque real-matter enrollment…');
    }

    async function recordRealMatterPilotWorkProduct() {
      let hashes;
      try { hashes = parsedArtifactHashes(); }
      catch (err) { showToast(err.message || 'Invalid work-product JSON.'); return; }
      await runReleasePilotAction('/api/limited-real-matter-pilot/work-products', {
        matter_id:String(realMatterPilotMatterId?.value || '').trim(),
        artifact_hashes:hashes,
        approved:true,
      }, 'Recording required work-product hashes…');
    }

    async function recordRealMatterPilotDailyReview() {
      await runReleasePilotAction('/api/limited-real-matter-pilot/daily-reviews', {
        matter_id:String(realMatterPilotMatterId?.value || '').trim(),
        participant_id:String(realMatterPilotParticipantId?.value || '').trim(),
        review_date:String(realMatterPilotReviewDate?.value || '').trim(),
        usefulness:String(realMatterPilotUsefulness?.value || 'not_yet_determined'),
        human_review_completed:true,
        source_verification_completed:true,
        export_gate_checked:true,
        blocker_codes:csvValues(realMatterPilotBlockers),
        review_evidence_sha256:String(realMatterPilotReviewHash?.value || '').trim(),
        approved:true,
      }, 'Recording hash-bound daily pilot review…');
    }

    async function recordRealMatterPilotSignoff() {
      await runReleasePilotAction('/api/limited-real-matter-pilot/signoffs', {
        matter_id:String(realMatterPilotMatterId?.value || '').trim(),
        participant_id:String(realMatterPilotParticipantId?.value || '').trim(),
        usefulness:String(realMatterPilotUsefulness?.value || 'partially_useful'),
        attorney_signoff_complete:Boolean(realMatterPilotSignoffComplete?.checked),
        blocker_codes:csvValues(realMatterPilotBlockers),
        signoff_evidence_sha256:String(realMatterPilotSignoffHash?.value || '').trim(),
        approved:true,
      }, 'Recording external attorney signoff reference…');
    }

    async function buildRealMatterPilotEvidence() {
      const payload = await runReleasePilotAction('/api/limited-real-matter-pilot/evidence/build', {approved:true}, 'Building immutable Pass 49 evidence packet…');
      const artifacts = Array.isArray(payload?.artifacts) ? payload.artifacts : [];
      if (payload && releasePilotHardeningResults) {
        const links = artifacts.map((row) => `<a class="secondary button-link" href="${escapeHtml(row.download_url || '#')}">${escapeHtml(row.filename || 'artifact')}</a>`).join(' ');
        releasePilotHardeningResults.insertAdjacentHTML('afterbegin', `<section><h3>Pass 49 evidence packet</h3><p>Generation <code>${escapeHtml(payload.generation_id || '')}</code></p><div class="artifact-links">${links}</div><p class="status-warn">This packet contains control evidence only and does not complete Pass 49 without external audit.</p></section>`);
      }
    }



    async function createGAReleaseCandidate() {
      await runReleasePilotAction('/api/ga-release-candidate/candidates', {
        candidate_id:String(gaReleaseCandidateId?.value || '').trim(),
        version:String(gaReleaseCandidateVersion?.value || '').trim(),
        source_repo_zip_sha256:String(gaReleaseCandidateSourceHash?.value || '').trim(),
        source_repo_zip_name:String(gaReleaseCandidateSourceName?.value || '').trim(),
        approved:true,
      }, 'Creating immutable Pass 50 candidate…');
    }

    async function recordGAReleaseCandidateArtifact() {
      const artifactType = String(gaReleaseCandidateArtifactType?.value || 'source_repo_zip');
      const defaultExternal = !['source_repo_zip','rollback_package','release_notes'].includes(artifactType);
      await runReleasePilotAction('/api/ga-release-candidate/artifacts', {
        candidate_id:String(gaReleaseCandidateId?.value || '').trim(),
        artifact_type:artifactType,
        artifact_version:String(gaReleaseCandidateArtifactVersion?.value || '').trim(),
        reference:String(gaReleaseCandidateArtifactReference?.value || '').trim(),
        sha256:String(gaReleaseCandidateArtifactHash?.value || '').trim(),
        present:true,
        external:gaReleaseCandidateArtifactExternal ? Boolean(gaReleaseCandidateArtifactExternal.checked) : defaultExternal,
        immutable:true,
        approved:true,
      }, 'Recording immutable release artifact reference…');
    }

    async function recordGAReleaseCandidateSignoff() {
      const localValue = String(gaReleaseCandidateSignedAt?.value || '').trim();
      const signedAt = localValue ? new Date(localValue).toISOString() : '';
      await runReleasePilotAction('/api/ga-release-candidate/signoffs', {
        candidate_id:String(gaReleaseCandidateId?.value || '').trim(),
        role:String(gaReleaseCandidateSignoffRole?.value || 'security'),
        signer_label:String(gaReleaseCandidateSigner?.value || '').trim(),
        status:String(gaReleaseCandidateSignoffStatus?.value || 'pending'),
        signed_at:signedAt,
        evidence_sha256:String(gaReleaseCandidateSignoffHash?.value || '').trim(),
        approved:true,
      }, 'Recording external signoff reference…');
    }

    async function recordGAReleaseCandidateBlocker() {
      await runReleasePilotAction('/api/ga-release-candidate/blockers', {
        candidate_id:String(gaReleaseCandidateId?.value || '').trim(),
        blocker_id:String(gaReleaseCandidateBlockerId?.value || '').trim(),
        severity:String(gaReleaseCandidateBlockerSeverity?.value || 'P1'),
        status:String(gaReleaseCandidateBlockerStatus?.value || 'open'),
        description_code:String(gaReleaseCandidateBlockerDescription?.value || '').trim(),
        evidence_sha256:String(gaReleaseCandidateBlockerHash?.value || '').trim(),
        approved:true,
      }, 'Recording release blocker state…');
    }

    async function freezeGAReleaseCandidate() {
      await runReleasePilotAction('/api/ga-release-candidate/freeze', {
        candidate_id:String(gaReleaseCandidateId?.value || '').trim(),
        audit_enterprise_readiness_status:String(gaReleaseCandidateReadiness?.value || 'blocked'),
        approved:true,
      }, 'Evaluating release candidate against Pass 50 gates…');
    }

    async function buildGAReleaseCandidateEvidence() {
      const payload = await runReleasePilotAction('/api/ga-release-candidate/evidence/build', {approved:true}, 'Building immutable Pass 50 evidence packet…');
      const artifacts = Array.isArray(payload?.artifacts) ? payload.artifacts : [];
      if (payload && releasePilotHardeningResults) {
        const links = artifacts.map((row) => `<a class="secondary button-link" href="${escapeHtml(row.download_url || '#')}">${escapeHtml(row.filename || 'artifact')}</a>`).join(' ');
        releasePilotHardeningResults.insertAdjacentHTML('afterbegin', `<section><h3>Pass 50 evidence packet</h3><p>Generation <code>${escapeHtml(payload.generation_id || '')}</code></p><div class="artifact-links">${links}</div><p class="status-warn">This packet records software-side controls and does not complete Pass 50 without genuine external signoffs and evidence.</p></section>`);
      }
    }

    async function createGAShipmentReadiness() {
      await runReleasePilotAction('/api/ga-shipment-readiness/shipments', {
        shipment_id:String(gaShipmentReadinessId?.value || '').trim(),
        version:String(gaShipmentReadinessVersion?.value || '').trim(),
        source_repo_zip_name:String(gaShipmentReadinessSourceName?.value || '').trim(),
        source_repo_zip_sha256:String(gaShipmentReadinessSourceHash?.value || '').trim(),
        release_candidate_id:String(gaShipmentReadinessRcId?.value || '').trim(),
        release_candidate_report_sha256:String(gaShipmentReadinessRcReportHash?.value || '').trim(),
        release_candidate_inventory_hash:String(gaShipmentReadinessRcInventoryHash?.value || '').trim(),
        release_channel:String(gaShipmentReadinessChannel?.value || 'source_release'),
        approved:true,
      }, 'Creating immutable Pass 51 shipment manifest…');
    }

    async function recordGAShipmentArtifact() {
      const artifactType = String(gaShipmentReadinessArtifactType?.value || 'clean_source_zip');
      const defaultExternal = ['external_legal_data_product_manifest','parsed_authority_build_manifest','retrieval_indexes_manifest','gold_eval_pack_manifest'].includes(artifactType);
      await runReleasePilotAction('/api/ga-shipment-readiness/artifacts', {
        shipment_id:String(gaShipmentReadinessId?.value || '').trim(),
        artifact_type:artifactType,
        artifact_version:String(gaShipmentReadinessArtifactVersion?.value || '').trim(),
        reference:String(gaShipmentReadinessArtifactReference?.value || '').trim(),
        sha256:String(gaShipmentReadinessArtifactHash?.value || '').trim(),
        present:true,
        external:gaShipmentReadinessArtifactExternal ? Boolean(gaShipmentReadinessArtifactExternal.checked) : defaultExternal,
        immutable:true,
        approved:true,
      }, 'Recording immutable Pass 51 artifact…');
    }

    async function recordGAShipmentControl() {
      await runReleasePilotAction('/api/ga-shipment-readiness/controls', {
        shipment_id:String(gaShipmentReadinessId?.value || '').trim(),
        control:String(gaShipmentReadinessControl?.value || ''),
        satisfied:Boolean(gaShipmentReadinessControlSatisfied?.checked),
        evidence_sha256:String(gaShipmentReadinessControlHash?.value || '').trim(),
        approved:true,
      }, 'Recording GA-definition control evidence…');
    }

    async function recordGAShipmentChannel() {
      await runReleasePilotAction('/api/ga-shipment-readiness/channels', {
        shipment_id:String(gaShipmentReadinessId?.value || '').trim(),
        channel:String(gaShipmentReadinessChannel?.value || 'source_release'),
        status:String(gaShipmentReadinessChannelStatus?.value || 'planned'),
        package_sha256:String(gaShipmentReadinessPackageHash?.value || '').trim(),
        qualification_evidence_sha256:String(gaShipmentReadinessQualificationHash?.value || '').trim(),
        rollback_evidence_sha256:String(gaShipmentReadinessRollbackHash?.value || '').trim(),
        distribution_reference:String(gaShipmentReadinessDistributionReference?.value || '').trim(),
        receipt_sha256:String(gaShipmentReadinessReceiptHash?.value || '').trim(),
        approved:true,
      }, 'Recording release-channel qualification evidence…');
    }

    async function recordGAShipmentBlocker() {
      await runReleasePilotAction('/api/ga-shipment-readiness/blockers', {
        shipment_id:String(gaShipmentReadinessId?.value || '').trim(),
        blocker_id:String(gaShipmentReadinessBlockerId?.value || '').trim(),
        severity:String(gaShipmentReadinessBlockerSeverity?.value || 'P1'),
        status:String(gaShipmentReadinessBlockerStatus?.value || 'open'),
        description_code:String(gaShipmentReadinessBlockerDescription?.value || '').trim(),
        evidence_sha256:String(gaShipmentReadinessBlockerHash?.value || '').trim(),
        approved:true,
      }, 'Recording shipment blocker…');
    }

    async function evaluateGAShipmentReadiness() {
      await runReleasePilotAction('/api/ga-shipment-readiness/evaluate', {
        shipment_id:String(gaShipmentReadinessId?.value || '').trim(),
        release_candidate_status:String(gaShipmentReadinessRcStatus?.value || 'blocked'),
        release_candidate_frozen:Boolean(gaShipmentReadinessRcFrozen?.checked),
        release_candidate_inventory_hash:String(gaShipmentReadinessRcInventoryHash?.value || '').trim(),
        approved:true,
      }, 'Evaluating final Pass 51 ship/no-ship gate…');
    }

    async function buildGAShipmentReadinessEvidence() {
      const payload = await runReleasePilotAction('/api/ga-shipment-readiness/evidence/build', {approved:true}, 'Building immutable Pass 51 evidence packet…');
      const artifacts = Array.isArray(payload?.artifacts) ? payload.artifacts : [];
      if (payload && releasePilotHardeningResults) {
        const links = artifacts.map((row) => `<a class="secondary button-link" href="${escapeHtml(row.download_url || '#')}">${escapeHtml(row.filename || 'artifact')}</a>`).join(' ');
        releasePilotHardeningResults.insertAdjacentHTML('afterbegin', `<section><h3>Pass 51 evidence packet</h3><p>Generation <code>${escapeHtml(payload.generation_id || '')}</code></p><div class="artifact-links">${links}</div><p class="status-warn">This packet records software-side shipment readiness and does not prove Store approval or GA shipment.</p></section>`);
      }
    }

    function closeEvidenceWorkProduct() {
      if (!evidenceWorkProductModal || evidenceWorkProductModal.hidden) return;
      evidenceWorkProductModal.hidden = true;
      evidenceWorkProductModal.setAttribute('aria-hidden', 'true');
      if (evidenceWorkProductBackdrop) evidenceWorkProductBackdrop.hidden = true;
      document.body.classList.remove('evidence-work-product-open');
      const owner = evidenceWorkProductOwner;
      evidenceWorkProductOwner = null;
      if (owner && typeof owner.focus === 'function') owner.focus({preventScroll: true});
    }

    function updateEvidenceWorkProductControls() {
      const currentId = String(recordInspectorState?.evidence_id || '');
      const allRecords = Boolean(evidenceWorkProductAllRecords?.checked);
      if (evidenceWorkProductBuild) evidenceWorkProductBuild.disabled = evidenceWorkProductBusy || !evidenceWorkProductApproved?.checked || (!allRecords && !currentId);
      if (evidenceWorkProductLoadActive) evidenceWorkProductLoadActive.disabled = evidenceWorkProductBusy;
      if (evidenceWorkProductScope) {
        evidenceWorkProductScope.innerHTML = allRecords
          ? '<strong>Scope:</strong> all indexed records in the active local matter.'
          : currentId
            ? `<strong>Scope:</strong> current indexed record <code>${escapeHtml(currentId)}</code>.`
            : '<strong>Scope blocked:</strong> no current indexed record is available.';
      }
    }

    function evidenceWorkProductArtifactLinks(artifacts) {
      const rows = Array.isArray(artifacts) ? artifacts : [];
      return rows.map((row) => row.download_url ? `<a class="secondary compact-action" href="${escapeHtml(row.download_url)}">Download ${escapeHtml(String(row.filename || row.name || 'artifact').replaceAll('_', ' '))}</a>` : '').filter(Boolean).join(' ');
    }

    function renderEvidenceWorkProduct(payload) {
      evidenceWorkProductPayload = payload || {};
      if (!evidenceWorkProductResults) return;
      const packet = payload?.packet || {};
      const summary = packet.summary || {};
      const timeline = Array.isArray(packet.timeline) ? packet.timeline : [];
      const ledger = Array.isArray(packet.contempt_enforcement_ledger) ? packet.contempt_enforcement_ledger : [];
      const contradictions = Array.isArray(packet.contradictions) ? packet.contradictions : [];
      const missing = Array.isArray(packet.missing_record_checklist) ? packet.missing_record_checklist : [];
      const exhibits = Array.isArray(packet.exhibit_index) ? packet.exhibit_index : [];
      const timelineMarkup = timeline.slice(0, 80).map((row) => `<article class="evidence-work-product-card"><div><strong>${escapeHtml(row.displayed_date || row.date || 'Date')}</strong><span class="badge warn">${escapeHtml(String(row.assertion_type || 'record statement').replaceAll('_', ' '))}</span></div><p>${escapeHtml(row.description || '')}</p><small>${escapeHtml(row?.source?.safe_filename || '')} · ${escapeHtml(row?.source?.evidence_id || '')} · span ${escapeHtml(row?.source?.span_start)}–${escapeHtml(row?.source?.span_end)}</small></article>`).join('') || '<p class="muted">No dated events were extracted.</p>';
      const ledgerMarkup = ledger.slice(0, 50).map((row) => {
        const order = Array.isArray(row.operative_order_language) ? row.operative_order_language : [];
        const conduct = Array.isArray(row.alleged_or_reported_conduct) ? row.alleged_or_reported_conduct : [];
        return `<article class="evidence-work-product-card"><div><strong>${escapeHtml(row?.source?.safe_filename || row.ledger_id || 'Record')}</strong><span class="badge warn">No legal conclusion</span></div><p><strong>Order language:</strong> ${escapeHtml(order.length)} span(s) · <strong>Reported conduct:</strong> ${escapeHtml(conduct.length)} span(s)</p>${order[0]?.text ? `<blockquote>${escapeHtml(order[0].text)}</blockquote>` : ''}${conduct[0]?.text ? `<blockquote>${escapeHtml(conduct[0].text)}</blockquote>` : ''}<small>${escapeHtml((row.missing_elements || []).join(', ') || 'Review notice, ability to comply, context, and requested relief.')}</small></article>`;
      }).join('') || '<p class="muted">No enforcement-focused ledger rows were extracted.</p>';
      const contradictionMarkup = contradictions.slice(0, 50).map((row) => `<article class="evidence-work-product-card"><div><strong>${escapeHtml(String(row.conflict_type || row.field_type || 'conflict').replaceAll('_', ' '))}</strong><span class="badge warn">Review required</span></div><p>${escapeHtml(row.does_not_prove || 'Different values or wording require source review.')}</p>${(row.occurrences || []).slice(0, 3).map((item) => `<blockquote>${escapeHtml(item.text || item.context || item.displayed_value || '')}<small>${escapeHtml(item.safe_filename || item.evidence_id || item.document_id || '')}</small></blockquote>`).join('')}</article>`).join('') || '<p class="muted">No deterministic contradiction candidate was identified.</p>';
      const missingMarkup = missing.map((row) => `<li><strong>${escapeHtml(String(row.code || '').replaceAll('_', ' '))}</strong> — ${escapeHtml(row.reason || '')}</li>`).join('') || '<li>No automatic missing-record item was generated.</li>';
      const exhibitsMarkup = exhibits.slice(0, 150).map((row) => `<tr><td>${escapeHtml(row.exhibit_id || '')}</td><td>${escapeHtml(row.safe_filename || '')}</td><td>${escapeHtml(String(row.source_type || '').replaceAll('_', ' '))}</td><td>${escapeHtml(row.evidence_id || '')}</td><td><code>${escapeHtml(String(row.source_hash || '').slice(0, 16))}</code></td></tr>`).join('');
      evidenceWorkProductResults.innerHTML = `<section class="evidence-work-product-summary"><div><span class="badge good">Immutable build ${escapeHtml(payload.build_id || packet.build_id || '')}</span><span class="badge warn">Review required</span></div><div class="evidence-work-product-metrics"><strong>${escapeHtml(summary.record_count || 0)} records</strong><strong>${escapeHtml(summary.timeline_event_count || 0)} events</strong><strong>${escapeHtml(summary.enforcement_ledger_count || 0)} enforcement rows</strong><strong>${escapeHtml(summary.contradiction_count || 0)} conflicts</strong><strong>${escapeHtml(summary.missing_record_count || 0)} missing items</strong></div><p>${escapeHtml(packet.disclaimer || 'This work product does not prove an allegation or legal conclusion.')}</p><div class="row">${evidenceWorkProductArtifactLinks(payload.artifacts)}</div></section><details open><summary>Evidence timeline (${escapeHtml(timeline.length)})</summary><div class="evidence-work-product-card-list">${timelineMarkup}</div></details><details open><summary>Contempt and enforcement ledger (${escapeHtml(ledger.length)})</summary><div class="evidence-work-product-card-list">${ledgerMarkup}</div></details><details><summary>Contradictions and conflicts (${escapeHtml(contradictions.length)})</summary><div class="evidence-work-product-card-list">${contradictionMarkup}</div></details><details><summary>Missing-record checklist (${escapeHtml(missing.length)})</summary><ul>${missingMarkup}</ul></details><details><summary>Exhibit index (${escapeHtml(exhibits.length)})</summary><div class="record-inspector-table-wrap"><table class="record-inspector-table"><thead><tr><th>ID</th><th>File</th><th>Type</th><th>Evidence ID</th><th>Hash</th></tr></thead><tbody>${exhibitsMarkup}</tbody></table></div></details>`;
    }

    async function openEvidenceWorkProduct(owner = null) {
      if (!evidenceWorkProductModal) return;
      setWorkflowFocus('evidence');
      evidenceWorkProductOwner = owner || document.activeElement;
      evidenceWorkProductModal.hidden = false;
      evidenceWorkProductModal.setAttribute('aria-hidden', 'false');
      if (evidenceWorkProductBackdrop) evidenceWorkProductBackdrop.hidden = false;
      document.body.classList.add('evidence-work-product-open');
      if (evidenceWorkProductApproved) evidenceWorkProductApproved.checked = false;
      if (evidenceWorkProductResults) evidenceWorkProductResults.textContent = 'Approve the local scope, then build the work product.';
      updateEvidenceWorkProductControls();
      try {
        const payload = await fetchJson('/api/evidence-work-product/status');
        if (evidenceWorkProductStatus) evidenceWorkProductStatus.textContent = payload.active_matter ? `${Number(payload.indexed_record_count || 0).toLocaleString()} indexed record rows available. ${payload.active_build ? 'An active verified work product exists.' : 'No active work product yet.'}` : 'Open a local matter before building evidence work product.';
      } catch (err) {
        if (evidenceWorkProductStatus) evidenceWorkProductStatus.textContent = `Work-product status failed: ${err.message}`;
      }
      evidenceWorkProductClose?.focus({preventScroll: true});
    }

    async function buildEvidenceWorkProduct() {
      if (evidenceWorkProductBusy || !evidenceWorkProductApproved?.checked) return;
      evidenceWorkProductBusy = true;
      updateEvidenceWorkProductControls();
      if (evidenceWorkProductStatus) evidenceWorkProductStatus.textContent = 'Building a content-addressed evidence work product…';
      const allRecords = Boolean(evidenceWorkProductAllRecords?.checked);
      const currentId = String(recordInspectorState?.evidence_id || '');
      const focusTerms = String(evidenceWorkProductFocus?.value || '').split(/[\n,]+/).map((item) => item.trim()).filter(Boolean).slice(0, 50);
      try {
        const payload = await fetchJson('/api/evidence-work-product/build', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({approved: true, include_all_records: allRecords, selected_evidence_ids: allRecords ? [] : [currentId], focus_terms: focusTerms}),
        });
        renderEvidenceWorkProduct(payload);
        if (evidenceWorkProductStatus) evidenceWorkProductStatus.textContent = payload.reused_existing_build ? 'The identical verified work product already existed and was reused.' : 'Immutable work product created and independently verified.';
      } catch (err) {
        if (evidenceWorkProductResults) evidenceWorkProductResults.innerHTML = `<section><h3>Work product blocked</h3><p class="status-warn">${escapeHtml(err.message)}</p></section>`;
        if (evidenceWorkProductStatus) evidenceWorkProductStatus.textContent = 'The work product was not created.';
      } finally {
        evidenceWorkProductBusy = false;
        updateEvidenceWorkProductControls();
      }
    }

    async function loadActiveEvidenceWorkProduct() {
      if (evidenceWorkProductBusy) return;
      evidenceWorkProductBusy = true;
      updateEvidenceWorkProductControls();
      try {
        const payload = await fetchJson('/api/evidence-work-product/active');
        renderEvidenceWorkProduct(payload);
        if (evidenceWorkProductStatus) evidenceWorkProductStatus.textContent = 'Active immutable work product loaded and verified.';
      } catch (err) {
        if (evidenceWorkProductResults) evidenceWorkProductResults.innerHTML = `<section><h3>No verified active work product</h3><p>${escapeHtml(err.message)}</p></section>`;
      } finally {
        evidenceWorkProductBusy = false;
        updateEvidenceWorkProductControls();
      }
    }

    localAgentClose?.addEventListener('click', closeLocalAgentDialog);
    localAgentCancel?.addEventListener('click', closeLocalAgentDialog);
    localAgentBackdrop?.addEventListener('click', closeLocalAgentDialog);
    localAgentRefreshPreview?.addEventListener('click', refreshLocalAgentPreview);
    localAgentRun?.addEventListener('click', runApprovedLocalAgent);
    localAgentProvider?.addEventListener('change', () => {
      if (localAgentProvider.value === 'ollama') {
        localAgentEndpoint.value = 'http://127.0.0.1:11434';
        if (!localAgentModel.value || localAgentModel.value === 'local-model') localAgentModel.value = 'qwen2.5:7b';
      } else {
        localAgentEndpoint.value = 'http://127.0.0.1:1234';
        if (!localAgentModel.value || localAgentModel.value === 'qwen2.5:7b') localAgentModel.value = 'local-model';
      }
      refreshLocalAgentPreview();
    });

    recordInspectorClose?.addEventListener('click', closeRecordInspector);
    recordInspectorBackdrop?.addEventListener('click', closeRecordInspector);
    recordInspectorOpenOriginal?.addEventListener('click', () => {
      if (recordInspectorState) openRecordOriginal({source_token: recordInspectorState.token}, Number(recordInspectorState.page || 0));
    });
    recordInspectorDownload?.addEventListener('click', () => {
      if (recordInspectorState) openRecordOriginal({source_token: recordInspectorState.token}, Number(recordInspectorState.page || 0), {download: true});
    });
    recordInspectorCopyDetails?.addEventListener('click', async () => {
      if (!recordInspectorState) return;
      const safe = {...recordInspectorState};
      delete safe.token;
      delete safe.open_url;
      delete safe.download_url;
      await navigator.clipboard.writeText(JSON.stringify(safe, null, 2));
      showToast('Safe source details copied.');
    });
    recordInspectorPrevPage?.addEventListener('click', () => changeInspectorPage(-1));
    recordInspectorNextPage?.addEventListener('click', () => changeInspectorPage(1));
    recordInspectorPageInput?.addEventListener('change', () => changeInspectorPage(0, recordInspectorPageInput.value));
    recordInspectorZoomIn?.addEventListener('click', () => changeInspectorZoom(.25));
    recordInspectorZoomOut?.addEventListener('click', () => changeInspectorZoom(-.25));
    recordInspectorZoomFit?.addEventListener('click', () => changeInspectorZoom(0, true));
    recordInspectorDocumentIntelligence?.addEventListener('click', () => openDocumentIntelligence(recordInspectorDocumentIntelligence));
    recordInspectorEvidenceWorkProduct?.addEventListener('click', () => openEvidenceWorkProduct(recordInspectorEvidenceWorkProduct));
    recordInspectorRetrievalWorkbench?.addEventListener('click', () => openRetrievalWorkbench(recordInspectorRetrievalWorkbench));
    recordInspectorReleasePilotHardening?.addEventListener('click', () => openReleasePilotHardening(recordInspectorReleasePilotHardening));
    releasePilotHardeningClose?.addEventListener('click', closeReleasePilotHardening);
    releasePilotHardeningBackdrop?.addEventListener('click', closeReleasePilotHardening);
    releasePilotHardeningRefresh?.addEventListener('click', loadReleasePilotHardeningStatus);
    releasePilotHardeningAudit?.addEventListener('click', () => runReleasePilotAction('/api/release-pilot-hardening/evidence/audit', {approved:true}, 'Auditing configured external release evidence…'));
    releasePilotHardeningObservability?.addEventListener('click', () => runReleasePilotAction('/api/release-pilot-hardening/observability/self-test', {approved:true}, 'Running privacy-safe observability self-test…'));
    releasePilotHardeningBackup?.addEventListener('click', () => { if (window.confirm('Create an external content-addressed backup and run a temporary isolated restore rehearsal? The active matter will not be modified.')) runReleasePilotAction('/api/release-pilot-hardening/backup-restore/drill', {approved:true}, 'Running backup and isolated restore rehearsal…'); });
    releasePilotRegister?.addEventListener('click', registerReleasePilotParticipant);
    releasePilotStartSession?.addEventListener('click', startReleasePilotSession);
    releasePilotSubmitFeedback?.addEventListener('click', submitReleasePilotFeedback);
    sandboxOperationsRefresh?.addEventListener('click', loadReleasePilotHardeningStatus);
    sandboxOperationsCreateProgram?.addEventListener('click', createSandboxOperationsProgram);
    sandboxOperationsCreateCohort?.addEventListener('click', createSandboxOperationsCohort);
    sandboxOperationsCreateAssignment?.addEventListener('click', createSandboxOperationsAssignment);
    sandboxOperationsSubmitReview?.addEventListener('click', submitSandboxOperationsReview);
    sandboxOperationsCompleteSession?.addEventListener('click', completeSandboxOperationsSession);
    sandboxOperationsBuildEvidence?.addEventListener('click', buildSandboxOperationsEvidence);
    realMatterPilotRefresh?.addEventListener('click', loadReleasePilotHardeningStatus);
    realMatterPilotCreateProgram?.addEventListener('click', createRealMatterPilotProgram);
    realMatterPilotEnroll?.addEventListener('click', enrollRealMatterPilotMatter);
    realMatterPilotWorkProduct?.addEventListener('click', recordRealMatterPilotWorkProduct);
    realMatterPilotDailyReview?.addEventListener('click', recordRealMatterPilotDailyReview);
    realMatterPilotSignoff?.addEventListener('click', recordRealMatterPilotSignoff);
    realMatterPilotBuildEvidence?.addEventListener('click', buildRealMatterPilotEvidence);
    gaReleaseCandidateRefresh?.addEventListener('click', loadReleasePilotHardeningStatus);
    gaReleaseCandidateCreate?.addEventListener('click', createGAReleaseCandidate);
    gaReleaseCandidateRecordArtifact?.addEventListener('click', recordGAReleaseCandidateArtifact);
    gaReleaseCandidateRecordSignoff?.addEventListener('click', recordGAReleaseCandidateSignoff);
    gaReleaseCandidateRecordBlocker?.addEventListener('click', recordGAReleaseCandidateBlocker);
    gaReleaseCandidateFreeze?.addEventListener('click', freezeGAReleaseCandidate);
    gaReleaseCandidateBuildEvidence?.addEventListener('click', buildGAReleaseCandidateEvidence);
    gaShipmentReadinessRefresh?.addEventListener('click', loadReleasePilotHardeningStatus);
    gaShipmentReadinessCreate?.addEventListener('click', createGAShipmentReadiness);
    gaShipmentReadinessRecordArtifact?.addEventListener('click', recordGAShipmentArtifact);
    gaShipmentReadinessRecordControl?.addEventListener('click', recordGAShipmentControl);
    gaShipmentReadinessRecordChannel?.addEventListener('click', recordGAShipmentChannel);
    gaShipmentReadinessRecordBlocker?.addEventListener('click', recordGAShipmentBlocker);
    gaShipmentReadinessEvaluate?.addEventListener('click', evaluateGAShipmentReadiness);
    gaShipmentReadinessBuildEvidence?.addEventListener('click', buildGAShipmentReadinessEvidence);
    retrievalWorkbenchClose?.addEventListener('click', closeRetrievalWorkbench);
    retrievalWorkbenchBackdrop?.addEventListener('click', closeRetrievalWorkbench);
    retrievalWorkbenchSearch?.addEventListener('click', runRetrievalWorkbenchSearch);
    retrievalWorkbenchEvaluate?.addEventListener('click', runRetrievalWorkbenchEvaluation);
    evidenceWorkProductClose?.addEventListener('click', closeEvidenceWorkProduct);
    evidenceWorkProductBackdrop?.addEventListener('click', closeEvidenceWorkProduct);
    evidenceWorkProductAllRecords?.addEventListener('change', updateEvidenceWorkProductControls);
    evidenceWorkProductApproved?.addEventListener('change', updateEvidenceWorkProductControls);
    evidenceWorkProductBuild?.addEventListener('click', buildEvidenceWorkProduct);
    evidenceWorkProductLoadActive?.addEventListener('click', loadActiveEvidenceWorkProduct);
    documentIntelligenceClose?.addEventListener('click', closeDocumentIntelligence);
    documentIntelligenceBackdrop?.addEventListener('click', closeDocumentIntelligence);
    documentIntelligenceApproved?.addEventListener('change', updateDocumentIntelligenceButtons);
    documentIntelligenceOcrApproved?.addEventListener('change', updateDocumentIntelligenceButtons);
    documentIntelligenceAnalyze?.addEventListener('click', runDocumentIntelligence);
    documentIntelligenceOcr?.addEventListener('click', runDocumentIntelligenceOcr);

    authorityVerificationClose?.addEventListener('click', closeAuthorityVerification);
    authorityVerificationDone?.addEventListener('click', closeAuthorityVerification);
    authorityVerificationBackdrop?.addEventListener('click', closeAuthorityVerification);
    authorityVerificationCopy?.addEventListener('click', async () => {
      if (!authorityVerificationReceipt) return;
      await navigator.clipboard.writeText(JSON.stringify(authorityVerificationReceipt, null, 2));
      authorityVerificationCopy.textContent = 'Copied';
      showToast('Verification receipt copied.');
      window.setTimeout(() => { authorityVerificationCopy.textContent = 'Copy verification receipt'; }, 1200);
    });
    matterCommandCenterClose?.addEventListener('click', () => closeOverlay(matterCommandCenterOverlay));
    matterCommandCenterOverlay?.addEventListener('mousedown', (event) => {
      if (event.target === matterCommandCenterOverlay) closeOverlay(matterCommandCenterOverlay);
    });
    matterCommandCenterRefresh?.addEventListener('click', () => loadMatterCommandCenter());
    matterCommandCenterFreeze?.addEventListener('click', freezeMatterCommandCenterSnapshot);
    matterCommandCenterBuild?.addEventListener('click', buildMatterCommandCenterPacket);
    matterCommandCenterCompare?.addEventListener('click', compareMatterCommandCenterPackets);
    matterCommandCenterApproved?.addEventListener('change', updateMatterCommandCenterControls);
    matterCommandCenterVariant?.addEventListener('change', updateMatterCommandCenterControls);
    matterCommandCenterCompareLeft?.addEventListener('change', updateMatterCommandCenterControls);
    matterCommandCenterCompareRight?.addEventListener('change', updateMatterCommandCenterControls);
    matterCommandCenterSnapshotRecords?.addEventListener('input', updateMatterCommandCenterControls);
    matterIntakeClose?.addEventListener('click', () => closeOverlay(matterIntakeOverlay));
    matterIntakeOverlay?.addEventListener('mousedown', (event) => { if (event.target === matterIntakeOverlay) closeOverlay(matterIntakeOverlay); });
    matterIntakeCreate?.addEventListener('click', createOrResumeMatterIntake);
    matterIntakeSave?.addEventListener('click', saveMatterIntakeStep);
    matterIntakeCoverage?.addEventListener('click', inspectMatterIntakeCoverage);
    matterIntakeComplete?.addEventListener('click', completeMatterIntake);
    matterIntakeReceipt?.addEventListener('click', showMatterIntakeReceipt);
    ordersWorkspaceClose?.addEventListener('click', () => closeOverlay(ordersWorkspaceOverlay));
    ordersWorkspaceOverlay?.addEventListener('mousedown', (event) => { if (event.target === ordersWorkspaceOverlay) closeOverlay(ordersWorkspaceOverlay); });
    ordersAdd?.addEventListener('click', addOrderCandidate);
    ordersRefresh?.addEventListener('click', refreshOrdersWorkspace);
    ordersReceipt?.addEventListener('click', showOrdersReceipt);
    calendarWorkspaceClose?.addEventListener('click', () => closeOverlay(calendarWorkspaceOverlay));
    calendarWorkspaceOverlay?.addEventListener('mousedown', (event) => { if (event.target === calendarWorkspaceOverlay) closeOverlay(calendarWorkspaceOverlay); });
    calendarAdd?.addEventListener('click', addCalendarEvent);
    calendarRefresh?.addEventListener('click', refreshCalendarWorkspace);
    calendarReceipt?.addEventListener('click', showCalendarReceipt);
    docketWorkspaceClose?.addEventListener('click', () => closeOverlay(docketWorkspaceOverlay));
    docketWorkspaceOverlay?.addEventListener('mousedown', (event) => { if (event.target === docketWorkspaceOverlay) closeOverlay(docketWorkspaceOverlay); });
    docketAdd?.addEventListener('click', addDocketEntry);
    docketReconcile?.addEventListener('click', reconcileDocketWorkspace);
    docketReceipt?.addEventListener('click', showDocketReceipt);
    discoveryWorkspaceClose?.addEventListener('click', () => closeOverlay(discoveryWorkspaceOverlay));
    discoveryWorkspaceOverlay?.addEventListener('mousedown', (event) => { if (event.target === discoveryWorkspaceOverlay) closeOverlay(discoveryWorkspaceOverlay); });
    discoveryAdd?.addEventListener('click', addDiscoveryItem);
    discoveryGaps?.addEventListener('click', refreshDiscoveryGaps);
    discoveryReceipt?.addEventListener('click', showDiscoveryReceipt);
    exhibitsWorkspaceClose?.addEventListener('click', () => closeOverlay(exhibitsWorkspaceOverlay));
    exhibitsWorkspaceOverlay?.addEventListener('mousedown', (event) => { if (event.target === exhibitsWorkspaceOverlay) closeOverlay(exhibitsWorkspaceOverlay); });
    exhibitsAdd?.addEventListener('click', addExhibitCandidate);
    exhibitsRefresh?.addEventListener('click', refreshExhibitsWorkspace);
    exhibitsReceipt?.addEventListener('click', showExhibitsReceipt);
    statementsWorkspaceClose?.addEventListener('click', () => closeOverlay(statementsWorkspaceOverlay));
    statementsWorkspaceOverlay?.addEventListener('mousedown', (event) => { if (event.target === statementsWorkspaceOverlay) closeOverlay(statementsWorkspaceOverlay); });
    statementsRefresh?.addEventListener('click', refreshStatementsWorkspace);
    statementsReceipt?.addEventListener('click', showStatementsReceipt);
    statementsAddPerson?.addEventListener('click', addStatementPerson);
    statementsAdd?.addEventListener('click', addStatement);
    hearingWorkspaceClose?.addEventListener('click',()=>closeOverlay(hearingWorkspaceOverlay)); hearingWorkspaceOverlay?.addEventListener('mousedown',e=>{if(e.target===hearingWorkspaceOverlay)closeOverlay(hearingWorkspaceOverlay);});hearingAdd?.addEventListener('click',addHearing);hearingRefresh?.addEventListener('click',refreshHearings);hearingReceipt?.addEventListener('click',showHearingReceipt);
    appellateWorkspaceClose?.addEventListener('click',()=>closeOverlay(appellateWorkspaceOverlay));appellateWorkspaceOverlay?.addEventListener('mousedown',e=>{if(e.target===appellateWorkspaceOverlay)closeOverlay(appellateWorkspaceOverlay);});appellateAdd?.addEventListener('click',addAppellate);appellateRefresh?.addEventListener('click',refreshAppellate);appellateReceipt?.addEventListener('click',showAppellateReceipt);
    uccjeaWorkspaceClose?.addEventListener('click',()=>closeOverlay(uccjeaWorkspaceOverlay));uccjeaWorkspaceOverlay?.addEventListener('mousedown',e=>{if(e.target===uccjeaWorkspaceOverlay)closeOverlay(uccjeaWorkspaceOverlay);});uccjeaAdd?.addEventListener('click',addUccjea);uccjeaRefresh?.addEventListener('click',refreshUccjea);uccjeaReceipt?.addEventListener('click',showUccjeaReceipt);
    icwaWorkspaceClose?.addEventListener('click',()=>closeOverlay(icwaWorkspaceOverlay));icwaWorkspaceOverlay?.addEventListener('mousedown',e=>{if(e.target===icwaWorkspaceOverlay)closeOverlay(icwaWorkspaceOverlay);});icwaAdd?.addEventListener('click',addIcwa);icwaRefresh?.addEventListener('click',refreshIcwa);icwaReceipt?.addEventListener('click',showIcwaReceipt);
    careWorkspaceClose?.addEventListener('click',()=>closeOverlay(careWorkspaceOverlay));careWorkspaceOverlay?.addEventListener('mousedown',e=>{if(e.target===careWorkspaceOverlay)closeOverlay(careWorkspaceOverlay);});careAdd?.addEventListener('click',addCare);careRefresh?.addEventListener('click',refreshCare);careReceipt?.addEventListener('click',showCareReceipt);
    safetyWorkspaceClose?.addEventListener('click',()=>closeOverlay(safetyWorkspaceOverlay));safetyWorkspaceOverlay?.addEventListener('mousedown',e=>{if(e.target===safetyWorkspaceOverlay)closeOverlay(safetyWorkspaceOverlay);});safetyAdd?.addEventListener('click',addSafety);safetyRefresh?.addEventListener('click',refreshSafety);safetyReceipt?.addEventListener('click',showSafetyReceipt);
    scheduleWorkspaceClose?.addEventListener('click',()=>closeOverlay(scheduleWorkspaceOverlay));scheduleWorkspaceOverlay?.addEventListener('mousedown',e=>{if(e.target===scheduleWorkspaceOverlay)closeOverlay(scheduleWorkspaceOverlay);});scheduleAdd?.addEventListener('click',addSchedule);scheduleRefresh?.addEventListener('click',refreshSchedule);scheduleReceipt?.addEventListener('click',showScheduleReceipt);
    lateReviewClose?.addEventListener('click',()=>closeOverlay(lateReviewOverlay));lateReviewOverlay?.addEventListener('mousedown',e=>{if(e.target===lateReviewOverlay)closeOverlay(lateReviewOverlay);});lateReviewRefresh?.addEventListener('click',refreshLateReview);lateReviewReceipt?.addEventListener('click',showLateReviewReceipt);
    corpusSelect?.addEventListener('change', () => {
      syncContextBar();
      if (matterCommandCenterOverlay && !matterCommandCenterOverlay.hidden) loadMatterCommandCenter();
    });

    sourcePreviewFlyout?.addEventListener('pointerenter', () => window.clearTimeout(sourcePreviewHideTimer));
    sourcePreviewFlyout?.addEventListener('pointerleave', scheduleSourcePreviewClose);
    sourcePreviewClose?.addEventListener('click', () => closeSourcePreview({force: true, returnFocus: true}));
    sourcePreviewBackdrop?.addEventListener('click', () => closeSourcePreview({force: true, returnFocus: true}));
    window.addEventListener('resize', () => positionSourcePreview(sourcePreviewOwner));
    document.addEventListener('scroll', () => positionSourcePreview(sourcePreviewOwner), true);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && localWorkbenchOverlay && !localWorkbenchOverlay.hidden) {
        event.preventDefault();
        closeLocalWorkbench();
        return;
      }
      if (event.key === 'Tab' && localWorkbenchOverlay && !localWorkbenchOverlay.hidden) {
        const focusable = overlayFocusableElements(localWorkbenchOverlay);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Escape' && releasePilotHardeningModal && !releasePilotHardeningModal.hidden) {
        event.preventDefault();
        closeReleasePilotHardening();
        return;
      }
      if (event.key === 'Tab' && releasePilotHardeningModal && !releasePilotHardeningModal.hidden) {
        const focusable = overlayFocusableElements(releasePilotHardeningModal);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Escape' && evidenceWorkProductModal && !evidenceWorkProductModal.hidden) {
        event.preventDefault();
        closeEvidenceWorkProduct();
        return;
      }
      if (event.key === 'Tab' && evidenceWorkProductModal && !evidenceWorkProductModal.hidden) {
        const focusable = overlayFocusableElements(evidenceWorkProductModal);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Escape' && documentIntelligenceModal && !documentIntelligenceModal.hidden) {
        event.preventDefault();
        closeDocumentIntelligence();
        return;
      }
      if (event.key === 'Tab' && documentIntelligenceModal && !documentIntelligenceModal.hidden) {
        const focusable = overlayFocusableElements(documentIntelligenceModal);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Escape' && authorityVerificationModal && !authorityVerificationModal.hidden) {
        event.preventDefault();
        closeAuthorityVerification();
        return;
      }
      if (event.key === 'Tab' && authorityVerificationModal && !authorityVerificationModal.hidden) {
        const focusable = overlayFocusableElements(authorityVerificationModal);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Escape' && localAgentModal && !localAgentModal.hidden) {
        event.preventDefault();
        closeLocalAgentDialog();
        return;
      }
      if (event.key === 'Tab' && localAgentModal && !localAgentModal.hidden) {
        const focusable = overlayFocusableElements(localAgentModal);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Escape' && documentWorkspace && !documentWorkspace.hidden) {
        event.preventDefault();
        closeDocumentWorkspace();
        return;
      }
      if (event.key === 'Tab' && documentWorkspace && !documentWorkspace.hidden) {
        const focusable = overlayFocusableElements(documentWorkspace);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Escape' && recordInspector && !recordInspector.hidden) {
        event.preventDefault();
        closeRecordInspector();
        return;
      }
      if (event.key === 'Tab' && recordInspector && !recordInspector.hidden) {
        const focusable = overlayFocusableElements(recordInspector);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Tab' && sourcePreviewPinned && sourcePreviewFlyout && !sourcePreviewFlyout.hidden) {
        const focusable = overlayFocusableElements(sourcePreviewFlyout);
        if (focusable.length) {
          const first = focusable[0];
          const last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      if (event.key === 'Escape' && sourcePreviewFlyout && !sourcePreviewFlyout.hidden) {
        event.preventDefault();
        closeSourcePreview({force: true, returnFocus: true});
      }
    });

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
      const pendingQuestion = question?.value || '';
      activateCorpusButton.disabled = true;
      try {
        const payload = await fetchJson('/api/activate-corpus', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({case_id: caseId})
        });
        corpusStatus.innerHTML = `<strong>Active corpus switched:</strong> ${escapeHtml(payload.active_case_label || 'selected matter')}<br><span class="muted">Private records stay on this device.</span>`;
        requestAbortReason = 'matter_switched';
        activeRequestController?.abort();
        resetSession({preserveContext: true});
        if (question) question.value = pendingQuestion;
        closeSourcePreview({force: true});
        showToast('Active matter switched. Prior-matter results were cleared; your unsent question was preserved.');
        await loadCorpusLibrary();
      } catch (err) {
        corpusStatus.innerHTML = `<span class="status-bad">Could not switch the active corpus: ${escapeHtml(err.message)}</span>`;
      } finally {
        activateCorpusButton.disabled = false;
      }
    }

    function sourceLane(item) {
      return normalizedSourceLane(item) === 'private_record' ? 'records' : 'law';
    }

    function sourceItemsFromPayload(payload) {
      const items = Array.isArray(payload?.citations) ? payload.citations.filter(Boolean) : [];
      const seen = new Set();
      return items.filter((item) => {
        const meta = item?.metadata || item || {};
        const lane = sourceLane(item);
        const canonical = lane === 'records'
          ? String(meta.canonical_document_key || meta.source_hash || meta.parent_evidence_id || item?.source_id || '')
          : String(item?.source_id || meta.id || item?.url || meta.url || '');
        const page = Number(meta.page_number || item?.page_number || 0);
        const snippet = String(item?.snippet || item?.text_excerpt || meta.text_excerpt || '').toLowerCase().replace(/\s+/g, ' ').trim();
        const key = `${lane}|${canonical}|${page}|${snippet}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    }

    function localAgentConfigPayload() {
      return {
        provider: String(localAgentProvider?.value || 'ollama'),
        endpoint: String(localAgentEndpoint?.value || 'http://127.0.0.1:11434').trim(),
        model: String(localAgentModel?.value || 'qwen2.5:7b').trim()
      };
    }

    function localAgentSourceCards(payload) {
      return sourceItemsFromPayload(payload).map((item) => {
        const meta = item?.metadata || item || {};
        return {
          source_id: item?.source_id || item?.evidence_id || meta.source_id || meta.id || '',
          title: item?.title || meta.title || sourceBasename(item),
          snippet: item?.snippet || item?.text_excerpt || meta.text_excerpt || meta.matched_text || '',
          locator: item?.locator || meta.source_locator_basename || meta.safe_locator || meta.citation_hint || '',
          metadata: {
            source_lane: normalizedSourceLane(item),
            source_class: meta.source_class || meta.source_type || '',
            authority_status: meta.authority_status || '',
            freshness_status: meta.freshness_status || meta.freshness || '',
            instruction_like_text_detected: Boolean(meta.instruction_like_text_detected)
          }
        };
      }).filter((item) => item.snippet);
    }

    function renderContextManifest(payload) {
      const manifest = payload?.context_manifest || payload?.metadata?.context_manifest || null;
      if (!manifest) return '';
      const lanes = manifest.lane_counts || {};
      const hash = String(manifest.manifest_sha256 || 'not available');
      return `<details class="chat-context-manifest">
        <summary>Local context manifest · ${escapeHtml(manifest.entry_count || 0)} source${Number(manifest.entry_count || 0) === 1 ? '' : 's'}</summary>
        <div class="chat-context-manifest-grid">
          <span><strong>Maine law</strong><br>${escapeHtml(lanes.legal_authority || 0)}</span>
          <span><strong>Private records</strong><br>${escapeHtml(lanes.private_record || 0)}</span>
          <span><strong>Characters</strong><br>${Number(manifest.total_chars || 0).toLocaleString()}</span>
        </div>
        <p class="muted">Nothing was sent to a model. This is the exact packet available for an optional loopback-only run.</p>
        <p><strong>Manifest hash:</strong> <code>${escapeHtml(hash)}</code></p>
      </details>`;
    }

    function renderLocalAgentReceipt(payload) {
      const receipt = payload?.provenance_receipt || {};
      if (!receipt.receipt_sha256) return '';
      return `<div class="local-agent-receipt"><strong>Hash-bound provenance receipt</strong><br>
        Answer <code>${escapeHtml(String(receipt.answer_sha256 || '').slice(0, 20))}…</code> ·
        Context <code>${escapeHtml(String(receipt.context_manifest_sha256 || '').slice(0, 20))}…</code> ·
        Receipt <code>${escapeHtml(receipt.receipt_sha256)}</code><br>
        <span class="muted">Model output is analytical work product only. Review required.</span></div>`;
    }

    function authoritySourceIds(payload) {
      const seen = new Set();
      return sourceItemsFromPayload(payload).filter((item) => sourceLane(item) !== 'records').map((item) => {
        const meta = item?.metadata || item || {};
        return String(item?.source_id || meta.source_id || meta.record_id || '').trim();
      }).filter((sourceId) => sourceId && !seen.has(sourceId) && seen.add(sourceId));
    }

    function authorityVerificationTone(status) {
      const value = String(status || '').toLowerCase();
      if (value === 'supported' || value === 'found' || value === 'exact_match' || value === 'verified_scope') return 'is-supported';
      if (value.includes('partial') || value.includes('fuzzy') || value.includes('warning')) return 'is-partial';
      return 'is-blocked';
    }

    function closeAuthorityVerification() {
      if (!authorityVerificationModal) return;
      authorityVerificationModal.hidden = true;
      authorityVerificationModal.setAttribute('aria-hidden', 'true');
      if (authorityVerificationBackdrop) {
        authorityVerificationBackdrop.hidden = true;
        authorityVerificationBackdrop.setAttribute('aria-hidden', 'true');
      }
      document.body.classList.remove('authority-verification-open');
      const owner = authorityVerificationOwner;
      authorityVerificationOwner = null;
      authorityVerificationBusy = false;
      owner?.focus?.({preventScroll: true});
    }

    function renderAuthorityVerification(result) {
      const report = result?.verification_report || {};
      const filingGate = result?.filing_gate || {};
      const receipt = result?.verification_receipt || null;
      authorityVerificationReceipt = receipt;
      const citations = Array.isArray(report.citations) ? report.citations : [];
      const claims = Array.isArray(report.claims) ? report.claims : [];
      const quotes = Array.isArray(report.quotes) ? report.quotes : [];
      const reportBlockers = Array.isArray(report.blockers) ? report.blockers : [];
      const filingBlockers = Array.isArray(filingGate.blockers) ? filingGate.blockers : [];
      const blockers = [...new Set([...reportBlockers, ...filingBlockers])];
      const buildId = String(result?.authority_build_id || 'not active');
      const status = String(result?.status || 'blocked');
      const supportedClaims = claims.filter((row) => row?.status === 'supported').length;
      authorityVerificationSummary.innerHTML = `
        <div><small>Authority build</small><strong>${escapeHtml(buildId)}</strong></div>
        <div><small>Citations resolved</small><strong>${citations.filter((row) => row?.status === 'found').length} / ${citations.length}</strong></div>
        <div><small>Claims supported</small><strong>${supportedClaims} / ${claims.length}</strong></div>
        <div><small>Review blockers</small><strong>${blockers.length}</strong></div>`;
      const blockedNotice = status === 'blocked' || result?.blockers
        ? `<section class="authority-verification-section"><div class="authority-verification-card is-blocked"><header><strong>Authority verification unavailable</strong><span class="authority-verification-status-pill is-blocked">blocked</span></header><p>${escapeHtml((result?.blockers || ['The active immutable authority product is not configured or did not verify.']).join(' · '))}</p><p>Connect a verified external authority generation before treating this as a current-law verification report.</p></div></section>`
        : '';
      const claimHtml = claims.length ? claims.map((row, index) => {
        const tone = authorityVerificationTone(row?.status);
        const span = row?.best_span || {};
        const sourceId = span.source_id || row?.source_trace?.best_source_id || 'no admitted source';
        return `<article class="authority-verification-card ${tone}">
          <header><strong>Claim ${index + 1}</strong><span class="authority-verification-status-pill ${tone}">${escapeHtml(row?.status || 'unknown')}</span></header>
          <p>${escapeHtml(row?.claim || '')}</p>
          ${span.text ? `<pre>${escapeHtml(span.text)}</pre>` : ''}
          <p class="muted">Source: ${escapeHtml(sourceId)} · score ${escapeHtml(Number(row?.confidence || 0).toFixed(3))}${Number.isInteger(span.start_offset) ? ` · offsets ${span.start_offset}–${span.end_offset}` : ''}</p>
        </article>`;
      }).join('') : '<div class="authority-verification-card is-blocked"><p>No legal claims were extracted. This prevents automated support certification.</p></div>';
      const citationHtml = citations.length ? citations.map((row) => {
        const tone = authorityVerificationTone(row?.status);
        return `<article class="authority-verification-card ${tone}"><header><strong>${escapeHtml(row?.citation?.normalized || row?.normalized_citation || row?.citation?.raw || 'Citation')}</strong><span class="authority-verification-status-pill ${tone}">${escapeHtml(row?.status || 'unknown')}</span></header><p>Source: ${escapeHtml(row?.source_id || 'not resolved')}</p></article>`;
      }).join('') : '<div class="authority-verification-card is-partial"><p>No legal citation was detected in this answer.</p></div>';
      const quoteHtml = quotes.length ? `<section class="authority-verification-section"><h3>Quoted text</h3><div class="authority-verification-grid">${quotes.map((row) => { const tone = authorityVerificationTone(row?.status); return `<article class="authority-verification-card ${tone}"><header><strong>${escapeHtml(row?.source_id || 'Quote')}</strong><span class="authority-verification-status-pill ${tone}">${escapeHtml(row?.status || 'unknown')}</span></header><p>${escapeHtml(row?.quoted_text || row?.normalized_quote || '')}</p></article>`; }).join('')}</div></section>` : '';
      const blockerHtml = blockers.length
        ? `<section class="authority-verification-section"><h3>Why filing-ready export remains blocked</h3><div class="authority-verification-card is-blocked"><ul class="authority-verification-blockers">${blockers.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div></section>`
        : '<section class="authority-verification-section"><div class="authority-verification-card is-partial"><strong>Source checks passed, but human legal review is still required.</strong></div></section>';
      const receiptHtml = receipt?.receipt_sha256
        ? `<section class="authority-verification-section"><h3>Reproducible receipt</h3><div class="authority-verification-card"><p><strong>Answer:</strong> <code>${escapeHtml(String(receipt.answer_sha256 || ''))}</code></p><p><strong>Authority manifest:</strong> <code>${escapeHtml(String(receipt.authority_manifest_sha256 || ''))}</code></p><p><strong>Receipt:</strong> <code>${escapeHtml(receipt.receipt_sha256)}</code></p></div></section>`
        : '';
      authorityVerificationBody.innerHTML = `${blockedNotice}<section class="authority-verification-section"><h3>Claim-to-source review</h3><div class="authority-verification-grid">${claimHtml}</div></section><section class="authority-verification-section"><h3>Citation resolution</h3><div class="authority-verification-grid">${citationHtml}</div></section>${quoteHtml}${blockerHtml}${receiptHtml}`;
      authorityVerificationCopy.disabled = !receipt?.receipt_sha256;
      authorityVerificationStatus.textContent = status === 'verified_pending_human_review'
        ? 'Source checks completed. Human review remains mandatory.'
        : 'Review required. The answer was not self-certified.';
    }

    async function openAuthorityVerification(text, payload, owner) {
      if (!authorityVerificationModal || authorityVerificationBusy) return;
      authorityVerificationOwner = owner || document.activeElement;
      authorityVerificationReceipt = null;
      authorityVerificationBusy = true;
      authorityVerificationModal.hidden = false;
      authorityVerificationModal.setAttribute('aria-hidden', 'false');
      if (authorityVerificationBackdrop) {
        authorityVerificationBackdrop.hidden = false;
        authorityVerificationBackdrop.setAttribute('aria-hidden', 'false');
      }
      document.body.classList.add('authority-verification-open');
      authorityVerificationSummary.innerHTML = '<div><small>Status</small><strong>Loading verified authority generation…</strong></div>';
      authorityVerificationBody.innerHTML = '<div class="authority-verification-card"><p>Resolving citations and mapping each legal claim to an exact admitted source span.</p></div>';
      authorityVerificationCopy.disabled = true;
      authorityVerificationStatus.textContent = 'No model is being asked to certify this answer.';
      authorityVerificationClose?.focus({preventScroll: true});
      try {
        const result = await fetchJson('/api/authority/verify-answer', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            text: String(text || ''),
            source_ids: authoritySourceIds(payload),
            quotes: [],
            claims: [],
            expected_jurisdiction: 'maine',
            auto_extract_claims: true
          })
        });
        renderAuthorityVerification(result);
      } catch (error) {
        renderAuthorityVerification({status: 'blocked', blockers: [String(error?.message || error || 'authority verification failed')]});
      } finally {
        authorityVerificationBusy = false;
      }
    }

    function closeLocalAgentDialog() {
      if (!localAgentModal) return;
      localAgentModal.hidden = true;
      localAgentModal.setAttribute('aria-hidden', 'true');
      if (localAgentBackdrop) { localAgentBackdrop.hidden = true; localAgentBackdrop.setAttribute('aria-hidden', 'true'); }
      document.body.classList.remove('local-agent-open');
      const owner = localAgentOwner;
      localAgentOwner = null;
      localAgentPreview = null;
      localAgentPayload = null;
      if (owner && typeof owner.focus === 'function') owner.focus({preventScroll: true});
    }

    async function refreshLocalAgentPreview() {
      if (!localAgentPayload || localAgentBusy) return;
      const cards = localAgentSourceCards(localAgentPayload);
      if (!cards.length) {
        localAgentPreviewSummary.textContent = 'No source excerpts are available for a local model run.';
        localAgentRun.disabled = true;
        return;
      }
      localAgentBusy = true;
      localAgentRun.disabled = true;
      localAgentRefreshPreview.disabled = true;
      localAgentStatus.textContent = 'Building the exact loopback context manifest…';
      try {
        const config = localAgentConfigPayload();
        const preview = await fetchJson('/api/local-agent/preview', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            question: localAgentPayload.question || '',
            source_cards: cards,
            run_id: localAgentPayload?.context_manifest?.run_id || '',
            ...config
          })
        });
        localAgentPreview = preview;
        const manifest = preview.context_manifest || {};
        const lanes = manifest.lane_counts || {};
        localAgentPreviewSummary.innerHTML = `<strong>Approval required.</strong> ${escapeHtml(manifest.entry_count || 0)} source blocks · ${Number(manifest.total_chars || 0).toLocaleString()} characters · Maine law ${escapeHtml(lanes.legal_authority || 0)} · private records ${escapeHtml(lanes.private_record || 0)}.<br><span class="muted">Destination: ${escapeHtml(preview.model?.endpoint_host || '')}:${escapeHtml(preview.model?.endpoint_port || '')} (${escapeHtml(preview.model?.endpoint_class || 'loopback')}).</span>`;
        localAgentContextList.innerHTML = (manifest.entries || []).map((entry) => `<article class="local-agent-context-item ${entry.lane === 'private_record' ? 'is-private' : 'is-authority'} ${entry.instruction_like_text_detected ? 'is-quarantined' : ''}">
          <header><span class="context-index">${escapeHtml(entry.index)}</span><strong>${escapeHtml(entry.title)}</strong><span class="badge ${entry.lane === 'private_record' ? 'warn' : 'good'}">${entry.lane === 'private_record' ? 'Private record' : 'Maine law'}</span>${entry.instruction_like_text_detected ? '<span class="badge warn">instructions quarantined</span>' : ''}</header>
          <small>${escapeHtml(entry.locator || entry.source_id)} · ${Number(entry.char_count || 0).toLocaleString()} characters · SHA-256 ${escapeHtml(String(entry.content_sha256 || '').slice(0, 18))}…</small>
          <p>${escapeHtml(entry.preview || '')}</p>
        </article>`).join('');
        localAgentSecurityReport.textContent = JSON.stringify({
          manifest_sha256: manifest.manifest_sha256,
          exact_context_sha256: manifest.exact_context_sha256,
          injection_report: preview.injection_report,
          model: preview.model
        }, null, 2);
        localAgentRun.disabled = Boolean(preview.injection_report?.direct_prompt_blocked);
        localAgentStatus.textContent = preview.injection_report?.direct_prompt_blocked
          ? 'Run blocked: the user prompt attempted to override protected instructions.'
          : 'Nothing has been transmitted. Review the source list, then approve the exact hash.';
      } catch (err) {
        localAgentPreview = null;
        localAgentPreviewSummary.innerHTML = `<span class="status-bad">Could not build the local model preview: ${escapeHtml(err.message)}</span>`;
        localAgentContextList.textContent = '';
        localAgentSecurityReport.textContent = '';
        localAgentStatus.textContent = 'Nothing was transmitted.';
      } finally {
        localAgentBusy = false;
        localAgentRefreshPreview.disabled = false;
      }
    }

    function openLocalAgentDialog(payload, owner) {
      if (!localAgentModal || !payload) return;
      localAgentPayload = payload;
      localAgentOwner = owner || document.activeElement;
      localAgentPreview = null;
      try {
        const saved = JSON.parse(window.localStorage.getItem('mfl-local-agent-settings') || '{}');
        if (saved.provider) localAgentProvider.value = saved.provider;
        if (saved.endpoint) localAgentEndpoint.value = saved.endpoint;
        if (saved.model) localAgentModel.value = saved.model;
      } catch (err) {}
      localAgentModal.hidden = false;
      localAgentModal.setAttribute('aria-hidden', 'false');
      if (localAgentBackdrop) { localAgentBackdrop.hidden = false; localAgentBackdrop.setAttribute('aria-hidden', 'false'); }
      document.body.classList.add('local-agent-open');
      localAgentPreviewSummary.textContent = 'Preparing the exact local context manifest…';
      localAgentContextList.textContent = '';
      localAgentSecurityReport.textContent = '';
      localAgentStatus.textContent = 'Nothing has been transmitted.';
      window.requestAnimationFrame(() => localAgentClose?.focus());
      refreshLocalAgentPreview();
    }

    async function runApprovedLocalAgent() {
      if (!localAgentPayload || !localAgentPreview || localAgentBusy) return;
      localAgentBusy = true;
      localAgentRun.disabled = true;
      localAgentRefreshPreview.disabled = true;
      localAgentStatus.textContent = 'Running the approved context through the loopback local model…';
      try {
        const config = localAgentConfigPayload();
        window.localStorage.setItem('mfl-local-agent-settings', JSON.stringify(config));
        const result = await fetchJson('/api/local-agent/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            question: localAgentPayload.question || '',
            source_cards: localAgentSourceCards(localAgentPayload),
            run_id: localAgentPreview.context_manifest?.run_id || '',
            approved_manifest_sha256: localAgentPreview.context_manifest?.manifest_sha256 || '',
            retrieval_diagnostics: localAgentPayload.retrieval_diagnostics || localAgentPayload?.metadata?.retrieval_diagnostics || {},
            ...config
          })
        });
        const original = localAgentPayload;
        closeLocalAgentDialog();
        const displayPayload = {
          ...result,
          question: original.question,
          citations: sourceItemsFromPayload(original),
          handoff_safe_source_cards: original.handoff_safe_source_cards || [],
          local_agent_result: true,
          structured_answer: null
        };
        addMessage('assistant', result.answer || 'The local model returned no text.', displayPayload);
        lastPayload = displayPayload;
        lastSources = displayPayload.citations || [];
        renderLatestAnswer(displayPayload);
        renderSources(displayPayload.citations || []);
        renderBadges(displayPayload);
        showToast('Loopback local model result added with provenance.');
      } catch (err) {
        localAgentStatus.innerHTML = `<span class="status-bad">Local model run failed: ${escapeHtml(err.message)}</span>`;
        localAgentRun.disabled = false;
      } finally {
        localAgentBusy = false;
        localAgentRefreshPreview.disabled = false;
      }
    }

    function renderInlineSourceCard(item, index, payload, hidden = false) {
      const meta = item?.metadata || item || {};
      const lane = sourceLane(item);
      const title = item?.title || meta.title || meta.id || 'Source';
      const sourceType = String(meta.source_type || meta.source_class || 'source').replaceAll('_', ' ');
      const citation = item?.citation || meta.citation_hint || '';
      const snippet = item?.snippet || item?.text_excerpt || meta.text_excerpt || meta.description || '';
      const pageNumber = Number(meta.page_number || item?.page_number || 0);
      const url = safeExternalUrl(item?.url || meta.url || meta.official_url);
      const binding = recordOpenBindingForPayload(item, payload);
      const duplicateCopies = Math.max(1, Number(meta.duplicate_copy_count || 1));
      const normalizationBadge = meta.match_normalization === 'hyphen_or_ocr_alias'
        ? '<span class="badge">hyphen/OCR match</span>'
        : '';
      const duplicateBadge = duplicateCopies > 1
        ? `<span class="badge">${escapeHtml(duplicateCopies)} identical copies grouped</span>`
        : '';
      const badges = `<span class="badge ${lane === 'records' ? 'warn' : 'good'}">${lane === 'records' ? 'My record' : 'Maine law'}</span><span class="badge">${escapeHtml(sourceType)}</span>${normalizationBadge}${duplicateBadge}`;
      const primaryAction = lane === 'records' && binding
        ? `<button class="primary-action compact-action" data-inline-inspect-record="${index}" type="button">Inspect</button><button class="secondary compact-action" data-inline-draft-record="${index}" type="button">Draft from record</button><button class="secondary compact-action" data-inline-open-record="${index}" type="button">Open original</button>${pageNumber > 0 ? `<button class="secondary compact-action" data-inline-inspect-page="${index}" data-page="${escapeHtml(pageNumber)}" type="button">Open at page ${escapeHtml(pageNumber)}</button>` : ''}`
        : (url ? `<a class="primary-action compact-action" href="${escapeHtml(url)}" target="_blank" rel="noreferrer noopener">Open official source</a>` : '');
      return `<article class="chat-evidence-card source-preview-anchor" data-inline-source-index="${index}" data-inline-source-lane="${lane}"${hidden ? ' hidden' : ''} tabindex="0">
        <div class="source-card-badges">${badges}</div>
        <button class="chat-evidence-title" data-inline-preview-source="${index}" type="button">${escapeHtml(title)}</button>
        <div class="source-card-compact-meta">${citation ? `<span>${escapeHtml(citation)}</span>` : ''}${pageNumber ? `<span>Page ${escapeHtml(pageNumber)}</span>` : ''}<span>${escapeHtml(sourceBasename(item))}</span></div>
        <div class="chat-evidence-snippet">${escapeHtml(snippet || 'Open the source preview for the complete local details.')}</div>
        <div class="source-card-actions">${primaryAction}<button class="secondary compact-action" data-inline-preview-source="${index}" type="button">Preview</button><button class="secondary compact-action" data-inline-copy-source="${index}" type="button">Copy</button></div>
      </article>`;
    }

    function renderInlineEvidence(payload) {
      const items = sourceItemsFromPayload(payload);
      if (!items.length) return '';
      const lawCount = items.filter((item) => sourceLane(item) === 'law').length;
      const recordCount = items.filter((item) => sourceLane(item) === 'records').length;
      const initialLimit = 4;
      return `<section class="chat-evidence-panel" data-inline-evidence-panel aria-label="Evidence used in this answer" tabindex="-1">
        <header class="chat-evidence-header"><div><span>Evidence used in this answer</span><strong>Open the proof here—no side-panel hunt required.</strong></div><button class="secondary compact-action" data-inline-open-workspace type="button">Evidence workspace</button></header>
        <div class="chat-evidence-filters" role="group" aria-label="Filter answer evidence"><button class="is-selected" data-inline-evidence-filter="all" aria-pressed="true" type="button">All <strong>${items.length}</strong></button><button data-inline-evidence-filter="law" aria-pressed="false" type="button">Maine law <strong>${lawCount}</strong></button><button data-inline-evidence-filter="records" aria-pressed="false" type="button">My records <strong>${recordCount}</strong></button></div>
        <div class="chat-evidence-grid">${items.map((item, index) => renderInlineSourceCard(item, index, payload, index >= initialLimit)).join('')}</div>
        ${items.length > initialLimit ? `<button class="chat-evidence-more" data-inline-evidence-more type="button">Show ${items.length - initialLimit} more source${items.length - initialLimit === 1 ? '' : 's'}</button>` : ''}
      </section>`;
    }

    function applyInlineEvidenceView(panel) {
      if (!panel) return;
      const filter = panel.dataset.inlineEvidenceFilter || 'all';
      const expanded = panel.dataset.inlineEvidenceExpanded === 'true';
      const cards = Array.from(panel.querySelectorAll('[data-inline-source-index]'));
      let visibleMatches = 0;
      cards.forEach((card) => {
        const laneMatches = filter === 'all' || card.dataset.inlineSourceLane === filter;
        const shouldShow = laneMatches && (expanded || filter !== 'all' || visibleMatches < 4);
        card.hidden = !shouldShow;
        if (laneMatches) visibleMatches += 1;
      });
      const more = panel.querySelector('[data-inline-evidence-more]');
      if (more) {
        const hiddenMatches = cards.filter((card) => (filter === 'all' || card.dataset.inlineSourceLane === filter) && card.hidden).length;
        more.hidden = hiddenMatches === 0 && !expanded;
        more.textContent = expanded ? 'Show fewer sources' : `Show ${hiddenMatches} more source${hiddenMatches === 1 ? '' : 's'}`;
      }
    }

    function bindInlineEvidenceActions(container, payload) {
      const items = sourceItemsFromPayload(payload);
      container.querySelectorAll('[data-inline-evidence-panel]').forEach((panel) => {
        panel.dataset.inlineEvidenceFilter = 'all';
        panel.dataset.inlineEvidenceExpanded = 'false';
        panel.querySelectorAll('[data-inline-evidence-filter]').forEach((button) => button.addEventListener('click', () => {
          panel.dataset.inlineEvidenceFilter = button.dataset.inlineEvidenceFilter || 'all';
          panel.dataset.inlineEvidenceExpanded = 'false';
          panel.querySelectorAll('[data-inline-evidence-filter]').forEach((row) => {
            const selected = row === button;
            row.classList.toggle('is-selected', selected);
            row.setAttribute('aria-pressed', selected ? 'true' : 'false');
          });
          applyInlineEvidenceView(panel);
        }));
        panel.querySelector('[data-inline-evidence-more]')?.addEventListener('click', () => {
          panel.dataset.inlineEvidenceExpanded = panel.dataset.inlineEvidenceExpanded === 'true' ? 'false' : 'true';
          applyInlineEvidenceView(panel);
        });
        panel.querySelector('[data-inline-open-workspace]')?.addEventListener('click', () => setDrawerOpen(true, 'evidence'));
        applyInlineEvidenceView(panel);
      });

      const itemAt = (button) => items[Number(button.dataset.inlinePreviewSource ?? button.dataset.inlineInspectRecord ?? button.dataset.inlineDraftRecord ?? button.dataset.inlineOpenRecord ?? button.dataset.inlineInspectPage ?? button.dataset.inlineCopySource)];
      container.querySelectorAll('[data-inline-preview-source]').forEach((button) => button.addEventListener('click', async (event) => {
        event.stopPropagation();
        const item = itemAt(button);
        if (!item) return;
        const card = button.closest('.chat-evidence-card') || button;
        showSourcePreview(item, card, {pin: true});
        const sourceId = sourceIdentity(item);
        if (!sourceId) return;
        try {
          const span = item?.metadata?.source_span || {};
          const spanQuery = Number.isInteger(span.start_offset) && Number.isInteger(span.end_offset)
            ? `?start_offset=${encodeURIComponent(span.start_offset)}&end_offset=${encodeURIComponent(span.end_offset)}`
            : '';
          const details = await fetchJson(`/inspect-source/${encodeURIComponent(sourceId)}${spanQuery}`);
          if (sourcePreviewOwner === card && sourcePreviewPinned && !sourcePreviewFlyout.hidden) showSourcePreview(item, card, {pin: true, payload: details});
        } catch (err) {
          if (sourcePreviewOwner === card && sourcePreviewBody && !sourcePreviewFlyout.hidden) sourcePreviewBody.insertAdjacentHTML('beforeend', `<p class="status-warn">Full local metadata was not available: ${escapeHtml(err.message)}</p>`);
        }
      }));
      container.querySelectorAll('[data-inline-inspect-record]').forEach((button) => button.addEventListener('click', (event) => {
        event.stopPropagation();
        const item = itemAt(button);
        openRecordInspector(recordOpenBindingForPayload(item, payload), 0, button);
      }));
      container.querySelectorAll('[data-inline-draft-record]').forEach((button) => button.addEventListener('click', async (event) => {
        event.stopPropagation();
        const item = itemAt(button);
        await importRecordToWorkspace(recordOpenBindingForPayload(item, payload), item?.title || sourceBasename(item));
      }));
      container.querySelectorAll('[data-inline-open-record]').forEach((button) => button.addEventListener('click', (event) => {
        event.stopPropagation();
        const item = itemAt(button);
        openRecordOriginal(recordOpenBindingForPayload(item, payload), 0);
      }));
      container.querySelectorAll('[data-inline-inspect-page]').forEach((button) => button.addEventListener('click', (event) => {
        event.stopPropagation();
        const item = itemAt(button);
        openRecordInspector(recordOpenBindingForPayload(item, payload), Number(button.dataset.page || 0), button);
      }));
      container.querySelectorAll('[data-inline-copy-source]').forEach((button) => button.addEventListener('click', async (event) => {
        event.stopPropagation();
        const item = itemAt(button) || {};
        const handoff = Array.isArray(payload?.handoff_safe_source_cards) ? payload.handoff_safe_source_cards : [];
        const safe = handoff.find((row) => sourceIdentity(row) === sourceIdentity(item)) || item;
        await navigator.clipboard.writeText(JSON.stringify(safe, null, 2));
        button.textContent = 'Copied';
        showToast('Source card copied.');
        window.setTimeout(() => { button.textContent = 'Copy'; }, 1100);
      }));
      container.querySelectorAll('.chat-evidence-card').forEach((card) => card.addEventListener('click', (event) => {
        if (event.target.closest('button, a')) return;
        const item = items[Number(card.dataset.inlineSourceIndex)];
        if (item) showSourcePreview(item, card, {pin: true});
      }));
    }

    function renderMainChatAnswer(text, payload) {
      if (payload?.local_agent_result) {
        return `<div class="chat-rich-answer"><div class="local-agent-answer-banner"><strong>Optional loopback local model analysis</strong><br>This answer used only the exact context you approved. It remains review-required analytical work product.</div><section class="chat-answer-main"><h3>Local model response</h3>${renderParagraphBlocks(text)}</section>${renderInlineEvidence(payload)}${renderContextManifest(payload)}${renderLocalAgentReceipt(payload)}</div>`;
      }
      if (payload?.direct_record_search) {
        return `${renderParagraphBlocks(text)}${renderRecordGroups(payload.record_groups)}${renderContextManifest(payload)}`;
      }
      const structured = payload?.structured_answer || null;
      if (!structured) return `${renderParagraphBlocks(text)}${renderInlineEvidence(payload)}${renderContextManifest(payload)}`;
      const primary = structured.what_this_means || text;
      const immediate = Array.isArray(structured.what_to_do_right_now) ? structured.what_to_do_right_now.slice(0, 4) : [];
      const next = Array.isArray(structured.next_three_steps) ? structured.next_three_steps.slice(0, 3) : [];
      return `<div class="chat-rich-answer"><section class="chat-answer-main"><h3>What this means</h3>${renderParagraphBlocks(primary)}</section>${renderInlineEvidence(payload)}${renderContextManifest(payload)}${renderCriticalDates(structured.critical_dates || structured.intake?.critical_dates)}${renderStructuredSection('What to do right now', immediate)}${renderStructuredSection('Next steps', next)}</div>`;
    }

    function addMessage(role, text, payload = null) {
      const at = new Date().toISOString();
      messages.push({role, text, at});
      const speaker = role === 'user' ? 'You' : 'Maine Family Law LLM';
      const bubbleClass = role === 'user' ? 'user-bubble' : 'assistant-bubble';
      const content = role === 'assistant' ? renderMainChatAnswer(text, payload) : `<p>${escapeHtml(text)}</p>`;
      const evidenceCount = role === 'assistant'
        ? (payload?.direct_record_search ? (Array.isArray(payload?.record_groups) ? payload.record_groups.length : 0) : sourceItemsFromPayload(payload).length)
        : 0;
      const evidenceJump = evidenceCount ? `<button class="message-evidence-jump" data-message-evidence-jump type="button">Evidence ${evidenceCount}</button>` : '';
      const draftAction = role === 'assistant' ? '<button class="message-draft-action" data-message-save-draft type="button">Save as draft</button>' : '';
      const localAgentAction = role === 'assistant' && payload?.local_agent_available && !payload?.local_agent_result
        ? '<button class="message-local-agent-action" data-message-local-agent type="button">Ask local model</button>'
        : '';
      const legalEvidenceCount = role === 'assistant' ? sourceItemsFromPayload(payload).filter((item) => sourceLane(item) !== 'records').length : 0;
      const authorityVerifyAction = legalEvidenceCount
        ? '<button class="message-authority-verify-action" data-message-authority-verify type="button">Verify support</button>'
        : '';
      const wrapper = document.createElement('div');
      wrapper.className = `message ${role}`;
      wrapper.innerHTML = `<div class="message-bubble ${bubbleClass}"><div class="message-speaker"><strong>${speaker}</strong><div class="message-speaker-meta">${draftAction}${localAgentAction}${authorityVerifyAction}${evidenceJump}<span>${formatLocalTime(at)}${role === 'assistant' ? ' <span class="message-verified" aria-label="Response complete">✓</span>' : ''}</span></div></div><div class="message-content">${content}</div></div>`;
      transcript.appendChild(wrapper);
      if (role === 'assistant' && payload) bindInlineEvidenceActions(wrapper, payload);
      if (payload?.direct_record_search) bindRecordOpenActions(wrapper);
      wrapper.querySelector('[data-message-save-draft]')?.addEventListener('click', () => saveAnswerAsDraft(text, payload));
      wrapper.querySelector('[data-message-local-agent]')?.addEventListener('click', (event) => openLocalAgentDialog(payload, event.currentTarget));
      wrapper.querySelector('[data-message-authority-verify]')?.addEventListener('click', (event) => openAuthorityVerification(text, payload, event.currentTarget));
      wrapper.querySelector('[data-message-evidence-jump]')?.addEventListener('click', () => {
        const target = wrapper.querySelector('.chat-evidence-panel, .record-results');
        target?.scrollIntoView({behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
        target?.focus({preventScroll: true});
      });
      if (chatScroll) {
        window.requestAnimationFrame(() => {
          if (role === 'assistant') wrapper.scrollIntoView({block: 'start'});
          else chatScroll.scrollTop = chatScroll.scrollHeight;
        });
      }
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
      updateTrustStatus();
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
        question.setAttribute('aria-invalid', 'true');
        answer.textContent = 'Type a Maine family-law question first.';
        question.focus({preventScroll: true});
        return;
      }
      question.removeAttribute('aria-invalid');
      sending = true;
      requestAbortReason = '';
      askButton.disabled = true;
      askButton.setAttribute('aria-label', 'Sending question. Use Stop to cancel.');
      chatPanel?.setAttribute('aria-busy', 'true');
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
        updateTrustStatus();
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
          if (!question.value.trim()) question.value = text;
          const serviceDisconnected = requestAbortReason === 'service_disconnected';
          answer.innerHTML = serviceDisconnected
            ? '<div class="answer-body"><div class="answer-callout status-bad"><strong>The local service disconnected before the answer was ready.</strong><br>Your question was restored. Your draft, conversation, and records remain local and unchanged. Reconnect, then send again.</div></div>'
            : '<div class="answer-body"><div class="answer-callout"><strong>The request was stopped.</strong><br>Your question was restored. Any completed source retrieval remains visible; no partial answer is presented as complete.</div></div>';
          showToast(serviceDisconnected ? 'Local service disconnected. Your draft was restored.' : 'Request stopped.');
          question.focus({preventScroll: true});
          return;
        }
        if (!question.value.trim()) question.value = text;
        question.style.height = 'auto';
        question.style.height = `${Math.min(question.scrollHeight, 180)}px`;
        const info = safeErrorInfo(err);
        answer.innerHTML = `<div class="answer-body">${renderRecoverableError(err, {title: 'The answer could not be completed'})}</div>`;
        addMessage('assistant', `${info.message} Error code: ${info.code}. ${info.recovery}`);
        answerBadges.innerHTML = '<span class="badge bad">error</span><span class="badge warn">server response handled</span>';
        sourceCards.innerHTML = '<section class="empty-state"><strong>No new source cards were added.</strong><p>Your prior matter data and originals were not changed. Confirm the active matter and local service, then retry.</p></section>';
        handoffPanel.textContent = 'No reviewer handoff metadata because the request failed.';
        checkLocalService({announce: true});
        question.focus({preventScroll: true});
      } finally {
        sending = false;
        askButton.disabled = false;
        askButton.removeAttribute('aria-label');
        chatPanel?.removeAttribute('aria-busy');
        activeRequestController = null;
        requestAbortReason = '';
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

    function authorityQueryParams() {
      const params = new URLSearchParams();
      const query = (authoritySearch?.value || '').trim();
      if (query) params.set('query', query);
      const sourceClass = authoritySourceClassFilter?.value || '';
      if (sourceClass) params.set('source_class', sourceClass);
      const freshness = authorityFreshnessFilter?.value || '';
      if (freshness) params.set('freshness', freshness);
      const issueTag = (authorityIssueFilter?.value || '').trim();
      if (issueTag) params.set('issue_tag', issueTag);
      params.set('limit', '200');
      params.set('offset', '0');
      return params.toString();
    }

    function updateAuthorityLibrarySummary(payload) {
      const counts = payload?.source_counts || payload?.counts || {};
      const classCounts = payload?.source_class_counts || {};
      const total = Number(payload?.count ?? counts.total ?? 0);
      const fresh = Number(counts.fresh || 0);
      const stale = Number(counts.stale || 0);
      const unknown = Number(counts.unknown || 0);
      const failed = Number(counts.retrieval_failed || 0) + Number(counts.parser_failed || 0);
      const buildId = payload?.build_id || payload?.active_build_id || payload?.build?.build_id || 'Not loaded';
      if (authorityLibraryBuildId) authorityLibraryBuildId.textContent = buildId || 'Not loaded';
      if (authorityLibraryCounts) authorityLibraryCounts.textContent = `${total.toLocaleString()} total`;
      if (authorityLibraryClassCounts) {
        authorityLibraryClassCounts.textContent = `${Object.entries(classCounts).map(([key, value]) => `${key}: ${value}`).join(' · ') || 'No official sources indexed.'}`;
        if (authorityLibraryLastUpdate) {
          authorityLibraryLastUpdate.textContent = payload?.last_successful_update || payload?.generated_at || 'No successful update yet.';
        }
      }
      if (authorityLibraryStatus) {
        if (payload?.running_update_job?.job_id) {
          authorityLibraryStatus.dataset.jobId = payload.running_update_job.job_id;
        } else {
          delete authorityLibraryStatus.dataset.jobId;
        }
        authorityLibraryStatus.textContent = payload?.message || `Fresh ${fresh} · stale ${stale} · unknown ${unknown} · failed ${failed}.`;
      }
      if (authorityUpdateProgress) {
        if (payload?.running_update_job) {
          authorityUpdateProgress.textContent = `${payload.running_update_job.status || 'running'} · ${payload.running_update_job.message || 'update in progress'}`;
        } else if (payload?.last_update_report?.status && payload.last_update_report.status !== 'pass') {
          authorityUpdateProgress.textContent = `Last update: ${payload.last_update_report.status}.`;
        } else {
          authorityUpdateProgress.textContent = 'No authority update is running.';
        }
      }
      // Only the status response is authoritative for activation. Source-list
      // responses intentionally omit `active`; merging one as a fresh trust
      // payload used to downgrade a verified build to "unavailable" after the
      // cards finished loading.
      if (payload && Object.prototype.hasOwnProperty.call(payload, 'active')) {
        authorityTrustPayload = {...payload, source_count: total};
      } else if (!authorityTrustPayload && payload) {
        authorityTrustPayload = {
          ...payload,
          active: payload.status === 'pass' && total > 0,
          source_count: total,
        };
      }
      updateTrustStatus();
    }

    async function loadAuthorityStatus() {
      try {
        const payload = await fetchJson('/api/authority/status');
        updateAuthorityLibrarySummary(payload);
        return payload;
      } catch (err) {
        authorityTrustPayload = {active: false, source_count: 0, blockers: [safeErrorInfo(err).code]};
        updateTrustStatus();
        if (authorityLibraryStatus) {
          authorityLibraryStatus.innerHTML = renderRecoverableError(err, {title: 'Official authority is unavailable'});
        }
        return null;
      }
    }

    async function loadSources() {
      sourcesButton.disabled = true;
      try {
        const payload = await fetchJson(`/api/authority/sources?${authorityQueryParams()}`);
        const cards = Array.isArray(payload) ? payload : (payload.sources || []);
        renderSources(cards);
        updateAuthorityLibrarySummary(payload);
      } catch (err) {
        try {
          const payload = await fetchJson('/sources');
          const cards = Array.isArray(payload) ? payload : (payload.sources || []);
          renderSources(cards);
        } catch (fallbackErr) {
          sourceCards.innerHTML = renderRecoverableError(fallbackErr || err, {title: 'Sources could not be loaded'});
        }
      } finally {
        sourcesButton.disabled = false;
      }
    }

    async function updateAuthorityLibrary() {
      if (authorityUpdateButton) authorityUpdateButton.disabled = true;
      try {
        const liveRequested = !authorityFixtureMode?.checked && !authorityDryRun?.checked;
        if (liveRequested && !authorityNetworkAck?.checked) {
          const confirmed = window.confirm('Live official-source updates may use the network and fetch public Maine authority. Continue?');
          if (!confirmed) {
            if (authorityUpdateProgress) authorityUpdateProgress.textContent = 'Live update canceled before network use.';
            return;
          }
          if (authorityNetworkAck) authorityNetworkAck.checked = true;
        }
        if (authorityUpdateProgress) {
          authorityUpdateProgress.textContent = authorityDryRun?.checked ? 'Running dry-run validation…' : 'Submitting update request…';
        }
        const payload = await fetchJson('/api/authority/update', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            dry_run: Boolean(authorityDryRun?.checked),
            fixture_mode: Boolean(authorityFixtureMode?.checked),
            allow_live: !authorityFixtureMode?.checked && !authorityDryRun?.checked,
            network_acknowledged: Boolean(authorityNetworkAck?.checked),
            force_refresh: Boolean(authorityForceRefresh?.checked),
            source_classes: authoritySourceClassFilter?.value ? [authoritySourceClassFilter.value] : [],
          }),
        });
        updateAuthorityLibrarySummary(payload);
        if (payload?.status === 'queued' || payload?.status === 'running') {
          window.setTimeout(async () => {
            await loadAuthorityStatus();
            await loadSources();
          }, 1200);
        } else {
          await loadAuthorityStatus();
          await loadSources();
        }
      } catch (err) {
        if (authorityUpdateProgress) authorityUpdateProgress.innerHTML = renderRecoverableError(err, {title: 'Authority update could not finish'});
      } finally {
        if (authorityUpdateButton) authorityUpdateButton.disabled = false;
      }
    }

    async function cancelAuthorityLibraryUpdate() {
      try {
        const payload = await fetchJson('/api/authority/update/cancel', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({job_id: authorityLibraryStatus?.dataset.jobId || ''}),
        });
        updateAuthorityLibrarySummary(payload);
      } catch (err) {
        if (authorityUpdateProgress) authorityUpdateProgress.innerHTML = renderRecoverableError(err, {title: 'Cancellation could not be confirmed'});
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
        return `<button class="secondary example" data-pack-prompt="${escapeHtml(row.prompt)}" data-pack-style="${escapeHtml(row.recommended_style || 'checklist')}" type="button">
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
        return `<button class="secondary example" data-library-prompt="${escapeHtml(prompt)}" data-library-topic="${escapeHtml(item.topic)}" type="button">
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
    stopButton?.addEventListener('click', () => {
      requestAbortReason = 'user_cancelled';
      activeRequestController?.abort();
    });
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
    authorityUpdateButton?.addEventListener('click', updateAuthorityLibrary);
    authorityUpdateCancelButton?.addEventListener('click', cancelAuthorityLibraryUpdate);
    authorityUpdateRefreshButton?.addEventListener('click', async () => {
      await loadAuthorityStatus();
      await loadSources();
    });
    [authoritySearch, authoritySourceClassFilter, authorityFreshnessFilter, authorityIssueFilter].forEach((field) => {
      field?.addEventListener('input', () => loadSources());
      field?.addEventListener('change', () => loadSources());
    });
    [authorityDryRun, authorityFixtureMode, authorityForceRefresh].forEach((field) => {
      field?.addEventListener('change', () => loadAuthorityStatus());
    });
    authorityNetworkAck?.addEventListener('change', () => loadAuthorityStatus());
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
    quickNewCorpus?.addEventListener('click', () => {
      setWorkflowFocus('matter');
      setDrawerOpen(true, 'setup');
      window.setTimeout(() => corpusSelect?.focus({preventScroll: true}), 20);
      showToast('Select an existing local corpus here, or use the desktop launcher to create one.');
    });
    quickOpenWorkspace?.addEventListener('click', () => openDocumentWorkspace());
    quickLocalWorkbench?.addEventListener('click', openLocalWorkbench);
    localWorkbenchButton?.addEventListener('click', openLocalWorkbench);
    localWorkbenchClose?.addEventListener('click', closeLocalWorkbench);
    localWorkbenchRefresh?.addEventListener('click', loadLocalWorkbenchStatus);
    localWorkbenchReleaseReadiness?.addEventListener('click', inspectLocalWorkbenchReleaseReadiness);
    localWorkbenchSavePreferences?.addEventListener('click', saveLocalWorkbenchPreferences);
    localWorkbenchOverlay?.addEventListener('mousedown', (event) => {
      if (event.target === localWorkbenchOverlay) closeLocalWorkbench();
    });
    quickExportChat?.addEventListener('click', () => downloadButton?.click());
    documentWorkspaceClose?.addEventListener('click', closeDocumentWorkspace);
    documentWorkspaceBackdrop?.addEventListener('click', closeDocumentWorkspace);
    documentWorkspaceStages.forEach((button) => button.addEventListener('click', () => openDocumentWorkspaceStage(button.dataset.documentStage)));
    documentWorkspaceRefresh?.addEventListener('click', () => loadDocumentWorkspaceDocuments(documentWorkspaceState.active?.document_id || ''));
    documentReviewQueueRefresh?.addEventListener('click', loadDocumentReviewQueue);
    documentWorkspaceNew?.addEventListener('click', () => newWorkspaceDraft());
    documentWorkspaceSaveNew?.addEventListener('click', saveWorkspaceNewDraft);
    documentWorkspacePropose?.addEventListener('click', proposeWorkspaceRevision);
    documentWorkspaceCommit?.addEventListener('click', commitWorkspaceRevision);
    documentWorkspaceReject?.addEventListener('click', rejectWorkspaceRevision);
    documentWorkspaceExportTxt?.addEventListener('click', () => workspaceDownload(documentWorkspaceState.active?.document_id, 'txt'));
    documentWorkspaceExportMd?.addEventListener('click', () => workspaceDownload(documentWorkspaceState.active?.document_id, 'md'));
    documentWorkspaceExportDocx?.addEventListener('click', () => workspaceDownload(documentWorkspaceState.active?.document_id, 'docx'));
    documentWorkspaceDelete?.addEventListener('click', softDeleteWorkspaceDocument);
    documentWorkspaceRestore?.addEventListener('click', restoreWorkspaceDocument);
    documentWorkspaceDocxLoad?.addEventListener('click', loadWorkspaceDocxParagraphs);
    documentWorkspaceDocxApply?.addEventListener('click', applyWorkspaceTrackedDocxEdit);
    documentReviewPrepare?.addEventListener('click', prepareDocumentReview);
    documentReviewCommit?.addEventListener('click', commitDocumentReview);
    findingsFormsApproved?.addEventListener('change', updateWorkspaceControls);
    findingsFormsBuild?.addEventListener('click', buildFindingsFormsReview);
    findingsFormsComplete?.addEventListener('click', completeFindingsFormsWorkingCopy);
    filingPacketExclusive?.addEventListener('change', updateWorkspaceControls);
    filingPacketApproved?.addEventListener('change', updateWorkspaceControls);
    filingPacketAssign?.addEventListener('click', assignFilingPacketReviewer);
    filingPacketRefresh?.addEventListener('click', () => loadFilingPacketStatus(documentWorkspaceState.active?.document_id || ''));
    filingPacketBuild?.addEventListener('click', buildReviewedFilingPacket);
    authorityImpactBase?.addEventListener('change', updateWorkspaceControls);
    authorityImpactTarget?.addEventListener('change', updateWorkspaceControls);
    authorityImpactApproved?.addEventListener('change', updateWorkspaceControls);
    authorityImpactRefresh?.addEventListener('click', () => loadAuthorityImpactStatus(documentWorkspaceState.active?.document_id || ''));
    authorityImpactAnalyze?.addEventListener('click', analyzeAuthorityImpact);
    authorityImpactBuild?.addEventListener('click', buildAuthorityImpactPacket);

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
      const tabs = Array.from(document.querySelectorAll('[data-drawer-tab]'));
      tabs.forEach((button, index) => {
        const active = button.dataset.drawerTab === name;
        if (!button.id) button.id = `drawer-tab-${button.dataset.drawerTab || index}`;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
        button.tabIndex = active ? 0 : -1;
      });
      document.querySelectorAll('[data-drawer-panel]').forEach((panel, index) => {
        const tab = tabs.find((button) => button.dataset.drawerTab === panel.dataset.drawerPanel);
        if (!panel.id) panel.id = `drawer-panel-${panel.dataset.drawerPanel || index}-${index}`;
        panel.setAttribute('role', 'tabpanel');
        if (tab) panel.setAttribute('aria-labelledby', tab.id);
        panel.hidden = panel.dataset.drawerPanel !== name;
      });
    }

    focusModeButton?.addEventListener('click', () => setDrawerOpen(document.body.dataset.drawer !== 'open', '', {userInitiated: true}));
    closeDrawerButton?.addEventListener('click', () => setDrawerOpen(false, '', {userInitiated: true}));
    drawerBackdrop?.addEventListener('click', () => setDrawerOpen(false, '', {userInitiated: true}));
    document.querySelectorAll('[data-drawer-tab]').forEach((button) => {
      button.addEventListener('click', () => selectDrawerTab(button.dataset.drawerTab || 'setup'));
      button.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const tabs = Array.from(document.querySelectorAll('[data-drawer-tab]'));
        const current = Math.max(0, tabs.indexOf(button));
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        selectDrawerTab(tabs[next].dataset.drawerTab || 'setup');
        tabs[next].focus({preventScroll: true});
      });
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
    recordCardFilter?.addEventListener('input', applyRecordCardFilter);
    recordCardFilter?.addEventListener('search', applyRecordCardFilter);
    recordCardFilterClear?.addEventListener('click', () => {
      if (recordCardFilter) recordCardFilter.value = '';
      applyRecordCardFilter();
      recordCardFilter?.focus({preventScroll: true});
    });
    connectionRetry?.addEventListener('click', () => checkLocalService({announce: true}));
    window.addEventListener('online', () => checkLocalService({announce: true}));
    window.addEventListener('offline', () => renderLocalConnectionState(false, {announce: true}));
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') checkLocalService({announce: true});
    });
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
    checkLocalService();
    window.setInterval(() => {
      if (document.visibilityState === 'visible') checkLocalService({announce: true});
    }, 30000);
    if (viewportProof) {
      window.addEventListener('load', () => {
        viewportProof.textContent = `innerWidth=${window.innerWidth}; scrollWidth=${document.documentElement.scrollWidth}; bodyClientWidth=${document.body.clientWidth}`;
      });
    }
    loadCorpusLibrary();
    loadQuestionLibrary();
    loadPromptPacks();
    loadRuntimeDiagnostics();
    loadAuthorityStatus();
    loadSources();
    loadLocalWorkbenchStatus();


    const commandDefinitions = [
      {id: 'new_conversation', group: 'Conversation', label: 'New conversation', hint: 'Clear the transcript but keep the active matter', aliases: 'new chat reset start over', run: () => newChatButton?.click()},
      {id: 'focus_composer', group: 'Conversation', label: 'Focus the question box', hint: 'Start typing immediately', aliases: 'write ask compose message', run: () => question?.focus()},
      {id: 'change_answer_style', group: 'Conversation', label: 'Change conversation settings', hint: 'Role, answer style and issue context', aliases: 'role tone style settings', run: () => openOverlay(welcomeOverlay)},
      {id: 'copy_settings_link', group: 'Conversation', label: 'Copy privacy-safe settings link', hint: 'Excludes questions, matter context, records and local paths', aliases: 'share link safe', run: () => copyLinkButton?.click()},
      {id: 'research_maine_law', group: 'Research', label: 'Research Maine law', hint: 'Use official and source-backed Maine-law material', aliases: 'statute rule court authority', run: () => setSearchMode('maine_law')},
      {id: 'search_my_records', group: 'Research', label: 'Search my records', hint: 'Search only the active private matter', aliases: 'documents case corpus files', run: () => setSearchMode('my_records')},
      {id: 'search_both_separately', group: 'Research', label: 'Search law and records separately', hint: 'Keep authority and matter facts in distinct lanes', aliases: 'both combined compare', run: () => setSearchMode('both')},
      {id: 'choose_matter', group: 'Matter', label: 'Choose active matter', hint: 'Open the local corpus library', aliases: 'case family client corpus', run: () => setDrawerOpen(true, 'setup')},
      {id: 'open_authority_library', group: 'Matter', label: 'Open Maine Authority Library', hint: 'Review official source counts and freshness', aliases: 'official law statutes rules forms opinions', run: () => { setDrawerOpen(true, 'setup'); window.setTimeout(() => authoritySearch?.focus({preventScroll: true}), 20); }},
      {id: 'open_document_intelligence', group: 'Evidence', label: 'Open document intelligence', hint: 'Inspect OCR, privacy review, and preservation copies', aliases: 'ocr redact preserve compare duplicate', run: () => openDocumentIntelligence()},
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
    trustRecordAction?.addEventListener('click', () => setDrawerOpen(true, 'setup'));
    trustAuthorityAction?.addEventListener('click', () => {
      setDrawerOpen(true, 'setup');
      window.setTimeout(() => authoritySearch?.focus({preventScroll: true}), 20);
    });
    trustReviewAction?.addEventListener('click', () => setDrawerOpen(true, 'review'));
    workflowActions.forEach((button) => button.addEventListener('click', async () => {
      const workflow = button.dataset.workflowAction || 'research';
      setWorkflowFocus(workflow);
      if (workflow === 'research') {
        question?.focus({preventScroll: true});
      } else if (workflow === 'matter') {
        setDrawerOpen(true, 'setup');
      } else if (workflow === 'authority') {
        setDrawerOpen(true, 'setup');
        window.setTimeout(() => authoritySearch?.focus({preventScroll: true}), 20);
      } else if (workflow === 'intelligence') {
        await openDocumentIntelligence(button);
      } else if (workflow === 'timeline') {
        await openEvidenceWorkProduct(button);
      } else if (workflow === 'claims') {
        await openDocumentWorkspace();
        openDocumentWorkspaceStage('filing');
      } else if (workflow === 'coverage') {
        await openMatterCommandCenter(button);
      } else if (workflow === 'enforcement') {
        await openEvidenceWorkProduct(button);
      } else if (workflow === 'findings' || workflow === 'forms') {
        await openDocumentWorkspace();
        openDocumentWorkspaceStage('findings');
      } else if (workflow === 'command') {
        await openMatterCommandCenter(button);
      } else if (workflow === 'evidence') {
        await openEvidenceWorkProduct(button);
      } else if (workflow === 'draft') {
        await openDocumentWorkspace();
      } else if (workflow === 'privacy') {
        openOverlay(privacyOverlay);
      }
      setWorkflowFocus(workflow);
    }));
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
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        closeCommandPalette();
      }
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
      question.removeAttribute('aria-invalid');
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
      const activeInside = activeOverlay.contains(document.activeElement);
      const dialog = activeOverlay.matches('[role="dialog"]') ? activeOverlay : activeOverlay.querySelector('[role="dialog"]');
      if (!activeInside || document.activeElement === dialog) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus({preventScroll: true});
      } else if (event.shiftKey && document.activeElement === first) {
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
      if (event.defaultPrevented) return;
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
        const activeOverlay = Array.from(document.querySelectorAll('.overlay-shell')).reverse().find((overlay) => !overlay.hidden);
        if (activeOverlay) {
          event.preventDefault();
          closeOverlay(activeOverlay);
          return;
        }
        closeOverlay(helpOverlay);
        closeOverlay(welcomeOverlay);
        closeOverlay(commandPalette);
        closeOverlay(justiceOverlay);
        closeOverlay(privacyOverlay);
        closeOverlay(shortcutsOverlay);
        closeOverlay(buildOverlay);
        closeOverlay(matterCommandCenterOverlay);
        closeOverlay(matterIntakeOverlay);
        closeOverlay(ordersWorkspaceOverlay);
        closeOverlay(calendarWorkspaceOverlay);
        closeOverlay(docketWorkspaceOverlay);
        closeOverlay(discoveryWorkspaceOverlay);
        closeOverlay(exhibitsWorkspaceOverlay);
        closeOverlay(statementsWorkspaceOverlay);
        closeOverlay(hearingWorkspaceOverlay);
        closeOverlay(appellateWorkspaceOverlay);
        closeOverlay(uccjeaWorkspaceOverlay);
        closeOverlay(icwaWorkspaceOverlay);
        closeOverlay(careWorkspaceOverlay);
        closeOverlay(safetyWorkspaceOverlay);
        closeOverlay(scheduleWorkspaceOverlay);
        closeOverlay(lateReviewOverlay);
        closeRetrievalWorkbench();
        closeReleasePilotHardening();
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
