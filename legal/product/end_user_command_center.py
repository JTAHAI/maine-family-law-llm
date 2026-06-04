from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "1.98.0"
PACK_SCHEMA = "maine_family_law_llm.end_user_command_center.v1"
AUDIT_SCHEMA = "maine_family_law_llm.end_user_command_center_audit.v1"
ROUTE_SCHEMA = "maine_family_law_llm.end_user_route.v1"

ROLE_ALIASES = {
    "srl": "self_represented",
    "pro_se": "self_represented",
    "pro-se": "self_represented",
    "client": "self_represented",
    "parent": "self_represented",
    "lawyer": "attorney",
    "counsel": "attorney",
    "legal_staff": "paralegal",
    "staff": "paralegal",
    "clinic": "legal_aid",
    "navigator": "court_help",
    "help_center": "court_help",
    "engineer": "developer",
}

ROLE_PROFILES: dict[str, dict[str, Any]] = {
    "self_represented": {
        "label": "I need help understanding what to do next",
        "default_mode": "plain_language",
        "tone": "calm, clear, step-by-step",
        "review_status": "information_only_not_legal_advice",
        "primary_goal": "understand options, deadlines, documents, and questions for a qualified reviewer",
    },
    "attorney": {
        "label": "I am reviewing or drafting legal work",
        "default_mode": "professional_research",
        "tone": "concise, source-first, audit-ready",
        "review_status": "attorney_review_required_until_verified",
        "primary_goal": "move from issue to source cards, authority matrix, draft review, and gate report quickly",
    },
    "paralegal": {
        "label": "I am organizing a file for attorney review",
        "default_mode": "workflow_checklist",
        "tone": "organized, checklist-driven, precise",
        "review_status": "attorney_review_required",
        "primary_goal": "prepare citations, documents, timelines, and missing-information lists",
    },
    "legal_aid": {
        "label": "I am helping screen or prepare a family-law matter",
        "default_mode": "plain_plus_professional",
        "tone": "public-friendly but source-aware",
        "review_status": "attorney_or_qualified_reviewer_required",
        "primary_goal": "triage safely, explain plainly, preserve review handoff",
    },
    "court_help": {
        "label": "I help people find court information",
        "default_mode": "public_help",
        "tone": "neutral, non-advisory, form-and-process focused",
        "review_status": "information_only_not_legal_advice",
        "primary_goal": "route to official forms, logistics, and questions without strategy advice",
    },
    "caregiver": {
        "label": "I care for a child and need to understand my lane",
        "default_mode": "plain_language",
        "tone": "careful, role-limited, safety-aware",
        "review_status": "information_only_not_legal_advice",
        "primary_goal": "separate caregiver role, parental rights, guardianship, DHHS, school, medical, and safety questions",
    },
    "counselor": {
        "label": "I am a counselor or school professional",
        "default_mode": "professional_boundary",
        "tone": "boundary-focused, privacy-aware, non-strategic",
        "review_status": "professional_and_legal_review_required",
        "primary_goal": "avoid legal strategy, protect confidentiality, prepare questions for counsel/supervision",
    },
    "therapist": {
        "label": "I am a therapist handling court-related questions",
        "default_mode": "professional_boundary",
        "tone": "role-limited, clinical-boundary aware",
        "review_status": "professional_and_legal_review_required",
        "primary_goal": "avoid custody opinions and non-delegation problems while organizing safe next questions",
    },
    "admin": {
        "label": "I manage the system",
        "default_mode": "operations",
        "tone": "operational, auditable, concise",
        "review_status": "not_a_legal_output",
        "primary_goal": "audit source hygiene, releases, uptime, policy, and user support",
    },
    "developer": {
        "label": "I build or integrate the system",
        "default_mode": "api_contract",
        "tone": "technical, schema-first, testable",
        "review_status": "not_a_legal_output",
        "primary_goal": "use stable API contracts, tests, and evidence artifacts",
    },
}

