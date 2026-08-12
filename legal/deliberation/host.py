from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legal.verifiers import LegalOutputVerifier, SourceAuthorityIndex
from legal.verifiers.source_cards import SourceCardStore

from .broker import DeliberationContext, DeliberationToolBroker
from .external_root import DeliberationLayout, external_deliberation_layout
from .schemas import (
    DeliberationEvent,
    DeliberationLimit,
    DeliberationRun,
    FinalSynthesis,
    ClaimLedgerEntry,
    ScopeFreeze,
    WorkerTurnRequest,
    WorkerTurnResult,
    safe_identifier,
    sha256_hex,
    utc_now,
)
from .state_machine import DeliberationStateMachine
from .workers import DeliberationWorker, MockDeliberationWorker

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "maine_deliberation_presets.json"


class DeliberationHostError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class PresetDefinition:
    preset_id: str
    label: str
    description: str
    worker_set: tuple[str, ...]
    worker_roles: tuple[str, ...]
    source_lanes: tuple[str, ...]
    max_rounds: int
    tool_call_limit: int
    required_tools: tuple[str, ...]

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "PresetDefinition":
        return cls(
            preset_id=str(row["preset_id"]),
            label=str(row.get("label") or row["preset_id"]),
            description=str(row.get("description") or ""),
            worker_set=tuple(str(item) for item in row.get("worker_set", [])),
            worker_roles=tuple(str(item) for item in row.get("worker_roles", [])),
            source_lanes=tuple(str(item) for item in row.get("source_lanes", [])),
            max_rounds=int(row.get("max_rounds", 5) or 5),
            tool_call_limit=int(row.get("tool_call_limit", 12) or 12),
            required_tools=tuple(str(item) for item in row.get("required_tools", [])),
        )


class DeliberationPresetCatalog:
    def __init__(self, config_path: str | Path = CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.presets = [PresetDefinition.from_dict(row) for row in payload.get("presets", [])]
        self.by_id = {preset.preset_id: preset for preset in self.presets}

    def get(self, preset_id: str) -> PresetDefinition:
        return self.by_id[preset_id]

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "preset_id": preset.preset_id,
                "label": preset.label,
                "description": preset.description,
                "worker_set": list(preset.worker_set),
                "worker_roles": list(preset.worker_roles),
                "source_lanes": list(preset.source_lanes),
                "max_rounds": preset.max_rounds,
                "tool_call_limit": preset.tool_call_limit,
                "required_tools": list(preset.required_tools),
            }
            for preset in self.presets
        ]


