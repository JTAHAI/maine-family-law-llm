"""Encrypted local draft-requirement profiles; never a court-approved template claim."""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")

def _now() -> str: return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
def _digest(value: Any) -> str: return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def _id(value: Any, name: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result): raise IntakeWorkbenchError(f"{name}_invalid")
    return result
def _text(value: Any, name: str, limit: int = 1000, required: bool = True) -> str:
    result = " ".join(str(value or "").replace("\x00", "").split())
    if required and not result: raise IntakeWorkbenchError(f"{name}_required")
    if len(result) > limit: raise IntakeWorkbenchError(f"{name}_too_long")
    return result

class DraftRequirementProfileStore:
    schema = "maine_family_law_llm.draft_requirement_profiles.v1"
    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve(); self.root = self.case_root / "19_DRAFTING" / "requirement-profiles"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()): raise IntakeWorkbenchError("requirement_profile_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]; self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
    @property
    def path(self) -> Path: return self.root / "profiles.json.enc"
    @property
    def lock(self) -> Path: return self.root / ".profiles.lock"
    def _load(self) -> dict[str, Any]:
        if not self.path.exists(): return {"schema":self.schema,"scope":self.scope,"profiles":[],"ledger":[],"revision":0}
        try: state=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=8*1024*1024,require_object=True))
        except Exception as exc: raise IntakeWorkbenchError("requirement_profile_store_unavailable",409) from exc
        if state.get("schema")!=self.schema or state.get("scope")!=self.scope: raise IntakeWorkbenchError("cross_matter_access_denied",404)
        state.setdefault("profiles",[]); state.setdefault("ledger",[]); return state
    def _save(self,state:dict[str,Any])->None: atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(state),sort_keys=True).encode(),mode=0o600)
    def _mutate(self, action:str, profile_id:str, callback): # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            state=self._load(); result=callback(state); prior=str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else ""
            event={"event_id":f"profile_{uuid.uuid4().hex}","at":_now(),"action":action,"profile_id":profile_id,"previous_event_hash":prior,"review_required":True}; event["event_hash"]=_digest(event); state["ledger"].append(event); state["revision"]=int(state.get("revision") or 0)+1; self._save(state); return result
    @staticmethod
    def _public(value:dict[str,Any])->dict[str,Any]:
        result=deepcopy(value); result.pop("scope",None); result.update({"status":"review_required","review_required":True,"filing_ready":False,"local_only":True,"notice":"This local profile is a reviewer checklist, not a court-approved form, rule, deadline, or filing determination."}); return result
    def create(self,payload:dict[str,Any])->dict[str,Any]:
        if payload.get("user_confirmed") is not True: raise IntakeWorkbenchError("requirement_profile_confirmation_required",409)
        profile_id=_id(payload.get("profile_id"),"profile_id"); reviewer_safe_id=_id(payload.get("reviewer_safe_id"),"reviewer_safe_id"); label=_text(payload.get("label"),"profile_label",300)
        sections=[]; seen=set()
        for raw in list(payload.get("required_sections") or [])[:50]:
            section=_text(raw,"required_section",160)
            if section.casefold() not in seen: sections.append(section); seen.add(section.casefold())
        if not sections: raise IntakeWorkbenchError("required_sections_required")
        max_chars=int(payload.get("max_characters") or 0)
        if max_chars < 1 or max_chars>1_500_000: raise IntakeWorkbenchError("max_characters_invalid")
        gates=[]
        for raw in list(payload.get("review_gates") or [])[:20]:
            gate=_text(raw,"review_gate",160)
            if gate.casefold() not in {item.casefold() for item in gates}: gates.append(gate)
        if not gates: gates=["human review required","source and citation review required"]
        def callback(state:dict[str,Any])->dict[str,Any]:
            if any(row.get("profile_id")==profile_id for row in state["profiles"]): raise IntakeWorkbenchError("requirement_profile_id_already_exists",409)
            profile={"profile_id":profile_id,"label":label,"reviewer_safe_id":reviewer_safe_id,"required_sections":sections,"max_characters":max_chars,"review_gates":gates,"created_at":_now(),"review_required":True,"filing_ready":False}
            state["profiles"].append(profile); return self._public(profile)
        return self._mutate("create_requirement_profile",profile_id,callback)
    def profiles(self,profile_id:str="")->dict[str,Any]:
        rows=[self._public(row) for row in self._load()["profiles"]]
        if profile_id:
            found=next((row for row in rows if row.get("profile_id")==profile_id),None)
            if found is None: raise IntakeWorkbenchError("requirement_profile_not_found",404)
            return {"profile":found,"review_required":True}
        return {"profiles":rows,"review_required":True,"local_only":True}
    def evaluate(self,profile_id:str,document:dict[str,Any])->dict[str,Any]:
        profile=self.profiles(profile_id)["profile"]; content=_text(document.get("content"),"document_content",1_500_000); low=content.casefold()
        missing=[section for section in profile["required_sections"] if section.casefold() not in low]
        over_limit=len(content)>int(profile["max_characters"])
        result={"profile_id":profile_id,"document_id":_text(document.get("document_id"),"document_id",80),"revision_id":_text(document.get("current_revision_id"),"revision_id",80),"document_content_sha256":hashlib.sha256(content.encode()).hexdigest(),"missing_sections":missing,"character_count":len(content),"max_characters":profile["max_characters"],"over_character_limit":over_limit,"review_gates":profile["review_gates"],"blockers":(["missing_required_section:"+item for item in missing]+(["character_limit_exceeded"] if over_limit else [])),"review_required":True,"filing_ready":False,"notice":"Profile evaluation checks only local reviewer-configured text conditions; it does not determine legal sufficiency or filing readiness."}
        return result