SAFETY_INVARIANTS = {
    "source_cards_visible_for_legal_claims": True,
    "review_status_visible_on_every_output": True,
    "filing_ready_disabled_until_all_gates_pass": True,
    "private_matter_files_never_train_shared_models_by_default": True,
    "official_maine_authority_beats_model_memory": True,
    "plain_language_keeps_citations_and_warnings": True,
    "urgent_safety_or_deadline_routes_are_high_priority": True,
}

VISUAL_SYSTEM = {
    "name": "FOCAF Velocity Command Center",
    "style": "gorgeous desktop-class shell with mobile-friendly command cards",
    "principles": [
        "one obvious next action",
        "zero mystery about review status",
        "source cards always within reach",
        "keyboard-first and touch-friendly",
        "fast safe partial result before slow advanced work",
        "calm public-facing language with attorney-grade drilldown",
    ],
    "tokens": {
        "surface": "deep navy glass over warm court-paper panels",
        "accent": "electric cyan for source confidence and gold for review warnings",
        "danger": "coral for deadlines, safety, missing citations, and blocked filing gates",
        "success": "green only for source-tree or workflow checks, never for legal signoff",
        "radius": "large cards, small source chips, compact keyboard controls",
    },
}

KEYBOARD_SHORTCUTS = {
    "/": "focus_global_question_box",
    "ctrl+enter": "submit_current_question",
    "alt+1": "ask_maine_family_law",
    "alt+2": "review_document",
    "alt+3": "draft_working_document",
    "alt+4": "verify_citations",
    "alt+5": "filing_ready_gate",
    "escape": "close_overlay_or_clear_focus",
}

INTENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "ask_maine_family_law": (
        r"\bwhat\b",
        r"\bhow\b",
        r"\bcan i\b",
        r"\bdoes maine\b",
        r"\bbest[- ]interest\b",
        r"\bparental rights\b",
    ),
    "review_document": (
        r"\breview\b",
        r"\bcheck my\b",
        r"\blook at this\b",
        r"\bupload\b",
        r"\bserved\b",
        r"\border\b",
        r"\bpaperwork\b",
    ),
    "draft_working_document": (
        r"\bdraft\b",
        r"\bwrite\b",
        r"\bmotion\b",
        r"\baffidavit\b",
        r"\bletter\b",
        r"\bproposed findings\b",
        r"\bobjection\b",
    ),
    "verify_citations": (
        r"\bcitation\b",
        r"\bcite\b",
        r"\b19-a\b",
        r"\bm\.r\.s\b",
        r"\bcase\b",
        r"\blaw court\b",
    ),
    "verify_quotes": (
        r"\bquote\b",
        r"\bquoted\b",
        r"\bexact words\b",
        r"\bspan\b",
    ),
    "map_evidence": (
        r"\bevidence\b",
        r"\bproof\b",
        r"\bexhibit\b",
        r"\btexts?\b",
        r"\bmessages?\b",
    ),
    "build_timeline": (
        r"\btimeline\b",
        r"\bchronolog",
        r"\bdate order\b",
        r"\bevents\b",
    ),
    "find_forms": (
        r"\bform\b",
        r"\bpacket\b",
        r"\bfm-\d+\b",
        r"\bwhere do i file\b",
    ),
    "filing_ready_gate": (
        r"\bfiling[- ]?ready\b",
        r"\bready to file\b",
        r"\bcan i file\b",
        r"\bsubmit\b",
        r"\bfinal version\b",
    ),
    "plain_language_explainer": (
        r"\bplain language\b",
        r"\bplain english\b",
        r"\bsimple\b",
        r"\bexplain\b",
    ),
}

URGENT_PATTERNS = (
    r"\bemergency\b",
    r"\bunsafe\b",
    r"\babuse\b",
    r"\bviolence\b",
    r"\bpfa\b",
    r"\bprotection from abuse\b",
    r"\bdeadline\b",
    r"\btoday\b",
    r"\btomorrow\b",
    r"\bserved\b",
    r"\bappeal\b",
)