class DeliberationRunStore:
    def __init__(self, layout: DeliberationLayout):
        self.layout = layout
        self.layout.ensure()

    def run_path(self, run_id: str) -> Path:
        return self.layout.runs / f"{run_id}.json"

    def event_path(self, run_id: str) -> Path:
        return self.layout.events / f"{run_id}.jsonl"

    def claim_path(self, run_id: str) -> Path:
        return self.layout.claims / f"{run_id}.json"

    def position_path(self, run_id: str) -> Path:
        return self.layout.positions / f"{run_id}.json"

    def synthesis_path(self, run_id: str) -> Path:
        return self.layout.synthesis / f"{run_id}.json"

    def tool_audit_path(self, run_id: str) -> Path:
        return self.layout.tool_audit / f"{run_id}.jsonl"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            handle.write("\n")

    def save_run(self, run: DeliberationRun) -> None:
        self._write_json(self.run_path(run.run_id), run.as_dict())

    def save_event(self, event: DeliberationEvent) -> None:
        self._append_jsonl(self.event_path(event.run_id), event.as_dict())

    def save_claims(self, run_id: str, claims: list[ClaimLedgerEntry]) -> None:
        self._write_json(self.claim_path(run_id), {"schema_version": "claim_ledger_v1", "run_id": run_id, "claims": [claim.as_dict() for claim in claims]})

    def save_positions(self, run_id: str, positions: list[dict[str, Any]]) -> None:
        self._write_json(self.position_path(run_id), {"schema_version": "worker_positions_v1", "run_id": run_id, "positions": positions})

    def save_synthesis(self, run_id: str, synthesis: FinalSynthesis | None) -> None:
        self._write_json(self.synthesis_path(run_id), {"schema_version": "final_synthesis_v1", "run_id": run_id, "synthesis": synthesis.as_dict() if synthesis else None})

    def append_tool_audit(self, run_id: str, row: dict[str, Any]) -> None:
        self._append_jsonl(self.tool_audit_path(run_id), row)

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        path = self.run_path(run_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def load_events(self, run_id: str) -> list[dict[str, Any]]:
        path = self.event_path(run_id)
        if not path.is_file():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def load_claims(self, run_id: str) -> list[dict[str, Any]]:
        path = self.claim_path(run_id)
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return list(payload.get("claims") or [])

    def load_positions(self, run_id: str) -> list[dict[str, Any]]:
        path = self.position_path(run_id)
        if not path.is_file():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return list(payload.get("positions") or [])

    def load_synthesis(self, run_id: str) -> dict[str, Any] | None:
        path = self.synthesis_path(run_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("synthesis")


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _claim_family_id(claim: str) -> str:
    return sha256_hex({"claim": _normalize_text(claim)})[:16]


def _event(run_id: str, event_type: str, state: str, summary: str, details: dict[str, Any] | None = None, *, round_number: int = 0) -> DeliberationEvent:
    return DeliberationEvent(
        event_id=safe_identifier(f"{run_id}:{event_type}:{state}:{uuid.uuid4().hex}", fallback="event"),
        run_id=run_id,
        event_type=event_type,
        round=round_number,
        state=state,
        summary=summary[:240],
        details=dict(details or {}),
        created_at=utc_now(),
    )


class DeliberationHost:
    def __init__(
        self,
        *,
        project_root: str | Path,
        root: str | Path | None = None,
        state_machine: DeliberationStateMachine | None = None,
        preset_catalog: DeliberationPresetCatalog | None = None,
        worker_registry: dict[str, DeliberationWorker] | None = None,
        tool_broker: DeliberationToolBroker | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = external_deliberation_layout(root, project_root=self.project_root, create=True)
        self.state_machine = state_machine or DeliberationStateMachine()
        self.preset_catalog = preset_catalog or DeliberationPresetCatalog()
        self.tool_broker = tool_broker or DeliberationToolBroker()
        self.store = DeliberationRunStore(self.layout)
        self.workers = worker_registry or self._default_workers()
        self._lock = threading.RLock()

    def _default_workers(self) -> dict[str, DeliberationWorker]:
        return {
            "mock_scope_scout": MockDeliberationWorker("mock_scope_scout", "scope_scout", "first-pass scope analysis", confidence_bias="high"),
            "mock_counterpoint_scout": MockDeliberationWorker("mock_counterpoint_scout", "counterpoint_scout", "credible dissent and rebuttal", confidence_bias="medium"),
            "mock_record_checker": MockDeliberationWorker("mock_record_checker", "record_checker", "record support and contradiction", confidence_bias="high"),
            "mock_omission_hunter": MockDeliberationWorker("mock_omission_hunter", "omission_hunter", "missing sources and gaps", confidence_bias="medium"),
            "mock_contrary_authority": MockDeliberationWorker("mock_contrary_authority", "contrary_authority", "contrary authority challenge", confidence_bias="medium"),
            "mock_missing_context_hunter": MockDeliberationWorker("mock_missing_context_hunter", "missing_context_hunter", "child impact and context gaps", confidence_bias="medium"),
            "mock_verifier": MockDeliberationWorker("mock_verifier", "verifier", "deterministic verification bridge", confidence_bias="high"),
        }

    def _run_dir(self, run_id: str) -> Path:
        return self.layout.runs / f"{run_id}.json"

    def list_presets(self) -> list[dict[str, Any]]:
        return self.preset_catalog.list()

    def list_tools(self) -> list[dict[str, Any]]:
        return self.tool_broker.list_tools()

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            preset_id = str(payload.get("preset_id") or payload.get("preset") or "").strip()
            preset = self.preset_catalog.by_id.get(preset_id) if preset_id else None
            limits = DeliberationLimit(
                max_rounds=int(payload.get("max_rounds") or (preset.max_rounds if preset else 5) or 5),
                time_limit_seconds=int(payload.get("time_limit_seconds") or 600),
                token_limit=int(payload.get("token_limit") or 120_000),
                context_limit_chars=int(payload.get("context_limit_chars") or 80_000),
                tool_call_limit=int(payload.get("tool_call_limit") or (preset.tool_call_limit if preset else 12) or 12),
                worker_call_limit=int(payload.get("worker_call_limit") or 12),
                max_output_chars=int(payload.get("max_output_chars") or 20_000),
            )
            worker_set = [str(item) for item in (payload.get("worker_set") or (preset.worker_set if preset else [])) if str(item).strip()]
            worker_roles = [str(item) for item in (payload.get("worker_roles") or (preset.worker_roles if preset else [])) if str(item).strip()]
            source_lanes = [str(item) for item in (payload.get("source_lanes") or (preset.source_lanes if preset else [])) if str(item).strip()]
            run_id = safe_identifier(payload.get("run_id") or uuid.uuid4().hex, fallback="run")
            run = DeliberationRun(
                run_id=run_id,
                matter_id=safe_identifier(payload.get("matter_id") or "unknown", fallback="matter"),
                question=str(payload.get("question") or "").strip(),
                user_role=str(payload.get("user_role") or "reviewer"),
                jurisdiction=str(payload.get("jurisdiction") or "maine"),
                date_range={"start": str((payload.get("date_range") or {}).get("start") or ""), "end": str((payload.get("date_range") or {}).get("end") or "")},
                desired_output=str(payload.get("desired_output") or "review_required_synthesis"),
                source_lanes=source_lanes,
                worker_set=worker_set,
                worker_roles=worker_roles,
                limits=limits,
                status="draft_scope",
                review_status="review_required",
                cancellation_state="active",
            )
            run.configuration_hash = sha256_hex(
                {
                    "run_id": run.run_id,
                    "matter_id": run.matter_id,
                    "question": run.question,
                    "user_role": run.user_role,
                    "jurisdiction": run.jurisdiction,
                    "date_range": run.date_range,
                    "desired_output": run.desired_output,
                    "source_lanes": run.source_lanes,
                    "worker_set": run.worker_set,
                    "worker_roles": run.worker_roles,
                    "limits": run.limits.as_dict(),
                    "preset_id": preset_id,
                }
            )
            self.store.save_run(run)
            self.store.save_event(_event(run.run_id, "run_created", run.status, "Run draft created", {"preset_id": preset_id, "worker_count": len(worker_set)}))
            return self._run_response(run)

    def _load_or_raise(self, run_id: str) -> DeliberationRun:
        payload = self.store.load_run(safe_identifier(run_id, fallback="run"))
        if payload is None:
            raise DeliberationHostError("run_not_found", "The deliberation run was not found.", status_code=404)
        return self._hydrate_run(payload)

    def _hydrate_run(self, payload: dict[str, Any]) -> DeliberationRun:
        limits = payload.get("limits") or {}
        scope = payload.get("scope_freeze")
        run = DeliberationRun(
            run_id=str(payload.get("run_id") or ""),
            matter_id=str(payload.get("matter_id") or ""),
            question=str(payload.get("question") or ""),
            user_role=str(payload.get("user_role") or ""),
            jurisdiction=str(payload.get("jurisdiction") or ""),
            date_range=dict(payload.get("date_range") or {}),
            desired_output=str(payload.get("desired_output") or ""),
            source_lanes=list(payload.get("source_lanes") or []),
            worker_set=list(payload.get("worker_set") or []),
            worker_roles=list(payload.get("worker_roles") or []),
            limits=DeliberationLimit(
                max_rounds=int(limits.get("max_rounds") or 5),
                time_limit_seconds=int(limits.get("time_limit_seconds") or 600),
                token_limit=int(limits.get("token_limit") or 120_000),
                context_limit_chars=int(limits.get("context_limit_chars") or 80_000),
                tool_call_limit=int(limits.get("tool_call_limit") or 12),
                worker_call_limit=int(limits.get("worker_call_limit") or 12),
                max_output_chars=int(limits.get("max_output_chars") or 20_000),
            ),
            status=str(payload.get("status") or "draft_scope"),
            review_status=str(payload.get("review_status") or "review_required"),
            cancellation_state=str(payload.get("cancellation_state") or "active"),
            created_at=str(payload.get("created_at") or utc_now()),
            updated_at=str(payload.get("updated_at") or utc_now()),
            confirmed_at=str(payload.get("confirmed_at") or ""),
            started_at=str(payload.get("started_at") or ""),
            completed_at=str(payload.get("completed_at") or ""),
            cancelled_at=str(payload.get("cancelled_at") or ""),
            last_error=str(payload.get("last_error") or ""),
            configuration_hash=str(payload.get("configuration_hash") or ""),
            tool_call_count=int(payload.get("tool_call_count") or 0),
            worker_turn_count=int(payload.get("worker_turn_count") or 0),
            verifier_status=str(payload.get("verifier_status") or "review_required"),
            restart_count=int(payload.get("restart_count") or 0),
        )
        if scope:
            run.scope_freeze = ScopeFreeze(
                exact_question=str(scope.get("exact_question") or ""),
                included_records=list(scope.get("included_records") or []),
                excluded_records=list(scope.get("excluded_records") or []),
                included_authority_sources=list(scope.get("included_authority_sources") or []),
                date_range=dict(scope.get("date_range") or {}),
                issue_filters=list(scope.get("issue_filters") or []),
                posture_filters=list(scope.get("posture_filters") or []),
                output_type=str(scope.get("output_type") or ""),
                worker_set=list(scope.get("worker_set") or []),
                allowed_tools=list(scope.get("allowed_tools") or []),
                context_budget=dict(scope.get("context_budget") or {}),
                consent_mode=str(scope.get("consent_mode") or "local_only"),
                configuration_hash=str(scope.get("configuration_hash") or ""),
                frozen_at=str(scope.get("frozen_at") or ""),
            )
        synthesis_payload = payload.get("synthesis") or {}
        if synthesis_payload:
            run.synthesis = FinalSynthesis(
                scope=dict(synthesis_payload.get("scope") or {}),
                what_sources_establish=list(synthesis_payload.get("what_sources_establish") or []),
                agreement=list(synthesis_payload.get("agreement") or []),
                dissent=list(synthesis_payload.get("dissent") or []),
                verified_legal_support=list(synthesis_payload.get("verified_legal_support") or []),
                verified_record_support=list(synthesis_payload.get("verified_record_support") or []),
                unsupported_claims=list(synthesis_payload.get("unsupported_claims") or []),
                contradicted_claims=list(synthesis_payload.get("contradicted_claims") or []),
                stale_jurisdiction_risks=list(synthesis_payload.get("stale_jurisdiction_risks") or []),
                missing_information=list(synthesis_payload.get("missing_information") or []),
                provider_worker_failures=list(synthesis_payload.get("provider_worker_failures") or []),
                next_review_steps=list(synthesis_payload.get("next_review_steps") or []),
                review_status=str(synthesis_payload.get("review_status") or "review_required"),
                unresolved_questions=list(synthesis_payload.get("unresolved_questions") or []),
            )
        run.events = [DeliberationEvent(**event) for event in self.store.load_events(run.run_id)]
        run.claims = [ClaimLedgerEntry(**claim) for claim in self.store.load_claims(run.run_id)]
        run.positions = self.store.load_positions(run.run_id)
        return run

    def _save_run(self, run: DeliberationRun) -> None:
        run.updated_at = utc_now()
        self.store.save_run(run)
        self.store.save_claims(run.run_id, run.claims)
        self.store.save_positions(run.run_id, run.positions)
        self.store.save_synthesis(run.run_id, run.synthesis)

    def confirm_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            run = self._load_or_raise(run_id)
            if run.status not in {"draft_scope", "awaiting_local_confirmation"}:
                raise DeliberationHostError("invalid_run_state", f"Cannot confirm run from state {run.status}.", status_code=409)
            if payload.get("local_only") is not True:
                raise DeliberationHostError("local_only_confirmation_required", "The deliberation host only accepts local-only confirmation.", status_code=409)
            if payload.get("consent_mode") not in {None, "local_only"}:
                raise DeliberationHostError("local_only_confirmation_required", "The consent mode must be local_only.", status_code=409)
            included_records = [dict(row) for row in payload.get("included_records") or []]
            included_authority_sources = [dict(row) for row in payload.get("included_authority_sources") or []]
            excluded_records = [dict(row) for row in payload.get("excluded_records") or []]
            issue_filters = [str(item) for item in (payload.get("issue_filters") or []) if str(item).strip()]
            posture_filters = [str(item) for item in (payload.get("posture_filters") or []) if str(item).strip()]
            allowed_tools = [str(item) for item in (payload.get("allowed_tools") or self.list_tools_by_preset(run.worker_set)) if str(item).strip()]
            scope = ScopeFreeze(
                exact_question=str(payload.get("exact_question") or run.question),
                included_records=included_records,
                excluded_records=excluded_records,
                included_authority_sources=included_authority_sources,
                date_range=dict(payload.get("date_range") or run.date_range),
                issue_filters=issue_filters,
                posture_filters=posture_filters,
                output_type=str(payload.get("output_type") or run.desired_output),
                worker_set=list(run.worker_set),
                allowed_tools=allowed_tools,
                context_budget={
                    "context_limit_chars": run.limits.context_limit_chars,
                    "token_limit": run.limits.token_limit,
                    "tool_call_limit": run.limits.tool_call_limit,
                },
                consent_mode="local_only",
                configuration_hash=sha256_hex(
                    {
                        "exact_question": str(payload.get("exact_question") or run.question),
                        "included_records": included_records,
                        "excluded_records": excluded_records,
                        "included_authority_sources": included_authority_sources,
                        "date_range": dict(payload.get("date_range") or run.date_range),
                        "issue_filters": issue_filters,
                        "posture_filters": posture_filters,
                        "output_type": str(payload.get("output_type") or run.desired_output),
                        "worker_set": list(run.worker_set),
                        "allowed_tools": allowed_tools,
                        "context_budget": {
                            "context_limit_chars": run.limits.context_limit_chars,
                            "token_limit": run.limits.token_limit,
                            "tool_call_limit": run.limits.tool_call_limit,
                        },
                        "consent_mode": "local_only",
                    }
                ),
                frozen_at=utc_now(),
            )
            run.scope_freeze = scope
            run.status = "awaiting_local_confirmation"
            run.confirmed_at = utc_now()
            run.review_status = "review_required"
            self._save_run(run)
            self.store.save_event(_event(run.run_id, "scope_confirmed", run.status, "Scope frozen and locally confirmed", {"worker_count": len(run.worker_set)}))
            return self._run_response(run)

    def start_run(self, run_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            run = self._load_or_raise(run_id)
            if run.status not in {"queued", "awaiting_local_confirmation"}:
                if run.status in {"completed_review_required", "cancelled", "failed_closed"}:
                    return self._run_response(run)
                raise DeliberationHostError("invalid_run_state", f"Cannot start run from state {run.status}.", status_code=409)
            if run.scope_freeze is None:
                raise DeliberationHostError("scope_not_confirmed", "The scope must be confirmed before the run can start.", status_code=409)
            if payload and payload.get("local_only") is not True:
                raise DeliberationHostError("local_only_required", "The run must remain local_only.", status_code=409)
            run.status = "queued"
            run = self._advance(run)
            self._save_run(run)
            return self._run_response(run)

    def cancel_run(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            run = self._load_or_raise(run_id)
            if run.status in {"cancelled", "completed_review_required", "failed_closed"}:
                return self._run_response(run)
            run.cancellation_state = "cancelling"
            run.status = "cancelling"
            run.last_error = str(payload.get("reason") or "cancelled_by_operator")
            self.store.save_event(_event(run.run_id, "run_cancel_requested", run.status, "Cancellation requested", {"reason": run.last_error}))
            run.cancellation_state = "cancelled"
            run.status = "cancelled"
            run.cancelled_at = utc_now()
            self.tool_broker.revoke_run_tokens(run.run_id)
            self._save_run(run)
            self.store.save_event(_event(run.run_id, "run_cancelled", run.status, "Run cancelled", {"reason": run.last_error}))
            return self._run_response(run)

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._run_response(self._load_or_raise(run_id))

    def get_events(self, run_id: str) -> dict[str, Any]:
        run = self._load_or_raise(run_id)
        return {"run_id": run.run_id, "events": [event.as_dict() for event in run.events], "count": len(run.events), "review_required": True}

    def get_claims(self, run_id: str) -> dict[str, Any]:
        run = self._load_or_raise(run_id)
        return {"run_id": run.run_id, "claims": [claim.as_dict() for claim in run.claims], "count": len(run.claims), "review_required": True}

    def get_positions(self, run_id: str) -> dict[str, Any]:
        run = self._load_or_raise(run_id)
        return {"run_id": run.run_id, "positions": list(run.positions), "count": len(run.positions), "review_required": True}

    def get_synthesis(self, run_id: str) -> dict[str, Any]:
        run = self._load_or_raise(run_id)
        return {"run_id": run.run_id, "synthesis": run.synthesis.as_dict() if run.synthesis else None, "status": run.status, "review_required": True}

    def invoke_tool(self, run_id: str, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            run = self._load_or_raise(run_id)
            if run.scope_freeze is None:
                raise DeliberationHostError("scope_not_confirmed", "The scope must be confirmed before tool calls are allowed.", status_code=409)
            worker_id = safe_identifier(str(payload.get("worker_id") or "worker"), fallback="worker")
            token_id = str(payload.get("tool_token") or payload.get("token") or "").strip()
            if not token_id:
                token = self.tool_broker.issue_token(run_id=run.run_id, matter_id=run.matter_id, worker_id=worker_id, tool_name=tool_name)
                token_id = token.token_id
            context = self._tool_context(run)
            result = self.tool_broker.invoke(token_id=token_id, tool_name=tool_name, payload=dict(payload.get("args") or payload), context=context)
            run.tool_call_count += 1
            self.store.append_tool_audit(run.run_id, result.get("tool_audit") or {})
            self._save_run(run)
            return result

    def _tool_context(self, run: DeliberationRun) -> DeliberationContext:
        scope = run.scope_freeze or ScopeFreeze(
            exact_question=run.question,
            included_records=[],
            excluded_records=[],
            included_authority_sources=[],
            date_range=run.date_range,
            issue_filters=[],
            posture_filters=[],
            output_type=run.desired_output,
            worker_set=run.worker_set,
            allowed_tools=[],
            context_budget={},
        )
        source_texts: dict[str, str] = {}
        source_metadata: dict[str, dict[str, Any]] = {}
        record_texts: dict[str, str] = {}
        record_metadata: dict[str, dict[str, Any]] = {}
        source_cards = SourceCardStore()
        authority_index = SourceAuthorityIndex()
        for row in scope.included_authority_sources:
            source_id = str(row.get("source_id") or "").strip()
            if not source_id:
                continue
            source_texts[source_id] = str(row.get("text") or row.get("source_text") or "")
            source_metadata[source_id] = dict(row)
            source_cards.add(row)
            if str(row.get("citation") or "").strip():
                authority_index.add(
                    kind=str(row.get("citation_kind") or row.get("kind") or "maine_statute"),
                    normalized_citation=str(row.get("citation") or row.get("normalized_citation") or "").strip(),
                    source_id=source_id,
                    authority_status=str(row.get("authority_status") or "stale_unknown"),
                    metadata=dict(row),
                )
        for row in scope.included_records:
            record_id = str(row.get("record_id") or row.get("source_id") or "").strip()
            if not record_id:
                continue
            record_texts[record_id] = str(row.get("text") or row.get("text_excerpt") or row.get("content") or "")
            record_metadata[record_id] = dict(row)
        return DeliberationContext(
            run_id=run.run_id,
            matter_id=run.matter_id,
            question=run.question,
            source_texts=source_texts,
            source_metadata=source_metadata,
            record_texts=record_texts,
            record_metadata=record_metadata,
            tool_call_limit=run.limits.tool_call_limit,
            allowed_tools=set(scope.allowed_tools or [tool["name"] for tool in self.list_tools()]),
            cancellation_state=run.cancellation_state,
            source_cards=source_cards,
            authority_index=authority_index,
        )

    def _worker(self, worker_name: str, *, role: str) -> DeliberationWorker:
        worker = self.workers.get(worker_name)
        if worker:
            return worker
        return MockDeliberationWorker(worker_name, role, "deterministic fallback worker")

    def _advance_to_final_positions(self, run: DeliberationRun) -> None:
        if run.status == "final_positions":
            return
        if run.status == "partial_worker_failure":
            run.status = self.state_machine.transition(run.status, "final_positions")
            self.store.save_event(_event(run.run_id, "final_positions", run.status, "Final positions begin", {"auto_advance": True}))
            return
        phase_paths = {
            "running_independent": ["aligning_claims", "cross_review", "rebuttal", "omission_hunt", "final_positions"],
            "aligning_claims": ["cross_review", "rebuttal", "omission_hunt", "final_positions"],
            "cross_review": ["rebuttal", "omission_hunt", "final_positions"],
            "rebuttal": ["omission_hunt", "final_positions"],
            "omission_hunt": ["final_positions"],
        }
        for target in phase_paths.get(run.status, ["final_positions"]):
            run.status = self.state_machine.transition(run.status, target)
            self.store.save_event(_event(run.run_id, target, run.status, f"{target.replace('_', ' ').title()} begins", {"auto_advance": True}))
            if target == "final_positions":
                break

    def _advance(self, run: DeliberationRun) -> DeliberationRun:
        started = time.perf_counter()
        scope = run.scope_freeze
        if scope is None:
            raise DeliberationHostError("scope_not_confirmed", "The run scope is missing.", status_code=409)
        context = self._tool_context(run)
        run.status = self.state_machine.transition(run.status, "running_independent")
        run.started_at = utc_now()
        self.store.save_event(_event(run.run_id, "round_begin", run.status, "Independent analysis begins", {"round": 0}))
        self._save_run(run)

        positions: list[dict[str, Any]] = []
        worker_failures: list[dict[str, Any]] = []
        phase_targets = {
            1: "aligning_claims",
            2: "cross_review",
            3: "rebuttal",
            4: "omission_hunt",
            5: "final_positions",
        }

        for round_number in range(1, run.limits.max_rounds + 1):
            if run.cancellation_state != "active":
                run.status = "cancelling"
                break
            if (time.perf_counter() - started) > run.limits.time_limit_seconds:
                run.status = "budget_exhausted"
                run.review_status = "review_required"
                self.store.save_event(_event(run.run_id, "budget_exhausted", run.status, "Time limit reached", {"round": round_number}))
                break
            for index, worker_name in enumerate(run.worker_set):
                role = run.worker_roles[index] if index < len(run.worker_roles) else worker_name
                worker = self._worker(worker_name, role=role)
                request = WorkerTurnRequest(
                    run_id=run.run_id,
                    round=round_number,
                    role=role,
                    task="deliberation",
                    approved_context_packet={
                        "question": run.question,
                        "sources": [
                            *scope.included_authority_sources,
                            *scope.included_records,
                        ],
                        "date_range": scope.date_range,
                        "output_type": scope.output_type,
                    },
                    prior_anonymized_structured_positions=[
                        {
                            "worker_id": row.get("worker_id"),
                            "round": row.get("round"),
                            "position_kind": row.get("position_kind"),
                            "claims": row.get("claims", []),
                        }
                        for row in positions
                    ],
                    output_schema={
                        "claims": True,
                        "source_refs": True,
                        "critiques": True,
                        "omissions": True,
                    },
                    limits=run.limits.as_dict(),
                    tool_grants=[{"tool_name": tool_name} for tool_name in scope.allowed_tools[: run.limits.worker_call_limit]],
                )
                try:
                    result = worker.run(request)
                except Exception as exc:  # pragma: no cover - defensive failure path
                    worker_failures.append({"worker_id": worker_name, "role": role, "round": round_number, "error": type(exc).__name__, "message": str(exc)})
                    run.status = "partial_worker_failure"
                    self.store.save_event(_event(run.run_id, "worker_failure", run.status, "Worker crash or malformed output", {"worker_id": worker_name, "error": type(exc).__name__}))
                    continue
                if not isinstance(result, WorkerTurnResult):
                    worker_failures.append({"worker_id": worker_name, "role": role, "round": round_number, "error": "malformed_worker_output"})
                    run.status = "partial_worker_failure"
                    self.store.save_event(_event(run.run_id, "worker_failure", run.status, "Worker returned malformed output", {"worker_id": worker_name}))
                    continue
                run.worker_turn_count += 1
                positions.append(
                    {
                        "worker_id": result.worker_id,
                        "role": role,
                        "round": round_number,
                        "position_kind": "independent" if round_number == 1 else "critique_or_revision",
                        "claims": result.claims,
                        "source_refs": result.source_refs,
                        "concise_rationale_summaries": result.concise_rationale_summaries,
                        "critiques": result.critiques,
                        "omissions": result.omissions,
                        "assumptions": result.assumptions,
                        "requested_sources": result.requested_sources,
                        "confidence_category": result.confidence_category,
                        "finish_status": result.finish_status,
                        "usage": result.usage,
                    }
                )
                self.store.save_event(
                    _event(
                        run.run_id,
                        "worker_turn",
                        run.status,
                        f"Worker {role} completed round {round_number}",
                        {"worker_id": result.worker_id, "claim_count": len(result.claims)},
                        round_number=round_number,
                    )
                )
                run.tool_call_count += len(result.requested_sources)
                if run.tool_call_count > run.limits.tool_call_limit:
                    run.status = "budget_exhausted"
                    self.store.save_event(_event(run.run_id, "budget_exhausted", run.status, "Tool budget exhausted", {"round": round_number}))
                    break
            if run.status == "budget_exhausted":
                break
            target_state = phase_targets.get(round_number)
            if target_state and run.status != target_state:
                run.status = self.state_machine.transition(run.status, target_state)
                self.store.save_event(_event(run.run_id, target_state, run.status, f"{target_state.replace('_', ' ').title()} begins", {"round": round_number}))
            if run.status in {"aligning_claims", "cross_review", "rebuttal", "omission_hunt", "final_positions"}:
                aligned_claims, _claim_changed = self._align_claims(run, positions)
                run.claims = aligned_claims
                run.positions = positions
                self._save_run(run)
            if run.status == "final_positions":
                break

        if run.status not in {"budget_exhausted", "cancelling", "cancelled", "failed_closed", "final_positions"}:
            self._advance_to_final_positions(run)
            run.positions = positions
            self._save_run(run)

        if run.status == "budget_exhausted":
            run.review_status = "review_required"
            run.completed_at = utc_now()
            run.synthesis = self._synthesize(run, positions, worker_failures)
            run.status = "budget_exhausted"
            run.verifier_status = "review_required"
            self._save_run(run)
            return run

        if run.cancellation_state != "active":
            run.status = self.state_machine.transition("cancelling", "cancelled")
            run.cancelled_at = utc_now()
            self.tool_broker.revoke_run_tokens(run.run_id)
            run.review_status = "review_required"
            self._save_run(run)
            return run

        run.status = self.state_machine.transition(run.status, "verifying")
        self.store.save_event(_event(run.run_id, "verification", run.status, "Verification begins", {"round": run.worker_turn_count}))
        verifier_result = self.tool_broker.invoke(
            token_id=self.tool_broker.issue_token(run_id=run.run_id, matter_id=run.matter_id, worker_id="system_verifier", tool_name="verification.check_claims").token_id,
            tool_name="verification.check_claims",
            payload={
                "claims": [claim.canonical_claim for claim in run.claims],
            },
            context=context,
        )
        run.verifier_status = str(((verifier_result.get("verification_report") or {}).get("blockers") and "review_required") or "source_supported")
        run.status = self.state_machine.transition("verifying", "synthesizing")
        run.synthesis = self._synthesize(run, positions, worker_failures, verifier_result=verifier_result)
        run.review_status = "review_required"
        run.status = self.state_machine.transition("synthesizing", "completed_review_required")
        run.completed_at = utc_now()
        self.tool_broker.revoke_run_tokens(run.run_id)
        self._save_run(run)
        self.store.save_event(_event(run.run_id, "run_completed", run.status, "Deliberation completed", {"claim_count": len(run.claims), "position_count": len(positions)}))
        return run

    def _align_claims(self, run: DeliberationRun, positions: list[dict[str, Any]]) -> tuple[list[ClaimLedgerEntry], bool]:
        families: dict[str, dict[str, Any]] = {}
        changed = False
        for position in positions:
            for claim in position.get("claims") or []:
                if not isinstance(claim, dict):
                    continue
                canonical_claim = str(claim.get("canonical_claim") or claim.get("claim") or "").strip()
                if not canonical_claim:
                    continue
                family_id = _claim_family_id(canonical_claim)
                family = families.setdefault(
                    family_id,
                    {
                        "canonical_claim": canonical_claim,
                        "claim_type": str(claim.get("claim_type") or "legal"),
                        "materiality": str(claim.get("materiality") or "contextual"),
                        "worker_positions": [],
                        "source_refs": [],
                        "record_refs": [],
                        "supporting_spans": [],
                        "contradicting_spans": [],
                        "verifier_status": "review_required",
                        "history": [],
                        "unresolved_questions": [],
                        "narrower_claims": [],
                        "broader_claims": [],
                        "conflicting_qualifications": [],
                        "withdrawn_claims": [],
                        "corrected_claims": [],
                    },
                )
                family["worker_positions"].append(
                    {
                        "worker_id": claim.get("worker_id") or position.get("worker_id"),
                        "role": claim.get("role") or position.get("role"),
                        "position": claim.get("position") or "maintain",
                        "support_status": claim.get("support_status") or "review_required",
                        "confidence_category": claim.get("confidence_category") or position.get("confidence_category") or "medium",
                    }
                )
                family["source_refs"].extend([dict(row) for row in claim.get("source_refs") or position.get("source_refs") or []])
                history_entry = {
                    "round": position.get("round"),
                    "worker_id": position.get("worker_id"),
                    "position": claim.get("position") or "maintain",
                    "summary": str(claim.get("canonical_claim") or "")[:240],
                }
                family["history"].append(history_entry)
                if claim.get("position") in {"withdraw", "correct", "narrow"}:
                    changed = True
                if claim.get("position") == "contradict":
                    family["contradicting_spans"].append({"summary": claim.get("canonical_claim"), "round": position.get("round")})
                else:
                    family["supporting_spans"].append({"summary": claim.get("canonical_claim"), "round": position.get("round")})
                if str(claim.get("support_status") or "").lower() in {"contradicted", "worker_disagreement"}:
                    changed = True
        entries: list[ClaimLedgerEntry] = []
        for family_id, family in sorted(families.items()):
            verifier_status = self._claim_verifier_status(run, family["canonical_claim"], family["source_refs"])
            family["verifier_status"] = verifier_status
            family["history"].append({"round": len(positions), "worker_id": "verifier", "position": "verify", "summary": verifier_status})
            entries.append(
                ClaimLedgerEntry(
                    canonical_claim=family["canonical_claim"],
                    claim_type=family["claim_type"],
                    materiality=family["materiality"],
                    worker_positions=family["worker_positions"],
                    source_refs=family["source_refs"],
                    record_refs=family["record_refs"],
                    supporting_spans=family["supporting_spans"],
                    contradicting_spans=family["contradicting_spans"],
                    verifier_status=verifier_status,
                    history=family["history"],
                    unresolved_questions=family["unresolved_questions"],
                    narrower_claims=family["narrower_claims"],
                    broader_claims=family["broader_claims"],
                    conflicting_qualifications=family["conflicting_qualifications"],
                    withdrawn_claims=family["withdrawn_claims"],
                    corrected_claims=family["corrected_claims"],
                )
            )
        return entries, changed

    def _claim_verifier_status(self, run: DeliberationRun, claim: str, source_refs: list[dict[str, Any]]) -> str:
        if not run.scope_freeze:
            return "review_required"
        verifier = LegalOutputVerifier(SourceAuthorityIndex.from_rows([]))
        source_texts = {}
        source_metadata = {}
        for row in run.scope_freeze.included_authority_sources:
            source_id = str(row.get("source_id") or "").strip()
            if source_id:
                source_texts[source_id] = str(row.get("text") or row.get("source_text") or "")
                source_metadata[source_id] = dict(row)
        for row in run.scope_freeze.included_records:
            record_id = str(row.get("record_id") or row.get("source_id") or "").strip()
            if record_id:
                source_texts[record_id] = str(row.get("text") or row.get("text_excerpt") or row.get("content") or "")
                source_metadata[record_id] = dict(row)
        report = verifier.verify_output(
            text=claim,
            source_texts=source_texts,
            source_metadata=source_metadata,
            auto_extract_claims=False,
            auto_extract_quotes=False,
        )
        blockers = report.get("blockers") or []
        if blockers:
            if any("citation_not_found" in blocker for blocker in blockers):
                return "unverified"
            if any("claim_contradicted" in blocker for blocker in blockers):
                return "contradicted"
            return "review_required"
        if any(row.get("status") == "contradicted" for row in report.get("claims") or []):
            return "contradicted"
        if any(row.get("status") == "stale" for row in report.get("claims") or []):
            return "stale_or_jurisdiction_risk"
        return "source_supported" if source_refs else "evidence_supported"

    def _synthesize(self, run: DeliberationRun, positions: list[dict[str, Any]], worker_failures: list[dict[str, Any]], *, verifier_result: dict[str, Any] | None = None) -> FinalSynthesis:
        scope_dict = run.scope_freeze.as_dict() if run.scope_freeze else {}
        agreement = []
        dissent = []
        verified_legal_support = []
        verified_record_support = []
        unsupported_claims = []
        contradicted_claims = []
        stale_jurisdiction_risks = []
        missing_information = []
        unresolved_questions = []
        for claim in run.claims:
            item = claim.as_dict()
            if claim.verifier_status in {"source_supported", "evidence_supported"}:
                if claim.source_refs:
                    verified_legal_support.append(item)
                else:
                    verified_record_support.append(item)
            elif claim.verifier_status == "contradicted":
                contradicted_claims.append(item)
            elif claim.verifier_status == "stale_or_jurisdiction_risk":
                stale_jurisdiction_risks.append(item)
            else:
                unsupported_claims.append(item)
            worker_positions = claim.worker_positions
            if len({row.get("position") for row in worker_positions if row.get("position")}) == 1:
                agreement.append(claim.canonical_claim)
            else:
                dissent.append({"claim": claim.canonical_claim, "worker_positions": worker_positions, "verifier_status": claim.verifier_status})
            unresolved_questions.extend(claim.unresolved_questions)
        if run.scope_freeze and not run.scope_freeze.included_records:
            missing_information.append({"type": "missing_records", "summary": "No private records were included in the frozen scope."})
        if not run.scope_freeze or not run.scope_freeze.included_authority_sources:
            missing_information.append({"type": "missing_authority", "summary": "No authority sources were included in the frozen scope."})
        if worker_failures:
            missing_information.append({"type": "worker_failure", "summary": "One or more workers failed or returned malformed output."})
        what_sources_establish = [
            {
                "source_id": row.get("source_id"),
                "title": row.get("title"),
                "authority_status": row.get("authority_status"),
                "freshness_status": row.get("freshness_status"),
            }
            for row in (run.scope_freeze.included_authority_sources if run.scope_freeze else [])[:20]
        ]
        review_status = "review_required"
        if run.status == "completed_review_required":
            review_status = "review_required"
        synthesis = FinalSynthesis(
            scope=scope_dict,
            what_sources_establish=what_sources_establish,
            agreement=agreement,
            dissent=dissent,
            verified_legal_support=verified_legal_support,
            verified_record_support=verified_record_support,
            unsupported_claims=unsupported_claims,
            contradicted_claims=contradicted_claims,
            stale_jurisdiction_risks=stale_jurisdiction_risks,
            missing_information=missing_information,
            provider_worker_failures=worker_failures,
            next_review_steps=[
                "Review unresolved dissent and omission notes.",
                "Verify any new or stale citations against current authority.",
                "Collect missing record slices before relying on any unsupported claim.",
            ],
            review_status=review_status,
            unresolved_questions=sorted(set(unresolved_questions)),
        )
        self.store.save_event(_event(run.run_id, "synthesis", run.status, "Final synthesis assembled", {"agreement_count": len(agreement), "dissent_count": len(dissent)}))
        return synthesis

    def list_tools_by_preset(self, worker_set: list[str]) -> list[str]:
        return [tool["name"] for tool in self.list_tools()]

    def _run_response(self, run: DeliberationRun) -> dict[str, Any]:
        self._save_run(run)
        hydrated = self._load_or_raise(run.run_id)
        return hydrated.as_dict() | {
            "events": [event.as_dict() for event in hydrated.events],
            "claims": [claim.as_dict() for claim in hydrated.claims],
            "positions": list(hydrated.positions),
            "synthesis": hydrated.synthesis.as_dict() if hydrated.synthesis else None,
            "review_required": True,
            "run_status": hydrated.status,
        }