PRIVATE_DATA_PATTERNS = (
    r"\bsocial security\b",
    r"\bssn\b",
    r"\bdate of birth\b",
    r"\btherapy notes?\b",
    r"\bmedical records?\b",
    r"\bminor child\b",
    r"\bsealed\b",
    r"\bconfidential\b",
)


@dataclass(frozen=True)
class CommandAction:
    action_id: str
    label: str
    short_label: str
    description: str
    endpoint: str
    icon: str
    latency_target_ms: int
    required_inputs: tuple[str, ...]
    output_artifacts: tuple[str, ...]
    default_review_status: str
    source_cards_required: bool
    roles: tuple[str, ...] = tuple(ROLE_PROFILES.keys())
    gorgeous_hint: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "label": self.label,
            "short_label": self.short_label,
            "description": self.description,
            "endpoint": self.endpoint,
            "icon": self.icon,
            "latency_target_ms": self.latency_target_ms,
            "required_inputs": list(self.required_inputs),
            "output_artifacts": list(self.output_artifacts),
            "default_review_status": self.default_review_status,
            "source_cards_required": self.source_cards_required,
            "roles": list(self.roles),
            "gorgeous_hint": self.gorgeous_hint,
        }


COMMAND_ACTIONS: tuple[CommandAction, ...] = (
    CommandAction(
        action_id="ask_maine_family_law",
        label="Ask Maine Family Law",
        short_label="Ask",
        description="Ask a normal question and get a fast source-backed answer envelope.",
        endpoint="/api/ask",
        icon="⚖️",
        latency_target_ms=2500,
        required_inputs=("question", "role"),
        output_artifacts=("answer", "source_cards", "warnings", "review_status"),
        default_review_status="information_only_or_review_required",
        source_cards_required=True,
        gorgeous_hint="Hero search card with source-card confidence chips.",
    ),
    CommandAction(
        action_id="review_document",
        label="Review a Document",
        short_label="Review",
        description="Spot issues, posture, red flags, missing facts, and next questions.",
        endpoint="/api/review",
        icon="📄",
        latency_target_ms=4500,
        required_inputs=("document_text_or_file",),
        output_artifacts=("issue_tree", "posture_summary", "red_flags", "missing_information"),
        default_review_status="review_required",
        source_cards_required=False,
        gorgeous_hint="Drop-zone card with red-flag ribbon and review queue handoff.",
    ),
    CommandAction(
        action_id="draft_working_document",
        label="Draft Working Document",
        short_label="Draft",
        description="Create a review-required motion, letter, affidavit, checklist, or proposed findings draft.",
        endpoint="/api/draft",
        icon="✍️",
        latency_target_ms=7000,
        required_inputs=("draft_type", "facts", "goal"),
        output_artifacts=("draft_packet", "citation_report", "human_review_checklist"),
        default_review_status="review_required_not_filing_ready",
        source_cards_required=True,
        gorgeous_hint="Split-pane drafting workspace with source sidebar and blocker meter.",
    ),
    CommandAction(
        action_id="verify_citations",
        label="Verify Citations",
        short_label="Cites",
        description="Check whether citations resolve to the right source and status.",
        endpoint="/api/citations/verify",
        icon="🔎",
        latency_target_ms=1800,
        required_inputs=("citations",),
        output_artifacts=("citation_verification_table", "source_cards"),
        default_review_status="verification_required",
        source_cards_required=True,
        gorgeous_hint="Compact table with found, not_found, stale_unknown, and official badges.",
    ),
    CommandAction(
        action_id="verify_quotes",
        label="Verify Quotes",
        short_label="Quotes",
        description="Find exact quote spans or block unsupported quote text.",
        endpoint="/api/quotes/verify",
        icon="❝",
        latency_target_ms=2200,
        required_inputs=("quote_text", "source_or_citation"),
        output_artifacts=("quote_span_report", "offsets"),
        default_review_status="verification_required",
        source_cards_required=True,
        gorgeous_hint="Inline highlighter with offset chips.",
    ),
    CommandAction(
        action_id="map_evidence",
        label="Map Facts to Evidence",
        short_label="Evidence",
        description="Connect facts to uploaded records, messages, orders, and source spans.",
        endpoint="/api/evidence/map",
        icon="🧩",
        latency_target_ms=5500,
        required_inputs=("facts", "documents"),
        output_artifacts=("fact_to_evidence_map", "missing_record_checklist"),
        default_review_status="review_required",
        source_cards_required=False,
        gorgeous_hint="Kanban-style fact cards linked to evidence tiles.",
    ),
    CommandAction(
        action_id="build_timeline",
        label="Build Timeline",
        short_label="Timeline",
        description="Turn messy events and documents into a chronological case timeline.",
        endpoint="/api/timeline/build",
        icon="🕒",
        latency_target_ms=5500,
        required_inputs=("documents_or_events",),
        output_artifacts=("timeline", "missing_dates"),
        default_review_status="review_required",
        source_cards_required=False,
        gorgeous_hint="Beautiful timeline lane with date confidence indicators.",
    ),
    CommandAction(
        action_id="find_forms",
        label="Find Forms",
        short_label="Forms",
        description="Find likely official Maine forms and freshness warnings.",
        endpoint="/api/research",
        icon="🧾",
        latency_target_ms=3000,
        required_inputs=("case_type_or_goal",),
        output_artifacts=("form_checklist", "freshness_warnings", "source_cards"),
        default_review_status="review_required",
        source_cards_required=True,
        gorgeous_hint="Form cards with official/freshness badges and required-field preview.",
    ),
    CommandAction(
        action_id="filing_ready_gate",
        label="Check Filing Readiness",
        short_label="Gate",
        description="Explain every blocker before anything can look filing-ready.",
        endpoint="/api/filing-ready/check",
        icon="🚦",
        latency_target_ms=2400,
        required_inputs=("draft_packet", "citation_report", "quote_report", "human_review_status"),
        output_artifacts=("filing_readiness_blocker_report",),
        default_review_status="blocked_not_filing_ready",
        source_cards_required=True,
        gorgeous_hint="High-contrast blocker board with no false green lights.",
    ),
    CommandAction(
        action_id="plain_language_explainer",
        label="Plain-Language Explainer",
        short_label="Explain",
        description="Turn sourced output into plain language without hiding citations or warnings.",
        endpoint="/api/ask",
        icon="💬",
        latency_target_ms=2200,
        required_inputs=("question_or_sourced_answer",),
        output_artifacts=("plain_language_explainer", "source_cards", "questions_for_review"),
        default_review_status="information_only_not_legal_advice",
        source_cards_required=True,
        gorgeous_hint="Readable client-facing card with reviewer handoff button.",
    ),
)


@dataclass(frozen=True)
class EndUserRoute:
    schema: str
    version: str
    role: str
    mode: str
    prompt: str
    matched_actions: tuple[str, ...]
    primary_action: str
    urgency: str
    private_data_boundary: str
    source_cards_required: bool
    review_required: bool
    filing_ready_allowed: bool
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    next_steps: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "role": self.role,
            "mode": self.mode,
            "prompt": self.prompt,
            "matched_actions": list(self.matched_actions),
            "primary_action": self.primary_action,
            "urgency": self.urgency,
            "private_data_boundary": self.private_data_boundary,
            "source_cards_required": self.source_cards_required,
            "review_required": self.review_required,
            "filing_ready_allowed": self.filing_ready_allowed,
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
            "next_steps": list(self.next_steps),
        }


@dataclass(frozen=True)
class CommandCenterPack:
    schema: str
    version: str
    generated_at: str
    title: str
    subtitle: str
    role_profiles: dict[str, dict[str, Any]]
    command_actions: tuple[dict[str, Any], ...]
    safety_invariants: dict[str, bool]
    visual_system: dict[str, Any]
    keyboard_shortcuts: dict[str, str]
    performance_budget: dict[str, int]
    evidence_statement: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "generated_at": self.generated_at,
            "title": self.title,
            "subtitle": self.subtitle,
            "role_profiles": self.role_profiles,
            "command_actions": list(self.command_actions),
            "safety_invariants": self.safety_invariants,
            "visual_system": self.visual_system,
            "keyboard_shortcuts": self.keyboard_shortcuts,
            "performance_budget": self.performance_budget,
            "evidence_statement": self.evidence_statement,
        }


@dataclass(frozen=True)
class CommandCenterAudit:
    schema: str
    version: str
    status: str
    generated_at: str
    action_count: int
    role_count: int
    blockers: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version": self.version,
            "status": self.status,
            "generated_at": self.generated_at,
            "action_count": self.action_count,
            "role_count": self.role_count,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_role(role: str | None) -> str:
    normalized = (role or "self_represented").strip().lower().replace(" ", "_")
    normalized = ROLE_ALIASES.get(normalized, normalized)
    return normalized if normalized in ROLE_PROFILES else "self_represented"


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.I) for pattern in patterns)


def detect_actions(prompt: str) -> tuple[str, ...]:
    text = prompt or ""
    matches = [action_id for action_id, patterns in INTENT_PATTERNS.items() if _matches_any(text, patterns)]
    if not matches:
        matches = ["ask_maine_family_law"]
    action_order = [action.action_id for action in COMMAND_ACTIONS]
    return tuple(action_id for action_id in action_order if action_id in matches)


def action_by_id(action_id: str) -> CommandAction:
    for action in COMMAND_ACTIONS:
        if action.action_id == action_id:
            return action
    return COMMAND_ACTIONS[0]


def route_end_user_intent(prompt: str, *, role: str | None = None) -> EndUserRoute:
    normalized_role = normalize_role(role)
    role_profile = ROLE_PROFILES[normalized_role]
    matched_actions = detect_actions(prompt)
    primary = matched_actions[0]
    urgency = "urgent_safety_deadline_or_court_risk" if _matches_any(prompt, URGENT_PATTERNS) else "normal"

    warnings: list[str] = []
    blockers: list[str] = []
    if urgency != "normal":
        warnings.append("urgent_or_safety_deadline_language_detected_use_official_or_human_help_first")
    if _matches_any(prompt, PRIVATE_DATA_PATTERNS):
        warnings.append("private_or_sensitive_record_language_detected_do_not_paste_private_records_into_public_repo")
    if "filing_ready_gate" in matched_actions:
        blockers.append("filing_ready_export_blocked_until_authority_citations_quotes_facts_forms_and_human_review_pass")

    selected_actions = [action_by_id(action_id) for action_id in matched_actions]
    source_required = any(action.source_cards_required for action in selected_actions)

    next_steps = [
        f"Start with {action_by_id(primary).label}.",
        "Keep review status visible before export or sharing.",
    ]
    if source_required:
        next_steps.append("Show source cards and freshness status for every legal claim.")
    if normalized_role in {"self_represented", "court_help", "caregiver"}:
        next_steps.append("Use plain-language mode and prepare questions for a qualified reviewer.")
    if normalized_role in {"attorney", "legal_aid", "paralegal"}:
        next_steps.append("Run verifier reports before relying on any draft or citation.")

    return EndUserRoute(
        schema=ROUTE_SCHEMA,
        version=VERSION,
        role=normalized_role,
        mode=str(role_profile["default_mode"]),
        prompt=prompt,
        matched_actions=matched_actions,
        primary_action=primary,
        urgency=urgency,
        private_data_boundary="Private matter files stay outside the source repository and do not train shared models by default.",
        source_cards_required=source_required,
        review_required=True,
        filing_ready_allowed=False,
        warnings=tuple(warnings),
        blockers=tuple(blockers),
        next_steps=tuple(next_steps),
    )


def build_command_center_pack() -> CommandCenterPack:
    return CommandCenterPack(
        schema=PACK_SCHEMA,
        version=VERSION,
        generated_at=utc_now(),
        title="Maine Family Law LLM Command Center",
        subtitle="One beautiful front door for fast, source-backed Maine family-law work.",
        role_profiles={key: dict(value) for key, value in ROLE_PROFILES.items()},
        command_actions=tuple(action.as_dict() for action in COMMAND_ACTIONS),
        safety_invariants=dict(SAFETY_INVARIANTS),
        visual_system=dict(VISUAL_SYSTEM),
        keyboard_shortcuts=dict(KEYBOARD_SHORTCUTS),
        performance_budget={
            "home_shell_first_paint_ms": 1000,
            "intent_route_ms": 250,
            "quick_action_card_render_ms": 200,
            "source_card_panel_open_ms": 350,
            "plain_language_explainer_ms": 2200,
            "filing_gate_summary_ms": 2400,
        },
        evidence_statement=(
            "This pass prepares UX, routing, and contracts. It does not claim attorney review, "
            "legal signoff, production deployment, real-matter pilot completion, or filing-ready output."
        ),
    )


def audit_command_center_pack(pack: CommandCenterPack | dict[str, Any]) -> CommandCenterAudit:
    payload = pack.as_dict() if isinstance(pack, CommandCenterPack) else pack
    blockers: list[str] = []
    warnings: list[str] = []

    if payload.get("schema") != PACK_SCHEMA:
        blockers.append("schema_mismatch")
    roles = payload.get("role_profiles", {})
    actions = payload.get("command_actions", [])
    invariants = payload.get("safety_invariants", {})

    for role in ("self_represented", "attorney", "paralegal", "legal_aid", "court_help", "caregiver", "counselor", "therapist"):
        if role not in roles:
            blockers.append(f"missing_role:{role}")

    required_actions = {
        "ask_maine_family_law",
        "review_document",
        "draft_working_document",
        "verify_citations",
        "verify_quotes",
        "map_evidence",
        "build_timeline",
        "find_forms",
        "filing_ready_gate",
        "plain_language_explainer",
    }
    action_ids = {action.get("action_id") for action in actions if isinstance(action, dict)}
    for action_id in sorted(required_actions - action_ids):
        blockers.append(f"missing_action:{action_id}")

    for action in actions:
        if not isinstance(action, dict):
            blockers.append("non_object_action")
            continue
        action_id = str(action.get("action_id", "missing"))
        if not str(action.get("endpoint", "")).startswith("/api/"):
            blockers.append(f"action_endpoint_not_api:{action_id}")
        latency = int(action.get("latency_target_ms") or 0)
        if latency <= 0 or latency > 10000:
            blockers.append(f"action_latency_out_of_budget:{action_id}:{latency}")
        if action.get("default_review_status") == "filing_ready":
            blockers.append(f"action_defaults_to_filing_ready:{action_id}")

    for invariant, expected in SAFETY_INVARIANTS.items():
        if invariants.get(invariant) is not expected:
            blockers.append(f"safety_invariant_missing_or_false:{invariant}")

    if len(actions) < 10:
        warnings.append("fewer_than_10_command_actions")

    return CommandCenterAudit(
        schema=AUDIT_SCHEMA,
        version=str(payload.get("version") or VERSION),
        status="pass" if not blockers else "blocked",
        generated_at=utc_now(),
        action_count=len(actions) if isinstance(actions, list) else 0,
        role_count=len(roles) if isinstance(roles, dict) else 0,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
    )


def render_command_center_html() -> str:
    pack_json = json.dumps(build_command_center_pack().as_dict(), sort_keys=True)
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Maine Family Law LLM Command Center</title>
  <style>
    :root { color-scheme: dark; --bg:#04101f; --panel:#071d33; --paper:#f7f0df; --cyan:#39f4ff; --gold:#ffd66e; --danger:#ff8f81; --ink:#f7fbff; --muted:#b7cad8; --line:rgba(96,221,255,.3); font-family: Inter, ui-sans-serif, system-ui, Segoe UI, Arial, sans-serif; }
    * { box-sizing: border-box; }
    body { margin:0; min-height:100vh; background: radial-gradient(circle at 15% 0%, rgba(57,244,255,.22), transparent 32rem), radial-gradient(circle at 90% 20%, rgba(255,214,110,.16), transparent 28rem), linear-gradient(135deg,#020712,#061a30 52%,#020712); color:var(--ink); }
    .shell { width:min(1220px, calc(100vw - 24px)); margin:12px auto; }
    .hero { display:grid; grid-template-columns:1.2fr .8fr; gap:18px; align-items:stretch; }
    .glass { border:1px solid var(--line); background:linear-gradient(145deg,rgba(9,34,59,.92),rgba(3,11,23,.94)); border-radius:28px; box-shadow:0 30px 70px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.08); }
    .hero-main { padding:32px; position:relative; overflow:hidden; }
    .hero-main:before { content:\"\"; position:absolute; inset:-40%; background:linear-gradient(115deg,transparent,rgba(57,244,255,.11),transparent); transform:rotate(12deg); }
    .hero-main > * { position:relative; }
    h1 { font-size:clamp(2.4rem, 5vw, 5.6rem); line-height:.9; margin:0 0 14px; letter-spacing:-.07em; }
    .tag { color:var(--cyan); font-weight:900; text-transform:uppercase; letter-spacing:.09em; }
    .sub { max-width:760px; color:#e7f7ff; font-size:1.16rem; }
    .search { display:grid; grid-template-columns:1fr auto; gap:10px; margin-top:24px; }
    input, select, button { font:inherit; }
    input, select { width:100%; border:1px solid rgba(255,255,255,.18); border-radius:18px; padding:16px 18px; background:rgba(255,255,255,.08); color:var(--ink); outline:none; }
    input:focus, select:focus { border-color:var(--cyan); box-shadow:0 0 0 3px rgba(57,244,255,.16); }
    button { border:0; border-radius:18px; padding:16px 20px; background:linear-gradient(135deg,#18c8ff,#2355ff); color:white; font-weight:900; cursor:pointer; box-shadow:0 12px 26px rgba(25,100,255,.32); }
    .status { padding:24px; display:flex; flex-direction:column; justify-content:space-between; }
    .badge { display:inline-flex; gap:9px; align-items:center; border:1px solid rgba(255,255,255,.2); border-radius:999px; padding:9px 13px; color:var(--cyan); font-weight:850; width:max-content; }
    .metrics { display:grid; grid-template-columns:repeat(2,1fr); gap:10px; margin-top:20px; }
    .metric { padding:14px; border-radius:18px; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.09); }
    .metric strong { display:block; font-size:1.5rem; color:white; }
    .grid { display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin-top:18px; }
    .card { padding:18px; min-height:184px; display:flex; flex-direction:column; justify-content:space-between; border-radius:24px; border:1px solid var(--line); background:linear-gradient(160deg,rgba(12,42,73,.92),rgba(4,14,28,.96)); box-shadow:0 18px 36px rgba(0,0,0,.28); }
    .card .icon { font-size:2rem; }
    .card h3 { margin:8px 0 6px; font-size:1.05rem; }
    .card p { color:var(--muted); margin:0; font-size:.92rem; }
    .chiprow { display:flex; gap:6px; flex-wrap:wrap; margin-top:12px; }
    .chip { border-radius:999px; padding:5px 8px; background:rgba(57,244,255,.11); color:#c8fbff; font-size:.75rem; border:1px solid rgba(57,244,255,.22); }
    .route { margin-top:18px; padding:18px; border-radius:24px; background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.12); }
    .warning { color:var(--gold); }
    .blocked { color:var(--danger); }
    footer { color:var(--muted); padding:18px 4px 6px; font-size:.92rem; }
    @media (max-width: 980px) { .hero { grid-template-columns:1fr; } .grid { grid-template-columns:repeat(2,1fr); } }
    @media (max-width: 620px) { .search { grid-template-columns:1fr; } .grid { grid-template-columns:1fr; } h1 { font-size:3rem; } }
  </style>
</head>
<body>
  <main class=\"shell\">
    <section class=\"hero\">
      <div class=\"hero-main glass\">
        <div class=\"tag\">Fast. Gorgeous. Source-backed. Review-gated.</div>
        <h1>What do you need to do?</h1>
        <p class=\"sub\">Start with a normal question. The command center routes you to the safest next action, keeps source cards visible, and blocks filing-ready output until every gate passes.</p>
        <div class=\"search\">
          <input id=\"prompt\" aria-label=\"Ask what you need\" placeholder=\"Example: I was served papers today. What do I do first?\" />
          <button id=\"go\">Route me</button>
        </div>
        <div style=\"margin-top:12px\"><select id=\"role\" aria-label=\"Role\"></select></div>
      </div>
      <aside class=\"status glass\">
        <div><span class=\"badge\">● Local-first public source shell</span></div>
        <div class=\"metrics\">
          <div class=\"metric\"><strong>10</strong>fast actions</div>
          <div class=\"metric\"><strong>0</strong>filing-ready shortcuts</div>
          <div class=\"metric\"><strong>Always</strong>review status</div>
          <div class=\"metric\"><strong>Always</strong>source cards</div>
        </div>
      </aside>
    </section>
    <section id=\"route\" class=\"route\">Type a question or choose an action.</section>
    <section id=\"cards\" class=\"grid\"></section>
    <footer>Not legal advice. Not attorney review. Not filing-ready. Built for Maine family-law research, organization, and review-required drafting workflows.</footer>
  </main>
<script>
const pack = {{PACK_JSON}};
const role = document.getElementById('role');
const cards = document.getElementById('cards');
const route = document.getElementById('route');
for (const [key, value] of Object.entries(pack.role_profiles)) {
  const opt = document.createElement('option'); opt.value = key; opt.textContent = value.label; role.appendChild(opt);
}
function card(action) {
  const el = document.createElement('article'); el.className = 'card';
  el.innerHTML = `<div><div class=\"icon\">${action.icon}</div><h3>${action.label}</h3><p>${action.description}</p></div><div class=\"chiprow\"><span class=\"chip\">${action.latency_target_ms}ms target</span><span class=\"chip\">${action.default_review_status}</span></div>`;
  return el;
}
pack.command_actions.forEach(a => cards.appendChild(card(a)));
function routeLocal() {
  const text = document.getElementById('prompt').value.toLowerCase();
  const matches = pack.command_actions.filter(a => text.includes(a.short_label.toLowerCase()) || text.includes(a.label.toLowerCase().split(' ')[0]));
  const action = matches[0] || pack.command_actions.find(a => a.action_id === 'ask_maine_family_law');
  const urgent = /(today|tomorrow|served|deadline|abuse|unsafe|pfa|appeal)/.test(text);
  const filing = /(filing-ready|ready to file|submit|final version|can i file)/.test(text);
  route.innerHTML = `<strong>Start with:</strong> ${action.icon} ${action.label}<br><span>${action.description}</span>` +
    (urgent ? `<br><span class=\"warning\">Urgent/safety/deadline wording detected. Use official or human help first.</span>` : '') +
    (filing ? `<br><span class=\"blocked\">Filing-ready remains blocked until authority, citations, quotes, facts, forms, and human review pass.</span>` : '');
}
document.getElementById('go').addEventListener('click', routeLocal);
document.getElementById('prompt').addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); routeLocal(); ev.currentTarget.value = ''; }});
document.addEventListener('keydown', ev => { if (ev.key === '/') { ev.preventDefault(); document.getElementById('prompt').focus(); }});
</script>
</body>
</html>
""".replace("{{PACK_JSON}}", pack_json)


def write_command_center_pack(output: str | Path) -> dict[str, Any]:
    payload = build_command_center_pack().as_dict()
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def write_command_center_audit(input_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
    report = audit_command_center_pack(payload).as_dict()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
